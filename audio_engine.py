"""Audio and Neural Speech Engine for J.A.R.V.I.S.
Handles:
1. Low-latency local audio capture via sounddevice with peak normalization.
2. Offline Speech-to-Text via faster-whisper (small.en) with hallucination suppression.
3. Expressive Neural TTS via Edge-TTS (Ryan/Sonia British voices) with local disk caching.
4. Thread-safe speech playback and instant interruption handling.
5. Cross-platform: macOS (afplay/say) + Windows (pyttsx3/winsound/playsound).
"""
import collections
import hashlib
import os
import queue
import re
import subprocess
import sys
import threading
import time
import warnings
import numpy as np
import sounddevice as sd

from jarvis_memory import get_voice, VOICE_MALE, VOICE_FEMALE

warnings.filterwarnings("ignore", category=RuntimeWarning, module="faster_whisper")

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")

SAMPLE_RATE = 16000
BLOCK_SIZE = 800  # 50ms at 16kHz for 20 FPS real-time speech visualizer
WHISPER_MODEL_NAME = "small.en"
MACOS_VOICE = os.getenv("MACOS_VOICE", "Daniel")

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
        (r"\b(?:soj|surch|serch)\b", "search"),
        (r"\bwhat\s+s\s+up\b", "what's up"),
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
_INTERRUPT_EVENT = threading.Event()


def stop_speaking() -> bool:
    """Instantly terminate any playing speech process and cancel pending queued audio."""
    global CURRENT_AUDIO_PROC
    _INTERRUPT_EVENT.set()
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.winmm.mciSendStringW("stop all", None, 0, 0)
            ctypes.windll.winmm.mciSendStringW("close all", None, 0, 0)
        except Exception:
            pass
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


def _audio_hash(text: str, voice: str) -> str:
    """Deterministic hash keyed to both the specific voice model and cleaned text."""
    return hashlib.sha1(f"{voice}|{text.strip()}".encode()).hexdigest()


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences for low-latency pipelined audio streaming."""
    raw = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    return raw if raw else ([text.strip()] if text.strip() else [])


def fetch_neural_tts(text: str, voice_override: str = None) -> tuple[str, int, bool]:
    """Generate studio-grade neural speech using Edge-TTS (Ryan / Sonia British)."""
    os.makedirs(NEURAL_CACHE_DIR, exist_ok=True)
    voice = voice_override or get_voice()
    h = _audio_hash(text, voice)
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


# Prefetch cache: audio_hash -> file_path
_PREFETCH_CACHE: dict[str, str] = {}
_PREFETCH_LOCK = threading.Lock()


def prefetch_tts(text: str) -> None:
    """Start generating TTS audio file in a background thread ahead of playback."""
    cleaned = re.sub(r"\[\w+\]\s*", "", text).strip()
    if not cleaned:
        return
    voice = get_voice()
    h = _audio_hash(cleaned, voice)
    with _PREFETCH_LOCK:
        if h in _PREFETCH_CACHE:
            return

    def _bg():
        path, _, _ = fetch_neural_tts(cleaned, voice_override=voice)
        if path:
            with _PREFETCH_LOCK:
                _PREFETCH_CACHE[h] = path

    threading.Thread(target=_bg, daemon=True, name=f"tts-prefetch-{h[:8]}").start()


def _play_file_blocking(path: str) -> bool:
    """Play an audio file blocking until completion or interrupt."""
    global CURRENT_AUDIO_PROC
    if not path or not os.path.exists(path) or os.path.getsize(path) == 0:
        return False
    if _INTERRUPT_EVENT.is_set():
        return False
    try:
        with CURRENT_AUDIO_LOCK:
            if IS_MAC:
                CURRENT_AUDIO_PROC = subprocess.Popen(["afplay", path])
            elif IS_WIN:
                # Windows native MP3 playback via winmm MCI (zero latency, hardware accelerated)
                try:
                    import ctypes
                    alias = f"niko_{int(time.time() * 1000)}"
                    norm_path = os.path.abspath(path).replace("/", "\\")
                    res = ctypes.windll.winmm.mciSendStringW(f'open "{norm_path}" type mpegvideo alias {alias}', None, 0, 0)
                    if res == 0:
                        ctypes.windll.winmm.mciSendStringW(f'play {alias} wait', None, 0, 0)
                        ctypes.windll.winmm.mciSendStringW(f'close {alias}', None, 0, 0)
                        return True
                except Exception:
                    pass
                # Fallback to Windows Media Player COM via PowerShell
                ps_cmd = (
                    f"Add-Type -AssemblyName presentationCore; "
                    f"$p = New-Object System.Windows.Media.MediaPlayer; "
                    f"$p.Open([System.Uri]'{os.path.abspath(path)}'); "
                    f"$p.Play(); "
                    f"Start-Sleep -Milliseconds 400; "
                    f"while ($p.NaturalDuration.HasTimeSpan -and ($p.Position -lt $p.NaturalDuration.TimeSpan)) {{ Start-Sleep -Milliseconds 80 }}"
                )
                CURRENT_AUDIO_PROC = subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd])
            else:
                CURRENT_AUDIO_PROC = subprocess.Popen(["aplay", path])
        if CURRENT_AUDIO_PROC:
            CURRENT_AUDIO_PROC.wait()
        return True
    except Exception as e:
        print(f"  [Audio Playback Error]: {e}")
        return False
    finally:
        with CURRENT_AUDIO_LOCK:
            CURRENT_AUDIO_PROC = None


def _tts_windows_native(text: str) -> bool:
    """Speak text on Windows using pyttsx3 (emergency offline fallback only)."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        for voice in engine.getProperty("voices"):
            if "david" in voice.name.lower() or "george" in voice.name.lower() or "uk" in voice.id.lower():
                engine.setProperty("voice", voice.id)
                break
        engine.setProperty("rate", 165)
        engine.setProperty("volume", 0.95)
        engine.say(text)
        engine.runAndWait()
        return True
    except Exception:
        return False


def speak(text: str) -> int:
    """Speak text using rich neural Edge-TTS voice (Ryan/Sonia) with streaming sentence pipelining."""
    global CURRENT_AUDIO_PROC
    cleaned = re.sub(r"\[\w+\]\s*", "", text).strip()
    if not cleaned:
        return 0
    t0 = time.time()
    voice = get_voice()
    _INTERRUPT_EVENT.clear()

    # 1. Fast Cache Check: Full text already prefetched or cached on disk (0ms latency)
    h_full = _audio_hash(cleaned, voice)
    with _PREFETCH_LOCK:
        prefetched = _PREFETCH_CACHE.pop(h_full, None)
    disk_path = os.path.join(NEURAL_CACHE_DIR, f"{h_full}.mp3")
    cached_path = prefetched if (prefetched and os.path.exists(prefetched)) else (
        disk_path if os.path.exists(disk_path) and os.path.getsize(disk_path) > 0 else None
    )

    if cached_path:
        _play_file_blocking(cached_path)
        return int((time.time() - t0) * 1000)

    # 2. Neural Generation: Single sentence or sentence-pipelined streaming
    sentences = _split_sentences(cleaned)
    if len(sentences) <= 1:
        path, _, _ = fetch_neural_tts(cleaned, voice_override=voice)
        if path and os.path.exists(path):
            _play_file_blocking(path)
            return int((time.time() - t0) * 1000)
    else:
        # Pipelined streaming: start playing sentence 0 as soon as it's ready,
        # while concurrently pre-fetching subsequent sentences in background
        audio_queue = queue.Queue()
        stop_worker = threading.Event()

        def _worker():
            for s in sentences[1:]:
                if stop_worker.is_set() or _INTERRUPT_EVENT.is_set():
                    break
                p, _, _ = fetch_neural_tts(s, voice_override=voice)
                audio_queue.put(p)
            audio_queue.put(None)

        worker = threading.Thread(target=_worker, daemon=True)
        worker.start()

        # Generate and play sentence 0 ASAP
        p0, _, _ = fetch_neural_tts(sentences[0], voice_override=voice)
        if p0 and os.path.exists(p0):
            _play_file_blocking(p0)
            while not _INTERRUPT_EVENT.is_set():
                p = audio_queue.get()
                if p is None:
                    break
                if p and os.path.exists(p):
                    _play_file_blocking(p)
            # Cache the full paragraph in background for instant playback next time
            threading.Thread(target=fetch_neural_tts, args=(cleaned, voice), daemon=True).start()
            return int((time.time() - t0) * 1000)
        else:
            stop_worker.set()

    # 3. Emergency Offline Fallback (Only if Edge-TTS network request fails completely)
    try:
        if IS_MAC:
            with CURRENT_AUDIO_LOCK:
                CURRENT_AUDIO_PROC = subprocess.Popen(["say", "-v", MACOS_VOICE, cleaned])
            CURRENT_AUDIO_PROC.wait()
        elif IS_WIN:
            _tts_windows_native(cleaned)
        else:
            for cmd in (["espeak", cleaned], ["festival", "--tts"]):
                try:
                    if cmd[0] == "festival":
                        subprocess.run(cmd, input=cleaned.encode(), capture_output=True)
                    else:
                        subprocess.run(cmd, capture_output=True)
                    break
                except Exception:
                    continue
    except Exception:
        pass
    return int((time.time() - t0) * 1000)


def prewarm_common_phrases():
    """Background pre-warming of frequent responses for 0ms latency."""
    common = [
        "Right away, sir.",
        "Good morning, sir.",
        "Good afternoon, sir.",
        "Good evening, sir.",
        "I'm listening, sir.",
        "At your command, sir.",
        "Opening that now, sir.",
        "Closing that now, sir.",
        "Playback paused, sir.",
        "Skipped to next track, sir.",
        "Workstation locked, sir.",
        "Understood, sir. I have committed that to memory.",
        "Screenshot taken and saved to your Desktop, sir.",
        "Your Mac is currently running on power adapter, sir.",
        "Trash has been emptied, sir.",
        "The result is 100, sir.",
    ]
    def _bg():
        time.sleep(1.5)
        v = get_voice()
        for phrase in common:
            try:
                fetch_neural_tts(phrase, voice_override=v)
            except Exception:
                pass
    threading.Thread(target=_bg, daemon=True, name="tts-prewarm").start()


# Start background prewarm immediately on module load
prewarm_common_phrases()


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
                try:
                    fft = np.abs(np.fft.rfft(block))
                    # 16000Hz / 800 = 20Hz per bin
                    b1 = float(np.mean(fft[4:15]))    # 80-300 Hz (vocal fundamentals / deep vowels)
                    b2 = float(np.mean(fft[15:40]))   # 300-800 Hz (vowel formants)
                    b3 = float(np.mean(fft[40:100]))  # 800-2000 Hz (nasals & consonants)
                    b4 = float(np.mean(fft[100:250])) # 2000-5000 Hz (fricatives & sibilance)

                    l1 = min(1.0, max(0.0, (b1 - 0.003) / 0.14)) ** 0.65
                    l2 = min(1.0, max(0.0, (b2 - 0.002) / 0.12)) ** 0.65
                    l3 = min(1.0, max(0.0, (b3 - 0.002) / 0.10)) ** 0.65
                    l4 = min(1.0, max(0.0, (b4 - 0.001) / 0.07)) ** 0.65
                    self.on_audio_level((l1, l2, l3, l4))
                except Exception:
                    norm_lvl = min(1.0, max(0.0, (rms - 0.002) / 0.04))
                    self.on_audio_level((norm_lvl, norm_lvl, norm_lvl, norm_lvl))

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
