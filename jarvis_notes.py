"""Quick Notes & Scratchpad Assistant for NIKO.
Stores notes cleanly in ~/Documents/Niko_Notes/ as formatted Markdown.
Requires zero external permissions or cloud dependencies.
"""
import os
import time
import glob
import re

PRIMARY_NOTES_DIR = os.path.expanduser("~/Documents/Niko_Notes")
FALLBACK_NOTES_DIR = os.path.expanduser("~/.niko/notes")


def get_notes_dir():
    try:
        os.makedirs(PRIMARY_NOTES_DIR, exist_ok=True)
        # Test write permission to avoid silent macOS TCC block
        test_file = os.path.join(PRIMARY_NOTES_DIR, ".write_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return PRIMARY_NOTES_DIR
    except Exception:
        os.makedirs(FALLBACK_NOTES_DIR, exist_ok=True)
        return FALLBACK_NOTES_DIR


NOTES_DIR = PRIMARY_NOTES_DIR


def ensure_notes_dir():
    global NOTES_DIR
    NOTES_DIR = get_notes_dir()
    return NOTES_DIR


def take_quick_note(note_text):
    """Save a quick timestamped note to the local Jarvis Notes vault."""
    if not note_text or not note_text.strip():
        return "Please specify what you would like me to note down, sir."
    ensure_notes_dir()
    now = time.localtime()
    date_str = time.strftime("%Y-%m-%d", now)
    time_str = time.strftime("%H:%M:%S", now)
    file_ts = time.strftime("%Y%m%d_%H%M%S", now)
    
    # Generate a clean short slug for the filename from the first 4 words
    words = [re.sub(r'[^a-zA-Z0-9]', '', w) for w in note_text.split()[:4]]
    slug = "_".join(w for w in words if w) or "note"
    filename = f"{file_ts}_{slug}.md"
    filepath = os.path.join(NOTES_DIR, filename)

    content = f"# Note - {date_str} {time_str}\n\n{note_text.strip()}\n"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return f"I have saved that note to your vault, sir."


def get_latest_note():
    """Retrieve the most recently created note."""
    ensure_notes_dir()
    files = sorted(glob.glob(os.path.join(NOTES_DIR, "*.md")), key=os.path.getmtime, reverse=True)
    if not files:
        return "You have no saved notes in your vault, sir."
    latest_file = files[0]
    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip() and not l.startswith("#")]
            preview = " ".join(lines)[:250]
            return f"Your latest note is: {preview}"
    except Exception as e:
        return f"Could not read your latest note: {e}"


def list_recent_notes(limit=3):
    """List the titles/dates of the most recent notes."""
    ensure_notes_dir()
    files = sorted(glob.glob(os.path.join(NOTES_DIR, "*.md")), key=os.path.getmtime, reverse=True)
    if not files:
        return "You have no notes saved yet, sir."
    titles = []
    for f in files[:limit]:
        b = os.path.basename(f)
        # Strip timestamps for human-friendly speech
        clean_name = re.sub(r"^\d+_\d+_", "", b.replace(".md", "")).replace("_", " ")
        titles.append(clean_name)
    count = len(files)
    return f"You have {count} note{'s' if count != 1 else ''}. Recent topics include: {', '.join(titles)}."
