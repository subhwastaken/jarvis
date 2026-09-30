"""Clipboard Assistant for NIKO (macOS native pbcopy / pbpaste bridge)."""
import subprocess
import re


def get_clipboard_text(max_chars=4000):
    """Retrieve plain text from the macOS system clipboard using pbpaste."""
    try:
        proc = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=3)
        if proc.returncode == 0:
            content = proc.stdout.strip()
            if not content:
                return None
            if len(content) > max_chars:
                return content[:max_chars] + f"\n... [Truncated: showing first {max_chars} characters]"
            return content
    except Exception as e:
        print(f"  [Clipboard] Read error: {e}")
    return None


def set_clipboard_text(text):
    """Copy text to the macOS system clipboard using pbcopy."""
    try:
        proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        proc.communicate(input=text.encode("utf-8"), timeout=3)
        return proc.returncode == 0
    except Exception as e:
        print(f"  [Clipboard] Write error: {e}")
        return False


def summarize_clipboard_content():
    """Returns a short description of what is in the clipboard."""
    text = get_clipboard_text()
    if not text:
        return "Your clipboard is currently empty, sir."
    lines = text.strip().splitlines()
    char_count = len(text)
    line_count = len(lines)
    preview = lines[0][:80].strip()
    return f"Your clipboard contains {line_count} line{'s' if line_count != 1 else ''} ({char_count} characters). It begins with: {preview}"
