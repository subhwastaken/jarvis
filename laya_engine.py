"""Laya Local Decision Engine for J.A.R.V.I.S.
Powered by Laya (https://github.com/NandhaKishorM/laya).
Non-autoregressive System 1 decision engine executing typed decisions locally on macOS.
100% Free, Offline, Sub-15ms, zero-cloud API costs.
"""
import os
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
import re
import time
import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="laya.*")
warnings.filterwarnings("ignore", message=".*ships invalid temperatures.*")

from laya import Agent

# Canonical applications mapping for slot extraction & normalization
APPS = {
    "music": "Music", "apple music": "Music", "apple_music": "Music", "itunes": "Music",
    "reminders": "Reminders", "reminder": "Reminders", "remainder": "Reminders",
    "notes": "Notes", "note": "Notes", "calendar": "Calendar", "calculator": "Calculator",
    "calc": "Calculator", "mail": "Mail", "messages": "Messages", "message": "Messages",
    "maps": "Maps", "weather": "Weather", "photos": "Photos", "photo": "Photos",
    "settings": "System Settings", "system settings": "System Settings",
    "system preferences": "System Settings", "clock": "Clock", "safari": "Safari",
    "finder": "Finder", "terminal": "Terminal", "preview": "Preview", "textedit": "TextEdit",
    "chrome": "Google Chrome", "google chrome": "Google Chrome", "google": "Google",
    "youtube": "YouTube", "you tube": "YouTube", "yout tube": "YouTube", "u tube": "YouTube",
    "brave": "Brave Browser", "brave browser": "Brave Browser", "vscode": "Visual Studio Code",
    "vs code": "Visual Studio Code", "code": "Visual Studio Code", "visual studio code": "Visual Studio Code",
    "slack": "Slack", "spotify": "Spotify", "discord": "Discord", "cursor": "Cursor",
    "notion": "Notion", "audacity": "Audacity", "keynote": "Keynote", "numbers": "Numbers",
    "pages": "Pages", "garageband": "GarageBand", "sublime": "Sublime Text",
    "sublime text": "Sublime Text", "iterm": "iTerm", "iterm2": "iTerm",
    "whatsapp": "WhatsApp", "telegram": "Telegram", "zoom": "zoom.us",
    "firefox": "Firefox", "arc": "Arc", "edge": "Microsoft Edge"
}

LEVEL_WORDS = {
    "silent": "0", "zero": "0", "mute": "0",
    "quiet": "25", "low": "25", "soft": "25",
    "medium": "50", "half": "50", "normal": "50", "middle": "50",
    "loud": "75", "high": "75",
    "max": "100", "maximum": "100", "full": "100", "hundred": "100"
}

# Laya Typed Question Schema tailored for desktop OS assistant
QUESTIONS = {
    "category": {
        "type": "choice",
        "instructions": "What kind of request is this?",
        "criteria": {
            "mac_command": "asks the computer to do something or control apps, settings, or windows",
            "information_request": "asks a general knowledge, factual question, or math calculation",
            "chit_chat": "just talking, greeting, thanking, or conversational pleasantry",
            "unclear": "garbled, empty, or makes no sense"
        }
    },
    "compound": {
        "type": "noul",
        "instructions": "Does the request contain more than one distinct action or command?"
    },
    "target": {
        "type": "choice",
        "instructions": "What is the primary thing being controlled?",
        "criteria": {
            "app": "an application (opening, closing, switching)",
            "volume": "sound or audio volume level",
            "display": "screen appearance or dark mode",
            "media": "music or video playback",
            "window": "window sizing, tiling, snapping, or moving",
            "browser": "browsing, searching the web, or managing tabs",
            "system": "locking, sleeping, or checking computer resources and stats",
            "timer": "setting, checking, or cancelling a timer or reminder",
            "clipboard": "reading, summarizing, or copying clipboard",
            "dev": "git or developer file inspection",
            "calc": "math expression or calculation",
            "none": "no computer control or system setting is being targeted"
        }
    },
    "app": {
        "type": "choice",
        "instructions": "Which app, if any, is named?",
        "criteria": {
            "spotify": None, "slack": None, "chrome": None, "vscode": None,
            "finder": None, "safari": None, "messages": None, "notes": None,
            "music": None, "terminal": None, "discord": None, "calculator": None,
            "reminders": None, "calendar": None, "none": None
        }
    },
    "app_action": {
        "type": "choice",
        "instructions": "What should happen to the app?",
        "criteria": {
            "open": "open, launch, or start the app itself",
            "quit": "quit, close, or kill the app",
            "none": "the request is not about opening or quitting an app"
        }
    },
    "volume_action": {
        "type": "choice",
        "instructions": "What should happen to the volume, if anything?",
        "criteria": {
            "up": "increase volume", "down": "decrease volume",
            "mute": "mute volume", "unmute": "unmute volume",
            "set": "set to a specific level", "none": "none"
        }
    },
    "volume_scope": {
        "type": "choice",
        "instructions": "Which volume should change?",
        "criteria": {
            "spotify": "Spotify's own in-app volume when Spotify is explicitly named",
            "system": "the Mac's overall output volume, including unqualified volume requests"
        }
    },
    "volume_level": {
        "type": "score",
        "instructions": "If a volume level is asked for, how loud?",
        "criteria": ["silent", "quiet", "medium", "loud", "max"]
    },
    "display_action": {
        "type": "choice",
        "instructions": "What should happen to dark mode or display?",
        "criteria": {
            "dark_on": "turn on dark mode",
            "dark_off": "turn off dark mode or switch to light mode",
            "toggle": "toggle dark mode",
            "sleep": "sleep display",
            "none": "none"
        }
    },
    "media_action": {
        "type": "choice",
        "instructions": "What should happen to music playback?",
        "criteria": {
            "play": "play or resume music",
            "pause": "pause or stop music",
            "next": "next track",
            "previous": "previous track",
            "search": "search or play on youtube",
            "none": "none"
        }
    },
    "window_action": {
        "type": "choice",
        "instructions": "What should happen to windows?",
        "criteria": {
            "maximize": "maximize or fill screen",
            "tile_left": "snap or tile left",
            "tile_right": "snap or tile right",
            "center": "center active window",
            "hide_others": "hide background applications",
            "none": "none"
        }
    },
    "browser_action": {
        "type": "choice",
        "instructions": "What should happen in the browser?",
        "criteria": {
            "open_url": "open a specific website or domain",
            "search": "search Google or the web",
            "new_tab": "open a new tab",
            "close_tab": "close active tab",
            "switch_tab": "switch to next or previous tab",
            "reload": "reload tab",
            "none": "none"
        }
    },
    "timer_action": {
        "type": "choice",
        "instructions": "What should happen with a timer or reminder?",
        "criteria": {
            "set": "start a timer or set a reminder",
            "check": "ask how much time is left",
            "cancel": "stop or cancel a timer",
            "none": "none"
        }
    },
    "system_action": {
        "type": "choice",
        "instructions": "What should happen to the computer?",
        "criteria": {
            "lock": "lock screen",
            "sleep": "sleep computer",
            "ram": "check RAM usage",
            "battery": "check battery percentage",
            "disk": "check disk space",
            "screenshot": "take a screenshot",
            "screen_analyze": "analyze screen content",
            "trash": "empty trash",
            "none": "none"
        }
    }
}


class LayaDecisionEngine:
    """Local System 1 Decision Engine using Laya (convaiinnovations/laya)."""

    def __init__(self, model_id=None, subfolder=None, device=None):
        self.model_id = model_id or os.getenv("LAYA_MODEL", "convaiinnovations/laya")
        self.subfolder = subfolder or os.getenv("LAYA_SUBFOLDER", "typed-decisions")
        self.device = device or os.getenv("LAYA_DEVICE", None)
        try:
            self.agent = Agent(self.model_id, subfolder=self.subfolder, device=self.device)
            self._laya_ready = True
        except Exception as e:
            print(f"  [Laya Engine Warning] Failed to initialize Agent ({e}). Running deterministic fallback.")
            self.agent = None
            self._laya_ready = False

    def extract_app(self, text: str) -> str:
        t_clean = text.lower().strip(" ,.!?\"'")
        for name in sorted(APPS.keys(), key=lambda x: len(x), reverse=True):
            pattern = r"\b" + re.escape(name) + r"\b"
            if re.search(pattern, t_clean):
                return APPS[name]
        m = re.search(r"\b(?:open|launch|quit|close|kill|exit|switch\s+to)\s+([a-zA-Z0-9\s]+?)(?:\s+(?:and|please|now)|$)", t_clean)
        if m:
            candidate = m.group(1).strip()
            if candidate in APPS:
                return APPS[candidate]
            if len(candidate) > 2 and candidate not in ("the", "it", "music", "volume", "screen", "timer", "window", "tab"):
                return candidate.title()
        return "none"

    def extract_volume_level(self, text: str) -> str:
        t_clean = text.lower()
        # Explicit percentage: e.g. "80%", "70 percent"
        m_pct = re.search(r"\b(\d{1,3})\s*(?:%|percent)\b", t_clean)
        if m_pct:
            val = int(m_pct.group(1))
            return str(max(0, min(100, val)))
        # Explicit volume assignment: e.g. "volume 50", "volume to 80", "sound at 30"
        m_vol = re.search(r"\b(?:volume|sound)\s+(?:to\s+|at\s+|level\s+)?(\d{1,3})\b", t_clean)
        if m_vol:
            val = int(m_vol.group(1))
            return str(max(0, min(100, val)))
        # Turn/set volume to level
        m_set = re.search(r"\b(?:set|turn|change)\s+(?:the\s+)?(?:volume|sound)\s+(?:to\s+)?(\d{1,3})\b", t_clean)
        if m_set:
            val = int(m_set.group(1))
            return str(max(0, min(100, val)))
        # Level words only when volume or sound is mentioned
        if re.search(r"\b(?:volume|sound|audio)\b", t_clean):
            for word, lvl in LEVEL_WORDS.items():
                if re.search(r"\b" + re.escape(word) + r"\b", t_clean):
                    return lvl
        return "none"

    def is_math_query(self, text: str) -> tuple[bool, str]:
        """Detect math questions like 'what is 25 * 4', 'calculate 150 / 3', '50 plus 20', 'perform 10 x 10'."""
        t_clean = text.strip().lower()
        t_expr = re.sub(
            r"^(?:(?:please\s+)?(?:what(?:'s|\s+is)|calculate|compute|solve|how\s+much\s+is|evaluate|perform|do|find(?:\s+the\s+value\s+of)?)(?:\s+(?:the|our|this|a))?\s+)",
            "",
            t_clean
        ).strip(" ?=.")

        # Word numbers mapping
        word_nums = {
            "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
            "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
            "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
            "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
            "eighteen": "18", "nineteen": "19", "twenty": "20", "thirty": "30",
            "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70",
            "eighty": "80", "ninety": "90", "hundred": "100"
        }
        expr = t_expr
        for w, n in word_nums.items():
            expr = re.sub(r"\b" + w + r"\b", n, expr)

        expr = expr.replace(" plus ", " + ").replace(" minus ", " - ").replace(" times ", " * ")
        expr = expr.replace(" to the power of ", " ** ").replace(" power of ", " ** ")
        expr = expr.replace(" multiplied by ", " * ").replace(" divided by ", " / ").replace(" over ", " / ")
        expr = re.sub(r"(\d+)\s*[xX]\s*(\d+)", r"\1 * \2", expr)
        expr = expr.replace("^", "**")

        clean_chars = re.sub(r"[0-9\s\+\-\*\/\(\)\.]", "", expr)
        if not clean_chars and any(op in expr for op in ("+", "-", "*", "/")):
            try:
                val = eval(expr, {"__builtins__": {}}, {})
                if isinstance(val, (int, float)):
                    fmt_val = int(val) if isinstance(val, float) and val.is_integer() else round(val, 4)
                    return True, str(fmt_val)
            except Exception:
                pass
        return False, ""

    def classify_clause(self, text: str, questions=None) -> tuple[dict, int]:
        t0 = time.time()
        t_clean = text.strip()
        if not t_clean:
            return self._blank_ans(), 0

        qs = questions or QUESTIONS
        t_lower = t_clean.lower()
        ans = {}

        # 1. Execute Laya typed decision if agent is available
        if self._laya_ready and self.agent:
            try:
                res = self.agent.predict(t_clean, qs)
                for k, a in res.get("answers", {}).items():
                    if a.get("type") == "noul":
                        prob = a.get("noul", 0.5)
                        ans[k] = (bool(prob >= 0.5), float(max(prob, 1 - prob)))
                    elif a.get("type") == "score":
                        score = a.get("score", 0)
                        legend = a.get("legend", {})
                        val = legend.get(str(int(round(score))), str(score)) if legend else str(score)
                        conf = float(a.get("answer_confidence", a.get("confidence", 0.8)))
                        ans[k] = (val, conf)
                    else:
                        choice = a.get("choice", "none")
                        conf = float(a.get("answer_confidence", a.get("confidence", 0.8)))
                        ans[k] = (choice, conf)
            except Exception as e:
                ans = self._blank_ans()
        else:
            ans = self._blank_ans()

        # 2. Slot normalization & High-Confidence Domain Heuristics
        # Apps (Ensure 'open google chrome' or 'close google chrome' stays an app command)
        extracted_app = self.extract_app(t_clean)
        is_app_action = bool(re.search(r"^(?:open|launch|start|switch\s+to|bring\s+up|quit|close|kill|exit)\b", t_lower))
        if extracted_app != "none" and is_app_action:
            ans["app"] = (extracted_app, 0.99)
            ans["target"] = ("app", 0.99)
            ans["category"] = ("mac_command", 0.99)
            if re.search(r"\b(?:quit|close|kill|exit)\b", t_lower):
                ans["app_action"] = ("quit", 0.99)
            else:
                ans["app_action"] = ("open", 0.99)

        # Volume
        vol_level = self.extract_volume_level(t_clean)
        is_vol_cmd = bool(
            (re.search(r"\b(?:volume|mute|unmute|louder|quieter|silence)\b", t_lower) or
             re.search(r"\b(?:sound\s+volume|turn\s+(?:up|down)\s+(?:the\s+)?sound|mute\s+sound|unmute\s+sound|restore\s+sound)\b", t_lower) or
             re.search(r"\bturn\s+(?:spotify|[a-z]+)?\s*(?:down|up)\b", t_lower) or
             vol_level != "none") and not re.search(r"\bplay\b.*\bon\s+youtube\b", t_lower)
        )
        if is_vol_cmd:
            ans["target"] = ("volume", 0.99)
            ans["category"] = ("mac_command", 0.99)
            scope = "spotify" if "spotify" in t_lower else "system"
            ans["volume_scope"] = (scope, 0.98)
            if re.search(r"\b(?:unmute|restore\s+sound|restore\s+volume)\b", t_lower):
                ans["volume_action"] = ("unmute", 0.99)
            elif re.search(r"\b(?:mute|silent|silence)\b", t_lower):
                ans["volume_action"] = ("mute", 0.99)
            elif re.search(r"\b(?:down|lower|quieter|decrease|turn\s+(?:[a-z]+\s+)?down)\b", t_lower):
                ans["volume_action"] = ("down", 0.99)
            elif re.search(r"\b(?:up|raise|higher|louder|increase|turn\s+(?:[a-z]+\s+)?up)\b", t_lower):
                ans["volume_action"] = ("up", 0.99)
            elif vol_level != "none":
                ans["volume_action"] = ("set", 0.99)
                ans["volume_level"] = (vol_level, 0.99)

        # Window management
        if re.search(r"\b(?:maximize|fill\s+the\s+screen|fill\s+screen|tile|snap|center(?:\s+active)?\s+window|hide\s+other\s+apps|hide\s+background\s+apps|hide\s+background\s+applications|focus\s+mode)\b", t_lower):
            ans["target"] = ("window", 0.99)
            ans["category"] = ("mac_command", 0.99)
            if "maximize" in t_lower or "fill" in t_lower:
                ans["window_action"] = ("maximize", 0.99)
            elif "left" in t_lower:
                ans["window_action"] = ("tile_left", 0.99)
            elif "right" in t_lower:
                ans["window_action"] = ("tile_right", 0.99)
            elif "center" in t_lower:
                ans["window_action"] = ("center", 0.99)
            elif "hide" in t_lower or "focus" in t_lower:
                ans["window_action"] = ("hide_others", 0.99)

        # Display & Appearance
        if re.search(r"\b(?:dark\s+mode|light\s+mode|appearance)\b", t_lower):
            ans["target"] = ("display", 0.99)
            ans["category"] = ("mac_command", 0.99)
            if "light" in t_lower or "off" in t_lower:
                ans["display_action"] = ("dark_off", 0.99)
            elif "toggle" in t_lower or "switch" in t_lower:
                ans["display_action"] = ("toggle", 0.99)
            else:
                ans["display_action"] = ("dark_on", 0.99)

        # Browser & Web
        if re.search(r"\b(?:new\s+tab|close\s+tab|reload\s+tab|next\s+tab|previous\s+tab|open\s+(?:a\s+)?new\s+tab|close\s+(?:this|active)?\s*tab)\b", t_lower):
            ans["target"] = ("browser", 0.99)
            ans["category"] = ("mac_command", 0.99)
            if "new" in t_lower:
                ans["browser_action"] = ("new_tab", 0.99)
            elif "close" in t_lower:
                ans["browser_action"] = ("close_tab", 0.99)
            elif "reload" in t_lower or "refresh" in t_lower:
                ans["browser_action"] = ("reload", 0.99)
            elif "next" in t_lower:
                ans["browser_action"] = ("switch_tab", 0.99)
            elif "previous" in t_lower:
                ans["browser_action"] = ("switch_tab", 0.99)
        elif re.search(r"\b(?:search\s+google|search\s+for|look\s+up)\b", t_lower) and not re.search(r"\b(?:youtube|spotify|music|app)\b", t_lower):
            ans["target"] = ("browser", 0.95)
            ans["category"] = ("mac_command", 0.95)
            ans["browser_action"] = ("search", 0.95)
        elif re.search(r"^google\s+(?!chrome)", t_lower):
            ans["target"] = ("browser", 0.95)
            ans["category"] = ("mac_command", 0.95)
            ans["browser_action"] = ("search", 0.95)
        elif re.search(r"\b(?:go\s+to|open)\s+[a-z0-9\-]+\.(?:com|org|io|dev|ai|net|edu|app)\b", t_lower):
            ans["target"] = ("browser", 0.98)
            ans["category"] = ("mac_command", 0.98)
            ans["browser_action"] = ("open_url", 0.98)

        # Media Playback & YouTube
        is_media = (
            t_lower.strip() in ("play", "pause", "resume", "stop", "next song", "previous song", "next track", "previous track") or
            re.search(r"\b(?:play\s+music|pause\s+music|stop\s+music|resume\s+playback|skip\s+track|go\s+back\s+one\s+song)\b", t_lower) or
            ("youtube" in t_lower and "open" not in t_lower.split()[:1]) or
            re.search(r"\bplay\b.*\b(?:youtube|lofi|jazz|playlist|symphony|song|track|beats|music)\b", t_lower)
        )
        if is_media and ans.get("target", ("none", 0))[0] != "volume":
            ans["target"] = ("media", 0.99)
            ans["category"] = ("mac_command", 0.99)
            if "pause" in t_lower or "stop" in t_lower:
                ans["media_action"] = ("pause", 0.99)
            elif "next" in t_lower or "skip" in t_lower:
                ans["media_action"] = ("next", 0.99)
            elif "previous" in t_lower or "back" in t_lower:
                ans["media_action"] = ("previous", 0.99)
            elif "youtube" in t_lower:
                ans["media_action"] = ("search", 0.99)
            else:
                ans["media_action"] = ("play", 0.99)

        # System controls & diagnostics
        if re.search(r"\b(?:lock\s+screen|lock\s+the\s+mac|lock\s+mac|lock\s+my\s+workstation|sleep\s+mac|sleep\s+computer|battery|ram\s+usage|memory\s+usage|memory\s+is\s+free|disk\s+space|storage\s+is\s+left|empty\s+trash|screenshot|screen\s+capture|capture\s+screen|analyze\s+screen)\b", t_lower):
            ans["target"] = ("system", 0.99)
            ans["category"] = ("mac_command", 0.99)
            if "lock" in t_lower:
                ans["system_action"] = ("lock", 0.99)
            elif "sleep" in t_lower:
                ans["system_action"] = ("sleep", 0.99)
            elif "battery" in t_lower or "power" in t_lower:
                ans["system_action"] = ("battery", 0.99)
            elif "ram" in t_lower or "memory" in t_lower:
                ans["system_action"] = ("ram", 0.99)
            elif "disk" in t_lower or "storage" in t_lower:
                ans["system_action"] = ("disk", 0.99)
            elif "screenshot" in t_lower or "screen capture" in t_lower or "capture screen" in t_lower:
                ans["system_action"] = ("screenshot", 0.99)
            elif "analyze" in t_lower:
                ans["system_action"] = ("screen_analyze", 0.99)
            elif "trash" in t_lower:
                ans["system_action"] = ("trash", 0.99)

        # Math / Calc
        is_math, math_res = self.is_math_query(t_clean)
        if is_math:
            ans["target"] = ("calc", 0.99)
            ans["category"] = ("information_request", 0.99)
            ans["math_result"] = (math_res, 0.99)

        # Timers & Reminders
        if re.search(r"\b(?:timer|countdown|remind|alarm)\b", t_lower):
            ans["target"] = ("timer", 0.98)
            ans["category"] = ("mac_command", 0.98)
            if "cancel" in t_lower or "stop" in t_lower or "delete" in t_lower:
                ans["timer_action"] = ("cancel", 0.98)
            elif "how much" in t_lower or "check" in t_lower or "left" in t_lower or "status" in t_lower:
                ans["timer_action"] = ("check", 0.98)
            else:
                ans["timer_action"] = ("set", 0.98)

        # General Knowledge & Chit-chat
        if not is_math and re.search(r"^(?:who|what|why|how|when|where|explain|tell\s+me\s+about)\b", t_lower) and ans.get("target", ("none", 0))[0] not in ("system", "timer", "volume", "window", "app"):
            ans["category"] = ("information_request", 0.96)
            ans["target"] = ("none", 0.96)
        elif re.search(r"^(?:hello|hi|hey|thanks|thank you|good morning|how are you|who are you|joke|tell\s+me\s+a\s+joke)\b", t_lower):
            ans["category"] = ("chit_chat", 0.96)
            ans["target"] = ("none", 0.96)

        # Safeguard: Filter low confidence target choices or conversational categories
        tgt, tgt_conf = ans.get("target", ("none", 0.0))
        cat, cat_conf = ans.get("category", ("none", 0.0))
        if tgt_conf < 0.65 or tgt == "none":
            ans["target"] = ("none", tgt_conf)
        elif cat in ("information_request", "chit_chat") and tgt not in ("calc", "system"):
            ans["target"] = ("none", 0.95)

        ms = int((time.time() - t0) * 1000)
        return ans, ms

    def route(self, text: str, is_split=False, questions=None) -> tuple[dict, int, float]:
        """Entry point for Laya local typed decision classification."""
        ans, ms = self.classify_clause(text, questions=questions)
        return ans, ms, 0.0

    def _blank_ans(self):
        return {
            "category": ("unclear", 0.0), "compound": (False, 0.0), "target": ("none", 0.0),
            "app": ("none", 0.0), "app_action": ("none", 0.0), "volume_action": ("none", 0.0),
            "volume_scope": ("system", 0.0), "volume_level": ("none", 0.0), "display_action": ("none", 0.0),
            "media_action": ("none", 0.0), "window_action": ("none", 0.0), "browser_action": ("none", 0.0),
            "timer_action": ("none", 0.0), "system_action": ("none", 0.0)
        }


# Singleton Laya Engine Instance
_LAYA_ENGINE = None


def get_laya_engine() -> LayaDecisionEngine:
    global _LAYA_ENGINE
    if _LAYA_ENGINE is None:
        _LAYA_ENGINE = LayaDecisionEngine()
    return _LAYA_ENGINE


def laya_decide(text: str, questions=None) -> tuple[dict, int, float]:
    """Execute typed intent classification using the Laya local decision engine."""
    engine = get_laya_engine()
    return engine.route(text, questions=questions)
