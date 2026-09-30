"""Python IPC Client for the J.A.R.V.I.S. Core Rust Daemon.
Connects via local Unix Domain Socket (/tmp/jarvis.sock) with microsecond latency.
"""
import json
import os
import socket
import subprocess
import time

SOCKET_PATH = "/tmp/jarvis.sock"
BINARY_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "jarvis_core")


def is_rust_daemon_running():
    """Check if the Rust daemon socket is live and accepting connections."""
    if not os.path.exists(SOCKET_PATH):
        return False
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(0.2)
        s.connect(SOCKET_PATH)
        s.close()
        return True
    except Exception:
        return False


def start_rust_daemon():
    """Start the Rust daemon in the background if not already running."""
    if is_rust_daemon_running():
        return True
    if not os.path.exists(BINARY_PATH):
        print(f"  [Rust Client] Binary not found at {BINARY_PATH}")
        return False
    try:
        subprocess.Popen([BINARY_PATH], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        # Give it up to 500ms to initialize the socket
        for _ in range(10):
            time.sleep(0.05)
            if is_rust_daemon_running():
                return True
    except Exception as e:
        print(f"  [Rust Client] Failed to launch daemon: {e}")
    return False


def send_rust_command(action, payload=None, timeout=1.0):
    """Send a JSON request to the Rust daemon over Unix socket and return response data."""
    def _try_send():
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(SOCKET_PATH)
        msg = json.dumps({"action": action, "payload": payload or {}}) + "\n"
        s.sendall(msg.encode("utf-8"))
        raw = s.recv(4096).decode("utf-8")
        s.close()
        if raw.strip():
            res = json.loads(raw.strip())
            if res.get("status") == "ok":
                return res.get("data")
        return None

    try:
        if os.path.exists(SOCKET_PATH):
            return _try_send()
    except Exception:
        pass

    # Fallback: start daemon if socket was stale or unavailable, then retry once
    if start_rust_daemon():
        try:
            return _try_send()
        except Exception as e:
            print(f"  [Rust Client] IPC error ({action}): {e}")
    return None


def get_rust_telemetry():
    """Retrieve full system telemetry from the native Rust daemon."""
    data = send_rust_command("telemetry")
    if data:
        uptime = data.get("uptime_secs", 0)
        ram = data.get("ram_usage", "")
        batt = data.get("battery", "")
        app = data.get("active_app", "")
        return f"Rust Core active (uptime {uptime}s). Front app: {app}. RAM: {ram}. Battery: {batt}."
    return None
