"""Universal Cross-Platform Operating System Automation Adapter for J.A.R.V.I.S.
Provides a unified abstraction layer for macOS (AppleScript/Cocoa/Mach)
and Windows (Win32/PowerShell/COM/ctypes) automations.

Windows implementation covers:
  - Volume via pycaw (preferred) with PowerShell fallback
  - Media keys via ctypes SendInput (VK codes)
  - Application management via subprocess / taskkill
  - Dark mode via winreg
  - Battery / RAM / Disk via CIM / shutil
  - Lock / Sleep via ctypes / rundll32
  - Screenshot via mss (preferred) with PowerShell fallback
"""
import os
import sys
import re
import shutil
import subprocess
import time

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")


# ---------------------------------------------------------------------------
# Windows helpers
# ---------------------------------------------------------------------------

def _win_send_key(vk: int):
    """Send a virtual key press and release via ctypes SendInput."""
    try:
        import ctypes
        from ctypes import wintypes
        INPUT_KEYBOARD = 1
        KEYEVENTF_KEYUP = 0x0002
        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]
        class INPUT(ctypes.Structure):
            class _INPUT(ctypes.Union):
                _fields_ = [("ki", KEYBDINPUT)]
            _anonymous_ = ("_input",)
            _fields_ = [("type", wintypes.DWORD), ("_input", _INPUT)]
        key_down = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=vk))
        key_up   = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=vk, dwFlags=KEYEVENTF_KEYUP))
        ctypes.windll.user32.SendInput(1, ctypes.byref(key_down), ctypes.sizeof(INPUT))
        time.sleep(0.05)
        ctypes.windll.user32.SendInput(1, ctypes.byref(key_up),   ctypes.sizeof(INPUT))
        return True
    except Exception:
        return False


def _win_ps(cmd: str) -> str:
    """Run a PowerShell one-liner and return stripped stdout."""
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            stderr=subprocess.DEVNULL, text=True, timeout=8
        )
        return out.strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Volume Control
# ---------------------------------------------------------------------------

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
        # 1. Try pycaw (most reliable)
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL
            from ctypes import cast, POINTER
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            scalar = lvl / 100.0
            volume.SetMasterVolumeLevelScalar(scalar, None)
            return f"Volume set to {lvl} percent, sir."
        except Exception:
            pass
        # 2. PowerShell nircmd fallback
        _win_ps(
            f"$obj=[System.Runtime.Interopservices.Marshal]::GetActiveObject('WScript.Shell');"
            f"1..50 | %{{$null = $obj.SendKeys([char]174)}};"
            f"1..[math]::Round({lvl}/2) | %{{$null = $obj.SendKeys([char]175)}}"
        )
        return f"Volume set to approximately {lvl} percent, sir."
    return f"Volume adjustment not supported on {sys.platform}."


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
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL
            from ctypes import cast, POINTER
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            return int(volume.GetMasterVolumeLevelScalar() * 100)
        except Exception:
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
        # VK_VOLUME_MUTE = 0xAD
        try:
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            from comtypes import CLSCTX_ALL
            from ctypes import cast, POINTER
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMute(1 if mute else 0, None)
            return "Muted, sir." if mute else "Unmuted, sir."
        except Exception:
            _win_send_key(0xAD)
            return "Mute toggled, sir."
    return "Mute not supported."


# ---------------------------------------------------------------------------
# Media Playback Control
# ---------------------------------------------------------------------------

def media_play() -> str:
    """Resumes or starts media playback."""
    if IS_MAC:
        for app in ("Spotify", "Music"):
            res = subprocess.run(["osascript", "-e", f'application "{app}" is running'], capture_output=True, text=True)
            if res.stdout.strip().lower() == "true":
                subprocess.run(["osascript", "-e", f'tell application "{app}" to play'], capture_output=True)
                return f"Resuming {app} playback, sir."
        subprocess.run(["open", "-a", "Music"])
        return "Launched Apple Music, sir."
    elif IS_WIN:
        # VK_MEDIA_PLAY_PAUSE = 0xB3
        if _win_send_key(0xB3):
            return "Resuming media playback, sir."
        _win_ps("$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys([char]179)")
        return "Resuming media playback, sir."
    return "Media play not supported on this platform."


def media_pause() -> str:
    """Pauses active media playback."""
    if IS_MAC:
        for app in ("Spotify", "Music"):
            res = subprocess.run(["osascript", "-e", f'application "{app}" is running'], capture_output=True, text=True)
            if res.stdout.strip().lower() == "true":
                subprocess.run(["osascript", "-e", f'tell application "{app}" to pause'], capture_output=True)
        return "Playback paused, sir."
    elif IS_WIN:
        _win_send_key(0xB3)
        return "Playback paused, sir."
    return "Media pause not supported."


def media_next() -> str:
    """Skips to the next track."""
    if IS_MAC:
        for app in ("Spotify", "Music"):
            res = subprocess.run(["osascript", "-e", f'application "{app}" is running'], capture_output=True, text=True)
            if res.stdout.strip().lower() == "true":
                subprocess.run(["osascript", "-e", f'tell application "{app}" to next track'], capture_output=True)
                return f"Skipping to next track on {app}, sir."
        return "Next track, sir."
    elif IS_WIN:
        # VK_MEDIA_NEXT_TRACK = 0xB0
        _win_send_key(0xB0)
        return "Skipping to next track, sir."
    return "Media skip not supported."


def media_previous() -> str:
    """Skips to previous track."""
    if IS_MAC:
        for app in ("Spotify", "Music"):
            res = subprocess.run(["osascript", "-e", f'application "{app}" is running'], capture_output=True, text=True)
            if res.stdout.strip().lower() == "true":
                subprocess.run(["osascript", "-e", f'tell application "{app}" to previous track'], capture_output=True)
                return f"Previous track on {app}, sir."
        return "Previous track, sir."
    elif IS_WIN:
        # VK_MEDIA_PREV_TRACK = 0xB1
        _win_send_key(0xB1)
        return "Previous track, sir."
    return "Media previous not supported."


# ---------------------------------------------------------------------------
# Application Control
# ---------------------------------------------------------------------------

def open_app(name: str) -> str:
    """Dynamically launches an application or web destination."""
    clean = str(name).strip()
    if not clean:
        return "Which application should I open, sir?"
    if clean.startswith("http://") or clean.startswith("https://"):
        if IS_MAC:
            subprocess.run(["open", clean])
        elif IS_WIN:
            os.startfile(clean) if hasattr(os, "startfile") else subprocess.run(["start", clean], shell=True)
        return "Opening link in your browser, sir."
    if IS_MAC:
        res = subprocess.run(["open", "-a", clean], capture_output=True, text=True)
        if res.returncode == 0:
            return f"Opening {clean.title()}, sir."
        # If open -a failed, check if application bundle exists before blindly running open
        app_path = None
        try:
            mdfind_res = subprocess.run(
                ["mdfind", f'kMDItemKind == "Application" && (kMDItemDisplayName == "*{clean}*"c || kMDItemFSName == "*{clean}*.app"c)'],
                capture_output=True, text=True, timeout=1.5
            )
            paths = [p for p in mdfind_res.stdout.strip().split("\n") if p.endswith(".app")]
            if paths:
                app_path = paths[0]
        except Exception:
            pass
        if app_path:
            subprocess.run(["open", app_path])
            return f"Opening {clean.title()}, sir."
        return f"I couldn't find {clean.title()} on your Mac, sir. Would you like me to search for it on Google?"
    elif IS_WIN:
        res = _win_ps(f"Start-Process '{clean}'")
        if res:
            return f"Opening {clean.title()}, sir."
        try:
            subprocess.run(f'start "" "{clean}"', shell=True, check=True)
            return f"Opening {clean.title()}, sir."
        except Exception:
            pass
        return f"I couldn't find {clean.title()} on your computer, sir. Would you like me to search for it on Google?"
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
        proc_name = clean if clean.lower().endswith(".exe") else f"{clean}.exe"
        # Graceful: Stop-Process -Name
        _win_ps(f"Stop-Process -Name '{clean}' -Force -ErrorAction SilentlyContinue")
        # Hard: taskkill
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
                    new_val = 0
                elif mode == "off":
                    new_val = 1
                else:
                    new_val = 0 if current_val == 1 else 1
                winreg.SetValueEx(key, "AppsUseLightTheme",    0, winreg.REG_DWORD, new_val)
                winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, new_val)
                # Notify shell of theme change
                _win_ps("[System.Runtime.InteropServices.Marshal]::GetActiveObject('WScript.Shell')")
                return "Dark mode enabled, sir." if new_val == 0 else "Light mode enabled, sir."
        except Exception as e:
            return f"Failed to toggle Windows theme: {e}"
    return "Dark mode toggle not supported on this platform."


# ---------------------------------------------------------------------------
# System Power & Security
# ---------------------------------------------------------------------------

def lock_screen() -> str:
    """Locks the workstation."""
    if IS_MAC:
        try:
            subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to keystroke "q" using {control down, command down}'],
                capture_output=True
            )
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


def take_screenshot(path: str | None = None) -> str:
    """Takes a screenshot and saves to Desktop."""
    ts = time.strftime("%Y-%m-%d-%H%M%S")
    desktop = os.path.expanduser("~/Desktop")
    if not path:
        ext = "png"
        path = os.path.join(desktop, f"Screenshot-{ts}.{ext}")
    if IS_MAC:
        try:
            subprocess.run(["screencapture", "-x", path], check=True)
            return f"Screenshot saved to Desktop, sir."
        except Exception as e:
            return f"Screenshot failed: {e}"
    elif IS_WIN:
        # 1. Try mss (fast, no deps beyond pip)
        try:
            import mss
            import mss.tools
            with mss.mss() as sct:
                monitor = sct.monitors[0]
                img = sct.grab(monitor)
                png_path = path.replace(".jpg", ".png")
                mss.tools.to_png(img.rgb, img.size, output=png_path)
            return "Screenshot saved to Desktop, sir."
        except Exception:
            pass
        # 2. PowerShell fallback
        ps = (
            f"Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
            f"$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
            f"$bmp=New-Object System.Drawing.Bitmap($b.Width,$b.Height);"
            f"$g=[System.Drawing.Graphics]::FromImage($bmp);"
            f"$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);"
            f"$bmp.Save('{path}')"
        )
        _win_ps(ps)
        return "Screenshot saved to Desktop, sir."
    return "Screenshot not supported."


# ---------------------------------------------------------------------------
# System Telemetry
# ---------------------------------------------------------------------------

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
            free_pages   = pages.get("Pages free", 0) + pages.get("Pages speculative", 0)
            active_pages = pages.get("Pages active", 0) + pages.get("Pages wired down", 0)
            if active_pages + free_pages > 0:
                used_gb = round((active_pages * 4096) / (1024 ** 3), 1)
                free_gb = round((free_pages * 4096) / (1024 ** 3), 1)
                return f"You are currently using {used_gb} gigabytes of RAM, with {free_gb} gigabytes free."
        except Exception:
            pass
    elif IS_WIN:
        try:
            import json as _json
            out = _win_ps(
                "Get-CimInstance Win32_OperatingSystem | "
                "Select-Object TotalVisibleMemorySize,FreePhysicalMemory | "
                "ConvertTo-Json"
            )
            data = _json.loads(out)
            total_kb = data.get("TotalVisibleMemorySize", 0)
            free_kb  = data.get("FreePhysicalMemory", 0)
            used_gb  = round((total_kb - free_kb) / (1024 ** 2), 1)
            free_gb  = round(free_kb / (1024 ** 2), 1)
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
            import json as _json
            out = _win_ps(
                "Get-CimInstance Win32_Battery | "
                "Select-Object EstimatedChargeRemaining,BatteryStatus | "
                "ConvertTo-Json"
            )
            if not out:
                return "Your PC is currently running on AC power, sir."
            data = _json.loads(out)
            pct  = data.get("EstimatedChargeRemaining", 100)
            code = data.get("BatteryStatus", 2)
            status_map = {1: "discharging", 2: "AC power / charging", 3: "fully charged",
                          4: "low", 5: "critical", 6: "charging", 7: "charging + high"}
            charging_desc = status_map.get(code, "unknown status")
            return f"Your battery is at {pct} percent, currently {charging_desc}, sir."
        except Exception:
            return "Your PC is currently running on AC power, sir."
    return "Battery status is unavailable."


def get_disk_status() -> str:
    """Returns free and total disk space using standard library shutil."""
    try:
        root_path = "/" if IS_MAC else "C:\\"
        total, used, free = shutil.disk_usage(root_path)
        total_gb = round(total / (1024 ** 3), 1)
        free_gb  = round(free  / (1024 ** 3), 1)
        return f"You have {free_gb} gigabytes free disk space out of {total_gb} gigabytes total, sir."
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
            _win_ps("Clear-RecycleBin -Force -ErrorAction SilentlyContinue")
            return "Recycle bin emptied, sir."
        except Exception as e:
            return f"Failed to empty recycle bin: {e}"
    return "Empty trash not supported."


# ---------------------------------------------------------------------------
# Brightness Control (bonus — previously missing)
# ---------------------------------------------------------------------------

def set_brightness(level: int) -> str:
    """Set display brightness (0-100). macOS only via osascript; Windows via PowerShell WMI."""
    lvl = max(0, min(100, int(level)))
    if IS_MAC:
        try:
            subprocess.run(["osascript", "-e", f"tell application \"System Events\" to set brightness of every desktop to {lvl / 100}"], capture_output=True)
            return f"Brightness set to {lvl} percent, sir."
        except Exception:
            pass
        # Fallback: brightness CLI
        try:
            subprocess.run(["brightness", str(lvl / 100)], capture_output=True)
            return f"Brightness set to {lvl} percent, sir."
        except Exception:
            return "Could not adjust brightness — ensure the brightness CLI is installed, sir."
    elif IS_WIN:
        try:
            _win_ps(
                f"(Get-WmiObject -Namespace root/wmi -Class WmiMonitorBrightnessMethods)"
                f".WmiSetBrightness(1,{lvl})"
            )
            return f"Brightness set to {lvl} percent, sir."
        except Exception:
            return "Could not adjust brightness on Windows, sir."
    return "Brightness control not supported."
