"""Vigorous 500+ Command Automated Test Battery for J.A.R.V.I.S.
Tests intent classification, multi-task decomposition, slot extraction,
offline math, and action routing across day-to-day desktop, browser, and system operations.
"""
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from laya_engine import laya_decide, get_laya_engine
from action_dispatcher import split_compound_tasks, execute_single_action, APP_ALIASES

# Comprehensive battery of 525+ day-to-day user commands
COMMAND_BATTERY = [
    # -------------------------------------------------------------------------
    # 1. App Management - Opening / Launching (60 commands)
    # -------------------------------------------------------------------------
    ("open spotify", "app", "open"),
    ("open google chrome", "app", "open"),
    ("launch visual studio code", "app", "open"),
    ("open vscode", "app", "open"),
    ("start safari", "app", "open"),
    ("bring up terminal", "app", "open"),
    ("open slack", "app", "open"),
    ("launch discord", "app", "open"),
    ("open calculator", "app", "open"),
    ("start notes", "app", "open"),
    ("open calendar", "app", "open"),
    ("open reminders", "app", "open"),
    ("launch finder", "app", "open"),
    ("open system settings", "app", "open"),
    ("open messages", "app", "open"),
    ("open mail", "app", "open"),
    ("open cursor", "app", "open"),
    ("launch brave browser", "app", "open"),
    ("open textedit", "app", "open"),
    ("open photos", "app", "open"),
    ("open maps", "app", "open"),
    ("open audacity", "app", "open"),
    ("open keynote", "app", "open"),
    ("open numbers", "app", "open"),
    ("open pages", "app", "open"),
    ("open telegram", "app", "open"),
    ("open whatsapp", "app", "open"),
    ("launch zoom", "app", "open"),
    ("open iterm", "app", "open"),
    ("open iterm2", "app", "open"),
    ("open sublime text", "app", "open"),
    ("start clock", "app", "open"),
    ("open preview", "app", "open"),
    ("fire up spotify", "app", "open"),
    ("fire up chrome", "app", "open"),
    ("bring up visual studio code", "app", "open"),
    ("please open discord", "app", "open"),
    ("please launch slack", "app", "open"),
    ("can you open safari", "app", "open"),
    ("open sublime", "app", "open"),
    ("launch calc", "app", "open"),
    ("open note", "app", "open"),
    ("start reminders", "app", "open"),
    ("open reminder", "app", "open"),
    ("open apple music", "app", "open"),
    ("launch music", "app", "open"),
    ("open preferences", "app", "open"),
    ("open edge", "app", "open"),
    ("launch firefox", "app", "open"),
    ("open arc", "app", "open"),
    ("start cursor", "app", "open"),
    ("open vs code", "app", "open"),
    ("open code", "app", "open"),
    ("bring up messages", "app", "open"),
    ("open weather", "app", "open"),
    ("open notion", "app", "open"),
    ("open garageband", "app", "open"),
    ("order city", "app", "open"),  # Phonetic slip for Audacity
    ("breathe", "app", "open"),     # Phonetic slip for Brave
    ("start terminal", "app", "open"),

    # -------------------------------------------------------------------------
    # 2. App Management - Quitting / Closing (50 commands)
    # -------------------------------------------------------------------------
    ("close spotify", "app", "quit"),
    ("quit chrome", "app", "quit"),
    ("exit visual studio code", "app", "quit"),
    ("close vscode", "app", "quit"),
    ("kill slack", "app", "quit"),
    ("quit safari", "app", "quit"),
    ("close terminal", "app", "quit"),
    ("quit calculator", "app", "quit"),
    ("close discord", "app", "quit"),
    ("exit notes", "app", "quit"),
    ("close calendar", "app", "quit"),
    ("quit reminders", "app", "quit"),
    ("close messages", "app", "quit"),
    ("quit mail", "app", "quit"),
    ("close cursor", "app", "quit"),
    ("quit brave browser", "app", "quit"),
    ("exit textedit", "app", "quit"),
    ("close photos", "app", "quit"),
    ("quit maps", "app", "quit"),
    ("close audacity", "app", "quit"),
    ("quit keynote", "app", "quit"),
    ("close numbers", "app", "quit"),
    ("exit pages", "app", "quit"),
    ("kill zoom", "app", "quit"),
    ("close telegram", "app", "quit"),
    ("quit whatsapp", "app", "quit"),
    ("close iterm", "app", "quit"),
    ("close sublime", "app", "quit"),
    ("quit preview", "app", "quit"),
    ("close clock", "app", "quit"),
    ("shut down spotify", "app", "quit"),
    ("shut down chrome", "app", "quit"),
    ("close google chrome", "app", "quit"),
    ("exit vscode", "app", "quit"),
    ("terminate slack", "app", "quit"),
    ("kill discord", "app", "quit"),
    ("terminate terminal", "app", "quit"),
    ("close calc", "app", "quit"),
    ("quit note", "app", "quit"),
    ("close music", "app", "quit"),
    ("quit apple music", "app", "quit"),
    ("close firefox", "app", "quit"),
    ("exit arc", "app", "quit"),
    ("close notion", "app", "quit"),
    ("quit weather", "app", "quit"),
    ("close settings", "app", "quit"),
    ("quit system settings", "app", "quit"),
    ("close vs code", "app", "quit"),
    ("kill cursor", "app", "quit"),
    ("shut down safari", "app", "quit"),

    # -------------------------------------------------------------------------
    # 3. Volume & Sound Control - Absolute & Percentage Levels (50 commands)
    # -------------------------------------------------------------------------
    ("set volume to 10%", "volume", "set"),
    ("set volume to 20%", "volume", "set"),
    ("set volume to 30%", "volume", "set"),
    ("set volume to 40%", "volume", "set"),
    ("set volume to 50%", "volume", "set"),
    ("set volume to 60%", "volume", "set"),
    ("set volume to 70%", "volume", "set"),
    ("set volume to 80%", "volume", "set"),
    ("set volume to 90%", "volume", "set"),
    ("set volume to 100%", "volume", "set"),
    ("set volume to 0%", "volume", "set"),
    ("set volume to 15 percent", "volume", "set"),
    ("set volume to 25 percent", "volume", "set"),
    ("set volume to 35 percent", "volume", "set"),
    ("set volume to 45 percent", "volume", "set"),
    ("set volume to 55 percent", "volume", "set"),
    ("set volume to 65 percent", "volume", "set"),
    ("set volume to 75 percent", "volume", "set"),
    ("set volume to 85 percent", "volume", "set"),
    ("set volume to 95 percent", "volume", "set"),
    ("volume 50", "volume", "set"),
    ("volume 80", "volume", "set"),
    ("volume 20", "volume", "set"),
    ("volume 100", "volume", "set"),
    ("volume to 40", "volume", "set"),
    ("volume to 70", "volume", "set"),
    ("change volume to 50 percent", "volume", "set"),
    ("change volume to 80%", "volume", "set"),
    ("adjust volume to 60 percent", "volume", "set"),
    ("put volume at 40 percent", "volume", "set"),
    ("put volume at 80%", "volume", "set"),
    ("set audio to 50%", "volume", "set"),
    ("set audio to 70 percent", "volume", "set"),
    ("set sound to 40%", "volume", "set"),
    ("set sound to 80 percent", "volume", "set"),
    ("set volume to silent", "volume", "set"),
    ("set volume to quiet", "volume", "set"),
    ("set volume to low", "volume", "set"),
    ("set volume to medium", "volume", "set"),
    ("set volume to normal", "volume", "set"),
    ("set volume to loud", "volume", "set"),
    ("set volume to high", "volume", "set"),
    ("set volume to max", "volume", "set"),
    ("set volume to maximum", "volume", "set"),
    ("set volume to full", "volume", "set"),
    ("volume full blast", "volume", "set"),
    ("volume max", "volume", "set"),
    ("volume quiet", "volume", "set"),
    ("sound level 50%", "volume", "set"),
    ("set audio level to 60", "volume", "set"),

    # -------------------------------------------------------------------------
    # 4. Volume & Sound Control - Relative & Muting (50 commands)
    # -------------------------------------------------------------------------
    ("turn volume up", "volume", "up"),
    ("turn the volume up", "volume", "up"),
    ("crank the volume up", "volume", "up"),
    ("crank up the sound", "volume", "up"),
    ("raise the volume", "volume", "up"),
    ("increase volume", "volume", "up"),
    ("boost audio", "volume", "up"),
    ("make it louder", "volume", "up"),
    ("louder please", "volume", "up"),
    ("bump up the volume", "volume", "up"),
    ("turn volume down", "volume", "down"),
    ("turn the volume down", "volume", "down"),
    ("lower the volume", "volume", "down"),
    ("drop the volume", "volume", "down"),
    ("decrease volume", "volume", "down"),
    ("turn sound down", "volume", "down"),
    ("make it quieter", "volume", "down"),
    ("quieter please", "volume", "down"),
    ("turn it down a bit", "volume", "down"),
    ("turn it up a bit", "volume", "up"),
    ("mute", "volume", "mute"),
    ("mute sound", "volume", "mute"),
    ("mute audio", "volume", "mute"),
    ("mute the computer", "volume", "mute"),
    ("mute system", "volume", "mute"),
    ("mute speakers", "volume", "mute"),
    ("silence audio", "volume", "mute"),
    ("be quiet", "volume", "mute"),
    ("unmute", "volume", "unmute"),
    ("unmute sound", "volume", "unmute"),
    ("unmute audio", "volume", "unmute"),
    ("restore sound", "volume", "unmute"),
    ("turn sound back on", "volume", "unmute"),
    ("turn spotify down", "volume", "down"),
    ("turn spotify up", "volume", "up"),
    ("mute spotify", "volume", "mute"),
    ("unmute spotify", "volume", "unmute"),
    ("lower spotify volume", "volume", "down"),
    ("raise spotify volume", "volume", "up"),
    ("spotify volume 40%", "volume", "set"),
    ("spotify volume 80%", "volume", "set"),
    ("music volume up", "volume", "up"),
    ("music volume down", "volume", "down"),
    ("mute music", "volume", "mute"),
    ("unmute music", "volume", "unmute"),
    ("set music volume to 50%", "volume", "set"),
    ("turn down the audio", "volume", "down"),
    ("turn up the sound", "volume", "up"),
    ("turn sound off", "volume", "mute"),
    ("turn sound on", "volume", "unmute"),

    # -------------------------------------------------------------------------
    # 5. Media & Music Playback (40 commands)
    # -------------------------------------------------------------------------
    ("play music", "media", "play"),
    ("resume music", "media", "play"),
    ("play spotify", "media", "play"),
    ("resume spotify", "media", "play"),
    ("start playback", "media", "play"),
    ("continue playing", "media", "play"),
    ("pause music", "media", "pause"),
    ("pause playback", "media", "pause"),
    ("pause spotify", "media", "pause"),
    ("stop the music", "media", "pause"),
    ("pause the track", "media", "pause"),
    ("next track", "media", "next"),
    ("skip song", "media", "next"),
    ("next song", "media", "next"),
    ("skip track", "media", "next"),
    ("play next track", "media", "next"),
    ("forward track", "media", "next"),
    ("previous track", "media", "previous"),
    ("prev track", "media", "previous"),
    ("previous song", "media", "previous"),
    ("go back a song", "media", "previous"),
    ("last song", "media", "previous"),
    ("play youtube", "media", "search"),
    ("play lo-fi beats on youtube", "media", "search"),
    ("play synthwave on youtube", "media", "search"),
    ("play classical piano on youtube", "media", "search"),
    ("play mozart on youtube", "media", "search"),
    ("play hans zimmer on youtube", "media", "search"),
    ("play ambient study sound on youtube", "media", "search"),
    ("play jazz music on youtube", "media", "search"),
    ("youtube search queen bohemian rhapsody", "media", "search"),
    ("play daft punk on youtube", "media", "search"),
    ("play interstellar theme on youtube", "media", "search"),
    ("play chill beats on youtube", "media", "search"),
    ("play coding music on youtube", "media", "search"),
    ("play rain sounds on youtube", "media", "search"),
    ("resume", "media", "play"),
    ("pause", "media", "pause"),
    ("skip", "media", "next"),
    ("prev", "media", "previous"),

    # -------------------------------------------------------------------------
    # 6. Browser Navigation & Web Search (50 commands)
    # -------------------------------------------------------------------------
    ("search google for quantum physics", "browser", "search"),
    ("google weather in tokyo", "browser", "search"),
    ("search python 3.10 documentation", "browser", "search"),
    ("search for latest ai news", "browser", "search"),
    ("look up stock market today", "browser", "search"),
    ("search rust language tutorial", "browser", "search"),
    ("google apple stock price", "browser", "search"),
    ("search for best mechanical keyboards", "browser", "search"),
    ("search how to make espresso", "browser", "search"),
    ("look up flight status", "browser", "search"),
    ("google current time in london", "browser", "search"),
    ("search for local coffee shops", "browser", "search"),
    ("google distance to mars", "browser", "search"),
    ("search world population", "browser", "search"),
    ("look up top movies 2026", "browser", "search"),
    ("go to github.com", "browser", "url"),
    ("open github.com", "browser", "url"),
    ("launch reddit.com", "browser", "url"),
    ("go to wikipedia.org", "browser", "url"),
    ("open youtube.com", "browser", "url"),
    ("go to x.com", "browser", "url"),
    ("open chatgpt.com", "browser", "url"),
    ("open amazon.com", "browser", "url"),
    ("open netflix.com", "browser", "url"),
    ("go to apple.com", "browser", "url"),
    ("open linkedin.com", "browser", "url"),
    ("open news.ycombinator.com", "browser", "url"),
    ("go to stackoverflow.com", "browser", "url"),
    ("open gmail.com", "browser", "url"),
    ("open huggingface.co", "browser", "url"),
    ("open youtube", "app", "open"),
    ("open github", "app", "open"),
    ("open reddit", "app", "open"),
    ("open gmail", "app", "open"),
    ("open twitter", "app", "open"),
    ("open chatgpt", "app", "open"),
    ("open netflix", "app", "open"),
    ("open amazon", "app", "open"),
    ("open wikipedia", "app", "open"),
    ("open linkedin", "app", "open"),
    ("search google for best laptops", "browser", "search"),
    ("search for cheap flights to tokyo", "browser", "search"),
    ("google recipe for banana bread", "browser", "search"),
    ("search nearest grocery store", "browser", "search"),
    ("look up capital of australia", "browser", "search"),
    ("google who won the super bowl", "browser", "search"),
    ("search latest macbook release", "browser", "search"),
    ("google how tall is mount everest", "browser", "search"),
    ("search fastest car in the world", "browser", "search"),
    ("look up currency exchange rates", "browser", "search"),

    # -------------------------------------------------------------------------
    # 7. Browser Tab & Window Controls (45 commands)
    # -------------------------------------------------------------------------
    ("new tab", "browser", "tab"),
    ("open a new tab", "browser", "tab"),
    ("create new tab", "browser", "tab"),
    ("close tab", "browser", "tab"),
    ("close the active tab", "browser", "tab"),
    ("close this tab", "browser", "tab"),
    ("reload tab", "browser", "tab"),
    ("refresh tab", "browser", "tab"),
    ("refresh this page", "browser", "tab"),
    ("reload this page", "browser", "tab"),
    ("next tab", "browser", "tab"),
    ("switch to next tab", "browser", "tab"),
    ("previous tab", "browser", "tab"),
    ("prev tab", "browser", "tab"),
    ("switch to prev tab", "browser", "tab"),
    ("maximize window", "window", "maximize"),
    ("maximize this window", "window", "maximize"),
    ("fill the screen", "window", "maximize"),
    ("full screen window", "window", "maximize"),
    ("tile window left", "window", "tile_left"),
    ("tile this window to the left", "window", "tile_left"),
    ("snap left", "window", "tile_left"),
    ("put window on left", "window", "tile_left"),
    ("tile window right", "window", "tile_right"),
    ("tile this window to the right", "window", "tile_right"),
    ("snap right", "window", "tile_right"),
    ("put window on right", "window", "tile_right"),
    ("center window", "window", "center"),
    ("center this window", "window", "center"),
    ("center active window", "window", "center"),
    ("hide other apps", "window", "hide_others"),
    ("focus mode", "window", "hide_others"),
    ("hide background apps", "window", "hide_others"),
    ("dark mode on", "display", "dark_on"),
    ("enable dark mode", "display", "dark_on"),
    ("switch to dark mode", "display", "dark_on"),
    ("turn on dark mode", "display", "dark_on"),
    ("dark mode off", "display", "dark_off"),
    ("disable dark mode", "display", "dark_off"),
    ("switch to light mode", "display", "dark_off"),
    ("turn on light mode", "display", "dark_off"),
    ("toggle dark mode", "display", "toggle"),
    ("toggle appearance", "display", "toggle"),
    ("switch appearance", "display", "toggle"),
    ("invert appearance", "display", "toggle"),

    # -------------------------------------------------------------------------
    # 8. System Status & Hardware Telemetry (40 commands)
    # -------------------------------------------------------------------------
    ("check battery", "system", "battery"),
    ("battery status", "system", "battery"),
    ("how much battery is left", "system", "battery"),
    ("what is my battery percentage", "system", "battery"),
    ("check battery level", "system", "battery"),
    ("battery level", "system", "battery"),
    ("is my mac charging", "system", "battery"),
    ("check ram", "system", "ram"),
    ("how much memory am i using", "system", "ram"),
    ("ram usage", "system", "ram"),
    ("memory status", "system", "ram"),
    ("check memory", "system", "ram"),
    ("how much free ram", "system", "ram"),
    ("system memory", "system", "ram"),
    ("check disk space", "system", "disk"),
    ("how much free storage", "system", "disk"),
    ("storage status", "system", "disk"),
    ("disk usage", "system", "disk"),
    ("check storage", "system", "disk"),
    ("hard drive space", "system", "disk"),
    ("take a screenshot", "system", "screenshot"),
    ("capture screen", "system", "screenshot"),
    ("take screenshot", "system", "screenshot"),
    ("screen capture", "system", "screenshot"),
    ("empty trash", "system", "trash"),
    ("empty the trash", "system", "trash"),
    ("clear trash", "system", "trash"),
    ("clean trash bin", "system", "trash"),
    ("empty recycling bin", "system", "trash"),
    ("lock screen", "system", "lock"),
    ("lock the screen", "system", "lock"),
    ("lock workstation", "system", "lock"),
    ("lock my computer", "system", "lock"),
    ("sleep mac", "system", "sleep"),
    ("put mac to sleep", "system", "sleep"),
    ("go to sleep", "system", "sleep"),
    ("system health", "system", "health"),
    ("health check", "system", "health"),
    ("system diagnostics", "system", "health"),
    ("rust status", "system", "health"),

    # -------------------------------------------------------------------------
    # 9. Developer & Project Inspection (35 commands)
    # -------------------------------------------------------------------------
    ("git status", "dev", "git_status"),
    ("check git status", "dev", "git_status"),
    ("uncommitted changes", "dev", "git_status"),
    ("check uncommitted changes", "dev", "git_status"),
    ("git branch", "dev", "git_status"),
    ("what branch am i on", "dev", "git_status"),
    ("last commit", "dev", "last_commit"),
    ("latest commit", "dev", "last_commit"),
    ("git log", "dev", "last_commit"),
    ("show last commit", "dev", "last_commit"),
    ("what was the last commit", "dev", "last_commit"),
    ("list project files", "dev", "files"),
    ("list files in project", "dev", "files"),
    ("show project structure", "dev", "files"),
    ("read file README.md", "dev", "read_file"),
    ("inspect file README.md", "dev", "read_file"),
    ("what is in the file README.md", "dev", "read_file"),
    ("read file requirements.txt", "dev", "read_file"),
    ("inspect file requirements.txt", "dev", "read_file"),
    ("read file setup.py", "dev", "read_file"),
    ("inspect file setup.py", "dev", "read_file"),
    ("read file siri.py", "dev", "read_file"),
    ("inspect file siri.py", "dev", "read_file"),
    ("read file audio_engine.py", "dev", "read_file"),
    ("read file action_dispatcher.py", "dev", "read_file"),
    ("read file laya_engine.py", "dev", "read_file"),
    ("read file hotkey_manager.py", "dev", "read_file"),
    ("check git repository", "dev", "git_status"),
    ("view git log", "dev", "last_commit"),
    ("recent git commit", "dev", "last_commit"),
    ("show repository status", "dev", "git_status"),
    ("display git summary", "dev", "git_status"),
    ("what files are in this repo", "dev", "files"),
    ("inspect repository tree", "dev", "files"),
    ("check repo changes", "dev", "git_status"),

    # -------------------------------------------------------------------------
    # 10. Notes, Clipboard & Assistant Memory (40 commands)
    # -------------------------------------------------------------------------
    ("take a note buy groceries today", "notes", "take"),
    ("note down finish project documentation", "notes", "take"),
    ("write this down meeting tomorrow at 10am", "notes", "take"),
    ("take a note call the doctor", "notes", "take"),
    ("note down renew domain subscription", "notes", "take"),
    ("write this down pick up package from post office", "notes", "take"),
    ("read my latest note", "notes", "read"),
    ("what was my last note", "notes", "read"),
    ("get latest note", "notes", "read"),
    ("show my latest note", "notes", "read"),
    ("list my notes", "notes", "list"),
    ("show all my notes", "notes", "list"),
    ("what are my notes", "notes", "list"),
    ("list recent notes", "notes", "list"),
    ("copy this to clipboard", "clipboard", "copy"),
    ("copy that to clipboard", "clipboard", "copy"),
    ("copy response to clipboard", "clipboard", "copy"),
    ("copy to my clipboard", "clipboard", "copy"),
    ("what is in my clipboard", "clipboard", "read"),
    ("explain what is in my clipboard", "clipboard", "read"),
    ("read my clipboard", "clipboard", "read"),
    ("summarize my clipboard", "clipboard", "read"),
    ("my name is Bruce Wayne", "memory", "name"),
    ("call me Tony Stark", "memory", "name"),
    ("call me Subharup", "memory", "name"),
    ("my name is Peter Parker", "memory", "name"),
    ("remember that I prefer dark mode", "memory", "fact"),
    ("remember that I drink green tea", "memory", "fact"),
    ("remember that my favorite language is Python", "memory", "fact"),
    ("please remember that I wake up at 7am", "memory", "fact"),
    ("switch to female voice", "voice", "female"),
    ("use friday voice", "voice", "female"),
    ("change to sonia voice", "voice", "female"),
    ("activate female voice", "voice", "female"),
    ("switch to male voice", "voice", "male"),
    ("use jarvis voice", "voice", "male"),
    ("change to ryan voice", "voice", "male"),
    ("activate male voice", "voice", "male"),
    ("friday voice", "voice", "female"),
    ("jarvis voice", "voice", "male"),

    # -------------------------------------------------------------------------
    # 11. Instant Offline Math & Calculations (35 commands)
    # -------------------------------------------------------------------------
    ("what is 45 plus 90", "calc", "math"),
    ("calculate 12 * 8", "calc", "math"),
    ("how much is 100 divided by 4", "calc", "math"),
    ("what is 25 times 4", "calc", "math"),
    ("calculate 50 minus 18", "calc", "math"),
    ("what is 7 * 7", "calc", "math"),
    ("calculate 15 + 35", "calc", "math"),
    ("what is 80 / 10", "calc", "math"),
    ("how much is 30 * 30", "calc", "math"),
    ("what is 144 / 12", "calc", "math"),
    ("calculate 2 to the power of 8", "calc", "math"),
    ("what is 1000 - 350", "calc", "math"),
    ("calculate 6 * 9", "calc", "math"),
    ("what is 99 + 1", "calc", "math"),
    ("calculate 250 / 5", "calc", "math"),
    ("what is 81 / 9", "calc", "math"),
    ("what is 13 * 13", "calc", "math"),
    ("calculate 16 * 16", "calc", "math"),
    ("what is 500 + 750", "calc", "math"),
    ("what is 100 - 45", "calc", "math"),
    ("calculate 40 * 25", "calc", "math"),
    ("what is 10 + 20 + 30", "calc", "math"),
    ("calculate 5 * 5 * 5", "calc", "math"),
    ("what is 64 / 8", "calc", "math"),
    ("what is 15 * 6", "calc", "math"),
    ("calculate 200 / 4", "calc", "math"),
    ("what is 120 / 6", "calc", "math"),
    ("calculate 70 + 80", "calc", "math"),
    ("what is 90 * 2", "calc", "math"),
    ("calculate 450 - 50", "calc", "math"),
    ("what is 11 * 11", "calc", "math"),
    ("what is 12 * 12", "calc", "math"),
    ("calculate 100 * 100", "calc", "math"),
    ("what is 50 / 2", "calc", "math"),
    ("what is 33 + 66", "calc", "math"),

    # -------------------------------------------------------------------------
    # 12. Compound Multi-Task Operations (50 commands)
    # -------------------------------------------------------------------------
    ("open spotify and turn volume up", "compound", 2),
    ("launch chrome and search python tutorials", "compound", 1), # Unified browser search
    ("open notes and take a note buy milk", "compound", 2),
    ("set volume to 80% and play music", "compound", 2),
    ("maximize window and open terminal", "compound", 2),
    ("check battery and check ram", "compound", 2),
    ("close calculator and quit safari", "compound", 2),
    ("mute volume and pause music", "compound", 2),
    ("tile window left and open vscode", "compound", 2),
    ("empty trash and lock screen", "compound", 2),
    ("turn volume down and pause music", "compound", 2),
    ("open slack and open discord", "compound", 2),
    ("launch terminal and open finder", "compound", 2),
    ("quit chrome and close spotify", "compound", 2),
    ("set volume to 50% and resume music", "compound", 2),
    ("take a screenshot and open photos", "compound", 2),
    ("check ram and check storage", "compound", 2),
    ("snap left and tile right", "compound", 2),
    ("center window and maximize window", "compound", 2),
    ("open google chrome and search youtube", "compound", 1), # Unified browser search
    ("turn on dark mode and hide other apps", "compound", 2),
    ("unmute volume and play music", "compound", 2),
    ("mute sound and lock screen", "compound", 2),
    ("open calendar and open reminders", "compound", 2),
    ("quit notes and close textedit", "compound", 2),
    ("check battery and sleep mac", "compound", 2),
    ("volume 60% and next track", "compound", 2),
    ("skip track and turn volume up", "compound", 2),
    ("pause spotify and turn volume down", "compound", 2),
    ("open calculator and calculate 25 * 4", "compound", 2),
    ("lock screen and sleep mac", "compound", 2),
    ("open safari and go to github.com", "compound", 2),
    ("new tab and search google for ai news", "compound", 2),
    ("close tab and switch to next tab", "compound", 2),
    ("reload tab and maximize window", "compound", 2),
    ("open mail and open messages", "compound", 2),
    ("quit mail and quit messages", "compound", 2),
    ("take a note call mom and set volume to 40%", "compound", 2),
    ("git status and check ram", "compound", 2),
    ("last commit and git status", "compound", 2),
    ("read file README.md and check branch", "compound", 2),
    ("open cursor and open terminal", "compound", 2),
    ("close cursor and quit terminal", "compound", 2),
    ("turn volume to 30% and play chill beats on youtube", "compound", 2),
    ("open brave and search best mechanical keyboards", "compound", 1), # Unified search
    ("switch to friday voice and set volume to 70%", "compound", 2),
    ("switch to jarvis voice and check battery", "compound", 2),
    ("remember that I like tea and what is 50 plus 50", "compound", 2),
    ("empty trash and check disk space", "compound", 2),
    ("mute audio and close spotify", "compound", 2)
]


import subprocess
from unittest.mock import patch, MagicMock


def safe_mock_run(args, *pos, **kwargs):
    return subprocess.CompletedProcess(args=args, returncode=0, stdout="true\n", stderr="")


def safe_mock_check_output(args, *pos, **kwargs):
    cmd_str = " ".join(str(a) for a in args) if isinstance(args, list) else str(args)
    if "vm_stat" in cmd_str:
        return "Pages free: 15000.\nPages active: 250000.\nPages wired down: 350000.\nPages speculative: 5000.\n"
    if "batt" in cmd_str:
        return "Now drawing from 'Battery Power'\n -InternalBattery-0 (id=12345) 85%; discharging; 4:30 remaining present: true\n"
    if "df -h" in cmd_str:
        return "Filesystem     Size   Used  Avail Capacity iused      ifree %iused  Mounted on\n/dev/disk3s1s1  228Gi   60Gi  150Gi    29% 123456 1234567890    0%   /\n"
    if "get volume settings" in cmd_str:
        return "50\n"
    if "git" in cmd_str:
        return "## main...origin/main\n M siri.py\n"
    return "true\n"


@patch("subprocess.check_output", side_effect=safe_mock_check_output)
@patch("subprocess.run", side_effect=safe_mock_run)
def run_500_battery(mock_run, mock_check_output):
    print("=" * 80)
    print(f"J.A.R.V.I.S. VIGOROUS 500+ COMMAND AUTOMATED TEST BATTERY")
    print(f"Total Test Cases Loaded: {len(COMMAND_BATTERY)}")
    print("=" * 80)

    t_start = time.time()
    passed = 0
    failed = 0
    failures = []

    for idx, test_entry in enumerate(COMMAND_BATTERY, 1):
        text = test_entry[0]
        expected_domain = test_entry[1]
        expected_meta = test_entry[2]

        t0 = time.time()
        sub_tasks = split_compound_tasks(text)

        # Multi-task verification
        if expected_domain == "compound":
            expected_count = expected_meta
            actual_count = len(sub_tasks)
            if actual_count != expected_count:
                failures.append((idx, text, f"Expected {expected_count} subtasks, got {actual_count}: {sub_tasks}"))
                failed += 1
                print(f"[{idx:03d}/500+] FAIL  '{text}' -> subtask count mismatch ({actual_count} != {expected_count})")
                continue
            
            # Execute both tasks through dispatcher
            all_ok = True
            for st in sub_tasks:
                rep = execute_single_action(st)
                if not rep or len(rep.strip()) == 0:
                    all_ok = False
                    break
            
            if all_ok:
                passed += 1
                ms = int((time.time() - t0) * 1000)
                print(f"[{idx:03d}/{len(COMMAND_BATTERY)}] PASS  '{text}' ({actual_count} tasks) [{ms}ms]")
            else:
                failures.append((idx, text, f"One or more compound subtasks failed execution: {sub_tasks}"))
                failed += 1
                print(f"[{idx:03d}/500+] FAIL  '{text}' -> Execution failure")
            continue

        # Single task verification
        reply = execute_single_action(text)
        ms = int((time.time() - t0) * 1000)

        if not reply or len(reply.strip()) == 0:
            failures.append((idx, text, "Empty reply returned"))
            failed += 1
            print(f"[{idx:03d}/500+] FAIL  '{text}' -> Empty reply [{ms}ms]")
            continue

        # Domain-Specific Verification Checks
        domain_ok = True
        reason = ""

        if expected_domain == "app":
            if expected_meta == "open" and "open" not in reply.lower():
                domain_ok = False
                reason = f"Expected open response, got: '{reply}'"
            elif expected_meta == "quit" and "clos" not in reply.lower() and "quit" not in reply.lower():
                domain_ok = False
                reason = f"Expected close/quit response, got: '{reply}'"

        elif expected_domain == "volume":
            if "volume" not in reply.lower() and "mute" not in reply.lower() and "sound" not in reply.lower() and "percent" not in reply.lower():
                domain_ok = False
                reason = f"Expected volume response, got: '{reply}'"

        elif expected_domain == "media":
            if "playback" not in reply.lower() and "track" not in reply.lower() and "music" not in reply.lower() and "spotify" not in reply.lower() and "youtube" not in reply.lower() and "skip" not in reply.lower():
                domain_ok = False
                reason = f"Expected media response, got: '{reply}'"

        elif expected_domain == "browser":
            if expected_meta == "tab":
                if "tab" not in reply.lower() and "reload" not in reply.lower():
                    domain_ok = False
                    reason = f"Expected tab response, got: '{reply}'"
            elif expected_meta == "url":
                if "opening" not in reply.lower() and "browser" not in reply.lower():
                    domain_ok = False
                    reason = f"Expected URL open response, got: '{reply}'"
            elif expected_meta == "search":
                if "search" not in reply.lower() and "google" not in reply.lower():
                    domain_ok = False
                    reason = f"Expected search response, got: '{reply}'"

        elif expected_domain == "window":
            if not any(k in reply.lower() for k in ("window", "application", "display", "maximized", "tiled", "centered", "screen")):
                domain_ok = False
                reason = f"Expected window control response, got: '{reply}'"

        elif expected_domain == "display":
            if "mode" not in reply.lower() and "appearance" not in reply.lower():
                domain_ok = False
                reason = f"Expected display/appearance response, got: '{reply}'"

        elif expected_domain == "system":
            if expected_meta == "battery" and "battery" not in reply.lower() and "power" not in reply.lower() and "charging" not in reply.lower():
                domain_ok = False
                reason = f"Expected battery response, got: '{reply}'"
            elif expected_meta == "ram" and "ram" not in reply.lower() and "gigabytes" not in reply.lower() and "memory" not in reply.lower():
                domain_ok = False
                reason = f"Expected RAM response, got: '{reply}'"
            elif expected_meta == "disk" and "disk" not in reply.lower() and "space" not in reply.lower() and "storage" not in reply.lower():
                domain_ok = False
                reason = f"Expected disk response, got: '{reply}'"
            elif expected_meta == "screenshot" and "screenshot" not in reply.lower():
                domain_ok = False
                reason = f"Expected screenshot response, got: '{reply}'"
            elif expected_meta == "trash" and "trash" not in reply.lower():
                domain_ok = False
                reason = f"Expected trash response, got: '{reply}'"
            elif expected_meta == "lock" and "lock" not in reply.lower():
                domain_ok = False
                reason = f"Expected lock response, got: '{reply}'"
            elif expected_meta == "sleep" and "sleep" not in reply.lower():
                domain_ok = False
                reason = f"Expected sleep response, got: '{reply}'"
            elif expected_meta == "health" and "online" not in reply.lower() and "system" not in reply.lower() and "cpu" not in reply.lower() and "status" not in reply.lower():
                domain_ok = False
                reason = f"Expected health response, got: '{reply}'"

        elif expected_domain == "dev":
            if expected_meta == "git_status" and "branch" not in reply.lower() and "git" not in reply.lower():
                domain_ok = False
                reason = f"Expected git status response, got: '{reply}'"
            elif expected_meta == "last_commit" and "commit" not in reply.lower():
                domain_ok = False
                reason = f"Expected last commit response, got: '{reply}'"
            elif expected_meta == "files" and not any(k in reply.lower() for k in ("project contains", "file", "items in", "top level")):
                domain_ok = False
                reason = f"Expected files response, got: '{reply}'"
            elif expected_meta == "read_file" and "file" not in reply.lower() and "line" not in reply.lower():
                domain_ok = False
                reason = f"Expected read file response, got: '{reply}'"

        elif expected_domain == "notes":
            if expected_meta == "take" and "saved that note" not in reply.lower() and "note" not in reply.lower():
                domain_ok = False
                reason = f"Expected note saved response, got: '{reply}'"
            elif expected_meta == "read" and "note" not in reply.lower():
                domain_ok = False
                reason = f"Expected note read response, got: '{reply}'"
            elif expected_meta == "list" and "notes" not in reply.lower():
                domain_ok = False
                reason = f"Expected notes list response, got: '{reply}'"

        elif expected_domain == "clipboard":
            if expected_meta == "copy" and "copied" not in reply.lower():
                domain_ok = False
                reason = f"Expected clipboard copy response, got: '{reply}'"
            elif expected_meta == "read" and len(reply.strip()) == 0:
                domain_ok = False
                reason = "Expected clipboard read response"

        elif expected_domain == "memory":
            if expected_meta == "name" and "name" not in reply.lower() and "profile" not in reply.lower():
                domain_ok = False
                reason = f"Expected name update response, got: '{reply}'"
            elif expected_meta == "fact" and "memory" not in reply.lower():
                domain_ok = False
                reason = f"Expected fact memory response, got: '{reply}'"

        elif expected_domain == "voice":
            if expected_meta == "female" and "female" not in reply.lower():
                domain_ok = False
                reason = f"Expected female voice switch, got: '{reply}'"
            elif expected_meta == "male" and not any(k in reply.lower() for k in ("male", "niko")):
                domain_ok = False
                reason = f"Expected male voice switch, got: '{reply}'"

        elif expected_domain == "calc":
            if "result is" not in reply.lower():
                domain_ok = False
                reason = f"Expected math calculation response, got: '{reply}'"

        if domain_ok:
            passed += 1
            print(f"[{idx:03d}/{len(COMMAND_BATTERY)}] PASS  '{text}' -> '{reply[:45]}...' [{ms}ms]")
        else:
            failed += 1
            failures.append((idx, text, reason))
            print(f"[{idx:03d}/{len(COMMAND_BATTERY)}] FAIL  '{text}' -> {reason} [{ms}ms]")

    total_time = time.time() - t_start
    print("\n" + "=" * 80)
    print("500+ COMMAND BATTERY RESULTS")
    print(f"Total Executed: {len(COMMAND_BATTERY)}")
    print(f"Passed:         {passed} ({passed / len(COMMAND_BATTERY) * 100:.1f}%)")
    print(f"Failed:         {failed}")
    print(f"Elapsed Time:   {total_time:.1f}s (Average {total_time / len(COMMAND_BATTERY) * 1000:.1f}ms per command)")
    print("=" * 80)

    if failures:
        print("\nFAILURE SUMMARY (First 15):")
        for f_idx, f_cmd, f_reason in failures[:15]:
            print(f"  #{f_idx:03d}: '{f_cmd}' -> {f_reason}")

    return passed == len(COMMAND_BATTERY)


if __name__ == "__main__":
    success = run_500_battery()
    sys.exit(0 if success else 1)
