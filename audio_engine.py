"""Audio and Neural Speech Engine for J.A.R.V.I.S.
Handles:
1. Low-latency local audio capture via sounddevice with peak normalization (preventing DAC 384kHz clipping).
2. Offline Speech-to-Text via faster-whisper (small.en) with hallucination suppression.
3. Expressive Neural TTS via Fish Audio & Edge-TTS (Ryan/Sonia British voices) with local disk caching.
4. Thread-safe speech playback and instant interruption handling.
"""
import collections
import hashlib
import os
import queue
import re
import subprocess
import threading
import time
import warnings
import numpy as np
import requests
import sounddevice as sd

from secrets_store import get_secret
from jarvis_memory import get_voice, VOICE_MALE, VOICE_FEMALE

warnings.filterwarnings("ignore", category=RuntimeWarning, module="faster_whisper")

SAMPLE_RATE = 16000
BLOCK_SIZE = 800  # 50ms at 16kHz for 20 FPS real-time speech visualizer
WHISPER_MODEL_NAME = "small.en"
MACOS_VOICE = os.getenv("MACOS_VOICE", "Daniel")
VOICE_ID = "9a9cf47702da476aa4629e2506d4a857"

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "tts")
NEURAL_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "tts_neural")

CURRENT_AUDIO_PROC = None
CURRENT_AUDIO_LOCK = threading.Lock()
SPEECH_LOCK = threading.Lock()

# --------------------------------------------------------------------------- Faster Whisper STT
_WHISPER_MODEL = None


def get_whisper_model():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        from faster_whisper import WhisperModel
        print("  [Audio Engine] Loading local Whisper speech-to-text model...")
        try:
            _WHISPER_MODEL = WhisperModel(WHISPER_MODEL_NAME, device="cpu", compute_type="int8", local_files_only=True)
        except Exception:
            _WHISPER_MODEL = WhisperModel(WHISPER_MODEL_NAME, device="cpu", compute_type="int8")
    return _WHISPER_MODEL


def clean_transcription(text: str) -> str:
    """Normalize transcribed text, correcting Whisper STT phonetic slips and dropping prompt hallucinations."""
    if not text:
        return ""
    t = text.strip()
    lower = t.lower()
    clean_alpha = re.sub(r"[^a-z\s]", "", lower).strip()

    # Reject single-word hallucinated fillers triggered by mic breathing/clicks
    fillers = (
        "oh", "yeah", "uh", "um", "ah", "huh", "ha", "you", "so", "like", "the",
        "bye", "okay", "ok", "hey", "yes", "no", "hi", "sir", "shh", "a", "i",
        "to", "and", "mm", "mmm", "hmm", "yep", "nope", "well"
    )
    if clean_alpha in fillers:
        return ""

    hallucinations = (
        "mac voice assistant commands macos applications and system controls",
        "hey niko open apple music", "niko play the music",
        "hey jarvis open apple music", "jarvis play the music", "turn the volume down",
        "close reminders", "thank you for watching", "subtitles by", "amaraorg",
        "thank you", "thanks for watching", "please subscribe", "subtitles", "watching",
        "yeah go to the office"
    )
    for h in hallucinations:
        if h in clean_alpha:
            clean_alpha = clean_alpha.replace(h, "").strip()
    if not clean_alpha or len(clean_alpha) < 2:
        return ""

    subs = [
        (r"\b(?:you\s+tube|yout\s+tube|u\s+tube|your\s+tube)\b", "youtube"),
        (r"\bgoggle\b", "google"),
        (r"\bserch\b", "search"),
        (r"\bsomehting\b", "something"),
        (r"\bbroswer\b", "browser"),
        (r"\bchrone\b", "chrome"),
        (r"\bsafri\b", "safari"),
    ]
    for pattern, repl in subs:
        t = re.sub(pattern, repl, t, flags=re.I)
    return t.strip()


def transcribe_audio_buffer(audio_array: np.ndarray) -> tuple[str, int]:
    """Transcribe a float32 numpy audio array using faster-whisper with Silero VAD and anti-hallucination gates."""
    # Discard audio shorter than 300ms (key taps or accidental micro-clicks)
    if len(audio_array) < int(SAMPLE_RATE * 0.3):
        return "", 0
    t0 = time.time()

    # Amplitude gate: discard pure background noise, mic hum or silent key taps
    max_amp = float(np.max(np.abs(audio_array)))
    if max_amp < 0.015:
        return "", 0

    norm_audio = (audio_array / max_amp) * 0.92

    model = get_whisper_model()
    try:
        segments, _ = model.transcribe(
            norm_audio,
            beam_size=1,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=400),
            no_speech_threshold=0.55,
            log_prob_threshold=-1.0,
            compression_ratio_threshold=2.4,
            initial_prompt="Niko macOS desktop voice assistant."
        )
        valid_segments = []
        for s in segments:
            if getattr(s, "no_speech_prob", 0.0) > 0.6 or getattr(s, "avg_logprob", 0.0) < -1.1:
                continue
            txt = s.text.strip()
            if txt:
                valid_segments.append(txt)
        raw_text = " ".join(valid_segments).strip()
    except Exception as e:
        print(f"  [Whisper transcription notice]: {e}")
        raw_text = ""

    ms = int((time.time() - t0) * 1000)
    return clean_transcription(raw_text), ms


# --------------------------------------------------------------------------- Neural TTS
def stop_speaking() -> bool:
    """Instantly terminate any playing speech process."""
    global CURRENT_AUDIO_PROC
    with CURRENT_AUDIO_LOCK:
        if CURRENT_AUDIO_PROC and CURRENT_AUDIO_PROC.poll() is None:
            try:
                CURRENT_AUDIO_PROC.terminate()
            except Exception:
                pass
            CURRENT_AUDIO_PROC = None
            return True
        CURRENT_AUDIO_PROC = None
    return False


def is_speaking() -> bool:
    with CURRENT_AUDIO_LOCK:
        return CURRENT_AUDIO_PROC is not None and CURRENT_AUDIO_PROC.poll() is None


def fetch_neural_tts(text: str, voice_override: str = None) -> tuple[str, int, bool]:
    """Generate studio-grade neural speech using Edge-TTS (Ryan / Sonia British)."""
    os.makedirs(NEURAL_CACHE_DIR, exist_ok=True)
    voice = voice_override or get_voice()
    h = hashlib.sha1(f"{voice}|{text}".encode()).hexdigest()
    path = os.path.join(NEURAL_CACHE_DIR, f"{h}.mp3")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path, 0, True
    t0 = time.time()
    try:
        import asyncio, edge_tts
        async def _gen():
            comm = edge_tts.Communicate(text, voice)
            await comm.save(path)
        asyncio.run(_gen())
        return path, int((time.time() - t0) * 1000), False
    except Exception as e:
        print(f"  [Neural TTS Warning] Edge-TTS error: {e}")
        return None, 0, False


def fetch_fish_tts(text: str) -> tuple[str, int, bool]:
    """Generate neural speech using Fish Audio S2.1 Pro."""
    fish_key = get_secret("FISH_AUDIO_API_KEY")
    if not fish_key:
        return None, 0, True
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, hashlib.sha1(f"{VOICE_ID}|{text}".encode()).hexdigest() + ".wav")
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path, 0, True
    t0 = time.time()
    try:
        r = requests.post(
            "https://api.fish.audio/v1/tts",
            headers={"Authorization": f"Bearer {fish_key}", "model": "s2.1-pro-free"},
            json={"text": text, "reference_id": VOICE_ID, "format": "wav"},
            timeout=4.0
        )
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)
        return path, int((time.time() - t0) * 1000), False
    except Exception:
        return None, 0, False


def speak(text: str) -> int:
    """Speak text using Edge-TTS -> Fish Audio -> macOS say fallback."""
    global CURRENT_AUDIO_PROC
    cleaned = re.sub(r"\[\w+\]\s*", "", text).strip()
    if not cleaned:
        return 0
    t0 = time.time()

    # 1. Edge-TTS Studio British Voice
    try:
        path, ms, cached = fetch_neural_tts(cleaned)
        if path and os.path.exists(path):
            with CURRENT_AUDIO_LOCK:
                CURRENT_AUDIO_PROC = subprocess.Popen(["afplay", path])
            CURRENT_AUDIO_PROC.wait()
            return ms
    except Exception:
        pass

    # 2. Fish Audio API
    try:
        path, ms, cached = fetch_fish_tts(cleaned)
        if path and os.path.exists(path):
            with CURRENT_AUDIO_LOCK:
                CURRENT_AUDIO_PROC = subprocess.Popen(["afplay", path])
            CURRENT_AUDIO_PROC.wait()
            return ms
    except Exception:
        pass

    # 3. macOS native say fallback
    try:
        with CURRENT_AUDIO_LOCK:
            CURRENT_AUDIO_PROC = subprocess.Popen(["say", "-v", MACOS_VOICE, cleaned])
        CURRENT_AUDIO_PROC.wait()
    except Exception:
        pass
    return int((time.time() - t0) * 1000)


def say(line: str, notify=None):
    """Thread-safe speech announcement with UI state emission."""
    with SPEECH_LOCK:
        print(f"  say: {line}")
        if notify:
            notify("Speaking", line)
        speak(line)


# --------------------------------------------------------------------------- Audio Stream Recorder
class AudioRecorder:
    def __init__(self, sample_rate=SAMPLE_RATE, block_size=BLOCK_SIZE, on_silence_stop=None, on_audio_level=None):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.lock = threading.Lock()
        self.frames = []
        self.on = False
        self.wake = False
        self.noise = 0.005
        self.auto_stop_on_silence = False
        self.has_spoken = False
        self.silent_blocks = 0
        self.initial_silent_blocks = 0
        self.on_silence_stop = on_silence_stop
        self.on_audio_level = on_audio_level
        self.stream = None
        self._init_stream()

    def _init_stream(self):
        try:
            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                blocksize=self.block_size,
                callback=self._callback
            )
            self.stream.start()
        except Exception as e:
            print(f"  [AudioRecorder Warning] Input stream error: {e}")

    def ensure_stream_alive(self):
        with self.lock:
            if self.stream is None or not getattr(self.stream, "active", False):
                self._init_stream()

    def start_recording(self, auto_stop=False):
        with self.lock:
            self.frames = []
            self.on = True
            self.has_spoken = False
            self.silent_blocks = 0
            self.initial_silent_blocks = 0
            self.auto_stop_on_silence = auto_stop

    def stop_recording(self) -> np.ndarray:
        with self.lock:
            self.on = False
            if not self.frames:
                return np.array([], dtype="float32")
            return np.concatenate(self.frames, axis=0)[:, 0]

    def _callback(self, indata, frames, time_info, status=None):
        trigger_stop = False
        trigger_timeout = False
        with self.lock:
            if not self.on:
                return
            self.frames.append(indata.copy())
            block = indata[:, 0].copy()
            rms = float(np.sqrt(np.mean(block ** 2)))
            loud = rms > max(self.noise * 2.5, 0.012)
            if loud:
                self.has_spoken = True
                self.silent_blocks = 0
            elif self.has_spoken:
                self.silent_blocks += 1
            else:
                self.initial_silent_blocks += 1

            if self.on_audio_level:
                # Dynamic speech level scaled 0.0 to 1.0
                norm_lvl = min(1.0, max(0.0, (rms - 0.003) / 0.08))
                try:
                    self.on_audio_level(norm_lvl)
                except Exception:
                    pass

            if self.auto_stop_on_silence:
                # 16 blocks = 800ms of silence at 50ms blocks
                if self.has_spoken and self.silent_blocks >= 16:
                    self.on = False
                    trigger_stop = True
                # 80 blocks = 4.0s of silence at 50ms blocks
                elif not self.has_spoken and self.initial_silent_blocks >= 80:
                    self.on = False
                    trigger_timeout = True

        if trigger_stop and self.on_silence_stop:
            threading.Thread(target=self.on_silence_stop, args=(False,), daemon=True).start()
        elif trigger_timeout and self.on_silence_stop:
            threading.Thread(target=self.on_silence_stop, args=(True,), daemon=True).start()
