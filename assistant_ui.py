"""Small native macOS status window for the NIKO voice assistant."""
import json
import queue
import re
import sys
import threading
import time

import objc
from AppKit import (
    NSApp,
    NSApplication,
    NSApplicationActivationPolicyRegular,
    NSBackingStoreBuffered,
    NSMenu,
    NSMenuItem,
    NSButton,
    NSColor,
    NSEvent,
    NSEventMaskFlagsChanged,
    NSEventMaskKeyDown,
    NSEventModifierFlagOption,
    NSFont,
    NSMakePoint,
    NSMakeRect,
    NSScreen,
    NSSegmentedControl,
    NSSwitchButton,
    NSWindow,
    NSSecureTextField,
    NSTextField,
    NSView,
    NSVisualEffectBlendingModeBehindWindow,
    NSVisualEffectMaterialHUDWindow,
    NSVisualEffectStateActive,
    NSVisualEffectView,
    NSWindowStyleMaskBorderless,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskMiniaturizable,
    NSWindowStyleMaskFullSizeContentView,
    NSWindowStyleMaskTitled,
)
from Foundation import NSObject, NSTimer, NSUserDefaults, NSURL
from WebKit import WKWebView, WKWebViewConfiguration, WKUserContentController
from Quartz import CAGradientLayer, CGPointMake
from secrets_store import KEY_NAMES, get_secret, missing_secrets, save_secret
import os


BASE_HEIGHT, ROW = 154, 24
STICK_TOP, STICK_BOTTOM = 8, 32  # NSViewMinYMargin, NSViewMaxYMargin
NORMAL, FLOATING = 0, 3  # NSNormalWindowLevel, NSFloatingWindowLevel
HINTS = {"ptt": "Hold Alt to talk", "wake": "Hold Alt or “Hey Niko” to wake"}
MODES = ("ptt", "wake")

def _cg(r, g, b, a=1.0):
    return NSColor.colorWithRed_green_blue_alpha_(r, g, b, a).CGColor()

LINE_GRADIENTS = {
    "Ready": [
        (_cg(0.0, 0.85, 0.95, 0.85), _cg(0.2, 0.55, 0.98, 0.85)),   # Cyan -> Electric Blue
        (_cg(0.2, 0.55, 0.98, 0.85), _cg(0.48, 0.38, 0.95, 0.85)),  # Electric Blue -> Indigo
        (_cg(0.48, 0.38, 0.95, 0.85), _cg(0.75, 0.25, 0.90, 0.85)), # Indigo -> Violet
        (_cg(0.75, 0.25, 0.90, 0.85), _cg(0.95, 0.28, 0.65, 0.85)), # Violet -> Magenta
    ],
    "Listening": [
        (_cg(0.0, 1.0, 0.9), _cg(0.05, 0.7, 1.0)),     # Vivid Aqua -> Sky
        (_cg(0.05, 0.7, 1.0), _cg(0.25, 0.45, 1.0)),   # Sky -> Blue
        (_cg(0.25, 0.45, 1.0), _cg(0.55, 0.3, 0.98)),  # Blue -> Purple
        (_cg(0.55, 0.3, 0.98), _cg(0.85, 0.2, 0.85)),  # Purple -> Hot Pink
    ],
    "Thinking": [
        (_cg(0.5, 0.2, 1.0), _cg(0.8, 0.15, 0.95)),   # Deep Violet -> Magenta
        (_cg(0.65, 0.15, 0.95), _cg(0.92, 0.1, 0.8)),  # Magenta -> Hot Pink
        (_cg(0.8, 0.1, 0.85), _cg(1.0, 0.2, 0.6)),    # Hot Pink -> Coral
        (_cg(0.92, 0.15, 0.75), _cg(1.0, 0.35, 0.45)),# Coral -> Sunset
    ],
    "Speaking": [
        (_cg(0.1, 1.0, 0.65), _cg(0.0, 0.8, 0.8)),     # Mint -> Teal
        (_cg(0.15, 0.92, 0.75), _cg(0.0, 0.7, 0.92)),  # Teal -> Sky
        (_cg(0.0, 0.8, 0.88), _cg(0.15, 0.55, 0.98)),  # Cyan -> Royal Blue
        (_cg(0.1, 0.7, 0.95), _cg(0.38, 0.4, 0.95)),   # Royal Blue -> Indigo
    ]
}

STATUS_COLORS = {
    "Starting": NSColor.systemOrangeColor(),
    "Ready": NSColor.systemGreenColor(),
    "Listening": NSColor.systemRedColor(),
    "Transcribing": NSColor.systemBlueColor(),
    "Thinking": NSColor.systemPurpleColor(),
    "Doing it": NSColor.systemOrangeColor(),
    "Speaking": NSColor.systemTealColor(),
    "Something went wrong": NSColor.systemRedColor(),
    "Time's up": NSColor.systemYellowColor(),
}


def label(text, frame, size, color=None):
    view = NSTextField.labelWithString_(text)
    view.setFrame_(frame)
    view.setFont_(NSFont.systemFontOfSize_weight_(size, 0.5))
    view.setTextColor_(color or NSColor.labelColor())
    view.setLineBreakMode_(4)
    return view


class IslandScriptHandler(NSObject):
    def initWithDelegate_(self, delegate):
        self = objc.super(IslandScriptHandler, self).init()
        if self is None:
            return None
        self.delegate = delegate
        return self

    def userContentController_didReceiveScriptMessage_(self, ucc, message):
        try:
            body = str(message.body())
            if body == "click" and self.delegate:
                if getattr(self.delegate, "current_state", "") == "Speaking":
                    self.delegate.controls.put("pause_speech")
                elif getattr(self.delegate, "current_state", "") == "Listening":
                    self.delegate.controls.put("release")
                else:
                    try:
                        from AppKit import NSSound
                        s = NSSound.soundNamed_("Tink")
                        if s:
                            s.play()
                    except Exception:
                        pass
                    self.delegate.controls.put("press")
        except Exception as e:
            print("Pill click handler error:", e)


class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, _notification):
        self.controls = queue.Queue()
        self.option_down = False
        self.worker_started = False
        self.mode = NSUserDefaults.standardUserDefaults().stringForKey_("mode") or "ptt"
        if self.mode not in MODES:
            self.mode = "ptt"
        style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable
                 | NSWindowStyleMaskFullSizeContentView)
        self.panel = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, 420, 154), style, NSBackingStoreBuffered, False
        )
        self.panel.setTitle_("NIKO - Voice Assistant")
        self.panel.setTitlebarAppearsTransparent_(True)
        self.panel.setMovableByWindowBackground_(True)
        self.panel.setReleasedWhenClosed_(False)  # closing just hides it, the Dock icon brings it back
        self.on_top = NSUserDefaults.standardUserDefaults().boolForKey_("keep_on_top")
        self.panel.setLevel_(FLOATING if self.on_top else NORMAL)
        self._add_window_menu()
        self._add_voice_menu()
        self._setup_notch_window()
        self._setup_status_item()

        background = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, 420, 154))
        background.setMaterial_(NSVisualEffectMaterialHUDWindow)
        background.setBlendingMode_(NSVisualEffectBlendingModeBehindWindow)
        background.setState_(NSVisualEffectStateActive)
        background.setAutoresizingMask_(18)  # grow with the window
        self.panel.setContentView_(background)
        self.background = background
        self.timer_rows = []

        self.dot = label("●", NSMakeRect(25, 76, 24, 30), 18, NSColor.systemOrangeColor())
        self.status = label("Starting", NSMakeRect(55, 78, 330, 30), 22)
        self.detail = label("Loading Whisper…", NSMakeRect(27, 39, 365, 30), 14, NSColor.secondaryLabelColor())
        self.hint = label(HINTS[self.mode], NSMakeRect(27, 14, 220, 22), 12, NSColor.tertiaryLabelColor())
        for view in (self.dot, self.status, self.detail, self.hint):
            background.addSubview_(view)
        for view in (self.dot, self.status, self.detail):
            view.setAutoresizingMask_(STICK_TOP)
        self.hint.setAutoresizingMask_(STICK_BOTTOM)

        settings = NSButton.buttonWithTitle_target_action_("Settings…", self, "showSettings:")
        settings.setFrame_(NSMakeRect(335, 118, 73, 24))  # top right, in line with the title bar
        settings.setBezelStyle_(1)  # rounded, so the title shows
        settings.setControlSize_(1)  # small
        settings.setFont_(NSFont.systemFontOfSize_(11))
        settings.setAutoresizingMask_(STICK_TOP)
        background.addSubview_(settings)

        self.mode_switch = NSSegmentedControl.segmentedControlWithLabels_trackingMode_target_action_(
            ["Alt / Tap", "Hey Niko"], 0, self, "modeChanged:"
        )
        self.mode_switch.setControlSize_(1)
        self.mode_switch.setFont_(NSFont.systemFontOfSize_(11))
        self.mode_switch.setFrame_(NSMakeRect(252, 12, 156, 24))
        self.mode_switch.setSelectedSegment_(MODES.index(self.mode))
        self.mode_switch.setAutoresizingMask_(STICK_BOTTOM)
        background.addSubview_(self.mode_switch)
        self.hotkey_lock = threading.Lock()
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(0.5, self, "tick:", None, True)

        screen = NSScreen.mainScreen().visibleFrame()
        self.panel.setFrameOrigin_(NSMakePoint(screen.origin.x + (screen.size.width - 420) / 2,
                                               screen.origin.y + screen.size.height - 190))
        # Keep window and settings closed on startup so reboot is quiet and non-intrusive
        # Settings and main window open only when the user clicks the menu bar icon near Wi-Fi
        self.global_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            NSEventMaskFlagsChanged, self._global_flags_changed
        )
        self.local_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            NSEventMaskFlagsChanged, self._local_flags_changed
        )
        self.key_global_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            NSEventMaskKeyDown, self._global_key_down
        )
        self.key_local_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            NSEventMaskKeyDown, self._local_key_down
        )
        self._start_pynput_listener()
        self._start_worker()

    @objc.python_method
    def _global_flags_changed(self, event):
        self._handle_flags(event)

    @objc.python_method
    def _local_flags_changed(self, event):
        self._handle_flags(event)
        return event

    @objc.python_method
    def trigger_alt_r(self, is_down):
        with self.hotkey_lock:
            now = time.time()
            if is_down == getattr(self, "option_down", False):
                return
            self.option_down = is_down

            if is_down:
                self.alt_r_down_time = now
                if getattr(self, "current_state", "") == "Speaking":
                    # Instant Push-to-Pause when assistant is speaking
                    self.controls.put("pause_speech")
                else:
                    # Push-to-Talk: press starts listening
                    try:
                        from AppKit import NSSound
                        s = NSSound.soundNamed_("Tink")
                        if s:
                            s.play()
                    except Exception:
                        pass
                    self.controls.put("press")
            else:
                # Push-to-Talk: key release stops listening and executes immediately!
                if getattr(self, "current_state", "") == "Listening":
                    self.controls.put("release")

    @objc.python_method
    def on_audio_level(self, level):
        now = time.time()
        if now - getattr(self, "_last_lvl_time", 0.0) < 0.035:
            return
        self._last_lvl_time = now
        if isinstance(level, (list, tuple)) and len(level) == 4:
            payload = [round(float(x), 2) for x in level]
        else:
            fl = round(float(level), 2)
            payload = [fl, fl, fl, fl]
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "updateAudioLevelOnMain:", payload, False
        )

    def updateAudioLevelOnMain_(self, levels):
        if getattr(self, "current_state", "") == "Listening":
            if getattr(self, "notch_webview", None):
                if isinstance(levels, (list, tuple)) and len(levels) == 4:
                    js = f"updateAudioLevel({levels[0]}, {levels[1]}, {levels[2]}, {levels[3]});"
                else:
                    fl = float(levels) if isinstance(levels, (int, float)) else 0.0
                    js = f"updateAudioLevel({fl}, {fl}, {fl}, {fl});"
                self.notch_webview.evaluateJavaScript_completionHandler_(js, None)

    @objc.python_method
    def _start_pynput_listener(self):
        try:
            from pynput import keyboard
            def on_press(key):
                if key in (keyboard.Key.alt_r, keyboard.Key.alt_l, keyboard.Key.alt):
                    self.trigger_alt_r(True)
            def on_release(key):
                if key in (keyboard.Key.alt_r, keyboard.Key.alt_l, keyboard.Key.alt):
                    self.trigger_alt_r(False)
            listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            listener.daemon = True
            listener.start()
            self.pynput_listener = listener
        except Exception as e:
            print("pynput listener initialization notice:", e)

    @objc.python_method
    def _handle_flags(self, event):
        # 61 = Right Option/Alt, 58 = Left Option/Alt
        if event.keyCode() in (58, 61):
            is_down = bool(event.modifierFlags() & NSEventModifierFlagOption)
            self.trigger_alt_r(is_down)
        elif bool(event.modifierFlags() & NSEventModifierFlagOption) != getattr(self, "option_down", False):
            is_down = bool(event.modifierFlags() & NSEventModifierFlagOption)
            self.trigger_alt_r(is_down)

    @objc.python_method
    def _global_key_down(self, event):
        self._handle_key_down(event)

    @objc.python_method
    def _local_key_down(self, event):
        if self._handle_key_down(event):
            return None
        return event

    @objc.python_method
    def _handle_key_down(self, event):
        # Hotkey: Option + Space (keycode 49 + Option modifier)
        if event.keyCode() == 49 and bool(event.modifierFlags() & NSEventModifierFlagOption):
            if getattr(self, "current_state", "") == "Speaking":
                self.controls.put("pause_speech")
            elif getattr(self, "current_state", "") == "Listening":
                self.controls.put("release")
            else:
                try:
                    from AppKit import NSSound
                    s = NSSound.soundNamed_("Tink")
                    if s:
                        s.play()
                except Exception:
                    pass
                self.controls.put("press")
            return True
        return False

    @objc.python_method
    def _setup_notch_window(self):
        screen = NSScreen.mainScreen().frame()
        saved = NSUserDefaults.standardUserDefaults().objectForKey_("enable_notch")
        self.notch_enabled = True if saved is None else NSUserDefaults.standardUserDefaults().boolForKey_("enable_notch")

        # Exact macOS menu bar height (25px) docked at top center
        pill_w, pill_h = 165, 25
        x = screen.origin.x + (screen.size.width - pill_w) / 2
        y = screen.origin.y + screen.size.height - pill_h

        self.notch_window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, pill_w, pill_h),
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False
        )
        self.notch_window.setLevel_(25)  # NSStatusWindowLevel - floats above menu bar & all apps
        self.notch_window.setCollectionBehavior_(1 | 16 | 64)  # CanJoinAllSpaces, FullScreenAuxiliary, Stationary
        self.notch_window.setOpaque_(False)
        self.notch_window.setBackgroundColor_(NSColor.clearColor())
        self.notch_window.setMovableByWindowBackground_(True)
        self.notch_window.setReleasedWhenClosed_(False)
        self.notch_window.setHasShadow_(False)  # HTML provides sleek custom drop shadow

        html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "dynamic_island.html")
        if os.path.exists(html_path):
            config = WKWebViewConfiguration.alloc().init()
            ucc = WKUserContentController.alloc().init()
            handler = IslandScriptHandler.alloc().initWithDelegate_(self)
            ucc.addScriptMessageHandler_name_(handler, "assistant")
            config.setUserContentController_(ucc)

            wv = WKWebView.alloc().initWithFrame_configuration_(NSMakeRect(0, 0, pill_w, pill_h), config)
            wv.setValue_forKey_(False, "drawsBackground")
            file_url = NSURL.fileURLWithPath_(html_path)
            wv.loadFileURL_allowingReadAccessToURL_(file_url, file_url.URLByDeletingLastPathComponent())
            self.notch_window.setContentView_(wv)
            self.notch_webview = wv
        else:
            bg = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, pill_w, pill_h))
            bg.setMaterial_(NSVisualEffectMaterialHUDWindow)
            bg.setWantsLayer_(True)
            bg.layer().setCornerRadius_(pill_h / 2)
            self.notch_window.setContentView_(bg)

        if self.notch_enabled:
            self.notch_window.orderFrontRegardless()

    @objc.python_method
    def _start_worker(self):
        if self.worker_started:
            return
        self.worker_started = True
        threading.Thread(target=self._run_assistant, daemon=True).start()

    @objc.python_method
    def _run_assistant(self):
        from siri import run_voice_assistant
        try:
            run_voice_assistant(mode=self.mode, notify=self.notify, controls=self.controls, on_audio_level=self.on_audio_level)
        except Exception as exc:
            self.notify("Something went wrong", str(exc))

    @objc.python_method
    def _add_window_menu(self):
        item = NSMenuItem.alloc().init()
        NSApp.mainMenu().addItem_(item)
        menu = NSMenu.alloc().initWithTitle_("Window")
        menu.addItemWithTitle_action_keyEquivalent_("Minimize", "performMiniaturize:", "m")
        self.on_top_item = menu.addItemWithTitle_action_keyEquivalent_("Keep on Top", "toggleOnTop:", "t")
        self.on_top_item.setTarget_(self)
        self.on_top_item.setState_(1 if self.on_top else 0)
        self.notch_menu_item = menu.addItemWithTitle_action_keyEquivalent_("Dynamic Notch HUD", "toggleNotchHUDFromMenu:", "d")
        self.notch_menu_item.setTarget_(self)
        self.notch_menu_item.setState_(1 if getattr(self, "notch_enabled", True) else 0)
        menu.addItemWithTitle_action_keyEquivalent_("Show Niko Window", "showMain:", "1").setTarget_(self)
        item.setSubmenu_(menu)
        NSApp.setWindowsMenu_(menu)

    def toggleNotchHUDFromMenu_(self, _sender):
        self.notch_enabled = not getattr(self, "notch_enabled", True)
        NSUserDefaults.standardUserDefaults().setBool_forKey_(self.notch_enabled, "enable_notch")
        if hasattr(self, "notch_menu_item"):
            self.notch_menu_item.setState_(1 if self.notch_enabled else 0)
        if hasattr(self, "notch_checkbox") and self.notch_checkbox:
            self.notch_checkbox.setState_(1 if self.notch_enabled else 0)
        if self.notch_enabled:
            self.notch_window.orderFrontRegardless()
        else:
            self.notch_window.orderOut_(None)

    def toggleNotchHUD_(self, sender):
        self.notch_enabled = (sender.state() == 1)
        NSUserDefaults.standardUserDefaults().setBool_forKey_(self.notch_enabled, "enable_notch")
        if hasattr(self, "notch_menu_item"):
            self.notch_menu_item.setState_(1 if self.notch_enabled else 0)
        if self.notch_enabled:
            self.notch_window.orderFrontRegardless()
        else:
            self.notch_window.orderOut_(None)

    @objc.python_method
    def _add_voice_menu(self):
        item = NSMenuItem.alloc().init()
        NSApp.mainMenu().addItem_(item)
        menu = NSMenu.alloc().initWithTitle_("Voice")
        from jarvis_memory import get_voice, VOICE_MALE, VOICE_FEMALE
        active_voice = get_voice()
        self.voice_male_item = menu.addItemWithTitle_action_keyEquivalent_("Male", "selectMaleVoice:", "")
        self.voice_male_item.setTarget_(self)
        self.voice_male_item.setState_(1 if active_voice == VOICE_MALE else 0)
        self.voice_female_item = menu.addItemWithTitle_action_keyEquivalent_("Female", "selectFemaleVoice:", "")
        self.voice_female_item.setTarget_(self)
        self.voice_female_item.setState_(1 if active_voice == VOICE_FEMALE else 0)
        item.setSubmenu_(menu)

    def selectMaleVoice_(self, _sender):
        from jarvis_memory import set_voice
        set_voice("male")
        if hasattr(self, "voice_male_item"):
            self.voice_male_item.setState_(1)
            self.voice_female_item.setState_(0)
        if hasattr(self, "voice_segment") and self.voice_segment:
            self.voice_segment.setSelectedSegment_(0)
        self.notify("Ready", "Voice: Male")

    def selectFemaleVoice_(self, _sender):
        from jarvis_memory import set_voice
        set_voice("female")
        if hasattr(self, "voice_male_item"):
            self.voice_male_item.setState_(0)
            self.voice_female_item.setState_(1)
        if hasattr(self, "voice_segment") and self.voice_segment:
            self.voice_segment.setSelectedSegment_(1)
        self.notify("Ready", "Voice: Female")

    def voiceChanged_(self, sender):
        if sender.selectedSegment() == 0:
            self.selectMaleVoice_(None)
        else:
            self.selectFemaleVoice_(None)

    @objc.python_method
    def _setup_status_item(self):
        try:
            from AppKit import NSStatusBar, NSVariableStatusItemLength, NSImage, NSMakeSize, NSImageLeft
            self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(-1)
            btn = self.status_item.button()
            if btn:
                icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "menubar_icon.png")
                if os.path.exists(icon_path):
                    img = NSImage.alloc().initWithContentsOfFile_(icon_path)
                    if img:
                        img.setSize_(NSMakeSize(18.0, 18.0))
                        img.setTemplate_(True)
                        btn.setImage_(img)
                        btn.setImagePosition_(NSImageLeft)
                        btn.setTitle_(" NIKO")
                else:
                    btn.setTitle_(" NIKO")
                btn.setFont_(NSFont.boldSystemFontOfSize_(11))
            
            menu = NSMenu.alloc().init()
            menu.addItemWithTitle_action_keyEquivalent_("Settings…", "showSettings:", ",")
            menu.addItemWithTitle_action_keyEquivalent_("Show Niko Window", "showMain:", "")
            menu.addItemWithTitle_action_keyEquivalent_("Toggle Top Dynamic Island", "toggleNotchHUDFromMenu:", "")
            menu.addItem_(NSMenuItem.separatorItem())
            menu.addItemWithTitle_action_keyEquivalent_("Switch to Male Voice", "selectMaleVoice:", "")
            menu.addItemWithTitle_action_keyEquivalent_("Switch to Female Voice", "selectFemaleVoice:", "")
            menu.addItem_(NSMenuItem.separatorItem())
            menu.addItemWithTitle_action_keyEquivalent_("Quit NIKO", "terminate:", "q")
            
            for item in menu.itemArray():
                if str(item.action()) != "terminate:":
                    item.setTarget_(self)
            self.status_item.setMenu_(menu)
        except Exception as e:
            print("Status item setup:", e)

    def toggleOnTop_(self, _sender):
        self.on_top = not self.on_top
        NSUserDefaults.standardUserDefaults().setBool_forKey_(self.on_top, "keep_on_top")
        self.panel.setLevel_(FLOATING if self.on_top else NORMAL)
        self.on_top_item.setState_(1 if self.on_top else 0)

    def showMain_(self, _sender):
        self.panel.deminiaturize_(None)
        self.panel.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)

    def applicationShouldHandleReopen_hasVisibleWindows_(self, _app, _visible):
        self.showMain_(None)
        return True

    def modeChanged_(self, sender):
        self.mode = MODES[sender.selectedSegment()]
        NSUserDefaults.standardUserDefaults().setObject_forKey_(self.mode, "mode")
        self.hint.setStringValue_(HINTS[self.mode])
        self.controls.put(("mode", self.mode))

    def showSettings_(self, _sender):
        try:
            self._show_settings()
        except Exception as exc:  # a Python error inside an AppKit callback would otherwise kill the app
            self.notify("Something went wrong", str(exc))

    @objc.python_method
    def _show_settings(self):
        if getattr(self, "settings_sheet", None):
            return
        sheet = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, 420, 280), NSWindowStyleMaskTitled, NSBackingStoreBuffered, False
        )
        content = sheet.contentView()
        content.addSubview_(label("Settings & Preferences", NSMakeRect(22, 235, 360, 30), 20))
        content.addSubview_(label("Voice, activation hotkeys, and Dynamic Notch HUD.",
                                  NSMakeRect(23, 213, 380, 20), 12, NSColor.secondaryLabelColor()))

        from jarvis_memory import get_voice, VOICE_MALE, VOICE_FEMALE
        content.addSubview_(label("Voice", NSMakeRect(23, 175, 84, 22), 13))
        self.voice_segment = NSSegmentedControl.segmentedControlWithLabels_trackingMode_target_action_(
            ["Male", "Female"], 0, self, "voiceChanged:"
        )
        self.voice_segment.setFrame_(NSMakeRect(108, 172, 280, 26))
        self.voice_segment.setSelectedSegment_(0 if get_voice() == VOICE_MALE else 1)
        content.addSubview_(self.voice_segment)

        content.addSubview_(label("Hotkeys", NSMakeRect(23, 137, 84, 22), 13))
        hotkey_hint = label("Right Alt (Wakeup) • Option+Space (Toggle)", NSMakeRect(108, 137, 280, 20), 12, NSColor.systemTealColor())
        content.addSubview_(hotkey_hint)

        self.notch_checkbox = NSButton.alloc().initWithFrame_(NSMakeRect(108, 102, 280, 24))
        self.notch_checkbox.setButtonType_(NSSwitchButton)
        self.notch_checkbox.setTitle_("Enable Dynamic Top Notch HUD")
        self.notch_checkbox.setState_(1 if getattr(self, "notch_enabled", True) else 0)
        self.notch_checkbox.setTarget_(self)
        self.notch_checkbox.setAction_("toggleNotchHUD:")
        content.addSubview_(self.notch_checkbox)

        # NVIDIA NIM key for deep LLM reasoning (meta/llama-3.1-8b-instruct)
        content.addSubview_(label("NVIDIA NIM", NSMakeRect(23, 63, 84, 22), 13))
        field = NSSecureTextField.alloc().initWithFrame_(NSMakeRect(108, 60, 280, 26))
        field.setBezelStyle_(1)  # rounded
        field.setFocusRingType_(1)
        field.setPlaceholderString_("Already configured" if get_secret("NVIDIA_API_KEY") else "Paste NVIDIA NIM key")
        content.addSubview_(field)
        self.key_fields = {"NVIDIA_API_KEY": field}

        self.settings_message = label("", NSMakeRect(23, 16, 180, 20), 11, NSColor.systemRedColor())
        content.addSubview_(self.settings_message)
        save = NSButton.buttonWithTitle_target_action_("Done", self, "saveSettings:")
        save.setFrame_(NSMakeRect(310, 12, 82, 32))
        save.setKeyEquivalent_("\r")
        content.addSubview_(save)
        cancel = NSButton.buttonWithTitle_target_action_("Cancel", self, "closeSettings:")
        cancel.setFrame_(NSMakeRect(220, 12, 86, 32))
        cancel.setKeyEquivalent_("\x1b")
        content.addSubview_(cancel)

        self.settings_sheet = sheet
        NSApp.activateIgnoringOtherApps_(True)
        self.panel.makeKeyAndOrderFront_(None)
        self.panel.beginSheet_completionHandler_(sheet, None)

    def closeSettings_(self, _sender):
        if getattr(self, "settings_sheet", None):
            self.panel.endSheet_(self.settings_sheet)
            self.settings_sheet.orderOut_(None)
            self.settings_sheet = None

    def saveSettings_(self, _sender):
        try:
            for key_name, field in self.key_fields.items():
                value = field.stringValue()
                if value:
                    save_secret(key_name, value)
            if hasattr(self, "notch_checkbox") and self.notch_checkbox:
                self.notch_enabled = (self.notch_checkbox.state() == 1)
                NSUserDefaults.standardUserDefaults().setBool_forKey_(self.notch_enabled, "enable_notch")
                if hasattr(self, "notch_menu_item"):
                    self.notch_menu_item.setState_(1 if self.notch_enabled else 0)
                if self.notch_enabled:
                    self.notch_window.orderFrontRegardless()
                else:
                    self.notch_window.orderOut_(None)
            from siri import reload_keys
            reload_keys()
            self.closeSettings_(None)
            self._start_worker()
        except Exception as exc:
            self.settings_message.setStringValue_(str(exc))

    @objc.python_method
    def notify(self, state, detail=""):
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            "updateStatus:", {"state": state, "detail": detail}, False
        )

    def waveTick_(self, _timer):
        # 20 FPS sound wave animation across all active states (listening, thinking, speaking, ready)
        if not hasattr(self, "notch_bars") or not self.notch_bars:
            return
        import random, math
        state = getattr(self, "current_state", "Ready")
        palette = LINE_GRADIENTS.get(state, LINE_GRADIENTS["Ready"])
        pill_h = 26
        line_w = 1.8
        now = time.time()
        
        # Ensure gradient colors match the active state
        if hasattr(self, "notch_grads") and self.notch_grads:
            for i, grad in enumerate(self.notch_grads):
                c_top, c_bot = palette[i]
                grad.setColors_([c_top, c_bot])
        
        if state == "Listening":
            # Dynamic human voice frequency waves (Cyan -> Blue -> Purple -> Pink gradient)
            for b in self.notch_bars:
                h = random.choice([4.0, 8.5, 12.5, 6.0, 11.0, 5.0, 13.0, 7.5, 10.0])
                bx = b.frame().origin.x
                b.setFrame_(NSMakeRect(bx, (pill_h - h) / 2, line_w, h))
        elif state == "Thinking":
            # Flowing sinusoidal wave ripple while processing (Violet -> Magenta -> Hot Pink gradient)
            for i, b in enumerate(self.notch_bars):
                sine_val = (math.sin(now * 9.0 + i * 0.9) + 1.0) / 2.0
                h = 3.0 + sine_val * 9.0  # 3.0px to 12.0px undulating wave
                bx = b.frame().origin.x
                b.setFrame_(NSMakeRect(bx, (pill_h - h) / 2, line_w, h))
        elif state == "Speaking":
            # Animated speech audio wave (Mint -> Teal -> Cyan gradient)
            for b in self.notch_bars:
                h = random.choice([4.0, 9.0, 12.0, 7.0, 11.0, 5.5, 9.5])
                bx = b.frame().origin.x
                b.setFrame_(NSMakeRect(bx, (pill_h - h) / 2, line_w, h))
        else:
            # Subtle low resting pulse (Iridescent soft gradient)
            for i, b in enumerate(self.notch_bars):
                h = 2.5 + (math.sin(now * 2.0 + i * 0.7) + 1.0) * 1.3
                bx = b.frame().origin.x
                b.setFrame_(NSMakeRect(bx, (pill_h - h) / 2, line_w, h))

    def tick_(self, _timer):
        siri = sys.modules.get("siri")
        timers = siri.timer_snapshot()[:3] if siri else []
        if len(timers) != len(self.timer_rows):
            self._layout_timer_rows(len(timers))
        for (name_view, time_view), (name, left) in zip(self.timer_rows, timers):
            name_view.setStringValue_(name)
            m, sec = divmod(int(left + 0.999), 60)
            h, m = divmod(m, 60)
            time_view.setStringValue_(f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}")

    @objc.python_method
    def _layout_timer_rows(self, count):
        for name_view, time_view in self.timer_rows:
            name_view.removeFromSuperview()
            time_view.removeFromSuperview()
        self.timer_rows = []
        frame = self.panel.frame()
        height = BASE_HEIGHT + ROW * count + (8 if count else 0)
        top = frame.origin.y + frame.size.height
        self.panel.setFrame_display_animate_(NSMakeRect(frame.origin.x, top - height, frame.size.width, height), True, True)
        for i in range(count):
            y = 44 + ROW * (count - 1 - i)  # soonest on top, just above the bottom row
            name_view = label("", NSMakeRect(27, y, 280, 20), 13, NSColor.secondaryLabelColor())
            time_view = label("", NSMakeRect(310, y, 98, 20), 15, NSColor.systemTealColor())
            time_view.setFont_(NSFont.monospacedDigitSystemFontOfSize_weight_(15, 0.4))
            time_view.setAlignment_(2)  # right
            for v in (name_view, time_view):
                v.setAutoresizingMask_(STICK_BOTTOM)
                self.background.addSubview_(v)
            self.timer_rows.append((name_view, time_view))

    def updateStatus_(self, payload):
        state = str(payload["state"])
        detail = str(payload.get("detail", ""))
        self.current_state = state
        color = STATUS_COLORS.get(state, NSColor.labelColor())
        if state != "Listening":
            self.recording_active = False
        if hasattr(self, "status") and self.status:
            self.status.setStringValue_(state)
        if hasattr(self, "detail") and self.detail:
            self.detail.setStringValue_(detail)
        if hasattr(self, "dot") and self.dot:
            self.dot.setTextColor_(color)

        # Dynamic Island Pill HUD with Siri Orb
        if getattr(self, "notch_window", None) and getattr(self, "notch_enabled", True):
            if getattr(self, "notch_webview", None):
                js = f"updateAssistantState({json.dumps(state)}, {json.dumps(detail)})"
                self.notch_webview.evaluateJavaScript_completionHandler_(js, None)

            self.notch_window.orderFrontRegardless()

    def applicationShouldTerminateAfterLastWindowClosed_(self, _application):
        return False  # keep listening with the window closed, the Dock icon reopens it

    def applicationWillTerminate_(self, _notification):
        if getattr(self, "global_monitor", None):
            NSEvent.removeMonitor_(self.global_monitor)
        if getattr(self, "local_monitor", None):
            NSEvent.removeMonitor_(self.local_monitor)
        if getattr(self, "key_global_monitor", None):
            NSEvent.removeMonitor_(self.key_global_monitor)
        if getattr(self, "key_local_monitor", None):
            NSEvent.removeMonitor_(self.key_local_monitor)


def build_menu():
    """App and Edit menus, so Cmd+Q works and Cmd+V pastes into the key fields."""
    bar = NSMenu.alloc().init()
    app_item = NSMenuItem.alloc().init()
    bar.addItem_(app_item)
    app_menu = NSMenu.alloc().init()
    app_menu.addItemWithTitle_action_keyEquivalent_("Quit NIKO", "terminate:", "q")
    app_item.setSubmenu_(app_menu)
    edit_item = NSMenuItem.alloc().init()
    bar.addItem_(edit_item)
    edit = NSMenu.alloc().initWithTitle_("Edit")
    for title, action, key in (("Undo", "undo:", "z"), ("Cut", "cut:", "x"), ("Copy", "copy:", "c"),
                               ("Paste", "paste:", "v"), ("Select All", "selectAll:", "a")):
        edit.addItemWithTitle_action_keyEquivalent_(title, action, key)
    edit_item.setSubmenu_(edit)
    NSApp.setMainMenu_(bar)


def run_app():
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)  # shows in the Dock with a menu bar
    build_menu()
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()
