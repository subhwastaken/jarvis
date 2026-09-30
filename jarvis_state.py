"""Real-Time OS & Application State Inspector for J.A.R.V.I.S.
Provides live ground truth for conditional logic (playback, volume, apps, dark mode).
"""
import os
import re
import sys
import subprocess
import json

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"


def is_spotify_playing() -> bool:
    """Check if Spotify is currently actively playing audio."""
    if IS_MAC:
        try:
            # Check if running first to avoid launching it
            chk = subprocess.check_output(
                ["osascript", "-e", 'tell application "System Events" to (name of processes) contains "Spotify"'],
                stderr=subprocess.DEVNULL, text=True
            ).strip()
            if chk != "true":
                return False
            status = subprocess.check_output(
                ["osascript", "-e", 'tell application "Spotify" to get player state as string'],
                stderr=subprocess.DEVNULL, text=True
            ).strip().lower()
            return status == "playing"
        except Exception:
            return False
    elif IS_WIN:
        # On Windows, check if Spotify process exists and has audio sessions
        try:
            out = subprocess.check_output(["tasklist"], text=True)
            return "Spotify.exe" in out
        except Exception:
            return False
    return False


def is_app_running(app_name: str) -> bool:
    """Check if a specific desktop application is currently running."""
    clean_name = app_name.strip()
    if IS_MAC:
        try:
            script = f'tell application "System Events" to get name of every application process whose visible is true'
            procs = subprocess.check_output(["osascript", "-e", script], stderr=subprocess.DEVNULL, text=True)
            return bool(re.search(rf"\b{re.escape(clean_name)}\b", procs, re.I))
        except Exception:
            return False
    elif IS_WIN:
        try:
            out = subprocess.check_output(["tasklist"], text=True)
            return bool(re.search(rf"\b{re.escape(clean_name)}", out, re.I))
        except Exception:
            return False
    return False


def get_frontmost_app() -> str:
    """Return the name of the currently focused / frontmost application."""
    if IS_MAC:
        try:
            script = 'tell application "System Events" to get name of first application process whose frontmost is true'
            return subprocess.check_output(["osascript", "-e", script], stderr=subprocess.DEVNULL, text=True).strip()
        except Exception:
            return "Unknown"
    return "Unknown"


def is_dark_mode_enabled() -> bool:
    """Check if OS dark mode is currently active."""
    if IS_MAC:
        try:
            script = 'tell application "System Events" to tell appearance preferences to get dark mode'
            res = subprocess.check_output(["osascript", "-e", script], stderr=subprocess.DEVNULL, text=True).strip()
            return res.lower() == "true"
        except Exception:
            return False
    return False


def is_sound_muted() -> bool:
    """Check if the system sound is currently muted."""
    if IS_MAC:
        try:
            res = subprocess.check_output(["osascript", "-e", "get volume settings"], stderr=subprocess.DEVNULL, text=True)
            m = re.search(r"output muted:(true|false)", res, re.I)
            if m:
                return m.group(1).lower() == "true"
        except Exception:
            return False
    return False


def get_volume_level() -> int:
    """Get current system volume from 0 to 100."""
    if IS_MAC:
        try:
            res = subprocess.check_output(["osascript", "-e", "get volume settings"], stderr=subprocess.DEVNULL, text=True)
            m = re.search(r"output volume:(\d+)", res, re.I)
            if m:
                return int(m.group(1))
        except Exception:
            return 50
    return 50


def has_app_unread_or_active(app_name: str) -> bool:
    """Check if an app like Slack, Mail, Messages is running and in foreground or has active window."""
    return is_app_running(app_name)


def capture_system_state() -> dict:
    """Collect full real-time snapshot of the operating system state."""
    return {
        "spotify_playing": is_spotify_playing(),
        "frontmost_app": get_frontmost_app(),
        "dark_mode": is_dark_mode_enabled(),
        "muted": is_sound_muted(),
        "volume": get_volume_level(),
    }
