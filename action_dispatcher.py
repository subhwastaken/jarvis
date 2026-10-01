"""Action Dispatcher and Execution Engine for J.A.R.V.I.S.
Coordinates intent execution across applications, system settings, media players,
window management, developer tools, web browsers, and self-healing workflows.
Includes an asynchronous worker pool so heavy AppleScript or system commands
never block the assistant UI or audio visualizer threads.

Upgrades (v2):
  - True parallel sub-task execution for independent commands
  - Multi-turn LLM conversation context injected from jarvis_memory
  - Persistent background scheduler (jarvis_scheduler) for timers & reminders
  - Self-heal call signature corrected
"""
import concurrent.futures
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import random
import requests

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")
from dotenv import load_dotenv
from secrets_store import get_secret
import laya_engine
from laya_engine import laya_decide, get_laya_engine, APPS, LEVEL_WORDS
import platform_adapter
from jarvis_memory import (
    get_memory_context, add_turn, remember_fact, update_name,
    get_voice, set_voice, get_assistant_name, VOICE_MALE, VOICE_FEMALE
)
from jarvis_search import search_and_synthesize
from jarvis_dev import get_git_summary, get_last_commit, read_project_file, list_project_files
from jarvis_daemon import get_system_health_status
from jarvis_browser import play_youtube, search_google_browser, open_website, control_browser_tab
from jarvis_clipboard import get_clipboard_text, set_clipboard_text
from jarvis_windows import maximize_active_window, tile_active_window, center_active_window, hide_other_applications
from jarvis_notes import take_quick_note, get_latest_note, list_recent_notes
from jarvis_rust_client import send_rust_command, get_rust_telemetry, is_rust_daemon_running
import jarvis_planner
from jarvis_self_healing import get_learned_store, execute_learned_entry, self_heal_action
from jarvis_gui import (
    click_web_element, fill_web_input, click_desktop_ui_button,
    format_excel_cell, perform_calculator_operation, get_frontmost_browser,
    get_active_page_text, get_active_page_url, paste_into_frontmost_app,
)
import jarvis_scheduler
from jarvis_scheduler import handle_timer_command, start_scheduler
from jarvis_email import compose_email

load_dotenv()
NVIDIA_KEY = get_secret("NVIDIA_API_KEY")
OR_KEY = get_secret("OPENROUTER_API_KEY")
LLM_MODEL = os.getenv("JARVIS_LLM_MODEL", "anthropic/claude-haiku-4.5")
LAST_ASSISTANT_REPLY = ""
PENDING_CONFIRMATION = None

# Asynchronous thread pool executor — 8 workers for parallel multi-task dispatch
_ASYNC_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="jarvis-action")

# ---------------------------------------------------------------------------
# Scheduler fire callback — called by jarvis_scheduler when a timer fires
# ---------------------------------------------------------------------------
_speak_callback = None   # set by main app (siri.py / audio_engine.py)


def set_speak_callback(fn):
    """Register the TTS function so scheduled reminders can be spoken aloud."""
    global _speak_callback
    _speak_callback = fn


def _on_task_fired(task_id: str, message: str):
    """Invoked by the scheduler daemon when a timer or reminder fires."""
    print(f"  [Dispatcher] Scheduled task '{task_id}' fired: {message!r}")
    # macOS notification
    try:
        send_rust_command("notify", {"title": "JARVIS Reminder", "message": message, "subtitle": ""})
    except Exception:
        pass
    # Speak the reminder if TTS callback is registered
    if _speak_callback:
        try:
            _speak_callback(message)
        except Exception as e:
            print(f"  [Dispatcher] Speak callback error: {e}")


# Wire and start scheduler at import time
jarvis_scheduler.set_fire_callback(_on_task_fired)
start_scheduler()

# Application Aliases Map
APP_ALIASES = {
    "chrome": "Google Chrome", "google chrome": "Google Chrome", "google": "Google Chrome",
    "vscode": "Visual Studio Code", "vs code": "Visual Studio Code", "code": "Visual Studio Code",
    "visual studio code": "Visual Studio Code", "visual studio": "Visual Studio Code",
    "slack": "Slack", "spotify": "Spotify", "discord": "Discord", "cursor": "Cursor",
    "safari": "Safari", "finder": "Finder", "terminal": "Terminal", "preview": "Preview",
    "textedit": "TextEdit", "notes": "Notes", "note": "Notes", "calculator": "Calculator",
    "calc": "Calculator", "calendar": "Calendar", "reminders": "Reminders", "reminder": "Reminders",
    "music": "Music", "apple music": "Music", "itunes": "Music", "messages": "Messages",
    "mail": "Mail", "maps": "Maps", "photos": "Photos", "photo": "Photos",
    "settings": "System Settings", "system settings": "System Settings", "preferences": "System Settings",
    "sublime": "Sublime Text", "sublime text": "Sublime Text", "iterm": "iTerm", "iterm2": "iTerm",
    "brave": "Brave Browser", "brave browser": "Brave Browser", "arc": "Arc", "firefox": "Firefox",
    "edge": "Microsoft Edge", "whatsapp": "WhatsApp", "telegram": "Telegram", "zoom": "zoom.us",
    "audacity": "Audacity", "order city": "Audacity", "keynote": "Keynote", "numbers": "Numbers", "pages": "Pages",
    "breathe": "Brave Browser", "the current default browser": "Safari", "default browser": "Safari", "browser": "Safari"
}

WEB_SHORTCUTS = {
    "youtube": "https://www.youtube.com", "you tube": "https://www.youtube.com",
    "google": "https://www.google.com", "gmail": "https://mail.google.com",
    "github": "https://github.com", "reddit": "https://reddit.com",
    "twitter": "https://x.com", "x": "https://x.com",
    "chatgpt": "https://chatgpt.com", "netflix": "https://netflix.com",
    "amazon": "https://amazon.com", "wikipedia": "https://wikipedia.org",
    "linkedin": "https://linkedin.com",
    "spotify web player": "https://open.spotify.com",
    "spotify web": "https://open.spotify.com",
    "official spotify web player": "https://open.spotify.com",
    "official spotify website": "https://open.spotify.com"
}


# --------------------------------------------------------------------------- OS Helpers
def run_async(fn, *args, timeout=5.0):
    """Execute a potentially slow function asynchronously in thread pool with timeout protection."""
    future = _ASYNC_POOL.submit(fn, *args)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        print(f"  [Async Action Timeout] Function {fn.__name__} timed out after {timeout}s")
        return None
    except Exception as e:
        print(f"  [Async Action Error] {fn.__name__}: {e}")
        return None


def resolve_app_path(name: str) -> str:
    """Dynamically resolve application bundle on macOS via Spotlight."""
    cleaned = str(name).strip()
    if not cleaned:
        return None
    query = f'kMDItemKind == "Application" && (kMDItemDisplayName == "*{cleaned}*"c || kMDItemFSName == "*{cleaned}*.app"c)'
    try:
        res = subprocess.run(["mdfind", query], capture_output=True, text=True, timeout=1.5)
        paths = [p for p in res.stdout.strip().split("\n") if p.endswith(".app")]
        if paths:
            for p in paths:
                if p.startswith("/Applications") or p.startswith(os.path.expanduser("~/Applications")) or p.startswith("/System/Applications"):
                    return p
            return paths[0]
    except Exception:
        pass
    return None


def open_app(name: str) -> str:
    """Launch any application or web shortcut dynamically."""
    global PENDING_CONFIRMATION
    raw = str(name).strip()
    if not raw:
        return "Which application would you like me to open, sir?"
    raw_lower = raw.lower()

    # Web shortcut
    if raw_lower in WEB_SHORTCUTS:
        url = WEB_SHORTCUTS[raw_lower]
        subprocess.run(["open", url])
        return f"Opening {raw.title()} in your browser, sir."

    # App alias resolution
    canonical = APP_ALIASES.get(raw_lower, raw)

    # Spotlight bundle resolution
    app_path = resolve_app_path(canonical)
    if app_path:
        app_name = os.path.splitext(os.path.basename(app_path))[0]
        subprocess.run(["open", app_path])
        return f"Opening {app_name}, sir."

    # Native NSWorkspace launch (macOS)
    if IS_MAC:
        try:
            from AppKit import NSWorkspace
            ws = NSWorkspace.sharedWorkspace()
            if ws.launchApplication_(canonical):
                return f"Opening {canonical.title()}, sir."
        except Exception:
            pass

        # Direct launch via `open -a`
        try_res = subprocess.run(["open", "-a", canonical], capture_output=True, text=True)
        if try_res.returncode == 0:
            return f"Opening {canonical.title()}, sir."

    # Windows application launch
    elif IS_WIN:
        try:
            from platform_adapter import _win_ps
            if _win_ps(f"Start-Process '{canonical}'"):
                return f"Opening {canonical.title()}, sir."
            res_proc = subprocess.run(f'start "" "{canonical}"', shell=True, capture_output=True)
            if res_proc.returncode == 0:
                return f"Opening {canonical.title()}, sir."
        except Exception:
            pass

    # Web URL fallback (e.g. if query contains a domain like github.com)
    if "." in raw_lower and not re.search(r"\s+", raw_lower):
        url = f"https://{raw_lower.strip('/')}"
        subprocess.run(["open", url])
        return f"Opening {raw} in your default browser, sir."

    # Application was NOT found on this system
    PENDING_CONFIRMATION = {
        "type": "search_google_app",
        "app_name": canonical.title(),
        "query": canonical,
        "created_at": time.time(),
    }
    device = "Mac" if IS_MAC else ("Windows PC" if IS_WIN else "computer")
    return f"I couldn't find {canonical.title()} on your {device}, sir. Would you like me to search for it on Google?"


def close_app(name: str) -> str:
    """Gracefully quit an application natively with fallback to pkill."""
    raw = str(name).strip()
    if not raw:
        return "Which application would you like me to close, sir?"
    raw_lower = raw.lower()
    canonical = APP_ALIASES.get(raw_lower, raw)

    try:
        from AppKit import NSWorkspace
        ws = NSWorkspace.sharedWorkspace()
        canonical_lower = canonical.lower()
        for app in ws.runningApplications():
            loc = app.localizedName()
            if loc and loc.lower() == canonical_lower:
                app.terminate()
                return f"Closing {canonical}, sir."
    except Exception:
        pass

    # Graceful AppleScript quit
    res = subprocess.run(["osascript", "-e", f'tell application "{canonical}" to quit'], capture_output=True, text=True, timeout=1.5)
    if res.returncode != 0 or res.stderr:
        subprocess.run(["pkill", "-f", canonical], capture_output=True)
    return f"Closing {canonical}, sir."


def is_app_running(name: str) -> bool:
    """Check if application is running in <2ms using native Cocoa."""
    try:
        from AppKit import NSWorkspace
        name_lower = name.lower()
        ws = NSWorkspace.sharedWorkspace()
        for app in ws.runningApplications():
            loc = app.localizedName()
            if loc and loc.lower() == name_lower:
                return True
        return False
    except Exception:
        pass
    try:
        res = subprocess.run(["osascript", "-e", f'application "{name}" is running'], capture_output=True, text=True, timeout=1.0)
        return res.stdout.strip().lower() == "true"
    except Exception:
        return False


def wait_for_app_ready(app_name: str, timeout: float = 4.0, poll: float = 0.1) -> bool:
    """Block until app_name has launched AND has at least one open window, or timeout expires.

    This fixes BUG-05: 'open google and search X' race where Step 2 fires before
    the browser window exists, causing the URL to open in the wrong/default app.

    Strategy:
      1. Poll NSWorkspace.runningApplications() until the process appears.
      2. Then poll AppleScript 'count windows' until >= 1 (window is ready).
      3. Give up after `timeout` seconds and continue anyway.
    """
    canonical = APP_ALIASES.get(app_name.lower(), app_name)
    deadline = time.monotonic() + timeout

    # Phase 1: wait for process to appear in NSWorkspace
    while time.monotonic() < deadline:
        if is_app_running(canonical):
            break
        time.sleep(poll)
    else:
        print(f"  [Boot Wait] '{canonical}' did not appear within {timeout}s — continuing anyway")
        return False

    # Phase 2: wait for at least one window to exist
    remaining = deadline - time.monotonic()
    window_poll_start = time.monotonic()
    while time.monotonic() < deadline:
        try:
            res = subprocess.run(
                ["osascript", "-e", f'tell application "{canonical}" to count windows'],
                capture_output=True, text=True, timeout=1.0
            )
            count = int(res.stdout.strip() or "0")
            if count >= 1:
                elapsed = time.monotonic() - window_poll_start
                print(f"  [Boot Wait] '{canonical}' ready with {count} window(s) in {elapsed:.2f}s")
                return True
        except Exception:
            pass
        time.sleep(poll)

    print(f"  [Boot Wait] '{canonical}' launched but no window appeared — continuing anyway")
    return False


# --------------------------------------------------------------------------- Volume Handlers
def set_system_volume(level) -> str:
    """Adjust system volume with word or numeric input."""
    val = parse_volume_value(level)
    return platform_adapter.set_volume(val)


def adjust_system_volume(delta: int) -> str:
    curr = platform_adapter.get_volume()
    target = max(0, min(100, curr + delta))
    return platform_adapter.set_volume(target)


def mute_system_volume(mute: bool = True) -> str:
    return platform_adapter.mute_volume(mute)


def parse_volume_value(lvl) -> int:
    clean = re.sub(r"[^\d]", "", str(lvl))
    if clean:
        return max(0, min(100, int(clean)))
    word = str(lvl).lower().strip()
    if word in LEVEL_WORDS:
        return int(LEVEL_WORDS[word])
    return 50


def media_volume_adjust(delta=None, level=None, mute=False, unmute=False) -> str:
    target = "Spotify" if is_app_running("Spotify") else "Music"
    try:
        if mute:
            subprocess.run(["osascript", "-e", f'tell application "{target}" to set sound volume to 0'], check=True)
            return f"{target} muted, sir."
        if unmute:
            subprocess.run(["osascript", "-e", f'tell application "{target}" to set sound volume to 50'], check=True)
            return f"{target} unmuted, sir."
        if level is not None:
            val = parse_volume_value(level)
            subprocess.run(["osascript", "-e", f'tell application "{target}" to set sound volume to {val}'], check=True)
            return f"{target} volume set to {val} percent, sir."
        if delta is not None:
            curr_str = subprocess.check_output(["osascript", "-e", f'tell application "{target}" to get sound volume'], text=True).strip()
            curr = int(curr_str) if curr_str.isdigit() else 50
            new_val = max(0, min(100, curr + delta))
            subprocess.run(["osascript", "-e", f'tell application "{target}" to set sound volume to {new_val}'], check=True)
            return f"{target} volume adjusted to {new_val} percent, sir."
    except Exception as e:
        return f"{target} volume adjusted, sir."
    return f"{target} volume adjusted, sir."


# --------------------------------------------------------------------------- Media Handlers
def media_play() -> str:
    if is_app_running("Spotify"):
        subprocess.run(["osascript", "-e", 'tell application "Spotify" to play'])
        return "Resuming Spotify playback, sir."
    if is_app_running("Music"):
        subprocess.run(["osascript", "-e", 'tell application "Music" to play'])
        return "Resuming Apple Music playback, sir."
    subprocess.run(["open", "-a", "Music"])
    return "Music application launched, sir."


def media_pause() -> str:
    paused = []
    if is_app_running("Spotify"):
        subprocess.run(["osascript", "-e", 'tell application "Spotify" to pause'])
        paused.append("Spotify")
    if is_app_running("Music"):
        subprocess.run(["osascript", "-e", 'tell application "Music" to pause'])
        paused.append("Music")
    return f"Playback paused on {', '.join(paused)}, sir." if paused else "Playback paused, sir."


def media_next() -> str:
    if is_app_running("Spotify"):
        subprocess.run(["osascript", "-e", 'tell application "Spotify" to next track'])
        return "Skipping to next track on Spotify, sir."
    if is_app_running("Music"):
        subprocess.run(["osascript", "-e", 'tell application "Music" to next track'])
        return "Skipping to next track, sir."
    return "Skipped to next track, sir."


def media_previous() -> str:
    if is_app_running("Spotify"):
        subprocess.run(["osascript", "-e", 'tell application "Spotify" to previous track'])
        return "Returning to previous track on Spotify, sir."
    if is_app_running("Music"):
        subprocess.run(["osascript", "-e", 'tell application "Music" to previous track'])
        return "Returning to previous track, sir."
    return "Previous track, sir."


# --------------------------------------------------------------------------- System Handlers
def system_lock() -> str:
    if is_rust_daemon_running():
        send_rust_command("lock_screen")
    else:
        subprocess.run(["osascript", "-e", 'tell application "System Events" to keystroke "q" using {control down, command down}'])
    return "Workstation locked, sir."


def system_sleep() -> str:
    subprocess.run(["pmset", "sleepnow"])
    return "Putting your Mac to sleep now. Goodnight, sir."


def system_ram() -> str:
    try:
        out = subprocess.check_output(["vm_stat"], text=True, stderr=subprocess.DEVNULL)
        pages = {}
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) == 2:
                num = re.sub(r"[^\d]", "", parts[1])
                if num:
                    pages[parts[0].strip()] = int(num)
        free_pages = pages.get("Pages free", 0) + pages.get("Pages speculative", 0)
        active_pages = pages.get("Pages active", 0) + pages.get("Pages wired down", 0)
        total_pages = free_pages + active_pages
        if total_pages > 0:
            used_gb = round((active_pages * 4096) / (1024 ** 3), 1)
            free_gb = round((free_pages * 4096) / (1024 ** 3), 1)
            return f"You are currently using {used_gb} gigabytes of RAM, with {free_gb} gigabytes free."
    except Exception:
        pass
    return "Could not determine RAM usage, sir."


def system_battery() -> str:
    try:
        out = subprocess.check_output(["pmset", "-g", "batt"]).decode()
        m = re.search(r"(\d+%);\s*([^;]+);", out)
        if m:
            pct, status = m.group(1), m.group(2).strip()
            return f"Your battery is at {pct}, currently {status}."
        return "Your Mac is currently running on power adapter, sir."
    except Exception as e:
        return f"Battery status unavailable: {e}"


def system_disk() -> str:
    try:
        out = subprocess.check_output(["df", "-h", "/"]).decode()
        lines = out.strip().splitlines()
        if len(lines) > 1:
            parts = lines[1].split()
            size, free = parts[1].replace("Gi", " gigabytes"), parts[3].replace("Gi", " gigabytes")
            return f"You have {free} free disk space out of {size} total, sir."
    except Exception:
        pass
    return "Could not determine disk space, sir."


def capture_screen_image() -> str | None:
    """Capture the screen to a temp PNG and return its path, or None on failure.

    BUG-22 note: if macOS Screen Recording permission is not granted, screencapture
    silently returns the desktop wallpaper. We detect this by checking image variance.
    """
    try:
        import tempfile
        path = tempfile.mktemp(suffix=".jpg")  # JPEG for smaller base64 payload
        # -x silent, -m main display only, -t jpeg
        result = subprocess.run(
            ["screencapture", "-x", "-m", "-t", "jpg", path],
            capture_output=True, timeout=5
        )
        if result.returncode != 0 or not os.path.exists(path):
            return None
        return path
    except Exception:
        return None


def system_screenshot() -> str:
    try:
        desktop = os.path.expanduser("~/Desktop")
        timestamp = time.strftime("%Y-%m-%d-%H%M%S")
        path = os.path.join(desktop, f"Screenshot-{timestamp}.png")
        subprocess.run(["screencapture", "-x", path], check=True)
        return "Screenshot taken and saved to your Desktop, sir."
    except Exception as e:
        return f"Failed to take screenshot: {e}"


def system_empty_trash() -> str:
    if is_rust_daemon_running():
        send_rust_command("empty_trash")
    else:
        subprocess.run(["osascript", "-e", 'tell application "Finder" to empty trash'])
    return "Trash has been emptied, sir."


# --------------------------------------------------------------------------- LLM Fallback
def ask_llm(prompt: str, include_history: bool = True) -> tuple[str, int, float]:
    """Query LLM with optional rolling multi-turn conversation context.

    Injects up to MAX_HISTORY_TURNS of recent conversation into the message list
    before the current user prompt, giving the LLM full conversational awareness.
    Falls back: NVIDIA NIM → OpenRouter.
    """
    t0 = time.time()

    # --- Build system prompt with user profile context ---
    mem_ctx, recent_history = get_memory_context()
    system_prompt = (
        "You are NIKO, a sophisticated, concise British AI assistant for macOS. "
        "Address the user politely as 'sir'. Answer concisely in 1 to 2 clear spoken sentences. "
        "Do NOT use markdown, asterisks, bullet points, or code formatting. "
        f"Context: {mem_ctx}"
    )

    # --- Assemble messages with conversation history ---
    messages = [{"role": "system", "content": system_prompt}]
    if include_history and recent_history:
        for turn in recent_history:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if content:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": prompt})

    nvidia_key = get_secret("NVIDIA_API_KEY")
    or_key = get_secret("OPENROUTER_API_KEY")
    nvidia_model = os.getenv("NVIDIA_MODEL", "meta/llama-3.2-11b-vision-instruct")

    # 1. NVIDIA NIM
    if nvidia_key:
        try:
            r = requests.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {nvidia_key}", "Content-Type": "application/json"},
                json={"model": nvidia_model, "max_tokens": 180, "messages": messages},
                timeout=12
            )
            if r.status_code == 200:
                content = r.json()["choices"][0]["message"]["content"].strip()
                clean = re.sub(r"[*#`_]", "", content).strip()
                ms = int((time.time() - t0) * 1000)
                return clean, ms, 0.0
            else:
                print(f"  [NVIDIA NIM Notice] Status {r.status_code}: {r.text[:120]}")
        except Exception as e:
            print(f"  [NVIDIA NIM Notice] Request failed: {e}")

    # 2. OpenRouter fallback
    if or_key:
        try:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {or_key}"},
                json={"model": LLM_MODEL, "max_tokens": 180, "messages": messages},
                timeout=12
            )
            if r.status_code == 200:
                content = r.json()["choices"][0]["message"]["content"].strip()
                clean = re.sub(r"[*#`_]", "", content).strip()
                ms = int((time.time() - t0) * 1000)
                return clean, ms, 0.0
        except Exception:
            pass

    return "I am unable to connect to online intelligence at the moment, sir.", int((time.time() - t0) * 1000), 0.0


def ask_vision_llm(image_path: str, user_prompt: str) -> tuple[str, int]:
    """Send a screenshot + text prompt to a multimodal vision LLM.

    Uses the OpenAI-compatible multimodal message format:
      content = [{type: image_url, image_url: {url: data:image/jpeg;base64,...}}, {type: text, text: ...}]

    Priority:
      1. NVIDIA NIM  (llama-3.2-11b-vision-instruct)  — fast, free tier
      2. OpenRouter  (google/gemini-flash-1.5)         — fallback
    """
    import base64
    t0 = time.time()

    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        return f"Could not read screenshot: {e}", 0

    image_url = f"data:image/jpeg;base64,{b64}"
    messages = [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": image_url}},
            {"type": "text",      "text": user_prompt}
        ]
    }]
    system_prompt = (
        "You are NIKO, a sophisticated British AI assistant. The user has shared a screenshot "
        "of their screen. Describe or answer their question concisely in 2-3 spoken sentences. "
        "No markdown, no bullet points, no asterisks."
    )
    nvidia_key = get_secret("NVIDIA_API_KEY")
    or_key = get_secret("OPENROUTER_API_KEY")
    nvidia_model = os.getenv("NVIDIA_MODEL", "meta/llama-3.2-11b-vision-instruct")

    # 1. NVIDIA NIM vision
    if nvidia_key:
        try:
            r = requests.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {nvidia_key}", "Content-Type": "application/json"},
                json={"model": nvidia_model, "max_tokens": 300,
                      "messages": [{"role": "system", "content": system_prompt}] + messages},
                timeout=20
            )
            if r.status_code == 200:
                text = r.json()["choices"][0]["message"]["content"].strip()
                return re.sub(r"[*#`_]", "", text), int((time.time() - t0) * 1000)
            print(f"  [Vision NVIDIA] {r.status_code}: {r.text[:120]}")
        except Exception as e:
            print(f"  [Vision NVIDIA] {e}")

    return "I was unable to analyse the screen at this moment, sir.", int((time.time() - t0) * 1000)


def analyze_screen(user_question: str = "") -> str:
    """Capture the screen and answer the user's question about it using a vision LLM.

    This is the implementation for commands like:
      - 'what is on my screen'
      - 'explain this'
      - 'what am I looking at'
      - 'read the error on my screen'

    BUG-22 mitigation: if Screen Recording is denied, screencapture returns the
    desktop wallpaper. We warn the user if the image appears to be very uniform
    (low pixel variance), which is the signature of a blank wallpaper capture.
    """
    img_path = capture_screen_image()
    if not img_path:
        return (
            "I was unable to capture your screen, sir. "
            "Please grant Screen Recording permission in System Settings → Privacy & Security → Screen Recording."
        )

    # BUG-22 detection: check if image looks like a blank wallpaper (very low variance)
    try:
        import struct, zlib
        with open(img_path, "rb") as f:
            data = f.read()
        # Sample the first 512 bytes of pixel data for a quick variance check
        pixel_sample = data[100:612]
        variance = max(pixel_sample) - min(pixel_sample)
        if variance < 8:
            return (
                "It appears Screen Recording permission has not been granted, sir. "
                "The screenshot only shows your desktop wallpaper. "
                "Please enable it in System Settings → Privacy & Security → Screen Recording."
            )
    except Exception:
        pass  # Can't check variance — proceed anyway

    prompt = user_question.strip() if user_question.strip() else (
        "Please describe what is visible on this screen. Mention the active application, "
        "what content is displayed, and any notable elements such as code, errors, or UI components."
    )
    reply, ms = ask_vision_llm(img_path, prompt)
    print(f"  [Vision] Analysed screen in {ms}ms")

    # Clean up temp file
    try:
        os.remove(img_path)
    except Exception:
        pass

    LAST_ASSISTANT_REPLY = reply
    return reply


# --------------------------------------------------------------------------- Compound Task Splitting
def split_compound_tasks(text: str) -> list[str]:
    """Break multi-step commands into discrete atomic executable sub-tasks."""
    clean = text.strip().strip(".!?")
    # Strip any wake prefix (e.g., "Hey Niko", "Niko", "Hey Jev", "Jarvis")
    clean = re.sub(r'^(?:(?:hey|hi|hello|ok|okay)?\s*(?:niko|jarvis|siri|friday|jev)[,\s]*)+', '', clean, flags=re.I).strip()
    if not clean:
        return []

    # Preserve conditionals for planner
    if re.search(r"\b(if|unless|otherwise)\b", clean, re.I):
        return [clean]

    # Preserve unified 2-step browser phrases: "open google and search X" or "open youtube and play X"
    # Narrow match: only fires when there is NO second 'and <verb>' after the search clause.
    if re.search(
        r"^(?:open|launch)\s+(?:google|youtube|browser|chrome|google\s+chrome|safari|brave)"
        r"\s+and\s+(?:search(?:\s+for)?|play|find)\s+(?:(?!\s+and\s+(?:play|search|open|find)\b).)+$",
        clean, re.I
    ):
        return [clean]

    # Split parallel app operations:
    #   "close calculator and safari"   -> ["close calculator", "close safari"]  (same verb applied)
    #   "close calculator and open spotify" -> ["close calculator", "open spotify"] (app2 has own verb)
    m_multi_app = re.match(r"^(open|launch|close|quit|kill|exit|shut\s+down|terminate)\s+([a-zA-Z0-9\s]+?)\s+(?:and|\&|\band\s+also\b)\s+([a-zA-Z0-9\s]+)$", clean, re.I)
    if m_multi_app:
        verb, app1, app2 = m_multi_app.group(1).strip(), m_multi_app.group(2).strip(), m_multi_app.group(3).strip()
        if not re.search(r"\b(search|find|click|write|read|check|calculate|perform|turn|set|mute|unmute|play|pause|lock|sleep|volume)\b", app2, re.I):
            # If app2 begins with its own action verb, use it verbatim; otherwise inherit the outer verb
            if re.match(r"^(open|launch|close|quit|kill|exit|shut\s+down|terminate)\b", app2, re.I):
                return [f"{verb} {app1}", app2]
            return [f"{verb} {app1}", f"{verb} {app2}"]

    action_verbs = (
        r"open|launch|close|quit|search|google|find|check|set|turn|mute|unmute|"
        r"play|pause|resume|calculate|perform|take|write|read|format|click|show|tell|"
        r"go|bring|switch|start|run|tile|maximize|minimize|hide|snap|copy|explain|"
        r"summarize|list|create|make|delete|remove|lock|sleep|next|prev|previous|"
        r"git|last|remember|what|shut\s+down|terminate"
    )
    pattern = (
        r"(?:\s*,\s*(?:and\s+then|and|then|after\s+that)\s+"
        r"|\s+(?:and\s+then|then|after\s+that)\s+"
        r"|\s*;\s*"
        rf"|\s*,\s*(?=(?:{action_verbs})\b)"  # bare comma before action verb: "open google, search X"
        rf"|\s+and\s+(?=(?:{action_verbs})\b))"
    )
    parts = [p.strip() for p in re.split(pattern, clean, flags=re.I) if p.strip()]
    return parts if len(parts) > 1 else [clean]


# --------------------------------------------------------------------------- Single Action Execution
def execute_single_action(text: str, notify=None) -> str:
    """Execute a single atomic command using Laya local decision engine and OS adapters."""
    global LAST_ASSISTANT_REPLY, PENDING_CONFIRMATION
    cleaned = text.strip().strip(".!?")
    # Strip any wake prefix (e.g., "Hey Niko", "Niko", "Hey Jev", "Jarvis")
    cleaned = re.sub(r'^(?:(?:hey|hi|hello|ok|okay)?\s*(?:niko|jarvis|siri|friday|jev)[,\s]*)+', '', cleaned, flags=re.I).strip()
    if not cleaned:
        return ""

    t_lower = cleaned.lower()

    # 0. Conversational Confirmation Handling (e.g. user says "yes" to "should I search it on Google?")
    if PENDING_CONFIRMATION:
        elapsed = time.time() - PENDING_CONFIRMATION.get("created_at", 0)
        if elapsed < 90:
            # Affirmative confirmation ("yes", "yeah", "sure", "yes please", "search on google", "go ahead")
            if re.search(r"^(?:yes|yeah|yep|sure|go\s+ahead|do\s+it|please|ok|okay)\b|\bsearch\s+(?:it\s+)?(?:on|in)\s+google\b", cleaned, re.I):
                conf = PENDING_CONFIRMATION
                PENDING_CONFIRMATION = None
                if conf.get("type") == "search_google_app":
                    app_name = conf.get("app_name") or conf.get("query")
                    return search_google_browser(app_name)
                elif conf.get("type") == "open_app":
                    return open_app(conf.get("app_name"))

            # Explicit rejection ("no", "nope", "never mind", "cancel", "don't")
            elif re.search(r"^(?:no(?:\s+thanks|\s+thank\s+you)?|nope|nah|never\s+mind|cancel|stop|don'?t)\b", cleaned, re.I):
                PENDING_CONFIRMATION = None
                return "Understood, sir."
        else:
            PENDING_CONFIRMATION = None

    # 1. Learned Self-Healing Reflex Cache
    learned_entry = get_learned_store().get(cleaned)
    if learned_entry:
        return execute_learned_entry(learned_entry)

    # 1a. Autonomous Multi-Step Planner (conditional & compound GUI tasks)
    #     Routes: "if X then Y", "when Z do A and B", "click the submit button",
    #             "open Excel and format cell A1", "calculate 45*9 in calculator"
    if jarvis_planner.is_conditional_or_gui_query(cleaned):
        try:
            plan_reply, _ = jarvis_planner.execute_plan(cleaned, execute_single_action)
            if plan_reply:
                LAST_ASSISTANT_REPLY = plan_reply
                return plan_reply
        except Exception as _pe:
            print(f"  [Planner] Error: {_pe}")

    # 2. Math Expressions (Instant Offline Math)
    is_math, math_res = laya_engine.get_laya_engine().is_math_query(cleaned)
    if is_math:
        return f"The result is {math_res}, sir."

    # 3. Voice Switcher Commands
    if re.search(r"\b(?:switch to|use|change to|set|activate|speak in|talk in)\s+(?:the\s+)?(female|woman|girl)\s*(?:voice)?\b|\bfemale\s+voice\b", cleaned, re.I):
        set_voice("female")
        return "Switched to female voice, sir."
    if re.search(r"\b(?:switch to|use|change to|set|activate|speak in|talk in)\s+(?:the\s+)?(male|man|boy)\s*(?:voice)?\b|\bmale\s+voice\b", cleaned, re.I):
        set_voice("male")
        return "Right away, sir. Switched to male voice."

    # 4. Personal Info & Memory
    m_name = re.search(r"^(?:my name is|call me)\s+([A-Za-z\s]+?)$", cleaned, re.I)
    if m_name:
        new_name = m_name.group(1).strip().title()
        update_name(new_name)
        return f"Understood, {new_name}. I have updated your profile in my memory."

    m_fact = re.search(r"^(?:please\s+)?remember\s+(?:that\s+)?(.+)", cleaned, re.I)
    if m_fact:
        remember_fact(m_fact.group(1).strip())
        return "Understood, sir. I have committed that to memory."

    # 5. Media & YouTube Direct Play
    if re.search(r"^(?:resume(?:\s+music|\s+spotify|\s+playback)?|continue\s+playing)$", cleaned, re.I):
        return media_play()
    if re.search(r"^(?:forward\s+track|next\s+track|next\s+song|skip\s+track|skip\s+song|^skip$)$", cleaned, re.I):
        return media_next()
    if re.search(r"^(?:previous\s+track|prev\s+track|previous\s+song|go\s+back\s+a\s+song|last\s+song|^prev$)$", cleaned, re.I):
        return media_previous()
    # 5. YouTube Playback (Unified & Direct)
    m_yt_unified = re.search(r"^(?:open|launch)\s+youtube\s+and\s+(?:play|search(?:\s+for)?)\s+(.+)$", cleaned, re.I)
    if m_yt_unified:
        return play_youtube(m_yt_unified.group(1).strip())

    if re.search(r"\b(?:play\s+youtube|play\s+on\s+youtube|youtube\s+search)\b", cleaned, re.I) or re.search(r"^play\s+(.+)\s+on\s+youtube$", cleaned, re.I):
        q = re.sub(r"^(?:play\s+youtube|play\s+on\s+youtube|youtube\s+search|play)\s*", "", cleaned, flags=re.I)
        q = re.sub(r"\s+on\s+youtube$", "", q, flags=re.I).strip()
        return play_youtube(q or "chill lofi music")

    # 6. Unified Browser Search: "open chrome and search for what's up", "open safari and look up weather"
    m_browser_search = re.search(
        r"^(?:open|launch)\s+(?P<browser>google\s+chrome|chrome|safari|brave|firefox|edge|browser|google)"
        r"\s+and\s+(?:search(?:\s+for)?|find|look\s+up|google)\s+(?P<query>.+)$",
        cleaned, re.I
    )
    if m_browser_search:
        b = m_browser_search.group("browser").strip()
        q = m_browser_search.group("query").strip()
        return search_google_browser(q, browser=b)

    # Search on target: "search for what's up on google / chrome / youtube"
    m_search_on = re.search(
        r"^(?:search(?:\s+for)?|look\s+up|find)\s+(?P<query>.+?)\s+(?:on|in|using)\s+(?P<target>google|chrome|google\s+chrome|safari|brave|firefox|edge|youtube|the\s+web)$",
        cleaned, re.I
    )
    if m_search_on:
        tgt = m_search_on.group("target").lower().strip()
        q = m_search_on.group("query").strip()
        if "youtube" in tgt:
            return play_youtube(q)
        return search_google_browser(q, browser=tgt if tgt not in ("google", "the web") else None)

    # 7. Web & Google Direct Search
    m_search = re.search(r"^(?:search\s+google\s+for|search(?:\s+for|\s+the\s+web\s+for)?|google(?:\s+for)?|look\s+up)\s+(.+)$", cleaned, re.I)
    if m_search and not re.search(r"\b(?:tab|window|file|app|screen|spotify|music)\b", cleaned, re.I):
        squery = m_search.group(1).strip()
        return search_google_browser(squery)

    # 7. Website Navigation (e.g. "go to github.com", "open apple.com")
    m_url = re.search(r"^(?:open|launch|go\s+to)\s+([A-Za-z0-9\-.]+\.(?:com|org|io|dev|ai|net|edu|app|co))\b", cleaned, re.I)
    if m_url:
        return open_website(m_url.group(1).strip())

    # Direct App Aliases (e.g. 'order city' -> Audacity, 'breathe' -> Brave)
    if t_lower in APP_ALIASES:
        return open_app(APP_ALIASES[t_lower])

    # Volume Shortcuts (e.g. 'crank up the sound', 'boost audio')
    if re.search(r"\b(?:crank(?:\s+up)?|boost\s+audio|pump\s+up)\b", cleaned, re.I):
        return adjust_system_volume(20)

    # 8. Browser Tab Controls
    if re.search(r"\b(close\s+(?:this|the|active)?\s*tab)\b", cleaned, re.I):
        return control_browser_tab("close_tab")
    if re.search(r"\b(new\s+tab|open\s+(?:a\s+)?new\s+tab|create\s+new\s+tab)\b", cleaned, re.I):
        return control_browser_tab("new_tab")
    if re.search(r"\b(reload\s+(?:this|the|active)?\s*tab|refresh\s+tab|refresh\s+this\s+page|reload\s+this\s+page)\b", cleaned, re.I):
        return control_browser_tab("reload")
    if re.search(r"\b(next\s+tab|switch\s+to\s+next\s+tab)\b", cleaned, re.I):
        return control_browser_tab("next_tab")
    if re.search(r"\b(previous\s+tab|prev\s+tab|switch\s+to\s+prev\s+tab)\b", cleaned, re.I):
        return control_browser_tab("prev_tab")

    # 9. Window Controls
    if re.search(r"\b(?:maximize(?:\s+this|\s+the|\s+active)?\s+window|fill(?:\s+the)?\s+screen|full\s+screen\s+window)\b", cleaned, re.I):
        return maximize_active_window()
    if re.search(r"\b(?:tile(?:\s+this|\s+the|\s+active)?\s+window\s+(?:to\s+the\s+)?left|snap\s+left|put\s+window\s+on\s+left)\b", cleaned, re.I):
        return tile_active_window("left")
    if re.search(r"\b(?:tile(?:\s+this|\s+the|\s+active)?\s+window\s+(?:to\s+the\s+)?right|snap\s+right|put\s+window\s+on\s+right)\b", cleaned, re.I):
        return tile_active_window("right")
    if re.search(r"\b(?:center(?:\s+this|\s+the|\s+active)?\s+window)\b", cleaned, re.I):
        return center_active_window()
    if re.search(r"\b(?:hide\s+other\s+apps|focus\s+mode|hide\s+background\s+apps)\b", cleaned, re.I):
        return hide_other_applications()

    # 10. Developer Tools Shortcuts
    if re.search(r"\b(git status|uncommitted changes|git branch|what branch am i on|show repository status|display git summary|check repo changes|check git repository)\b", cleaned, re.I):
        return get_git_summary()
    if re.search(r"\b(last commit|git log|latest commit|view git log|recent git commit|show last commit|what was the last commit)\b", cleaned, re.I):
        return get_last_commit()
    m_read = re.search(r"\b(?:read|inspect|what is in)\s+(?:the\s+)?file\s+([A-Za-z0-9_.\-/]+)", cleaned, re.I)
    if m_read:
        return read_project_file(m_read.group(1).strip())
    if re.search(r"\b(list project files|list files in project|show project structure|what files are in this repo|inspect repository tree)\b", cleaned, re.I):
        return list_project_files()

    # 11. Notes Shortcuts
    m_note = re.search(r"^(?:take\s+a\s+note|note\s+down|write\s+this\s+down)(?:\s+that|\s*:)?\s+(.+)", cleaned, re.I)
    if m_note:
        return take_quick_note(m_note.group(1).strip())
    if re.search(r"\b(?:read|what\s+was|get|show)\s+(?:my\s+)?(?:latest|last)\s+note\b", cleaned, re.I):
        return get_latest_note()
    if re.search(r"\b(?:list|show|what\s+are)\s+(?:all\s+)?(?:my\s+)?notes\b", cleaned, re.I):
        return list_recent_notes()

    # 11a. Timer & Reminder Commands (persistent background scheduler)
    _TIMER_RE = re.compile(
        r"\b(?:remind\s+me|set\s+(?:a\s+)?(?:timer|reminder|alarm)|timer\s+for"
        r"|countdown|alarm\s+(?:in|for)"
        r"|check\s+(?:my\s+)?(?:timer|reminder)s?"
        r"|cancel\s+(?:all\s+)?(?:timer|reminder|alarm)s?"
        r"|list\s+(?:my\s+)?(?:timer|reminder|task)s?)\b",
        re.I
    )
    if _TIMER_RE.search(cleaned):
        return handle_timer_command(cleaned)

    # 11b. Email / Gmail Compose
    #  "write an email to xyz@gmail.com"  /  "compose email to boss about report"
    #  "send email to john saying hi there"
    _EMAIL_CMD_RE = re.compile(
        r"\b(?:write|compose|send|draft|create|email|mail)\s+(?:an?\s+)?(?:email|mail|message)\b"
        r"|\bemail\s+(?:to\s+)?[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}"
        r"|\bcompose\s+to\b",
        re.I
    )
    if _EMAIL_CMD_RE.search(cleaned):
        return compose_email(cleaned)

    # 11c. Screen Vision
    _SCREEN_VISION_RE = re.compile(
        r"\b(?:"
        r"what(?:'s|\s+is)?\s+(?:on|in|happening\s+on)?\s+(?:my\s+)?screen"
        r"|what\s+am\s+i\s+(?:looking\s+at|seeing)"
        r"|explain\s+(?:this|what(?:'s|\s+is)?\s+(?:on|in)?\s+(?:my\s+)?screen)"
        r"|read\s+(?:the\s+)?(?:error|message|text|content)\s+(?:on|from)\s+(?:my\s+)?screen"
        r"|(?:look\s+at|analyse|analyze|describe)\s+(?:my\s+)?screen"
        r"|what\s+does\s+(?:my\s+)?screen\s+(?:say|show)"
        r"|can\s+you\s+see\s+(?:my\s+)?screen"
        r")\b",
        re.I
    )
    if _SCREEN_VISION_RE.search(cleaned):
        # Extract optional specific question (everything after "screen" if present)
        q_match = re.search(
            r"(?:screen|this)\s+(.{10,})", cleaned, re.I
        )
        question = q_match.group(1).strip() if q_match else ""
        return analyze_screen(question)

    # 12. Clipboard Intelligence
    if re.search(r"\b(?:copy(?:\s+that|\s+this)?(?:\s+to(?:\s+my)?\s+clipboard)?|copy\s+to\s+clipboard|copy\s+response\s+to\s+clipboard)\b", cleaned, re.I) and not re.search(r"\b(?:what|explain|read|debug)\b", cleaned, re.I):
        text_to_copy = LAST_ASSISTANT_REPLY or "NIKO Desktop Assistant - Operational"
        ok = set_clipboard_text(text_to_copy)
        return "I have copied my last response to your clipboard, sir." if ok else "I encountered an issue copying to your clipboard, sir."
    if re.search(r"\b(?:explain|what(?:'s|\s+is)\s+in|read|summarize)\s+(?:what(?:'s|\s+is)\s+in\s+)?(?:my\s+)?clipboard\b", cleaned, re.I):
        clip = get_clipboard_text()
        if not clip:
            return "Your clipboard is currently empty, sir."
        prompt = f"The user asked to explain their clipboard contents.\nClipboard text:\n```\n{clip[:2500]}\n```\nExplain what it is concisely in one or two clear spoken sentences. No markdown."
        line, _, _ = ask_llm(prompt)
        return line

    # 12b. Summarize active browser page ("summarize this", "summarize this page", "what is on this page")
    if re.search(
        r"\b(?:summarize|tldr|tl\s*;?\s*dr|give\s+me\s+a\s+summary\s+of|what(?:'s|\s+is)\s+(?:on|this)|read\s+this|explain\s+this\s+page)"
        r"(?:\s+(?:this|the|current|active|open))?(?:\s+(?:page|site|website|tab|article|url))?\b",
        cleaned, re.I
    ):
        url = get_active_page_url()
        page_text = get_active_page_text(max_chars=3500)
        if not page_text:
            return (
                "I was unable to read the page content, sir. "
                "Please ensure 'Allow JavaScript from Apple Events' is enabled in your browser's "
                "Developer menu, and that Screen Recording permission is granted."
            )
        url_hint = f" ({url})" if url else ""
        prompt = (
            f"The user has a webpage open{url_hint} and asked for a summary.\n"
            f"Page text (first 3500 chars):\n```\n{page_text}\n```\n"
            "Summarise the key points in 2-3 concise spoken sentences. No markdown, no bullet points."
        )
        summary, _, _ = ask_llm(prompt)
        LAST_ASSISTANT_REPLY = summary   # store so user can later copy/paste it
        return summary

    # 12c. Paste last reply into an app ("paste that into google docs", "open notes and paste the summary")
    m_paste = re.search(
        r"\bpaste\s+(?:it|that|the\s+(?:summary|result|response|answer)|this)?\s*"
        r"(?:(?:into|in(?:\s+to)?|to)\s+(?P<app>[a-zA-Z0-9\s\-]+?))?\s*$",
        cleaned, re.I
    )
    if m_paste:
        target_app = (m_paste.group("app") or "").strip()
        text_to_paste = LAST_ASSISTANT_REPLY
        if not text_to_paste:
            return "There is nothing in my last response to paste, sir."
        set_clipboard_text(text_to_paste)
        if target_app:
            canonical = APP_ALIASES.get(target_app.lower(), target_app)
            # Handle web apps (Google Docs, Notion, etc.)
            web_apps = {
                "google docs": "https://docs.google.com/document/create",
                "google doc": "https://docs.google.com/document/create",
                "notion": "https://www.notion.so",
                "notes": None,  # native app
            }
            web_url = web_apps.get(target_app.lower())
            if web_url:
                import subprocess as _sp
                _sp.run(["open", web_url])
                wait_for_app_ready("Google Chrome")   # wait for the tab
                import time as _t; _t.sleep(1.2)      # extra settle for doc editor
                paste_into_frontmost_app()
                return f"Opened {target_app.title()} and pasted the summary, sir."
            else:
                # Native app
                open_app(canonical)
                wait_for_app_ready(canonical)
                paste_into_frontmost_app()
                return f"Opened {canonical} and pasted the summary, sir."
        else:
            paste_into_frontmost_app()
            return "Pasted my last response into the active window, sir."

    if re.search(r"\b(system health|health check|diagnostics|rust status|daemon status)\b", cleaned, re.I):
        if is_rust_daemon_running():
            telem = get_rust_telemetry()
            return f"Rust Core daemon is online, sir. {telem}"
        return get_system_health_status()
    if re.search(r"\b(?:is\s+my\s+mac\s+charging|battery\s+level|what\s+is\s+my\s+battery\s+percentage|check\s+battery)\b", cleaned, re.I):
        return system_battery()
    if re.search(r"\b(?:memory\s+status|system\s+memory|how\s+much\s+memory|how\s+much\s+free\s+ram|ram\s+usage)\b", cleaned, re.I):
        return system_ram()
    if re.search(r"\b(?:free\s+storage|storage\s+status|check\s+storage|hard\s+drive\s+space|disk\s+usage)\b", cleaned, re.I):
        return system_disk()
    if re.search(r"\b(?:clear\s+trash|clean\s+trash\s+bin|empty\s+recycling\s+bin)\b", cleaned, re.I):
        return system_empty_trash()
    if re.search(r"\b(?:lock\s+(?:the\s+)?screen|lock\s+my\s+computer|lock\s+workstation)\b", cleaned, re.I):
        return system_lock()

    # Universal App Open / Launch / Fire Up (before speculative Laya)
    m_open_gen = re.search(r'^(?:open|launch|start|run|go\s+to|fire\s+up|bring\s+up)\s+(.+)$', cleaned, re.I)
    if m_open_gen:
        target_name = m_open_gen.group(1).strip(" .!?")
        if not re.search(r"\b(?:search|google|website|tab|window|file|setting|sound|volume|music)\b", target_name, re.I):
            return open_app(target_name)

    # Universal App Close / Quit / Kill / Shut Down / Terminate (before speculative Laya)
    m_close_gen = re.search(r'^(?:close|quit|kill|exit|shut\s+down|terminate)\s+([A-Za-z0-9\s\-]+?)$', cleaned, re.I)
    if m_close_gen:
        target_name = m_close_gen.group(1).strip(" .!?")
        if not re.search(r"\b(?:tab|window)\b", target_name, re.I):
            return close_app(target_name)

    # Fast-Path Direct Intelligence for Conversational & Open-Domain Questions
    is_direct_question = bool(re.search(r"^(?:who|what|why|how|when|where|explain|tell\s+me|joke|can\s+you|could\s+you)\b", cleaned, re.I))
    is_os_intent = bool(re.search(r"\b(?:tab|window|app|volume|sound|mute|battery|ram|disk|trash|note|timer|git|display|dark\s+mode|light\s+mode)\b", cleaned, re.I))
    if is_direct_question and not is_os_intent:
        reply, _, _ = ask_llm(cleaned)
        LAST_ASSISTANT_REPLY = reply
        return reply

    if re.search(r"^(?:hello|hi|hey|good\s+(?:morning|afternoon|evening|night)|greetings|howdy|what(?:'s|\s+up))\b", cleaned, re.I):
        hour = time.localtime().tm_hour
        if 5 <= hour < 12:
            period = "Good morning"
        elif 12 <= hour < 17:
            period = "Good afternoon"
        elif 17 <= hour < 21:
            period = "Good evening"
        else:
            period = "Good evening"
        greetings = [
            f"{period}, sir. Systems are fully operational and ready to assist.",
            f"{period}, sir. How may I be of service today?",
            f"{period}, sir. At your command.",
        ]
        return random.choice(greetings)

    # 13b. World time ("what time is it in Tokyo", "current time in London")
    _TIME_QUERY_RE = re.compile(
        r"\b(?:what(?:'s|\s+is)?\s+(?:the\s+)?(?:current\s+)?time|what\s+time\s+is\s+it|current\s+time)\b"
        r"(?:\s+(?:in|at|for)\s+(?P<city>[a-zA-Z\s]+?))?(?:\s+(?:right\s+now|now|currently))?$",
        re.I
    )
    m_time = _TIME_QUERY_RE.search(cleaned)
    if m_time:
        city_raw = (m_time.group("city") or "").strip().lower()
        # Comprehensive city → IANA timezone map (no third-party package required)
        CITY_TZ = {
            # Americas
            "new york": "America/New_York", "nyc": "America/New_York",
            "los angeles": "America/Los_Angeles", "la": "America/Los_Angeles",
            "chicago": "America/Chicago", "toronto": "America/Toronto",
            "vancouver": "America/Vancouver", "sao paulo": "America/Sao_Paulo",
            "mexico city": "America/Mexico_City", "miami": "America/New_York",
            "denver": "America/Denver", "seattle": "America/Los_Angeles",
            "san francisco": "America/Los_Angeles", "sf": "America/Los_Angeles",
            # Europe
            "london": "Europe/London", "paris": "Europe/Paris",
            "berlin": "Europe/Berlin", "madrid": "Europe/Madrid",
            "rome": "Europe/Rome", "amsterdam": "Europe/Amsterdam",
            "moscow": "Europe/Moscow", "istanbul": "Europe/Istanbul",
            "zurich": "Europe/Zurich", "stockholm": "Europe/Stockholm",
            "oslo": "Europe/Oslo", "helsinki": "Europe/Helsinki",
            "warsaw": "Europe/Warsaw", "vienna": "Europe/Vienna",
            "prague": "Europe/Prague", "budapest": "Europe/Budapest",
            "athens": "Europe/Athens", "lisbon": "Europe/Lisbon",
            # Asia
            "tokyo": "Asia/Tokyo", "japan": "Asia/Tokyo",
            "beijing": "Asia/Shanghai", "shanghai": "Asia/Shanghai",
            "hong kong": "Asia/Hong_Kong", "hk": "Asia/Hong_Kong",
            "singapore": "Asia/Singapore", "seoul": "Asia/Seoul",
            "korea": "Asia/Seoul", "mumbai": "Asia/Kolkata",
            "delhi": "Asia/Kolkata", "bangalore": "Asia/Kolkata",
            "kolkata": "Asia/Kolkata", "india": "Asia/Kolkata",
            "dubai": "Asia/Dubai", "uae": "Asia/Dubai",
            "riyadh": "Asia/Riyadh", "karachi": "Asia/Karachi",
            "dhaka": "Asia/Dhaka", "kathmandu": "Asia/Kathmandu",
            "colombo": "Asia/Colombo", "bangkok": "Asia/Bangkok",
            "jakarta": "Asia/Jakarta", "kuala lumpur": "Asia/Kuala_Lumpur",
            "taipei": "Asia/Taipei", "manila": "Asia/Manila",
            # Oceania
            "sydney": "Australia/Sydney", "melbourne": "Australia/Melbourne",
            "brisbane": "Australia/Brisbane", "perth": "Australia/Perth",
            "auckland": "Pacific/Auckland",
            # Africa
            "cairo": "Africa/Cairo", "nairobi": "Africa/Nairobi",
            "lagos": "Africa/Lagos", "johannesburg": "Africa/Johannesburg",
            "cape town": "Africa/Johannesburg",
        }
        try:
            from zoneinfo import ZoneInfo  # Python 3.9+ stdlib
            import datetime
            if city_raw and city_raw in CITY_TZ:
                tz = ZoneInfo(CITY_TZ[city_raw])
                now = datetime.datetime.now(tz)
                city_display = city_raw.title()
                offset = now.strftime("%z")
                offset_fmt = f"UTC{offset[:3]}:{offset[3:]}" if offset else ""
                abbr = now.strftime("%Z")
                return (
                    f"It is currently {now.strftime('%I:%M %p')} in {city_display}, sir."
                    f" ({abbr}, {offset_fmt})"
                )
            elif city_raw:
                # Unknown city — try as IANA tz directly
                guesses = [c for c in CITY_TZ if city_raw in c or c in city_raw]
                if guesses:
                    tz = ZoneInfo(CITY_TZ[guesses[0]])
                    now = datetime.datetime.now(tz)
                    return f"It is currently {now.strftime('%I:%M %p')} in {guesses[0].title()}, sir."
                return f"I don't have timezone data for {city_raw.title()}, sir. Try a major city name."
            else:
                # Local time
                import datetime
                now = datetime.datetime.now()
                return f"The current local time is {now.strftime('%I:%M %p')}, sir."
        except ImportError:
            import datetime
            now = datetime.datetime.now()
            return f"The current local time is {now.strftime('%I:%M %p')}, sir. (Install Python 3.9+ for world time support)"

    # 14. LAYA TYPED DECISION ROUTING (System 1 Engine)
    ans, laya_ms, cost = laya_decide(cleaned)
    print(f"  laya {laya_ms}ms  ${cost:.6f}")

    target = ans.get("target", ("none", 0.0))[0]
    category = ans.get("category", ("none", 0.0))[0]

    # Target-Driven Dispatch
    if target == "app":
        app_action = ans.get("app_action", ("open", 0.9))[0]
        app_name = ans.get("app", ("none", 0.0))[0]
        if app_name != "none":
            if app_action == "quit":
                return close_app(app_name)
            return open_app(app_name)

    if target == "volume":
        vol_action = ans.get("volume_action", ("none", 0.0))[0]
        scope = ans.get("volume_scope", ("system", 0.9))[0]
        vol_lvl = ans.get("volume_level", ("none", 0.0))[0]

        if vol_action != "none":
            if scope == "spotify":
                if vol_action == "up":
                    return media_volume_adjust(delta=20)
                elif vol_action == "down":
                    return media_volume_adjust(delta=-20)
                elif vol_action == "mute":
                    return media_volume_adjust(mute=True)
                elif vol_action == "unmute":
                    return media_volume_adjust(unmute=True)
                elif vol_lvl != "none":
                    return media_volume_adjust(level=vol_lvl)
            else:
                if vol_action == "up":
                    return adjust_system_volume(20)
                elif vol_action == "down":
                    return adjust_system_volume(-20)
                elif vol_action == "mute":
                    return mute_system_volume(True)
                elif vol_action == "unmute":
                    return mute_system_volume(False)
                elif vol_lvl != "none":
                    return set_system_volume(vol_lvl)

    if target == "media":
        act = ans.get("media_action", ("play", 0.9))[0]
        if act == "pause":
            return media_pause()
        elif act == "next":
            return media_next()
        elif act == "previous":
            return media_previous()
        elif act == "search":
            return play_youtube(cleaned)
        return media_play()

    if target == "display":
        act = ans.get("display_action", ("dark_on", 0.9))[0]
        if act == "dark_off":
            platform_adapter.set_dark_mode(False)
            return "Switching to light mode, sir."
        elif act == "toggle":
            platform_adapter.toggle_dark_mode()
            return "Display appearance toggled, sir."
        else:
            platform_adapter.set_dark_mode(True)
            return "Switching to dark mode, sir."

    if target == "window":
        act = ans.get("window_action", ("maximize", 0.9))[0]
        if act == "tile_left":
            return tile_active_window("left")
        elif act == "tile_right":
            return tile_active_window("right")
        elif act == "center":
            return center_active_window()
        elif act == "hide_others":
            return hide_other_applications()
        return maximize_active_window()

    if target == "browser":
        act = ans.get("browser_action", ("none", 0.0))[0]
        if act == "new_tab":
            return control_browser_tab("new_tab")
        elif act == "close_tab":
            return control_browser_tab("close_tab")
        elif act == "reload":
            return control_browser_tab("reload")
        elif act == "switch_tab":
            return control_browser_tab("next_tab")
        elif act == "open_url" and re.search(r"\b[a-z0-9\-]+\.(?:com|org|io|dev|ai|net|edu|app)\b", t_lower):
            m_u = re.search(r"\b([a-z0-9\-]+\.(?:com|org|io|dev|ai|net|edu|app))\b", t_lower)
            if m_u:
                return open_website(m_u.group(1))
        elif re.search(r"\b(?:search|google|look\s+up|find\s+on\s+(?:the\s+)?web)\b", t_lower):
            m_uni = re.search(r"^(?:open|launch)\s+(?:[a-zA-Z\s]+?)\s+and\s+(?:search(?:\s+for)?|find|look\s+up|google)\s+(.+)$", cleaned, re.I)
            if m_uni:
                squery = m_uni.group(1).strip()
            else:
                squery = re.sub(r"^(?:open\s+[a-zA-Z\s]+?\s+and\s+)?(?:search(?:\s+for|\s+google\s+for|\s+the\s+web\s+for)?|google(?:\s+for)?|look\s+up)\s*", "", cleaned, flags=re.I).strip()
            return search_google_browser(squery or cleaned)

    if target == "system":
        act = ans.get("system_action", ("none", 0.0))[0]
        if act == "lock":
            return system_lock()
        elif act == "sleep":
            return system_sleep()
        elif act == "ram":
            return system_ram()
        elif act == "battery":
            return system_battery()
        elif act == "disk":
            return system_disk()
        elif act == "screenshot":
            return system_screenshot()
        elif act == "trash":
            return system_empty_trash()

    # 15. Chit-Chat & Information Request
    if category == "chit_chat":
        if re.search(r"^(?:hello|hi|hey|good\s+morning|good\s+afternoon|good\s+evening)\b", t_lower):
            greetings = [
                "Good day, sir. How may I be of assistance?",
                "At your service, sir.",
                "All systems operational and ready, sir."
            ]
            return random.choice(greetings)

    # Fallback to LLM for open domain knowledge and conversation
    reply, _, _ = ask_llm(cleaned)
    LAST_ASSISTANT_REPLY = reply
    return reply


# Regex to detect an app/browser launch task so dispatch() can trigger the boot wait
_LAUNCH_TASK_RE = re.compile(
    r"^(?:open|launch|start|run|fire\s+up|bring\s+up)\s+(?P<name>[a-zA-Z0-9\s\-]+?)"  # verb + name
    r"(?:\s+in\s+your\s+browser|\s+sir\.?)?$",
    re.I
)
_BROWSER_NAMES = {
    "google chrome", "chrome", "google", "safari", "brave browser", "brave",
    "arc", "firefox", "microsoft edge", "edge"
}


def _extract_launched_app(task: str) -> str | None:
    """If `task` is an app-launch command, return the canonical app name; else None."""
    m = _LAUNCH_TASK_RE.match(task.strip())
    if not m:
        return None
    raw = m.group("name").strip().lower()
    return APP_ALIASES.get(raw, raw.title())


# --------------------------------------------------------------------------- Master Dispatcher
def dispatch(text: str, notify=None) -> list[str]:
    """Break user query into sub-tasks and execute each sequentially with self-healing protection.

    BUG-05 fix: after any app/browser launch step, wait for the app window to be
    ready before executing the next step, eliminating the cold-boot race condition.
    """
    tasks = split_compound_tasks(text)
    print(f"\n[Task Decomposition] {len(tasks)} sub-task(s) identified for: '{text}'")
    for i, t in enumerate(tasks, 1):
        print(f"  Step {i}: {t}")

    # ------------------------------------------------------------------
    # Parallel execution for independent sub-tasks
    # ------------------------------------------------------------------
    # Strategy:
    #   • If any task is an app/browser *launch*, the immediately following
    #     task may depend on it (BUG-05), so we keep those sequential.
    #   • Otherwise, independent tasks (e.g. "play music" + "open chrome")
    #     run concurrently in the thread pool and finish faster.
    #
    # Independence heuristic: a task is independent if it doesn't start with
    # an action verb that typically follows a launch step (search, go to, etc.).

    _DEPENDENT_PREFIXES_RE = re.compile(
        r"^(?:search|find|go\s+to|look\s+up|play|open\s+(?:a\s+)?(?:tab|new))",
        re.I
    )

    def _is_independent(t: str, prev: str | None) -> bool:
        """Return True if this task can safely run in parallel with others."""
        if prev and _extract_launched_app(prev):
            return False   # Previous step launched an app — must wait
        if _DEPENDENT_PREFIXES_RE.match(t.strip()):
            return False   # This step looks like it follows a launch
        return True

    def _run_task(task: str, idx: int, notify=None) -> tuple[int, str]:
        """Execute one sub-task with self-healing protection. Returns (idx, reply)."""
        if notify:
            notify("Doing it", task)
        reply = execute_single_action(task, notify=notify)
        # Self-healing
        if not reply or any(kw in reply.lower() for kw in ("could not", "failed", "error", "unable")):
            print(f"  [Self-Healing] Intercepting potential failure on task: '{task}'")
            healed = self_heal_action(task, reply or "no reply", execute_single_action)
            if healed and healed != reply:
                reply = healed
        if reply:
            try:
                from audio_engine import prefetch_tts
                prefetch_tts(reply)
            except Exception:
                pass
        return idx, reply

    results = [""] * len(tasks)

    # Group tasks into sequential batches separated by launch dependencies
    i = 0
    while i < len(tasks):
        task = tasks[i]
        prev = tasks[i - 1] if i > 0 else None

        if not _is_independent(task, prev):
            # Sequential: wait for previous app to be ready, then execute
            if prev:
                launched = _extract_launched_app(prev)
                if launched:
                    print(f"  [Boot Wait] Waiting for '{launched}' window before step {i + 1}...")
                    wait_for_app_ready(launched)
            _, reply = _run_task(task, i, notify)
            results[i] = reply
            i += 1
        else:
            # Collect a batch of consecutive independent tasks
            batch = []
            j = i
            while j < len(tasks) and _is_independent(tasks[j], tasks[j - 1] if j > 0 else None):
                batch.append((j, tasks[j]))
                j += 1

            if len(batch) == 1:
                # Single independent task — no point spawning a thread
                _, reply = _run_task(task, i, notify)
                results[i] = reply
            else:
                # Parallel execution of independent batch
                print(f"  [Parallel] Running {len(batch)} independent task(s) concurrently")
                futures = {
                    _ASYNC_POOL.submit(_run_task, t, idx, notify): idx
                    for idx, t in batch
                }
                for future in concurrent.futures.as_completed(futures):
                    try:
                        idx_res, reply = future.result(timeout=30)
                        results[idx_res] = reply
                    except Exception as e:
                        idx_res = futures[future]
                        results[idx_res] = f"Task failed: {e}"
            i = j

    return results
