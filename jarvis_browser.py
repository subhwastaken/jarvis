"""Browser and Media Automation Engine for J.A.R.V.I.S."""
import subprocess
import urllib.parse
import re
import threading
import time

SUPPORTED_BROWSERS = [
    "Google Chrome", "Safari", "Brave Browser", "Arc", "Microsoft Edge",
    "Firefox", "Zen Browser", "Orion", "Vivaldi", "Opera"
]


def get_active_browser():
    for b in SUPPORTED_BROWSERS:
        try:
            res = subprocess.check_output(
                ["osascript", "-e", f'application "{b}" is running'],
                stderr=subprocess.DEVNULL,
                text=True
            ).strip()
            if res == "true":
                return b
        except Exception:
            pass
    return None


def play_youtube(query):
    clean_query = query.strip(" '\"`")
    encoded = urllib.parse.quote_plus(clean_query)
    url = f"https://www.youtube.com/results?search_query={encoded}"
    
    # Launch browser in a background thread promptly
    def _open():
        time.sleep(0.1)
        subprocess.run(["open", url])
    
    threading.Thread(target=_open, daemon=True).start()
    return f"Right away, sir. Opening YouTube for {clean_query}."


def search_google_browser(query):
    clean_query = query.strip(" '\"`")
    encoded = urllib.parse.quote_plus(clean_query)
    url = f"https://www.google.com/search?q={encoded}"
    
    def _open():
        time.sleep(0.1)
        subprocess.run(["open", url])
        
    threading.Thread(target=_open, daemon=True).start()
    return f"Searching Google for {clean_query}, sir."


def open_website(url):
    clean_url = url.strip(" '\"`")
    # URL Scheme Guard: allow only http and https
    if re.match(r"^(?:file|javascript|data|about):", clean_url, re.I):
        return "Access denied: unsafe URL protocol, sir."
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        clean_url = "https://" + clean_url

    try:
        domain = urllib.parse.urlparse(clean_url).netloc or clean_url
        subprocess.run(["open", clean_url], check=True)
        return f"Opening {domain}, sir."
    except Exception as e:
        return f"Failed to open {url}: {e}"


def control_browser_tab(action):
    browser = get_active_browser()
    if not browser:
        return "There are currently no active web browsers open, sir."

    keystrokes = {
        "close_tab": 'keystroke "w" using {command down}',
        "new_tab": 'keystroke "t" using {command down}',
        "reload": 'keystroke "r" using {command down}',
        "next_tab": 'keystroke "]" using {command down, shift down}',
        "prev_tab": 'keystroke "[" using {command down, shift down}',
    }
    keystroke = keystrokes.get(action)
    if not keystroke:
        return f"Unsupported browser action: {action}, sir."

    # Activate browser explicitly first so keystroke doesn't hit terminal/IDE
    script = f'''
    tell application "{browser}" to activate
    tell application "System Events" to {keystroke}
    '''
    try:
        subprocess.run(["osascript", "-e", script], check=True)
        replies = {
            "close_tab": f"Closed active tab in {browser}, sir.",
            "new_tab": f"New tab opened in {browser}, sir.",
            "reload": f"Reloaded tab in {browser}, sir.",
            "next_tab": f"Switched to next tab in {browser}, sir.",
            "prev_tab": f"Switched to previous tab in {browser}, sir."
        }
        return replies.get(action, "Done, sir.")
    except Exception as e:
        return f"Failed to execute tab command on {browser}: {e}"
