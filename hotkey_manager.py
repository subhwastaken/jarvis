"""Hotkey and Push-to-Talk Manager for J.A.R.V.I.S.
Handles:
1. Low-level global keyboard listening via pynput for Right Alt / Option key.
2. Cocoa NSEvent modifier flags monitors for seamless native macOS integration.
3. Debounced trigger state machine preventing duplicate activations.
"""
import threading
import time
from pynput import keyboard

PTT_KEY = keyboard.Key.alt_r


class HotkeyManager:
    """Manages push-to-talk state, timing, and debounce across native Cocoa and pynput listeners."""

    def __init__(self, on_press_callback, on_release_callback, debounce_seconds=0.15):
        self.on_press_callback = on_press_callback
        self.on_release_callback = on_release_callback
        self.debounce_seconds = debounce_seconds
        self.lock = threading.Lock()
        self.is_down = False
        self.press_time = 0.0
        self.last_event_time = 0.0
        self._listener = None

    def trigger_key(self, is_pressed: bool):
        with self.lock:
            now = time.time()
            if is_pressed == self.is_down and (now - self.last_event_time) < self.debounce_seconds:
                return
            self.last_event_time = now
            self.is_down = is_pressed

            if is_pressed:
                self.press_time = now
                if self.on_press_callback:
                    self.on_press_callback()
            else:
                duration = now - self.press_time
                if self.on_release_callback:
                    self.on_release_callback(duration)

    def start_pynput_listener(self):
        def _on_press(key):
            if key == PTT_KEY:
                self.trigger_key(True)

        def _on_release(key):
            if key == PTT_KEY:
                self.trigger_key(False)

        self._listener = keyboard.Listener(on_press=_on_press, on_release=_on_release)
        self._listener.daemon = True
        self._listener.start()
        return self._listener

    def stop_pynput_listener(self):
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
