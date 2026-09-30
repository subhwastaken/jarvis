"""Persistent Memory and User Profile Engine for NIKO."""
import os
import json
import time
import threading

MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis_memory.json")
MAX_HISTORY_TURNS = 5
MEM_LOCK = threading.Lock()


def get_default_memory():
    return {
        "user_profile": {
            "name": "Subharup",
            "title": "Sir",
            "primary_projects": ["niko", "Courtroom", "react"],
            "preferences": {
                "voice": "Daniel",
                "speech_style": "Concise, articulate, polite British butler"
            },
            "custom_facts": []
        },
        "recent_history": []
    }


def load_memory():
    with MEM_LOCK:
        if not os.path.exists(MEMORY_FILE):
            mem = get_default_memory()
            try:
                with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                    json.dump(mem, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
            return mem
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"  [Memory] Error loading memory: {e}, using default")
            return get_default_memory()


def save_memory(mem):
    with MEM_LOCK:
        try:
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(mem, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"  [Memory] Error saving memory: {e}")


def add_turn(user_text, assistant_text):
    mem = load_memory()
    history = mem.get("recent_history", [])
    history.append({
        "role": "user",
        "content": user_text[:300].strip(),
        "timestamp": int(time.time())
    })
    history.append({
        "role": "assistant",
        "content": assistant_text[:300].strip(),
        "timestamp": int(time.time())
    })
    # Keep rolling last MAX_HISTORY_TURNS * 2 messages
    mem["recent_history"] = history[-(MAX_HISTORY_TURNS * 2):]
    save_memory(mem)


VOICE_MALE = "en-GB-RyanNeural"
VOICE_FEMALE = "en-GB-SoniaNeural"

VOICE_MAP = {
    "male": VOICE_MALE,
    "jarvis": VOICE_MALE,
    "ryan": VOICE_MALE,
    "man": VOICE_MALE,
    "boy": VOICE_MALE,
    "en-gb-ryanneural": VOICE_MALE,
    "female": VOICE_FEMALE,
    "friday": VOICE_FEMALE,
    "sonia": VOICE_FEMALE,
    "woman": VOICE_FEMALE,
    "girl": VOICE_FEMALE,
    "en-gb-sonianeural": VOICE_FEMALE,
}


def get_voice():
    mem = load_memory()
    voice = str(mem.get("user_profile", {}).get("preferences", {}).get("voice", "male")).strip()
    return VOICE_MAP.get(voice.lower(), VOICE_FEMALE if ("female" in voice.lower() or "sonia" in voice.lower() or "friday" in voice.lower()) else VOICE_MALE)


def set_voice(gender_or_name):
    clean = str(gender_or_name).lower().strip()
    chosen = VOICE_MAP.get(clean, VOICE_MALE if "male" in clean else VOICE_FEMALE)
    mem = load_memory()
    mem.setdefault("user_profile", {}).setdefault("preferences", {})["voice"] = chosen
    save_memory(mem)
    return chosen


def get_assistant_name():
    """Returns 'NIKO'"""
    return "NIKO"


def update_name(name):
    mem = load_memory()
    mem.setdefault("user_profile", {})["name"] = name
    save_memory(mem)


def set_preference(key, value):
    mem = load_memory()
    mem.setdefault("user_profile", {}).setdefault("preferences", {})[key] = value
    save_memory(mem)


def remember_fact(fact):
    mem = load_memory()
    facts = mem.setdefault("user_profile", {}).setdefault("custom_facts", [])
    if fact not in facts:
        facts.append(fact)
        save_memory(mem)
        return True
    return False


def get_memory_context():
    mem = load_memory()
    profile = mem.get("user_profile", {})
    name = profile.get("name", "Sir")
    title = profile.get("title", "Sir")
    projects = ", ".join(profile.get("primary_projects", []))
    facts = "; ".join(profile.get("custom_facts", []))
    
    ctx = f"The user's name is {name} (address as {title} or {name}). Active projects: {projects}."
    if facts:
        ctx += f" Facts you know about the user: {facts}."
    return ctx, mem.get("recent_history", [])
