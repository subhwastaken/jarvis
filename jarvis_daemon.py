"""Proactive Background Health and Battery Alerts Daemon for J.A.R.V.I.S."""
import subprocess
import threading
import time
import re

ALERT_COOLDOWN = 900  # 15 minutes between repeated alerts
_LAST_ALERTS = {}
_RUNNING = False
_MONITOR_THREAD = None


def check_battery():
    try:
        out = subprocess.check_output(["pmset", "-g", "batt"], stderr=subprocess.DEVNULL, text=True)
        m = re.search(r"(\d+)%;\s*([^;]+);", out)
        if m:
            pct = int(m.group(1))
            status = m.group(2).strip().lower()
            is_charging = "charging" in status or "ac attached" in status
            return pct, is_charging
        if "ac power" in out.lower():
            return None, True
    except Exception:
        pass
    return None, None


def check_memory_pressure():
    """Returns kernel memory pressure percentage (0-100%). Uses macOS Mach kernel memory_pressure."""
    try:
        out = subprocess.check_output(["memory_pressure"], stderr=subprocess.DEVNULL, text=True)
        m = re.search(r"System-wide memory free percentage:\s*(\d+)%", out)
        if m:
            free_pct = int(m.group(1))
            return 100 - free_pct
    except Exception:
        pass

    # Fallback to vm_stat if memory_pressure tool is unavailable
    try:
        out = subprocess.check_output(["vm_stat"], stderr=subprocess.DEVNULL, text=True)
        pages = {}
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) == 2:
                num = re.sub(r"[^\d]", "", parts[1])
                if num:
                    pages[parts[0].strip()] = int(num)
        free = pages.get("Pages free", 0) + pages.get("Pages speculative", 0)
        active = pages.get("Pages active", 0) + pages.get("Pages wired down", 0)
        total = free + active
        if total > 0:
            return int((active / total) * 100)
    except Exception:
        pass
    return None


def get_system_health_status():
    batt_pct, is_charging = check_battery()
    mem_pressure = check_memory_pressure()
    
    parts = []
    if mem_pressure is not None:
        parts.append(f"Memory pressure is at {mem_pressure} percent")
    if batt_pct is not None:
        chg_text = "charging" if is_charging else "on battery"
        parts.append(f"battery is at {batt_pct} percent ({chg_text})")
    elif is_charging:
        parts.append("running securely on AC power")
        
    status = ", and ".join(parts) if parts else "all systems nominal"
    return f"Diagnostics complete, sir. {status}. All core systems are functioning normally."


def poll_health_alerts():
    alerts = []
    now = time.time()
    
    # Check battery
    pct, is_charging = check_battery()
    if pct is not None and not is_charging and pct <= 20:
        last_batt = _LAST_ALERTS.get("battery", 0)
        if now - last_batt > ALERT_COOLDOWN:
            _LAST_ALERTS["battery"] = now
            alerts.append(f"Pardon the interruption, sir, but your battery is critically low at {pct} percent. Please connect your charger.")

    # Check RAM pressure
    ram_pressure = check_memory_pressure()
    if ram_pressure is not None and ram_pressure >= 90:
        last_ram = _LAST_ALERTS.get("ram", 0)
        if now - last_ram > ALERT_COOLDOWN:
            _LAST_ALERTS["ram"] = now
            alerts.append(f"Sir, system memory pressure is critically high at {ram_pressure} percent.")

    return alerts


def start_proactive_monitor(speak_callback=None, can_speak_predicate=None, interval_secs=60):
    global _RUNNING, _MONITOR_THREAD
    if _RUNNING:
        return
    _RUNNING = True

    def _loop():
        # Initial sleep so assistant starts up cleanly
        time.sleep(15)
        while _RUNNING:
            try:
                alerts = poll_health_alerts()
                for alert in alerts:
                    if speak_callback:
                        # Wait until microphone and assistant are not busy speaking or recording (max 30s)
                        wait_start = time.time()
                        while _RUNNING and can_speak_predicate and not can_speak_predicate():
                            if time.time() - wait_start > 30:
                                break
                            time.sleep(1)
                        if _RUNNING:
                            speak_callback(alert)
            except Exception as e:
                print(f"  [Daemon] Health monitor check: {e}")
            time.sleep(interval_secs)

    _MONITOR_THREAD = threading.Thread(target=_loop, daemon=True)
    _MONITOR_THREAD.start()
    print("  [Daemon] J.A.R.V.I.S. proactive health daemon active.")


def stop_proactive_monitor():
    global _RUNNING
    _RUNNING = False
