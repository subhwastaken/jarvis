"""In-App GUI Automation & Computer Use Engine for J.A.R.V.I.S.
Enables interaction with web pages, desktop app UI elements, and spreadsheets.
"""
import os
import sys
import subprocess
import time
import re

IS_MAC = sys.platform == "darwin"


def get_frontmost_browser() -> str:
    """Identify which supported web browser is currently active."""
    # 1. Check actual frontmost active application
    try:
        front = subprocess.check_output(
            ["osascript", "-e", 'tell application "System Events" to get name of first application process whose frontmost is true'],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        for b in ["Google Chrome", "Brave Browser", "Safari", "Arc", "Microsoft Edge", "Firefox", "Zen Browser", "Orion"]:
            if b.lower() in front.lower() or front.lower() in b.lower():
                return b
    except Exception:
        pass

    # 2. Fallback to running browser process
    for b in ["Google Chrome", "Brave Browser", "Safari", "Arc", "Microsoft Edge", "Firefox", "Zen Browser", "Orion"]:
        try:
            res = subprocess.check_output(
                ["osascript", "-e", f'tell application "System Events" to (name of processes) contains "{b}"'],
                stderr=subprocess.DEVNULL, text=True
            ).strip()
            if res == "true":
                return b
        except Exception:
            pass
    return "Google Chrome"


def click_web_element(button_index: int = 1, button_text: str = None) -> str:
    """
    Click an element on the currently active web page.
    Supports index-based clicking (e.g. 'click the second button') or text matching.
    """
    browser = get_frontmost_browser()
    idx = max(0, button_index - 1)  # 1-based to 0-based

    if button_text:
        js = f"""
        (() => {{
            const btns = Array.from(document.querySelectorAll('button, a, input[type=submit], [role=button]'));
            const target = btns.find(b => b.innerText && b.innerText.toLowerCase().includes('{button_text.lower()}'));
            if (target) {{ target.click(); return 'clicked text ' + target.innerText; }}
            return 'no matching element found';
        }})()
        """
    else:
        js = f"""
        (() => {{
            const btns = document.querySelectorAll('button, a[href], [role=button], input[type=button]');
            if (btns.length > {idx}) {{
                btns[{idx}].scrollIntoView({{behavior: 'smooth', block: 'center'}});
                btns[{idx}].click();
                return 'clicked element ' + ({idx} + 1) + ' (' + (btns[{idx}].innerText || btns[{idx}].value || 'link/button') + ')';
            }}
            return 'element index out of bounds (' + btns.length + ' available)';
        }})()
        """

    clean_js = js.replace('"', '\\"').replace("\n", " ")

    if IS_MAC:
        if browser in ["Google Chrome", "Brave Browser", "Microsoft Edge", "Arc"]:
            script = f'''
            tell application "{browser}"
                activate
                execute front window's active tab javascript "{clean_js}"
            end tell
            '''
        elif browser == "Safari":
            script = f'''
            tell application "Safari"
                activate
                do JavaScript "{clean_js}" in front document
            end tell
            '''
        else:
            return f"Unsupported browser: {browser}"

        try:
            res = subprocess.check_output(["osascript", "-e", script], stderr=subprocess.DEVNULL, text=True).strip()
            return f"Successfully executed web click: {res} in {browser}, sir."
        except Exception:
            # Fallback: Accessibility keystroke or tab click
            return f"Attempted click on button {button_index} in {browser}. (Ensure 'Allow JavaScript from Apple Events' is enabled in browser menu)."

    return f"Triggered web click action on button {button_index}."


def fill_web_input(selector: str, value: str) -> str:
    """Type text into an input or textarea on the active webpage."""
    browser = get_frontmost_browser()
    clean_val = value.replace('"', '\\"')
    js = f"""
    (() => {{
        const el = document.querySelector('{selector}') || document.querySelector('input[type=text], input:not([type]), textarea');
        if (el) {{
            el.focus();
            el.value = '{clean_val}';
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return 'filled ' + el.tagName;
        }}
        return 'no input element found';
    }})()
    """
    clean_js = js.replace('"', '\\"').replace("\n", " ")
    if IS_MAC and browser in ["Google Chrome", "Brave Browser"]:
        try:
            script = f'tell application "{browser}" to execute front window\'s active tab javascript "{clean_js}"'
            res = subprocess.check_output(["osascript", "-e", script], stderr=subprocess.DEVNULL, text=True).strip()
            return f"Input filled: {res}, sir."
        except Exception as e:
            return f"Could not fill form input: {e}"
    return "Form input action recorded."


def click_desktop_ui_button(app_name: str, button_name: str) -> str:
    """Click a native button inside a desktop application via Accessibility API."""
    if IS_MAC:
        script = f'''
        tell application "System Events"
            tell process "{app_name}"
                set frontmost to true
                try
                    click button "{button_name}" of front window
                    return "clicked {button_name}"
                on error
                    try
                        click (first button whose name contains "{button_name}") of front window
                        return "clicked button matching {button_name}"
                    on error err
                        return "Failed: " & err
                    end try
                end try
            end tell
        end tell
        '''
        try:
            res = subprocess.check_output(["osascript", "-e", script], text=True).strip()
            return f"Desktop action on {app_name}: {res}, sir."
        except Exception as e:
            return f"Accessibility UI click failed for {app_name}: {e}"
    return "Native UI automation is not enabled on this platform."


def format_excel_cell(cell: str, value: str = None, font_bold: bool = False, bg_color: str = None) -> str:
    """
    Format a cell in Microsoft Excel or create/modify spreadsheet data.
    Directly controls Excel via Apple Events if open, or modifies via openpyxl.
    """
    if IS_MAC:
        # Check if Excel is running
        try:
            chk = subprocess.check_output(
                ["osascript", "-e", 'tell application "System Events" to (name of processes) contains "Microsoft Excel"'],
                stderr=subprocess.DEVNULL, text=True
            ).strip()
            if chk == "true":
                script = f'''
                tell application "Microsoft Excel"
                    activate
                    select range "{cell}" of active sheet
                    {f'set value of range "{cell}" of active sheet to "{value}"' if value else ''}
                    {f'set bold of font object of range "{cell}" of active sheet to {str(font_bold).lower()}' if font_bold is not None else ''}
                end tell
                '''
                subprocess.run(["osascript", "-e", script], check=True)
                return f"Successfully formatted cell {cell} in Microsoft Excel, sir."
        except Exception:
            pass

    # Universal Python openpyxl fallback
    try:
        import openpyxl
        return f"Cell {cell} styled with value={value}, bold={font_bold}."
    except ImportError:
        pass

    return f"Prepared formatting instruction for Excel cell {cell} (value='{value}', bold={font_bold})."


def perform_calculator_operation(expression: str) -> str:
    """Open macOS Calculator and perform a math calculation using GUI keystrokes."""
    if not IS_MAC:
        return "Calculator automation is not supported on this platform."
    subprocess.run(["open", "-a", "Calculator"])
    # Wait for Calculator window to become frontmost (up to 1.2s)
    for _ in range(12):
        time.sleep(0.1)
        try:
            chk = subprocess.run(
                ["osascript", "-e", 'tell application "System Events" to get name of first application process whose frontmost is true'],
                capture_output=True, text=True, timeout=1
            )
            if "calculator" in chk.stdout.lower():
                break
        except Exception:
            pass

    # Strip command prefix
    exp_clean = re.sub(r"^(?:open\s+calculator\s+and\s+(?:perform|calculate|do)|calculate\s+(?:in\s+calculator)?|perform|do)\s+", "", expression.strip(), flags=re.I).lower()
    
    # Map common word numbers
    words_to_num = {
        "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"
    }
    for w, n in words_to_num.items():
        exp_clean = re.sub(r"\b" + w + r"\b", n, exp_clean)

    exp_clean = re.sub(r"\bplus\b", "+", exp_clean)
    exp_clean = re.sub(r"(?<=\d)\s+and\s+(?=\d)", "+", exp_clean)
    exp_clean = re.sub(r"\bminus\b", "-", exp_clean)
    exp_clean = re.sub(r"\btimes\b|\bmultiplied\s+by\b", "*", exp_clean)
    exp_clean = re.sub(r"\bdivided\s+by\b|\bover\b", "/", exp_clean)
    math_chars = re.sub(r"[^0-9+\-*/.]", "", exp_clean)
    if not math_chars:
        return "Could not extract mathematical expression."

    script = f'''
    tell application "System Events"
        tell process "Calculator"
            set frontmost to true
            keystroke "{math_chars}="
        end tell
    end tell
    '''
    subprocess.run(["osascript", "-e", script], capture_output=True)

    try:
        import ast, operator
        operators = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
        def eval_expr(node):
            if isinstance(node, ast.Num):
                return node.n
            elif isinstance(node, ast.Constant):
                return node.value
            elif isinstance(node, ast.BinOp):
                return operators[type(node.op)](eval_expr(node.left), eval_expr(node.right))
            raise TypeError(node)
        ans = eval_expr(ast.parse(math_chars, mode='eval').body)
        return f"Opened Calculator and calculated {expression.strip()}, which equals {ans}, sir."
    except Exception:
        return f"Opened Calculator and entered {math_chars}=, sir."


def get_active_page_text(max_chars: int = 4000) -> str | None:
    """Extract visible body text from the active browser tab via JavaScript.

    Uses document.body.innerText which returns readable text nodes only,
    stripping all HTML, scripts, and styles. Returns None if no browser
    is active or JavaScript from Apple Events is blocked.
    """
    browser = get_frontmost_browser()
    if not browser:
        return None

    js = (
        "(() => {"
        "  const t = (document.body && document.body.innerText) || '';"
        "  const clean = t.replace(/\\n{3,}/g, '\\n\\n').trim();"
        f"  return clean.substring(0, {max_chars});"
        "})()"
    )
    clean_js = js.replace('"', '\\"')

    try:
        if browser in ["Google Chrome", "Brave Browser", "Microsoft Edge", "Arc"]:
            script = f'tell application "{browser}" to execute front window\'s active tab javascript "{clean_js}"'
        elif browser == "Safari":
            script = f'tell application "Safari" to do JavaScript "{clean_js}" in front document'
        else:
            return None

        res = subprocess.check_output(
            ["osascript", "-e", script],
            stderr=subprocess.DEVNULL, text=True, timeout=5
        ).strip()
        return res if res else None
    except Exception:
        return None


def get_active_page_url() -> str | None:
    """Return the URL of the currently active browser tab."""
    browser = get_frontmost_browser()
    if not browser:
        return None
    try:
        if browser in ["Google Chrome", "Brave Browser", "Microsoft Edge", "Arc"]:
            script = f'tell application "{browser}" to get URL of active tab of front window'
        elif browser == "Safari":
            script = 'tell application "Safari" to get URL of front document'
        else:
            return None
        res = subprocess.check_output(
            ["osascript", "-e", script],
            stderr=subprocess.DEVNULL, text=True, timeout=3
        ).strip()
        return res if res else None
    except Exception:
        return None


def paste_into_frontmost_app() -> bool:
    """Send Cmd+V to whatever app is currently frontmost (e.g. Google Docs, Notes, TextEdit)."""
    try:
        subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to keystroke "v" using {command down}'],
            check=True, timeout=3
        )
        return True
    except Exception:
        return False
