"""Universal Cross-Platform Dynamic Island HUD Controller for NIKO.
Renders the Dynamic Island floating pill on both macOS and Windows.
- macOS: Uses native Cocoa NSPanel + WKWebView (0 dependencies, transparent, non-activating).
- Windows: Uses Microsoft Edge WebView2 / pywebview (frameless, transparent, always on top).
"""
import os
import sys
import json
import threading
import time

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")
HTML_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "assets", "dynamic_island.html"))


class BaseHUD:
    def update(self, state: str, detail: str = ""):
        pass

    def close(self):
        pass


class MacCocoaHUD(BaseHUD):
    """Native macOS Dynamic Island Pill docked at top center."""
    def __init__(self):
        self.panel = None
        self.webview = None
        self._init_mac_panel()

    def _init_mac_panel(self):
        try:
            from AppKit import (
                NSPanel, NSBackingStoreBuffered, NSWindowCollectionBehaviorCanJoinAllSpaces,
                NSWindowCollectionBehaviorStationary, NSWindowCollectionBehaviorFullScreenAuxiliary,
                NSColor, NSScreen, NSMakeRect, NSFloatingWindowLevel
            )
            from WebKit import WKWebView, WKWebViewConfiguration

            screen = NSScreen.mainScreen()
            if not screen:
                return
            sf = screen.frame()
            pill_w = 270.0
            pill_h = 38.0
            # Position at top center, 12px below top of screen
            x = (sf.size.width - pill_w) / 2.0
            y = sf.size.height - pill_h - 12.0

            style_mask = 1 << 7  # NSWindowStyleMaskBorderless
            self.panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
                NSMakeRect(x, y, pill_w, pill_h),
                style_mask,
                NSBackingStoreBuffered,
                False
            )
            self.panel.setLevel_(NSFloatingWindowLevel + 2)
            self.panel.setOpaque_(False)
            self.panel.setBackgroundColor_(NSColor.clearColor())
            self.panel.setHasShadow_(False)
            self.panel.setIgnoresMouseEvents_(False)
            self.panel.setCollectionBehavior_(
                NSWindowCollectionBehaviorCanJoinAllSpaces |
                NSWindowCollectionBehaviorStationary |
                NSWindowCollectionBehaviorFullScreenAuxiliary
            )

            config = WKWebViewConfiguration.alloc().init()
            if hasattr(config.preferences(), "setValue_forKey_"):
                config.preferences().setValue_forKey_(True, "developerExtrasEnabled")

            self.webview = WKWebView.alloc().initWithFrame_configuration_(
                NSMakeRect(0, 0, pill_w, pill_h), config
            )
            self.webview.setValue_forKey_(False, "drawsBackground")

            from Foundation import NSURL
            file_url = NSURL.fileURLWithPath_(HTML_PATH)
            self.webview.loadFileURL_allowingReadAccessToURL_(file_url, file_url.URLByDeletingLastPathComponent())

            self.panel.contentView().addSubview_(self.webview)
            self.panel.orderFrontRegardless()
        except Exception as e:
            print(f"  [MacHUD] Initialization warning: {e}")

    def update(self, state: str, detail: str = ""):
        if self.webview:
            js = f"updateAssistantState({json.dumps(state)}, {json.dumps(detail)})"
            self.webview.evaluateJavaScript_completionHandler_(js, None)
        if self.panel:
            self.panel.orderFrontRegardless()

    def close(self):
        if self.panel:
            self.panel.orderOut_(None)


class WindowsHUD(BaseHUD):
    """Windows Dynamic Island Pill using WebView2 / pywebview."""
    def __init__(self):
        self.window = None
        self.thread = None
        self._start_windows_hud()

    def _start_windows_hud(self):
        def _run():
            try:
                import webview
                # 270x38 centered at top
                self.window = webview.create_window(
                    "NIKO Dynamic Island",
                    url=HTML_PATH,
                    width=270,
                    height=38,
                    frameless=True,
                    easy_drag=True,
                    on_top=True,
                    transparent=True
                )
                webview.start(debug=False)
            except ImportError:
                print("  [WindowsHUD] Note: 'pywebview' not installed. Install with 'pip install pywebview' for native floating pill.")
            except Exception as e:
                print(f"  [WindowsHUD] Error: {e}")

        self.thread = threading.Thread(target=_run, daemon=True)
        self.thread.start()

    def update(self, state: str, detail: str = ""):
        if self.window:
            js = f"updateAssistantState({json.dumps(state)}, {json.dumps(detail)})"
            try:
                self.window.evaluate_js(js)
            except Exception:
                pass

    def close(self):
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass


_HUD_INSTANCE = None


def get_hud():
    """Returns singleton cross-platform Dynamic Island HUD instance."""
    global _HUD_INSTANCE
    if _HUD_INSTANCE is None:
        if IS_MAC:
            _HUD_INSTANCE = MacCocoaHUD()
        elif IS_WIN:
            _HUD_INSTANCE = WindowsHUD()
        else:
            _HUD_INSTANCE = BaseHUD()
    return _HUD_INSTANCE


def update_hud(state: str, detail: str = ""):
    """Updates Dynamic Island Siri Orb status universally."""
    hud = get_hud()
    if hud:
        hud.update(state, detail)
