"""Store API keys in the macOS login Keychain, with .env as a dev fallback."""
import os
import sys
import json
import subprocess

from dotenv import load_dotenv

load_dotenv()  # so a .env works from the app bundle too, not just the terminal


def reload_secrets():
    load_dotenv(override=True)


SERVICE = "com.niko.keys"
FALLBACK_SERVICE = "com.jevsiri.keys"
KEY_NAMES = ("NVIDIA_API_KEY",)

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")
WIN_SECRETS_DIR = os.path.expanduser("~/.niko")
WIN_SECRETS_FILE = os.path.join(WIN_SECRETS_DIR, "secrets.json")
FALLBACK_WIN_SECRETS_FILE = os.path.expanduser("~/.hey_jev/secrets.json")


def os_store_value(name):
    if IS_MAC:
        for s in (SERVICE, FALLBACK_SERVICE):
            result = subprocess.run(
                ["security", "find-generic-password", "-a", name, "-s", s, "-w"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        return None
    elif IS_WIN:
        for fpath in (WIN_SECRETS_FILE, FALLBACK_WIN_SECRETS_FILE):
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        val = json.load(f).get(name)
                        if val:
                            return val
                except Exception:
                    pass
        return None


def get_secret(name):
    return os.getenv(name) or os_store_value(name)  # .env wins, so editing it always takes effect


def save_secret(name, value):
    if name not in KEY_NAMES:
        raise ValueError(f"unknown secret: {name}")
    value = value.strip()
    if not value:
        return

    if IS_MAC:
        result = subprocess.run(
            ["security", "add-generic-password", "-U", "-a", name, "-s", SERVICE, "-w", value],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "Could not save to Keychain")
    elif IS_WIN:
        os.makedirs(WIN_SECRETS_DIR, exist_ok=True)
        data = {}
        if os.path.exists(WIN_SECRETS_FILE):
            try:
                with open(WIN_SECRETS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data[name] = value
        with open(WIN_SECRETS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


def missing_secrets():
    # Zero external secrets are required. Decision engine (Laya) and speech run 100% locally.
    return []

