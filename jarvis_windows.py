"""macOS Window Management & Workspace Controller for NIKO."""
import subprocess


def _get_screen_dimensions():
    """Returns (width, height, usable_height, menu_bar_offset) of the primary display."""
    try:
        from AppKit import NSScreen
        screen = NSScreen.mainScreen()
        frame = screen.frame()
        visible = screen.visibleFrame()
        w = int(visible.size.width)
        h = int(visible.size.height)
        offset_y = int(frame.size.height - visible.origin.y - visible.size.height)
        return w, h, offset_y
    except Exception:
        pass

    script = '''
    tell application "Finder"
        set b to bounds of window of desktop
        return (item 3 of b as string) & "x" & (item 4 of b as string)
    end tell
    '''
    try:
        res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and "x" in res.stdout:
            w, h = res.stdout.strip().split("x")
            return int(w), int(h) - 28, 28
    except Exception as e:
        print(f"  [Window Manager] Error getting bounds: {e}")
    return 1920, 1052, 28


def maximize_active_window():
    """Expand the frontmost application window to fill the screen beneath the menu bar."""
    w, usable_h, menu_bar = _get_screen_dimensions()
    script = f'''
    tell application "System Events"
        set frontApp to first application process whose frontmost is true
        if (count of windows of frontApp) > 0 then
            set frontWin to front window of frontApp
            try
                set position of frontWin to {{0, {menu_bar}}}
                set size of frontWin to {{{w}, {usable_h}}}
                return name of frontApp
            on error
                return "could_not_resize"
            end try
        end if
    end tell
    '''
    try:
        res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            out = res.stdout.strip()
            if out and out != "could_not_resize":
                return f"Maximized {out} to fill your screen, sir."
            elif out == "could_not_resize":
                return "The active window does not support resizing, sir."
    except Exception as e:
        print(f"  [Window Manager] Maximize error: {e}")
    return "I couldn't resize the active window, sir."


def tile_active_window(side="left"):
    """Snap the active window to the left or right half of the display."""
    w, usable_h, menu_bar = _get_screen_dimensions()
    half_w = int(w / 2)
    pos_x = 0 if side.lower() == "left" else half_w

    script = f'''
    tell application "System Events"
        set frontApp to first application process whose frontmost is true
        if (count of windows of frontApp) > 0 then
            set frontWin to front window of frontApp
            try
                set position of frontWin to {{{pos_x}, {menu_bar}}}
                set size of frontWin to {{{half_w}, {usable_h}}}
                return name of frontApp
            on error
                return "could_not_resize"
            end try
        end if
    end tell
    '''
    try:
        res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            out = res.stdout.strip()
            if out and out != "could_not_resize":
                return f"Tiled {out} to the {side}, sir."
            elif out == "could_not_resize":
                return "The active window does not support resizing, sir."
    except Exception as e:
        print(f"  [Window Manager] Tile error: {e}")
    return f"Unable to tile the window to the {side}, sir."


def center_active_window():
    """Center the active window on screen with a clean 75% comfortable margin."""
    w, usable_h, menu_bar = _get_screen_dimensions()
    win_w = int(w * 0.75)
    win_h = int(usable_h * 0.85)
    pos_x = int((w - win_w) / 2)
    pos_y = menu_bar + int((usable_h - win_h) / 2)

    script = f'''
    tell application "System Events"
        set frontApp to first application process whose frontmost is true
        if (count of windows of frontApp) > 0 then
            set frontWin to front window of frontApp
            try
                set position of frontWin to {{{pos_x}, {pos_y}}}
                set size of frontWin to {{{win_w}, {win_h}}}
                return name of frontApp
            on error
                return "could_not_resize"
            end try
        end if
    end tell
    '''
    try:
        res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            out = res.stdout.strip()
            if out and out != "could_not_resize":
                return f"Centered {out} on screen, sir."
            elif out == "could_not_resize":
                return "The active window does not support resizing, sir."
    except Exception as e:
        print(f"  [Window Manager] Center error: {e}")
    return "I couldn't center the active window, sir."


def hide_other_applications():
    """Hide all background applications for focused productivity."""
    script = '''
    tell application "System Events"
        set frontApp to first application process whose frontmost is true
        set visible of (every application process whose frontmost is false and visible is true) to false
        return name of frontApp
    end tell
    '''
    try:
        res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and res.stdout.strip():
            return f"Focused on {res.stdout.strip()}. All other background applications hidden, sir."
    except Exception as e:
        print(f"  [Window Manager] Focus error: {e}")
    return "Could not hide background applications, sir."
