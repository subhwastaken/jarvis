"""Autonomous Conditional Reasoning & Multi-Step Planner for J.A.R.V.I.S.
Deconstructs complex 'if/else' conditionals, inspects state, and executes multi-step plans.
"""
import os
import re
import sys
import json
import time
import requests
import subprocess

import jarvis_state
import jarvis_gui

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


def is_conditional_or_gui_query(text: str) -> bool:
    """Detect if a user prompt requires multi-step branching, compound actions, or in-app GUI manipulation."""
    clean = text.strip().lower()
    # Simple app open/close should NOT be intercepted as GUI automation
    if re.match(r"^(?:open|launch|start|run|quit|close|exit)\s+[a-z0-9\s\-]+$", clean):
        if not re.search(r"\b(and|then|click|press|format|cell|button|calculate|perform|\+|\-|\*|\/)\b", clean):
            return False
    # Conditional patterns
    has_condition = bool(re.search(r"\b(if|when|unless|otherwise|else|if not)\b", clean))
    # In-app GUI patterns (including button clicks, typing, excel, calculation)
    has_gui = bool(re.search(r"\b(click|press button|second button|third button|submit button|fill|format cell|excel cell|calculate|perform|keystroke)\b", clean))
    # Compound multi-step patterns with actions
    has_compound = bool(re.search(r"\b(?:and\s+then|and\s+perform|and\s+calculate|and\s+click|and\s+format|and\s+type|and\s+open|and\s+close)\b", clean))
    return has_condition or has_gui or has_compound


class ActionExecutor:
    """Safe execution sandbox for OS and GUI actions."""
    def __init__(self):
        self.logs = []

    def mute_sound(self):
        subprocess.run(["osascript", "-e", "set volume output muted true"], stderr=subprocess.DEVNULL)
        self.logs.append("Muted system volume")
        return "I have muted the volume, sir."

    def unmute_sound(self):
        subprocess.run(["osascript", "-e", "set volume output muted false"], stderr=subprocess.DEVNULL)
        self.logs.append("Unmuted system volume")
        return "I have restored the volume, sir."

    def set_volume(self, level: int):
        subprocess.run(["osascript", "-e", f"set volume output volume {level}"], stderr=subprocess.DEVNULL)
        self.logs.append(f"Set volume to {level}")
        return f"Volume adjusted to {level} percent, sir."

    def open_app(self, app_name: str):
        subprocess.run(["open", "-a", app_name], stderr=subprocess.DEVNULL)
        self.logs.append(f"Opened {app_name}")
        return f"Opening {app_name}, sir."

    def quit_app(self, app_name: str):
        subprocess.run(["osascript", "-e", f'tell application "{app_name}" to quit'], stderr=subprocess.DEVNULL)
        self.logs.append(f"Quit {app_name}")
        return f"Closed {app_name}, sir."

    def set_dark_mode(self, enabled: bool):
        val = "true" if enabled else "false"
        subprocess.run(["osascript", "-e", f'tell application "System Events" to tell appearance preferences to set dark mode to {val}'], stderr=subprocess.DEVNULL)
        self.logs.append(f"Set dark mode to {enabled}")
        return f"Dark mode {'enabled' if enabled else 'disabled'}, sir."

    def pause_music(self):
        subprocess.run(["osascript", "-e", 'tell application "Spotify" to pause'], stderr=subprocess.DEVNULL)
        self.logs.append("Paused Spotify playback")
        return "Paused music playback, sir."

    def click_web_button(self, index: int = 1, text: str = None):
        res = jarvis_gui.click_web_element(button_index=index, button_text=text)
        self.logs.append(f"Web click: {res}")
        return res

    def format_excel_cell(self, cell: str, value: str = None, bold: bool = False):
        res = jarvis_gui.format_excel_cell(cell, value, font_bold=bold)
        self.logs.append(f"Excel format: {res}")
        return res

    def calculate_in_calculator(self, expression: str):
        res = jarvis_gui.perform_calculator_operation(expression)
        self.logs.append(f"Calculated in Calculator: {res}")
        return res


def execute_conditional_plan(user_query: str) -> tuple[str, int]:
    """
    Evaluate user's conditional prompt:
    1. Reads live OS state
    2. Uses System 2 LLM to generate the exact decision tree
    3. Executes the matched branch and returns spoken confirmation.
    """
    t0 = time.time()
    current_state = jarvis_state.capture_system_state()
    # Add running applications for context
    try:
        procs = subprocess.check_output(
            ["osascript", "-e", 'tell application "System Events" to get name of every application process whose visible is true'],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        running_apps = [p.strip() for p in procs.split(",") if p.strip()]
    except Exception:
        running_apps = ["Finder"]

    state_desc = (
        f"- Spotify Playing: {current_state['spotify_playing']}\n"
        f"- Frontmost App: {current_state['frontmost_app']}\n"
        f"- Dark Mode Active: {current_state['dark_mode']}\n"
        f"- Sound Muted: {current_state['muted']}\n"
        f"- Sound Volume: {current_state['volume']}%\n"
        f"- Running Visible Apps: {', '.join(running_apps[:8])}"
    )

    system_prompt = f"""You are the Execution Logic Brain for J.A.R.V.I.S.
The user has given a conditional or GUI automation instruction:
"{user_query}"

CURRENT SYSTEM STATE:
{state_desc}

AVAILABLE ACTIONS:
- actions.mute_sound()
- actions.unmute_sound()
- actions.set_volume(level)
- actions.open_app(app_name)
- actions.quit_app(app_name)
- actions.set_dark_mode(True/False)
- actions.pause_music()
- actions.click_web_button(index=N, text="label")
- actions.format_excel_cell(cell="A1", value="...", bold=True)

Analyze the user's logic step-by-step based on the CURRENT STATE.
Output a valid JSON object ONLY, with these exact keys:
{{
  "condition_evaluated": "brief explanation of which condition matched based on current state",
  "action_to_call": "exact method name from AVAILABLE ACTIONS (e.g. mute_sound, open_app, set_dark_mode, click_web_button, format_excel_cell)",
  "action_args": {{ "key": "value" }},
  "spoken_confirmation": "Concise 1-sentence response as J.A.R.V.I.S. explaining what condition matched and what action was taken (e.g. 'Spotify was active, so I muted the volume, sir.')"
}}
"""

    executor = ActionExecutor()
    # 1. Query Ollama or Cloud LLM
    try:
        model = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
        r = requests.post(
            f"{OLLAMA_HOST}/v1/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a logical computer controller. You output a valid JSON object ONLY. No other text."},
                    {"role": "user", "content": system_prompt}
                ],
                "temperature": 0.0,
                "max_tokens": 180
            },
            timeout=25
        )
        if r.status_code == 200:
            content = r.json()["choices"][0]["message"]["content"].strip()
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            # Extract JSON block
            m = re.search(r"\{.*\}", content, re.DOTALL)
            if m:
                plan = json.loads(m.group(0))
                action_name = plan.get("action_to_call", "")
                action_args = plan.get("action_args", {})
                spoken = plan.get("spoken_confirmation", "Done, sir.")

                # Execute action
                if hasattr(executor, action_name):
                    method = getattr(executor, action_name)
                    method(**action_args)
                    elapsed = int((time.time() - t0) * 1000)
                    return spoken, elapsed
    except Exception as e:
        print(f"  [Planner Agent Local Ollama Notice] {e}")

    # 2. Cloud Fallback (OpenRouter / NVIDIA) if Ollama is unreachable
    try:
        from secrets_store import get_secret
        or_key = get_secret("OPENROUTER_API_KEY")
        nvidia_key = get_secret("NVIDIA_API_KEY")
        cloud_content = None

        if or_key:
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {or_key}"},
                json={
                    "model": "anthropic/claude-haiku-4.5",
                    "messages": [
                        {"role": "system", "content": "You are a logical computer controller. You output a valid JSON object ONLY."},
                        {"role": "user", "content": system_prompt}
                    ],
                    "temperature": 0.0,
                    "max_tokens": 180,
                    "response_format": {"type": "json_object"}
                },
                timeout=15
            )
            if r.status_code == 200:
                cloud_content = r.json()["choices"][0]["message"]["content"].strip()
        elif nvidia_key:
            r = requests.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {nvidia_key}"},
                json={
                    "model": "meta/llama-3.2-3b-instruct",
                    "messages": [
                        {"role": "system", "content": "You are a logical computer controller. You output a valid JSON object ONLY."},
                        {"role": "user", "content": system_prompt}
                    ],
                    "temperature": 0.0,
                    "max_tokens": 180
                },
                timeout=15
            )
            if r.status_code == 200:
                cloud_content = r.json()["choices"][0]["message"]["content"].strip()

        if cloud_content:
            m = re.search(r"\{.*\}", cloud_content, re.DOTALL)
            if m:
                plan = json.loads(m.group(0))
                action_name = plan.get("action_to_call", "")
                action_args = plan.get("action_args", {})
                spoken = plan.get("spoken_confirmation", "Done, sir.")
                if hasattr(executor, action_name):
                    method = getattr(executor, action_name)
                    method(**action_args)
                    elapsed = int((time.time() - t0) * 1000)
                    return spoken, elapsed
    except Exception as e:
        print(f"  [Planner Cloud Fallback Error] {e}")

    # Fallback heuristic parser if LLM offline
    if "spotify is playing" in user_query.lower() or "if spotify" in user_query.lower():
        if current_state["spotify_playing"]:
            if "mute" in user_query.lower():
                executor.mute_sound()
                return "Spotify was playing, so I have muted the system volume, sir.", int((time.time() - t0) * 1000)
        else:
            # Check secondary condition
            if "slack" in user_query.lower():
                if "Slack" in running_apps or jarvis_state.is_app_running("Slack"):
                    executor.open_app("Slack")
                    return "Spotify was not playing, but Slack is running, so I brought it up, sir.", int((time.time() - t0) * 1000)
            if "dark mode" in user_query.lower():
                executor.set_dark_mode(False)
                return "Spotify was not playing, so I proceeded to disable dark mode, sir.", int((time.time() - t0) * 1000)

    # Web click fallback
    m_click = re.search(r"click\s+(?:on\s+)?(?:the\s+)?(first|second|third|fourth|fifth|\d+)(?:st|nd|rd|th)?\s+(?:button|link|result|element|item)", user_query, re.I)
    if not m_click:
        m_click = re.search(r"click\s+(?:on\s+)?(?:the\s+)?(?:link|button|result)\s+(first|second|third|fourth|fifth|\d+)", user_query, re.I)
    if m_click:
        ord_map = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}
        val = m_click.group(1).lower()
        idx = ord_map.get(val, int(val) if val.isdigit() else 1)
        res = executor.click_web_button(index=idx)
        return res, int((time.time() - t0) * 1000)

    # Excel fallback
    m_excel = re.search(r"format\s+(?:cell\s+)?([A-Za-z]\d+)(?:\s+in\s+excel)?", user_query, re.I)
    if m_excel:
        cell_id = m_excel.group(1).upper()
        res = executor.format_excel_cell(cell=cell_id, value="Updated by Jarvis", bold=True)
        return res, int((time.time() - t0) * 1000)

    # Calculator GUI execution fallback
    m_calc = re.search(r"(?:open\s+calculator\s+and\s+(?:perform|calculate|do)|calculate\s+(?:in\s+calculator)?|perform)\s+(.+)", user_query, re.I)
    if not m_calc:
        m_calc = re.search(r"calculator.*?([0-9\s+\-*/xX]+|(?:plus|minus|times|divided\s+by|\d+)+)", user_query, re.I)
    if m_calc:
        expr = m_calc.group(1).strip(" .!?")
        res = executor.calculate_in_calculator(expr)
        return res, int((time.time() - t0) * 1000)

    return "I could not determine the appropriate conditional action, sir.", int((time.time() - t0) * 1000)


# ---------------------------------------------------------------------------
# Public adapter — called from action_dispatcher
# ---------------------------------------------------------------------------

def execute_plan(user_query: str, executor_fn=None) -> tuple[str, int]:
    """Entry point called by the main dispatcher.

    Args:
        user_query:  The raw user command text.
        executor_fn: Optional callable(task_str) -> str.
                     If provided, simple multi-step tasks that don't need
                     the full conditional planner are executed via this
                     function (which is execute_single_action from the dispatcher).
                     Conditional / GUI tasks always go through execute_conditional_plan.

    Returns:
        (reply_text, elapsed_ms)
    """
    import time as _time
    t0 = _time.time()

    # Delegate to the conditional + GUI planner
    reply, ms = execute_conditional_plan(user_query)

    # If planner returned a generic failure and executor_fn is available,
    # try breaking the command into steps and running them sequentially.
    if executor_fn and "could not determine" in reply.lower():
        steps = [s.strip() for s in re.split(r"\band\s+then\b|\bthen\b", user_query, flags=re.I) if s.strip()]
        if len(steps) > 1:
            results = []
            for step in steps:
                try:
                    res = executor_fn(step)
                    if res:
                        results.append(res)
                except Exception as e:
                    results.append(f"Step failed: {e}")
            if results:
                reply = " ".join(results)
                ms = int((_time.time() - t0) * 1000)

    return reply, ms
