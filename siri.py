"""NIKO Voice Operating Assistant.
Orchestrates:
- Local Laya Decision Engine (System 1)
- Audio capture with faster-whisper & peak normalization
- Studio neural speech synthesis (Fish Audio / Edge-TTS)
- Asynchronous OS & browser automation dispatch
- Native Dynamic Island HUD and Push-to-Talk
"""
import argparse
import os
import queue
import re
import sys
import threading
import time

from dotenv import load_dotenv

# Modular Subsystems
from laya_engine import laya_decide, get_laya_engine, APPS, LEVEL_WORDS
from action_dispatcher import (
    dispatch, execute_single_action, split_compound_tasks,
    open_app, close_app, is_app_running, resolve_app_path,
    set_system_volume, adjust_system_volume, mute_system_volume,
    media_play, media_pause, media_next, media_previous,
    system_lock, system_sleep, system_ram, system_battery,
    system_disk, system_screenshot, system_empty_trash
)
from audio_engine import (
    say, speak, stop_speaking, is_speaking,
    transcribe_audio_buffer, clean_transcription,
    fetch_neural_tts, AudioRecorder,
    prefetch_tts,
)
from hotkey_manager import HotkeyManager, PTT_KEY
from secrets_store import get_secret, reload_secrets
from jarvis_memory import add_turn, get_voice, set_voice, VOICE_MALE, VOICE_FEMALE

load_dotenv()

# Compatibility Aliases
def reload_keys():
    reload_secrets()

# --------------------------------------------------------------------------- Timers and Reminders
NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "ninety": 90, "couple": 2, "few": 3
}
UNITS = {
    "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
    "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600
}
DURATION_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)\b(\s+and\s+a\s+half)?")

TIMERS = []
TIMERS_LOCK = threading.Lock()


def parse_duration(text: str):
    total = 0
    clean = text.lower()
    for num, unit, half in DURATION_RE.findall(clean):
        secs = UNITS.get(unit, 1)
        total += float(num) * secs + (secs / 2 if half else 0)
    return int(total) or None


def parse_reminder(text: str):
    m = re.search(r"\bto\s+(.+)$", text, re.I)
    if not m:
        return None
    what = DURATION_RE.sub("", m.group(1))
    what = re.sub(r"\bplease\b", "", what).strip(" .,!?")
    what = re.sub(r"\s*\b(in|for|after)$", "", what).strip(" .,!?")
    return what or None


def add_timer(secs, label=None):
    t = {"end": time.time() + secs, "secs": secs, "label": label}
    with TIMERS_LOCK:
        TIMERS.append(t)
        TIMERS.sort(key=lambda x: x["end"])
    return t


def timer_snapshot():
    now = time.time()
    with TIMERS_LOCK:
        out = []
        for t in TIMERS:
            lbl = t.get("label") or f"{int(t.get('secs', 0))}s timer"
            left = max(0, t["end"] - now)
            out.append((lbl.capitalize(), left))
        return out


# --------------------------------------------------------------------------- High-Level One Turn
def handle(text: str, stt_ms=None, notify=None):
    """Execute transcribed user query through the decoupled action dispatcher and speak result."""
    clean = clean_transcription(text)
    if not clean:
        return ""
    if notify:
        notify("Thinking", clean)

    replies = dispatch(clean, notify=notify)
    if not replies:
        return ""

    final_reply = " ".join(r.strip() for r in replies if r.strip())
    if final_reply:
        # Prefetch TTS audio in background immediately — eliminates voice-start lag
        prefetch_tts(final_reply)
        say(final_reply, notify=notify)
        add_turn(clean, final_reply)
        if notify:
            notify("Ready", final_reply)
    return final_reply


# Backward compatible jev classification pointer
def jev(text, questions=None):
    return laya_decide(text, questions=questions)


# --------------------------------------------------------------------------- Voice Assistant Loop
def run_voice_assistant(mode="ptt", notify=None, controls=None, on_audio_level=None, **kwargs):
    """Run interactive audio loop with Push-to-Talk or Wake-Word activation."""
    # Resilient handling for inverted positional arguments
    if callable(mode):
        notify, controls, mode = mode, notify, (controls or "ptt")
    if "mode" in kwargs:
        mode = kwargs["mode"]
    if "notify" in kwargs:
        notify = kwargs["notify"]
    if "controls" in kwargs:
        controls = kwargs["controls"]
    if "on_audio_level" in kwargs:
        on_audio_level = kwargs["on_audio_level"]

    print(f"\n[mode: {'always listening for Hey Niko' if mode == 'wake' else 'Alt push-to-talk'}]")
    print("ready. ctrl+c to quit.\n")

    # Auto-initialize native Rust daemon in background
    try:
        from jarvis_rust_client import start_rust_daemon
        threading.Thread(target=start_rust_daemon, daemon=True).start()
    except Exception:
        pass

    processing_lock = threading.Lock()

    def process_audio(audio_buf):
        with processing_lock:
            if len(audio_buf) == 0:
                if notify:
                    notify("Ready", "")
                return
            if notify:
                notify("Thinking", "Transcribing speech...")
            transcript, stt_ms = transcribe_audio_buffer(audio_buf)
            if transcript:
                print(f"\n> {transcript} ({stt_ms}ms)")
                handle(transcript, stt_ms=stt_ms, notify=notify)
            else:
                if notify:
                    notify("Ready", "")

    def on_press():
        # Stop speech immediately on push
        stop_speaking()
        recorder.start_recording(auto_stop=False)
        if notify:
            notify("Listening", "Listening...")

    def on_release(duration=0.5):
        buf = recorder.stop_recording()
        threading.Thread(target=process_audio, args=(buf,), daemon=True).start()

    def handle_silence_stop(is_timeout=False):
        if is_timeout:
            recorder.stop_recording()
            if notify:
                notify("Ready", "")
            return
        on_release(0.5)

    recorder = AudioRecorder(on_silence_stop=handle_silence_stop, on_audio_level=on_audio_level)
    if notify:
        notify("Ready", "Hold Alt to talk" if mode == "ptt" else "Say 'Hey Niko'")

    # Start standalone hotkey listener only if UI controls queue is not driving events
    if not controls:
        hotkey = HotkeyManager(on_press, on_release)
        hotkey.start_pynput_listener()

    # Worker queue listener for assistant UI integration
    if controls and hasattr(controls, "get"):
        while True:
            try:
                item = controls.get(timeout=0.2)
                if isinstance(item, tuple):
                    cmd, val = item
                else:
                    cmd, val = str(item), None

                if cmd == "mode":
                    mode = val or "ptt"
                elif cmd in ("press", "wake"):
                    on_press()
                elif cmd == "release":
                    on_release(0.5)
                elif cmd == "pause_speech":
                    stop_speaking()
                    if notify:
                        notify("Ready", "")
            except queue.Empty:
                pass
            except Exception as e:
                print(f"  [Controls loop notice]: {e}")
    else:
        try:
            while True:
                time.sleep(0.5)
                recorder.ensure_stream_alive()
        except KeyboardInterrupt:
            print("\nShutting down NIKO.")
            hotkey.stop_pynput_listener()


# --------------------------------------------------------------------------- CLI Entrypoint
def main():
    parser = argparse.ArgumentParser(description="NIKO (Voice Operating Assistant)")
    parser.add_argument("--text", help="skip microphone, run one turn on text")
    parser.add_argument("--ui", action="store_true", help="show native floating status and Dynamic Island HUD")
    parser.add_argument("--wake", action="store_true", help="always listening wake-word mode")
    args = parser.parse_args()

    if args.ui:
        if sys.platform == "darwin":
            from assistant_ui import run_app
            run_app()
        else:
            from jarvis_hud import get_hud, update_hud
            get_hud()
            run_voice_assistant(mode="wake" if args.wake else "ptt", notify=update_hud)
        return

    if args.text:
        handle(args.text)
        return

    run_voice_assistant(mode="wake" if args.wake else "ptt")


if __name__ == "__main__":
    main()
