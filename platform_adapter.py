"""Universal Cross-Platform Operating System Automation Adapter for J.A.R.V.I.S.
Provides a unified abstraction layer for macOS (AppleScript/Cocoa/Mach)
and Windows (Win32/PowerShell/Registry) automations.
"""
import os
import sys
import re
import shutil
import subprocess
import time

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")


# --------------------------------------------------------------------------- Volume Control
def set_volume(level: int) -> str:
    """Sets system output volume (0-100)."""
    lvl = max(0, min(100, int(level)))
    if IS_MAC:
        try:
            subprocess.run(["osascript", "-e", f"set volume output volume {lvl}"], check=True, capture_output=True)
            return f"Volume set to {lvl} percent, sir."
        except Exception as e:
            return f"Failed to set volume on macOS: {e}"
    elif IS_WIN:
        # Windows: Use PowerShell with SndVol or AudioEndpoint API fallback
        ps_cmd = (
            f"$obj = New-Object -ComObject WScript.Shell; "
            f"1..50 | ForEach-Object {{ $obj.SendKeys([char]174) }}; "  # Send volume down 50 times (mute)
            f"$steps = [math]::Round({lvl} / 2); "
            f"1..$steps | ForEach-Object {{ $obj.SendKeys([char]175) }}"  # Send volume up
        )
        try:
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd], capture_output=True)
            return f"Volume set to approximately {lvl} percent, sir."
        except Exception as e:
            return f"Failed to set volume on Windows: {e}"
    return f"Platform {sys.platform} does not support volume adjustment."


def get_volume() -> int:
    """Queries current output volume (0-100)."""
    if IS_MAC:
        try:
            out = subprocess.check_output(
                ["osascript", "-e", "output volume of (get volume settings)"],
                text=True, stderr=subprocess.DEVNULL
            ).strip()
            return int(out)
        except Exception:
            return 50
    elif IS_WIN:
        # Fallback default for Windows when native audio endpoint COM is not wrapped
        return 50
    return 50


def mute_volume(mute: bool = True) -> str:
    """Mutes or unmutes system sound."""
    if IS_MAC:
        val = "true" if mute else "false"
        try:
            subprocess.run(["osascript", "-e", f"set volume output muted {val}"], check=True, capture_output=True)
            return "Volume muted, sir." if mute else "Volume unmuted, sir."
        except Exception as e:
            return f"Failed to toggle mute: {e}"
    elif IS_WIN:
        # VK_VOLUME_MUTE = 0xAD (173)
        try:
            import ctypes
            ctypes.windll.user32.keybd_event(173, 0, 0, 0)
            ctypes.windll.user32.keybd_event(173, 0, 2, 0)
            return "Mute toggled, sir."
        except Exception:
            subprocess.run(["powershell", "-c", "$w = New-Object -ComObject WScript.Shell; $w.SendKeys([char]173)"], capture_output=True)
            return "Mute toggled, sir."
    return "Mute not supported."


# --------------------------------------------------------------------------- Media Playback Control
def media_play() -> str:
    """Universally resumes or starts media playback (Music, Spotify, YouTube)."""
    if IS_MAC:
        for app in ("Music", "Spotify"):
            res = subprocess.run(["osascript", "-e", f'application "{app}" is running'], capture_output=True, text=True)
            if res.stdout.strip().lower() == "true":
                subprocess.run(["osascript", "-e", f'tell application "{app}" to play'], capture_output=True)
                return f"Resuming {app} playback, sir."
        subprocess.run(["open", "-a", "Music"])
        return "Launched Apple Music, sir."
    elif IS_WIN:
        # VK_MEDIA_PLAY_PAUSE = 0xB3 (179)
        try:
            import ctypes
            ctypes.windll.user32.keybd_event(179, 0, 0, 0)
            ctypes.windll.user32.keybd_event(179, 0, 2, 0)
            return "Resuming media playback, sir."
        except Exception:
            subprocess.run(["powershell", "-c", "$w = New-Object -ComObject WScript.Shell; $w.SendKeys([char]179)"], capture_output=True)
            return "Resuming media playback, sir."
    return "Media play not supported on this platform."


def media_pause() -> str:
    """Universally pauses active media playback."""
    if IS_MAC:
        for app in ("Music", "Spotify"):
            res = subprocess.run(["osascript", "-e", f'application "{app}" is running'], capture_output=True, text=True)
            if res.stdout.strip().lower() == "true":
                subprocess.run(["osascript", "-e", f'tell application "{app}" to pause'], capture_output=True)
        return "Playback paused, sir."
    elif IS_WIN:
        try:
            import ctypes
            ctypes.windll.user32.keybd_event(179, 0, 0, 0)
            ctypes.windll.user32.keybd_event(179, 0, 2, 0)
            return "Playback paused, sir."
        except Exception:
            subprocess.run(["powershell", "-c", "$w = New-Object -ComObject WScript.Shell; $w.SendKeys([char]179)"], capture_output=True)
            return "Playback paused, sir."
    return "Media pause not supported."


def media_next() -> str:
    """Skips to the next track."""
    if IS_MAC:
        for app in ("Music", "Spotify"):
            res = subprocess.run(["osascript", "-e", f'application "{app}" is running'], capture_output=True, text=True)
            if res.stdout.strip().lower() == "true":
                subprocess.run(["osascript", "-e", f'tell application "{app}" to next track'], capture_output=True)
                return f"Skipping to next track on {app}, sir."
        return "Next track, sir."
    elif IS_WIN:
        # VK_MEDIA_NEXT_TRACK = 0xB0 (176)
        try:
            import ctypes
            ctypes.windll.user32.keybd_event(176, 0, 0, 0)
            ctypes.windll.user32.keybd_event(176, 0, 2, 0)
            return "Skipping to next track, sir."
        except Exception:
            subprocess.run(["powershell", "-c", "$w = New-Object -ComObject WScript.Shell; $w.SendKeys([char]176)"], capture_output=True)
            return "Skipping to next track, sir."
    return "Media skip not supported."


def media_previous() -> str:
    """Skips to previous track."""
    if IS_MAC:
        for app in ("Music", "Spotify"):
            res = subprocess.run(["osascript", "-e", f'application "{app}" is running'], capture_output=True, text=True)
            if res.stdout.strip().lower() == "true":
                subprocess.run(["osascript", "-e", f'tell application "{app}" to previous track'], capture_output=True)
                return f"Previous track on {app}, sir."
        return "Previous track, sir."
    elif IS_WIN:
        # VK_MEDIA_PREV_TRACK = 0xB1 (177)
        try:
            import ctypes
            ctypes.windll.user32.keybd_event(177, 0, 0, 0)
            ctypes.windll.user32.keybd_event(177, 0, 2, 0)
            return "Previous track, sir."
        except Exception:
            subprocess.run(["powershell", "-c", "$w = New-Object -ComObject WScript.Shell; $w.SendKeys([char]177)"], capture_output=True)
            return "Previous track, sir."
    return "Media previous not supported."


# --------------------------------------------------------------------------- Application Control
def open_app(name: str) -> str:
    """Dynamically launches an application or navigates to a web destination."""
    clean = str(name).strip()
    if not clean:
        return "Which application should I open, sir?"

    # Check for direct URL
    if clean.startswith("http://") or clean.startswith("https://"):
        if IS_MAC:
            subprocess.run(["open", clean])
        elif IS_WIN:
            os.startfile(clean) if hasattr(os, "startfile") else subprocess.run(["start", clean], shell=True)
        return f"Opening link in your browser, sir."

    if IS_MAC:
        try_res = subprocess.run(["open", "-a", clean], capture_output=True, text=True)
        if try_res.returncode == 0:
            return f"Opening {clean.title()}, sir."
        # Try generic open
        subprocess.run(["open", clean])
        return f"Opening {clean.title()}, sir."
    elif IS_WIN:
        try:
            subprocess.run(f'start "" "{clean}"', shell=True)
            return f"Opening {clean.title()}, sir."
        except Exception:
            subprocess.run(["powershell", "-c", f"Start-Process '{clean}'"], capture_output=True)
            return f"Opening {clean.title()}, sir."

    return f"Cannot open {clean} on this system."


def close_app(name: str) -> str:
    """Quits or terminates a running application."""
    clean = str(name).strip()
    if not clean:
        return "Which application should I close, sir?"

    if IS_MAC:
        subprocess.run(["osascript", "-e", f'tell application "{clean}" to quit'], capture_output=True)
        subprocess.run(["pkill", "-f", clean], capture_output=True)
        return f"Closing {clean.title()}, sir."
    elif IS_WIN:
        proc_name = clean if clean.endswith(".exe") else f"{clean}.exe"
        subprocess.run(["taskkill", "/f", "/im", proc_name], capture_output=True)
        return f"Closed {clean.title()}, sir."

    return f"Cannot close {clean}."


def set_dark_mode(enabled: bool) -> str:
    """Explicitly enable or disable dark mode."""
    return toggle_dark_mode("on" if enabled else "off")


def toggle_dark_mode(mode: str | None = None) -> str:
    """Sets or toggles Dark Mode on macOS and Windows."""
    if IS_MAC:
        if mode == "on":
            script = 'tell application "System Events" to tell appearance preferences to set dark mode to true'
        elif mode == "off":
            script = 'tell application "System Events" to tell appearance preferences to set dark mode to false'
        else:
            script = 'tell application "System Events" to tell appearance preferences to set dark mode to not dark mode'
        try:
            subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
            return "Appearance updated, sir."
        except Exception as e:
            return f"Failed to toggle dark mode on Mac: {e}"

    elif IS_WIN:
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
                current_val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                if mode == "on":
                    new_val = 0  # 0 is dark
                elif mode == "off":
                    new_val = 1  # 1 is light
                else:
                    new_val = 0 if current_val == 1 else 1

                winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, new_val)
                winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, new_val)
                return "Dark mode enabled, sir." if new_val == 0 else "Light mode enabled, sir."
        except Exception as e:
            return f"Failed to toggle Windows theme: {e}"

    return "Dark mode toggle not supported on this platform."


# --------------------------------------------------------------------------- System Power & Security
def lock_screen() -> str:
    """Locks the workstation."""
    if IS_MAC:
        try:
            subprocess.run(["osascript", "-e", 'tell application "System Events" to keystroke "q" using {control down, command down}'], capture_output=True)
            return "Workstation locked, sir."
        except Exception:
            subprocess.run(["pmset", "displaysleepnow"])
            return "Screen locked, sir."
    elif IS_WIN:
        try:
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return "Windows workstation locked, sir."
        except Exception:
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
            return "Workstation locked, sir."
    return "Screen lock not supported."


def sleep_system() -> str:
    """Puts the computer to sleep."""
    if IS_MAC:
        subprocess.run(["pmset", "sleepnow"], capture_output=True)
        return "Entering system sleep, sir."
    elif IS_WIN:
        subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], capture_output=True)
        return "Putting computer to sleep, sir."
    return "Sleep not supported."


# --------------------------------------------------------------------------- System Telemetry
def get_ram_status() -> str:
    """Returns memory usage in human-readable prose."""
    if IS_MAC:
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
            if active_pages + free_pages > 0:
                used_gb = round((active_pages * 4096) / (1024 ** 3), 1)
                free_gb = round((free_pages * 4096) / (1024 ** 3), 1)
                return f"You are currently using {used_gb} gigabytes of RAM, with {free_gb} gigabytes free."
        except Exception:
            pass

    elif IS_WIN:
        try:
            out = subprocess.check_output(
                ["powershell", "-c", "Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize, FreePhysicalMemory | ConvertTo-Json"],
                text=True, stderr=subprocess.DEVNULL
            )
            import json
            data = json.loads(out)
            total_kb = data.get("TotalVisibleMemorySize", 0)
            free_kb = data.get("FreePhysicalMemory", 0)
            used_gb = round((total_kb - free_kb) / (1024 ** 2), 1)
            free_gb = round(free_kb / (1024 ** 2), 1)
            return f"You are currently using {used_gb} gigabytes of RAM, with {free_gb} gigabytes free."
        except Exception:
            pass

    return "Could not determine system RAM usage."


def get_battery_status() -> str:
    """Returns battery charge percentage and charging state."""
    if IS_MAC:
        try:
            out = subprocess.check_output(["pmset", "-g", "batt"], text=True)
            m = re.search(r"(\d+%);\s*([^;]+);", out)
            if m:
                return f"Your battery is at {m.group(1)}, currently {m.group(2).strip()}."
            return "Your Mac is currently running on power adapter."
        except Exception as e:
            return f"Failed to check battery: {e}"

    elif IS_WIN:
        try:
            out = subprocess.check_output(
                ["powershell", "-c", "Get-CimInstance Win32_Battery | Select-Object EstimatedChargeRemaining, BatteryStatus | ConvertTo-Json"],
                text=True, stderr=subprocess.DEVNULL
            )
            import json
            data = json.loads(out)
            pct = data.get("EstimatedChargeRemaining", 100)
            status_code = data.get("BatteryStatus", 2)
            charging_desc = "charging" if status_code == 2 else "discharging"
            return f"Your battery is at {pct} percent, currently {charging_desc}."
        except Exception:
            return "Your PC is currently running on AC power."

    return "Battery status is unavailable."


def get_disk_status() -> str:
    """Returns free and total disk space using standard library shutil."""
    try:
        root_path = "/" if IS_MAC else "C:\\"
        total, used, free = shutil.disk_usage(root_path)
        total_gb = round(total / (1024 ** 3), 1)
        free_gb = round(free / (1024 ** 3), 1)
        return f"You have {free_gb} gigabytes free disk space out of {total_gb} gigabytes total."
    except Exception as e:
        return f"Failed to determine disk space: {e}"


def empty_trash() -> str:
    """Empties the Trash or Recycle Bin."""
    if IS_MAC:
        try:
            subprocess.run(["osascript", "-e", 'tell application "Finder" to empty trash'], check=True, capture_output=True)
            return "Trash emptied, sir."
        except Exception as e:
            return f"Failed to empty trash: {e}"
    elif IS_WIN:
        try:
            subprocess.run(["powershell", "-c", "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"], capture_output=True)
            return "Recycle bin emptied, sir."
        except Exception as e:
            return f"Failed to empty recycle bin: {e}"
    return "Empty trash not supported."
