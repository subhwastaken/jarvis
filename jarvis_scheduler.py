"""Persistent Background Task Scheduler for J.A.R.V.I.S.
Handles timers, reminders, and recurring tasks that survive across assistant
sessions via a JSON-backed persistent store.

Architecture:
  - A single daemon thread wakes every second to check due tasks
  - Tasks are persisted to disk so 'remind me in 10 minutes' survives a
    Python restart (as long as the scheduler is re-loaded next session)
  - Thread-safe; can be called from any thread

Supported task types:
  timer       – fires once after N seconds, speaks a message
  reminder    – same as timer but user-specified text
  recurring   – fires every N seconds until cancelled
"""

import json
import os
import re
import threading
import time
import uuid
from typing import Callable, Optional

SCHEDULER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_tasks.json")

# Callback invoked when a task fires: (task_id, message) -> None
_fire_callback: Optional[Callable[[str, str], None]] = None


def set_fire_callback(fn: Callable[[str, str], None]):
    """Register the function called when a task fires."""
    global _fire_callback
    _fire_callback = fn


# ---------------------------------------------------------------------------
# Time-phrase parser
# ---------------------------------------------------------------------------

_TIME_PATTERNS = [
    (re.compile(r"(\d+)\s*h(?:our)?s?", re.I), 3600),
    (re.compile(r"(\d+)\s*m(?:in(?:ute)?s?)?", re.I), 60),
    (re.compile(r"(\d+)\s*s(?:ec(?:ond)?s?)?", re.I), 1),
]


def parse_duration_seconds(text: str) -> int:
    """Convert a natural-language duration string to seconds."""
    total = 0
    for pattern, multiplier in _TIME_PATTERNS:
        for m in pattern.finditer(text):
            total += int(m.group(1)) * multiplier
    return total


def human_duration(seconds: int) -> str:
    """Format seconds as human-readable string."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    parts = []
    if h:
        parts.append(f"{h} hour{'s' if h != 1 else ''}")
    if m:
        parts.append(f"{m} minute{'s' if m != 1 else ''}")
    if s and not h:
        parts.append(f"{s} second{'s' if s != 1 else ''}")
    return " and ".join(parts) if parts else f"{seconds} seconds"


# ---------------------------------------------------------------------------
# Persistent store helpers
# ---------------------------------------------------------------------------

_STORE_LOCK = threading.Lock()


def _load_tasks() -> dict:
    with _STORE_LOCK:
        if not os.path.exists(SCHEDULER_FILE):
            return {}
        try:
            with open(SCHEDULER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}


def _save_tasks(tasks: dict):
    with _STORE_LOCK:
        try:
            with open(SCHEDULER_FILE, "w", encoding="utf-8") as f:
                json.dump(tasks, f, indent=2)
        except Exception as e:
            print(f"  [Scheduler] Save error: {e}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def schedule_timer(message: str, delay_seconds: int, task_type: str = "timer",
                   interval_seconds: int = 0) -> str:
    """Create a new scheduled task. Returns task_id."""
    task_id = str(uuid.uuid4())[:8]
    tasks = _load_tasks()
    tasks[task_id] = {
        "id": task_id,
        "type": task_type,
        "message": message,
        "fire_at": time.time() + delay_seconds,
        "interval": interval_seconds,
        "created_at": time.time(),
        "fired": False,
    }
    _save_tasks(tasks)
    print(f"  [Scheduler] Task '{task_id}' ({task_type}) in {delay_seconds}s: {message!r}")
    return task_id


def cancel_task(task_id: str) -> bool:
    tasks = _load_tasks()
    if task_id in tasks:
        del tasks[task_id]
        _save_tasks(tasks)
        return True
    return False


def cancel_all_tasks() -> int:
    tasks = _load_tasks()
    count = len(tasks)
    _save_tasks({})
    return count


def list_tasks() -> list:
    tasks = _load_tasks()
    pending = [t for t in tasks.values() if not t.get("fired")]
    return sorted(pending, key=lambda t: t["fire_at"])


def get_task_status() -> str:
    pending = list_tasks()
    if not pending:
        return "No reminders or timers are currently scheduled, sir."
    lines = []
    now = time.time()
    for t in pending:
        remaining = max(0, int(t["fire_at"] - now))
        lines.append(f"  - {t['type'].title()} in {human_duration(remaining)}: \"{t['message']}\"")
    return "Scheduled tasks:\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# Natural language scheduling interface
# ---------------------------------------------------------------------------

def parse_schedule_command(text: str) -> tuple:
    """Parse a user scheduling request. Returns (message, delay_seconds, task_type)."""
    t_lower = text.strip()

    m_remind = re.search(
        r"\b(?:remind\s+me|set\s+(?:a\s+)?reminder)\b(.+?)(?:\bto\b|\bthat\b)\s+(.+)",
        t_lower, re.I
    )
    m_timer = re.search(
        r"\b(?:set\s+(?:a\s+)?timer|timer|countdown|alarm)\b(.+)",
        t_lower, re.I
    )

    if m_remind:
        time_part = m_remind.group(1)
        message_part = m_remind.group(2).strip().rstrip(".,!?")
        delay = parse_duration_seconds(time_part) or parse_duration_seconds(t_lower)
        message = message_part.capitalize() if message_part else "Reminder, sir."
        return message, delay, "reminder"

    elif m_timer:
        time_part = m_timer.group(1)
        delay = parse_duration_seconds(time_part) or parse_duration_seconds(t_lower)
        return "Your timer has gone off, sir.", delay, "timer"

    delay = parse_duration_seconds(t_lower)
    if delay and re.search(r"\b(?:remind|timer|alarm|countdown)\b", t_lower, re.I):
        return "Your reminder has fired, sir.", delay, "timer"

    return "", 0, "timer"


def handle_timer_command(text: str) -> str:
    """High-level handler for all timer/reminder intents."""
    t_lower = text.lower().strip()

    if re.search(r"\b(?:check|status|how much|list|show|what)\b.*\b(?:timer|reminder|alarm)\b", t_lower):
        return get_task_status()
    if re.search(r"\b(?:list|show)\b.*\b(?:timer|reminder|task)\b", t_lower):
        return get_task_status()
    if re.search(r"\b(?:cancel|stop|clear|delete)\b.*\b(?:all|every)\b.*\b(?:timer|reminder|task|alarm)\b", t_lower):
        count = cancel_all_tasks()
        return f"All {count} scheduled task(s) have been cancelled, sir."
    if re.search(r"\b(?:cancel|stop|delete)\b.*\b(?:timer|reminder|alarm)\b", t_lower):
        pending = list_tasks()
        if not pending:
            return "No active timers or reminders to cancel, sir."
        cancel_task(pending[0]["id"])
        return "Cancelled your next scheduled task, sir."

    message, delay, task_type = parse_schedule_command(text)
    if not delay:
        return (
            "I could not determine a duration, sir. "
            "Try: 'remind me in 10 minutes to take a break'."
        )
    if not message:
        message = "Your reminder has fired, sir." if task_type == "reminder" else "Your timer has gone off, sir."

    task_id = schedule_timer(message, delay, task_type)
    return (
        f"Done, sir. I will remind you in {human_duration(delay)}: \"{message}\" "
        f"(Task {task_id})"
    )


# ---------------------------------------------------------------------------
# Background daemon thread
# ---------------------------------------------------------------------------

_DAEMON_THREAD = None
_DAEMON_RUNNING = threading.Event()


def _daemon_loop():
    print("  [Scheduler] Daemon started.")
    while _DAEMON_RUNNING.is_set():
        now = time.time()
        tasks = _load_tasks()
        changed = False

        for task_id, task in list(tasks.items()):
            if task.get("fired"):
                continue
            if now >= task["fire_at"]:
                message = task.get("message", "Reminder, sir.")
                print(f"  [Scheduler] Task '{task_id}' fired: {message!r}")
                if _fire_callback:
                    try:
                        _fire_callback(task_id, message)
                    except Exception as e:
                        print(f"  [Scheduler] Callback error: {e}")

                interval = task.get("interval", 0)
                if interval and task.get("type") == "recurring":
                    tasks[task_id]["fire_at"] = now + interval
                else:
                    tasks[task_id]["fired"] = True
                changed = True

        if changed:
            _save_tasks(tasks)

        time.sleep(1.0)

    print("  [Scheduler] Daemon stopped.")


def start_scheduler():
    """Start the background scheduler daemon. Safe to call multiple times."""
    global _DAEMON_THREAD
    if _DAEMON_THREAD and _DAEMON_THREAD.is_alive():
        return
    _DAEMON_RUNNING.set()
    _DAEMON_THREAD = threading.Thread(target=_daemon_loop, daemon=True, name="jarvis-scheduler")
    _DAEMON_THREAD.start()


def stop_scheduler():
    """Gracefully stop the scheduler daemon."""
    _DAEMON_RUNNING.clear()
    if _DAEMON_THREAD:
        _DAEMON_THREAD.join(timeout=3)
