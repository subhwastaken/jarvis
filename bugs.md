# Comprehensive Bug, Vulnerability & Failure Mode Audit (bugs.md)
**Project**: J.A.R.V.I.S. / Hey-Jev Voice Assistant (`/Volumes/WD_Subharup/jev`)  
**Audit Date**: September 2026  
**Target Environment**: macOS Sonoma / Sequoia (Apple Silicon / Intel)

---

## 1. Executive Summary & Vulnerability Matrix

This audit documents every architectural bottleneck, unhandled edge case, operating system permission trap, concurrency flaw, and silent failure identified across the codebase.

| ID | Severity | Category | File & Location | Failure Symptom |
| :--- | :--- | :--- | :--- | :--- |
| **BUG-01** | **CRITICAL** | macOS Permissions | [jarvis_gui.py:L79](file:///Volumes/WD_Subharup/jev/jarvis_gui.py#L79) | Web clicks fail if Chrome *Allow JavaScript from Apple Events* is disabled |
| **BUG-02** | **CRITICAL** | macOS TCC Security | [jarvis_gui.py:L205](file:///Volumes/WD_Subharup/jev/jarvis_gui.py#L205) | Keystrokes & Calculator automation blocked without *Accessibility* access |
| **BUG-03** | **HIGH** | Hardware / Audio | [siri.py:L1815](file:///Volumes/WD_Subharup/jev/siri.py#L1815) | 384kHz USB DAC input mismatch & quiet mic signals leading to STT hallucinations |
| **BUG-04** | **HIGH** | UI / Display | [jarvis_windows.py:L32](file:///Volumes/WD_Subharup/jev/jarvis_windows.py#L32) | Hardcoded `1920x1052` fallback breaks window sizing on Retina & Ultrawide displays |
| **BUG-05** | **HIGH** | Process Race | [siri.py:L1675](file:///Volumes/WD_Subharup/jev/siri.py#L1675) | App cold-boot latency causes multi-step search to open in wrong/blank window |
| **BUG-06** | **HIGH** | Process Killing | [siri.py:L524](file:///Volumes/WD_Subharup/jev/siri.py#L524) | `killall` fails on multi-word app names (e.g. `Google Chrome`, `Visual Studio Code`) |
| **BUG-07** | **HIGH** | Network / Scraping | [jarvis_search.py:L30](file:///Volumes/WD_Subharup/jev/jarvis_search.py#L30) | DuckDuckGo returns 403 / CAPTCHA on automated search scraping |
| **BUG-08** | **MEDIUM** | Audio Query | [siri.py:L443](file:///Volumes/WD_Subharup/jev/siri.py#L443) | `volume()` crashes with `ValueError` if external monitor lacks audio control |
| **BUG-09** | **MEDIUM** | Process Inspection | [jarvis_state.py:L47](file:///Volumes/WD_Subharup/jev/jarvis_state.py#L47) | `is_app_running` returns `False` for menu bar or background apps |
| **BUG-10** | **MEDIUM** | Browser Support | [jarvis_browser.py:L8](file:///Volumes/WD_Subharup/jev/jarvis_browser.py#L8) | Non-Chromium/Safari browsers (Firefox, Zen, Orion) ignored as active browsers |
| **BUG-11** | **CRITICAL** | Audio / Parsing | [siri.py:L240](file:///Volumes/WD_Subharup/jev/siri.py#L240), [siri.py:L735](file:///Volumes/WD_Subharup/jev/siri.py#L735) | Numeric volume requests (e.g. "80%") fail regex or force-reset to 50% |
| **BUG-12** | **CRITICAL** | Automation / Logic | [jarvis_gui.py:L13-L25](file:///Volumes/WD_Subharup/jev/jarvis_gui.py#L13-L25) | `get_frontmost_browser` selects background browsers over active front browser |
| **BUG-13** | **HIGH** | Concurrency / Threading | [jarvis_daemon.py:L116](file:///Volumes/WD_Subharup/jev/jarvis_daemon.py#L116) | Unbounded spin-wait loop hangs background daemon thread indefinitely |
| **BUG-14** | **HIGH** | LLM / Planner | [jarvis_planner.py:L151](file:///Volumes/WD_Subharup/jev/jarvis_planner.py#L151) | Conditional planner crashes or falls back to basic heuristics if Ollama is offline |
| **BUG-15** | **HIGH** | Security / Path Traversal | [jarvis_dev.py:L93](file:///Volumes/WD_Subharup/jev/jarvis_dev.py#L93) | Prefix collision in `target_path.startswith(path)` allows path traversal bypass |
| **BUG-16** | **HIGH** | Concurrency / IPC | [jarvis_core/src/main.rs:L100](file:///Volumes/WD_Subharup/jev/jarvis_core/src/main.rs#L100) | Synchronous IPC handler starves accept loop when `osascript` hangs |
| **BUG-17** | **MEDIUM** | UI / Injection | [assistant_ui.py:L692](file:///Volumes/WD_Subharup/jev/assistant_ui.py#L692) | Unescaped line breaks and quotes trigger WebKit JS syntax error, freezing HUD |
| **BUG-18** | **MEDIUM** | GUI / Timing | [jarvis_gui.py:L185-L202](file:///Volumes/WD_Subharup/jev/jarvis_gui.py#L185-L202) | Calculator cold-boot timing drops keystrokes; replacing "and" injects "+" |
| **BUG-19** | **MEDIUM** | Multi-Monitor Display | [jarvis_windows.py:L8-L15](file:///Volumes/WD_Subharup/jev/jarvis_windows.py#L8-L15) | `NSScreen.mainScreen()` forces windows from external displays to jump screens |
| **BUG-20** | **HIGH** | Security / Execution | [jarvis_self_healing.py:L292](file:///Volumes/WD_Subharup/jev/jarvis_self_healing.py#L292) | Unsanitized `shell=True` runs raw LLM code without safety validation |
| **BUG-21** | **MEDIUM** | Concurrency / Race | [siri.py:L981-L982](file:///Volumes/WD_Subharup/jev/siri.py#L981-L982) | Concurrent timer cancellation raises unhandled `ValueError` killing timer thread |
| **BUG-22** | **HIGH** | macOS Privacy / Vision | [siri.py:L676](file:///Volumes/WD_Subharup/jev/siri.py#L676) | Screen capture silently returns blank desktop wallpaper without Screen Recording permission |
| **BUG-23** | **HIGH** | Hardware / Audio | [siri.py:L1760](file:///Volumes/WD_Subharup/jev/siri.py#L1760) | Audio stream goes permanently deaf if USB DAC or Bluetooth headset disconnects |
| **BUG-24** | **MEDIUM** | Search / Secrets | [jarvis_search.py:L7](file:///Volumes/WD_Subharup/jev/jarvis_search.py#L7) | Import-time API key caching causes runtime key updates to be ignored |
| **BUG-25** | **MEDIUM** | TTS / Reminders | [siri.py:L929](file:///Volumes/WD_Subharup/jev/siri.py#L929) | Reminder pre-caching calls Fish Audio exclusively, skipping Edge-TTS |
| **BUG-26** | **CRITICAL** | Intent / Routing / STT | [siri.py:L1478](file:///Volumes/WD_Subharup/jev/siri.py#L1478) | Search inversion & STT phonetic slips cause "open google", "open youtube", and search commands to mis-route or scrape DDG |

---

## 2. In-Depth Bug Analysis & Root Causes

### BUG-01: Chromium Browser Apple Events JavaScript Blocking
* **Location**: [jarvis_gui.py:L70-L85](file:///Volumes/WD_Subharup/jev/jarvis_gui.py#L70-L85)
* **Code**:
  ```python
  script = f'tell application "{browser}" to execute front window\'s active tab javascript "{clean_js}"'
  res = subprocess.check_output(["osascript", "-e", script], stderr=subprocess.DEVNULL, text=True).strip()
  ```
* **Failure Trigger**: User asks to click links or buttons on Google Chrome, Brave, or Microsoft Edge.
* **Root Cause**: By default, Chromium disables external script injection for security. If **`View → Developer → Allow JavaScript from Apple Events`** is unchecked, AppleScript throws:
  `execution error: A privilege violation occurred (-10004)`
* **Mitigation / Self-Heal**:
  Catch the exception in [jarvis_self_healing.py](file:///Volumes/WD_Subharup/jev/jarvis_self_healing.py) and fall back to native macOS Accessibility keystrokes (`Tab`, `Return`) or Accessibility UI element clicking.

---

### BUG-02: Accessibility Keystroke Simulation Block (TCC Sandboxing)
* **Location**: [jarvis_gui.py:L205](file:///Volumes/WD_Subharup/jev/jarvis_gui.py#L205), [jarvis_windows.py:L26](file:///Volumes/WD_Subharup/jev/jarvis_windows.py#L26)
* **Code**:
  ```applescript
  tell application "System Events"
      tell process "Calculator"
          keystroke "{safe_expr}"
          keystroke return
      end tell
  end tell
  ```
* **Failure Trigger**: Running calculator keystrokes, window resizing, or UI clicks.
* **Root Cause**: macOS requires explicit user authorization in **System Settings → Privacy & Security → Accessibility**. If the host process (`python3.10`, Terminal, iTerm, or VS Code) is not enabled, `System Events` throws:
  `execution error: Not authorized to send Apple events to System Events (-1743)`

---

### BUG-03: Audio Interface Sample Rate Mismatch & Low Signal
* **Location**: [siri.py:L1815-L1835](file:///Volumes/WD_Subharup/jev/siri.py#L1815-L1835)
* **Root Cause**: The user's system runs a `CX31993 384Khz HIFI AUDIO` external interface. When downsampling to 16,000 Hz:
  1. Low microphone volume leads to quiet input where Whisper attention heads hallucinate or miss words.
  2. Denormalized floating-point math triggers `RuntimeWarning: divide by zero encountered in matmul` on Apple Silicon Accelerate BLAS.
* **Fix Applied**: 
  - Audio peak normalization (`audio / max_amp * 0.92`) ensures Whisper receives a full-scale signal.
  - Runtime warnings filtered via `warnings.filterwarnings("ignore")`.
  - Configured `temperature=0.0` and `condition_on_previous_text=False` to prevent repetitive loop hallucinations.

---

### BUG-04: Hardcoded Fallback Display Dimensions
* **Location**: [jarvis_windows.py:L32](file:///Volumes/WD_Subharup/jev/jarvis_windows.py#L32)
* **Code**:
  ```python
  return 1920, 1052, 28
  ```
* **Failure Trigger**: Running `"Maximize window"` or `"Snap window left"` on a MacBook Air (1470x956), MacBook Pro 14" (1512x982), 4K monitor (3840x2160), or Ultrawide (3440x1440) if `NSScreen` and Finder bounds both miss.
* **Root Cause**: Hardcoded `1920x1052` forces windows to stretch off-screen or fail to fill larger displays.
* **Fix**: Query `NSScreen.mainScreen().frame()` dynamically via PyObjC AppKit.

---

### BUG-05: Multi-Step App Boot Race Condition
* **Location**: [siri.py:L1675](file:///Volumes/WD_Subharup/jev/siri.py#L1675)
* **Code**:
  ```python
  for task in tasks:
      reply = execute_single_action(task)
  ```
* **Failure Trigger**: Compound commands like `"Open Brave and search GitHub"` when Brave was closed.
* **Root Cause**: `open -a Brave` is asynchronous. macOS takes 1.5–2.5 seconds to initialize the window. If Step 2 executes `open https://...` before the window exists, macOS opens the link in the system default browser instead of the newly launched application.
* **Fix**: In compound browser commands, add an active wait loop (`time.sleep(0.8)` or checking `application "Brave" is running and has windows`) before dispatching the search URL.

---

### BUG-06: Process Termination Failure on Multi-Word Names
* **Location**: [siri.py:L524](file:///Volumes/WD_Subharup/jev/siri.py#L524)
* **Code**:
  ```python
  if res.returncode != 0 or res.stderr:
      subprocess.run(["killall", app_name], capture_output=True)
  ```
* **Failure Trigger**: Force-quitting apps with spaces like `"Google Chrome"` or `"Visual Studio Code"`.
* **Root Cause**: The Unix `killall` command expects exact process names without spaces, or targets multiple process names if unquoted (`killall Google Chrome` attempts to kill process `Google` and process `Chrome`).
* **Fix Applied**: Replaced with `pkill -f "{app_name}"`.

---

### BUG-07: Search Snippet 403 Rate Limiting
* **Location**: [jarvis_search.py:L30](file:///Volumes/WD_Subharup/jev/jarvis_search.py#L30)
* **Code**:
  ```python
  requests.post("https://html.duckduckgo.com/html/", data={"q": clean_q}, timeout=4)
  ```
* **Failure Trigger**: Repeated web searches within a short window.
* **Root Cause**: DuckDuckGo's HTML endpoint blocks automated scrapers with HTTP 403 or bot challenges.
* **Fix Applied**: Multi-tier failover from DuckDuckGo HTML -> DuckDuckGo Instant Answer API -> Wikipedia Summary API -> Local synthesis.

---

### BUG-08: Volume Conversion Crash on External Displays
* **Location**: [siri.py:L443](file:///Volumes/WD_Subharup/jev/siri.py#L443)
* **Code**:
  ```python
  def volume():
      return int(osa("output volume of (get volume settings)"))
  ```
* **Failure Trigger**: Calling `"turn volume up"` when connected to an external DisplayPort/HDMI monitor or audio interface that does not support AppleScript volume control.
* **Root Cause**: `get volume settings` returns an empty string or error, causing `int("")` to crash with `ValueError`.
* **Fix Applied**: Wrapped in `try ... except Exception: return 50`.

---

### BUG-09: Process Detection Concealment for Menu Bar / Background Apps
* **Location**: [jarvis_state.py:L47](file:///Volumes/WD_Subharup/jev/jarvis_state.py#L47)
* **Code**:
  ```applescript
  tell application "System Events" to get name of every application process whose visible is true
  ```
* **Failure Trigger**: Conditional queries like `"If Spotify is running, mute volume"`.
* **Root Cause**: If Spotify is minimized to the menu bar or hidden, `whose visible is true` returns `false`, causing the assistant to assume Spotify is closed.
* **Fix**: Query `name of every application process` without the `visible is true` constraint.

---

### BUG-10: Non-Chromium Browser Exclusion
* **Location**: [jarvis_browser.py:L8](file:///Volumes/WD_Subharup/jev/jarvis_browser.py#L8)
* **Code**:
  ```python
  SUPPORTED_BROWSERS = ["Google Chrome", "Safari", "Brave Browser", "Arc", "Microsoft Edge"]
  ```
* **Failure Trigger**: Asking to `"close tab"` or `"open new tab"` when using Firefox, Zen, Orion, or Opera.
* **Root Cause**: Whitelist excluded Firefox and other Gecko/WebKit browsers.
* **Fix Applied**: Expanded `SUPPORTED_BROWSERS` to include Firefox, Zen, Orion, Vivaldi, and Opera.

---

### BUG-11: Numeric Volume Setting Broken & Quantized
* **Locations**: [siri.py:L240](file:///Volumes/WD_Subharup/jev/siri.py#L240), [siri.py:L735](file:///Volumes/WD_Subharup/jev/siri.py#L735), [siri.py:L591](file:///Volumes/WD_Subharup/jev/siri.py#L591), [system_one_router.py:L130-L136](file:///Volumes/WD_Subharup/jev/system_one_router.py#L130-L136)
* **Code**:
  ```python
  # siri.py regex only matched named buckets:
  m_vol_set = re.search(r"^(?:set\s+(?:the\s+)?volume\s+to\s+)?(silent|quiet|medium|loud|max)$", t_clean, re.I)
  
  # siri.py execution defaults any numeric integer to 50:
  "volume_set": lambda lvl: osa(f"set volume output volume {LEVELS.get(lvl, 50)}")
  ```
* **Failure Trigger**: Asking `"Set volume to 80%"` or `"Set Spotify volume to 40"`.
* **Root Cause**:
  1. The regex completely rejects numeric digits, dropping the command to the information search or clarification branch.
  2. If a numeric value is passed directly to `volume_set`, `LEVELS.get(80, 50)` returns `50`, force-setting the volume to 50% regardless of what was requested.
  3. `system_one_router.py` quantizes numbers into five broad buckets (`silent`, `quiet`, `medium`, `loud`, `max`).
* **Fix**: Support regex matching `(\d{1,3})(?:%|\s*percent)?` and accept integer volume values directly in `volume_set` and `media_volume_adjust`.

---

### BUG-12: Background App Misdetection in GUI Automation (`get_frontmost_browser`)
* **Location**: [jarvis_gui.py:L13-L25](file:///Volumes/WD_Subharup/jev/jarvis_gui.py#L13-L25)
* **Code**:
  ```python
  for b in ["Google Chrome", "Brave Browser", "Safari", "Arc", "Microsoft Edge"]:
      res = subprocess.check_output(
          ["osascript", "-e", f'tell application "System Events" to (name of processes) contains "{b}"'],
          stderr=subprocess.DEVNULL, text=True
      ).strip()
      if res == "true":
          return b
  ```
* **Failure Trigger**: Asking to click a web link while using Safari or Brave when Google Chrome is running in the background.
* **Root Cause**: `(name of processes) contains "{b}"` tests whether the process is *running anywhere in memory*, not if it is *frontmost*. Because Google Chrome is first in the list, it is always selected, sending clicks to an unseen background Chrome window.
* **Fix**: Query `first application process whose frontmost is true` to obtain the actual active application.

---

### BUG-13: Multithreaded Unbounded While Loop in Proactive Alerts Daemon
* **Location**: [jarvis_daemon.py:L116-L118](file:///Volumes/WD_Subharup/jev/jarvis_daemon.py#L116-L118)
* **Code**:
  ```python
  while can_speak_predicate and not can_speak_predicate():
      time.sleep(1)
  speak_callback(alert)
  ```
* **Failure Trigger**: An alert triggers while recording or during system shutdown.
* **Root Cause**: The `while` loop has no check for `_RUNNING` and no timeout expiration. If the assistant enters a long task or shuts down while waiting to speak, the background thread hangs forever in an infinite spin.
* **Fix**: Add `while _RUNNING and can_speak_predicate and not can_speak_predicate():` with a 30-second timeout.

---

### BUG-14: Cloud LLM Planner Failure on Local Ollama Absence
* **Location**: [jarvis_planner.py:L150-L165](file:///Volumes/WD_Subharup/jev/jarvis_planner.py#L150-L165)
* **Code**:
  ```python
  r = requests.post(f"{OLLAMA_HOST}/v1/chat/completions", ...)
  ```
* **Failure Trigger**: Multi-step or conditional commands when Ollama is not installed or running locally.
* **Root Cause**: `jarvis_planner.py` only connects to `localhost:11434`. When connection is refused, it catches the exception and drops directly to a basic hardcoded heuristic that only knows about Spotify and Slack. It ignores configured OpenRouter (`OR_KEY`) and Gemini (`GEMINI_KEY`) cloud credentials.
* **Fix**: Introduce multi-tier fallback: Local Ollama -> OpenRouter -> Gemini -> Heuristic.

---

### BUG-15: Path Traversal String Boundary Bypass in Project File Reader
* **Location**: [jarvis_dev.py:L93](file:///Volumes/WD_Subharup/jev/jarvis_dev.py#L93)
* **Code**:
  ```python
  if not target_path.startswith(path):
      return "Access denied: the requested path is outside the project boundaries, sir."
  ```
* **Failure Trigger**: Reading files in adjacent directories sharing the same prefix name.
* **Root Cause**: `target_path.startswith(path)` without a trailing slash matches any folder whose name begins with `path` (e.g. `/Volumes/WD_Subharup/jev_private/secret.txt` matches `/Volumes/WD_Subharup/jev`).
* **Fix**: Use `os.path.commonpath([path, target_path]) == path` or append `os.sep`.

---

### BUG-16: Synchronous Event Loop Starvation in Rust Core Daemon
* **Location**: [jarvis_core/src/main.rs:L100-L165](file:///Volumes/WD_Subharup/jev/jarvis_core/src/main.rs#L100-L165), [jarvis_core/src/main.rs:L198](file:///Volumes/WD_Subharup/jev/jarvis_core/src/main.rs#L198)
* **Code**:
  ```rust
  match listener.accept() {
      Ok((stream, _)) => {
          handle_client(stream, start_time); // Synchronous blocking call
      }
  ...
  ```
* **Failure Trigger**: Any telemetry query while `osascript` is displaying a modal dialogue or hanging.
* **Root Cause**: `handle_client` runs on the primary socket accept thread and executes blocking child processes (`Command::new("osascript")`). A hung AppleScript freezes the entire daemon, causing all other IPC requests to time out.
* **Fix**: Dispatch client socket streams into separate worker threads (`std::thread::spawn(move || handle_client(...))`).

---

### BUG-17: JavaScript Code Injection & Syntax Crash in WebKit Dynamic Island HUD
* **Location**: [assistant_ui.py:L692-L695](file:///Volumes/WD_Subharup/jev/assistant_ui.py#L692-L695)
* **Code**:
  ```python
  safe_detail = detail.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"').replace("\n", " ")
  js = f"updateAssistantState('{safe_state}', '{safe_detail}')"
  self.notch_webview.evaluateJavaScript_completionHandler_(js, None)
  ```
* **Failure Trigger**: Spoken transcript containing carriage returns (`\r`), Unicode line breaks (`\u2028`, `\u2029`), or backticks.
* **Root Cause**: Incomplete manual escaping results in invalid ECMAScript string tokens, causing WebKit to throw `SyntaxError: Invalid or unexpected token` and stop updating the HUD orb.
* **Fix**: Use `json.dumps(state)` and `json.dumps(detail)` to generate syntactically safe JavaScript string literals.

---

### BUG-18: Calculator Cold Boot Key Drop & Destructive Word Replacement
* **Location**: [jarvis_gui.py:L185-L202](file:///Volumes/WD_Subharup/jev/jarvis_gui.py#L185-L202)
* **Code**:
  ```python
  exp_clean = re.sub(r"\bplus\b|\band\b", "+", exp_clean)
  ...
  subprocess.run(["open", "-a", "Calculator"])
  time.sleep(0.3)
  ```
* **Failure Trigger**: "Open calculator and calculate 50 minus 10" or using word numbers ("two plus two").
* **Root Cause**:
  1. Replacing `\band\b` with `+` converts the English conjunction in compound prompts into a plus sign (`+50-10`).
  2. `0.3s` sleep is insufficient for cold-booting Calculator on macOS Sequoia, causing keystrokes to drop before the UI window is ready.
  3. Word numbers ("two", "five") are stripped by `re.sub(r"[^0-9+\-*/.]", "")`, leaving bare operators that crash the calculation.
* **Fix**: Increase window readiness polling and sanitize math phrases independently from compound command conjunctions.

---

### BUG-19: Multi-Monitor Window Coordinate Flipping & Origin Desync
* **Location**: [jarvis_windows.py:L8-L15](file:///Volumes/WD_Subharup/jev/jarvis_windows.py#L8-L15)
* **Code**:
  ```python
  screen = NSScreen.mainScreen()
  frame = screen.frame()
  visible = screen.visibleFrame()
  ```
* **Failure Trigger**: Calling `"maximize window"` on an external display.
* **Root Cause**: `NSScreen.mainScreen()` returns the screen with keyboard focus, not necessarily the screen hosting the target window. In addition, secondary monitors frequently have negative origin offsets (e.g. `{-1920, 0}`), so setting `{0, menu_bar}` forcibly drags the window across displays onto the laptop screen.
* **Fix**: Query the window's current screen via AppleScript bounds before recalculating target dimensions.

---

### BUG-20: Unchecked `shell=True` Subprocess Execution in Self-Healing Remediation
* **Location**: [jarvis_self_healing.py:L291-L293](file:///Volumes/WD_Subharup/jev/jarvis_self_healing.py#L291-L293)
* **Code**:
  ```python
  res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
  ```
* **Failure Trigger**: LLM hallucinating complex or destructive shell commands during automated self-repair.
* **Root Cause**: Running `shell=True` on dynamically generated text from an external LLM without command whitelisting introduces arbitrary command execution risks.
* **Fix**: Enforce strict command prefix verification and avoid shell string execution.

---

### BUG-21: Timer Cancellation Concurrency Race Terminating Timer Thread
* **Location**: [siri.py:L981-L982](file:///Volumes/WD_Subharup/jev/siri.py#L981-L982)
* **Code**:
  ```python
  due = [t for t in TIMERS if t["end"] <= time.time()]
  for t in due:
      TIMERS.remove(t)
  ```
* **Failure Trigger**: User says "cancel all timers" or cancels a timer right as another timer expires.
* **Root Cause**: If `TIMERS.clear()` executes concurrently between the list comprehension and `remove()`, `TIMERS.remove(t)` throws an unhandled `ValueError: list.remove(x): x not in list`, terminating the background timer thread.
* **Fix**: Guard removal with `if t in TIMERS: TIMERS.remove(t)`.

---

### BUG-22: Screen Recording TCC Blindness & Silent Failure on Desktop Wallpaper
* **Location**: [siri.py:L676](file:///Volumes/WD_Subharup/jev/siri.py#L676)
* **Code**:
  ```python
  sh("screencapture", "-x", "-m", "-t", "jpg", tmp_path)
  ```
* **Failure Trigger**: Calling `"What is on my screen?"` when macOS Screen Recording permission has not been granted.
* **Root Cause**: `screencapture` does not return an error code when permission is denied; macOS privacy sandboxing returns an image showing only the empty desktop wallpaper. The vision model then states it only sees wallpaper, confusing the user.
* **Fix**: Check `CGPreflightScreenCaptureAccess()` or inspect captured image variance to detect blank wallpaper capture.

---

### BUG-23: Audio Stream Watchdog Missing / Device Disconnection Deafness
* **Location**: [siri.py:L1760](file:///Volumes/WD_Subharup/jev/siri.py#L1760)
* **Code**:
  ```python
  self.stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                               blocksize=self.BLOCK, callback=self._cb)
  ```
* **Failure Trigger**: Unplugging or reconnecting USB DAC, Bluetooth headset, or system sleep/wake.
* **Root Cause**: PortAudio callback flags (`status` argument in `_cb`) and device disconnection errors are ignored. Once the stream enters an inactive state, the assistant remains deaf until manually restarted.
* **Fix**: Implement an audio stream watchdog that re-initializes `sd.InputStream` if stream becomes inactive.

---

### BUG-24: Stale Key Loading and Missing OpenRouter Fallback in Web Search
* **Location**: [jarvis_search.py:L7](file:///Volumes/WD_Subharup/jev/jarvis_search.py#L7)
* **Code**:
  ```python
  NVIDIA_KEY = get_secret("NVIDIA_API_KEY")
  ```
* **Failure Trigger**: Changing API keys in `.env` or keychain during a running session.
* **Root Cause**: Key is read only once when the module is imported. Subsequent changes are ignored. In addition, OpenRouter fallback is referenced in comments but never implemented in code.
* **Fix**: Query `get_secret()` dynamically in `search_and_synthesize()` and implement the OpenRouter fallback.

---

### BUG-25: Fish Audio Hard Dependency in Reminder Pre-Caching
* **Location**: [siri.py:L929](file:///Volumes/WD_Subharup/jev/siri.py#L929)
* **Code**:
  ```python
  fetch_tts(data["alert"])  # cache the audio now
  ```
* **Failure Trigger**: Setting a reminder when `FISH_AUDIO_API_KEY` is not configured.
* **Root Cause**: `fetch_tts()` returns `None, 0, True` when `FISH_KEY` is missing and never invokes `fetch_neural_tts()`. The audio is not pre-cached with Edge-TTS, causing delays when the reminder fires.
* **Fix**: Call `fetch_neural_tts(data["alert"])` if `FISH_KEY` is not present.

---

### BUG-26: Search Inversion & STT Phonetic Mis-routing for Common Web Operations
* **Location**: [siri.py:L38](file:///Volumes/WD_Subharup/jev/siri.py#L38), [siri.py:L600](file:///Volumes/WD_Subharup/jev/siri.py#L600), [siri.py:L1520](file:///Volumes/WD_Subharup/jev/siri.py#L1520), [siri.py:L1610](file:///Volumes/WD_Subharup/jev/siri.py#L1610)
* **Failure Trigger**: 
  1. Saying "open google" launches Chrome app without navigating to `google.com`.
  2. Saying "open you tube" or "open yout tube" fails with `I couldn't locate an application or page named you tube, sir.`
  3. Saying "open youtube and search something" searches Google instead of YouTube, or splits into two disjointed actions.
  4. Saying "search lofi on youtube" triggers `search_and_synthesize` scraping DuckDuckGo and reading aloud an essay instead of opening YouTube.
  5. Saying "search python tutorial on google" mangles the search query into `"search python tutorial on"` because trailing `google` matches `m_trail` prematurely.
  6. Silent pauses during PTT cause Whisper to transcribe `COMMAND_PROMPT` ("Mac voice assistant commands..."), triggering accidental volume mutes.
* **Root Cause**: 
  1. `_parse_search_intent` ran before `play_youtube` and `search_google_browser`, intercepting search phrases and treating them as knowledge queries (`smode='smart'`).
  2. `open_app()` only looked for `.app` bundles on disk or single words with no spaces; multi-word web destinations ("you tube", "web whatsapp", etc.) failed.
  3. `split_compound_tasks` split "open X and search Y" into independent tasks, stripping the context of the destination site.
  4. Whisper STT lacked phonetic post-processing for common slips ("you tube", "goggle", "serch", "somehting").
* **Fix**:
  1. Implemented `clean_transcription()` to drop hallucinated prompts and normalize common phonetic slips and stuttering.
  2. Implemented `extract_youtube_search()` and `extract_google_search()` with top-priority routing in `execute_single_action()`.
  3. Added `WEB_TARGETS` dictionary in `open_app()` to directly navigate to Google, YouTube, Gmail, GitHub, Reddit, and other popular destinations.
  4. Preserved unified search compound phrases in `split_compound_tasks()` to prevent fragmentation.
  5. Reduced browser launch delay in `jarvis_browser.py` from 1.0s to 0.1s for instantaneous responsiveness.

---

## 3. Operational Best Practices to Prevent Failures

1. **macOS Permissions**:
   * Grant **Accessibility** and **Screen Recording** to Terminal/Python in *System Settings → Privacy & Security*.
2. **Browser Settings**:
   * Enable *Allow JavaScript from Apple Events* in Chrome / Brave menu: `View → Developer`.
3. **Audio Configuration**:
   * Ensure external DACs (like CX31993) are set as default input in *System Settings → Sound*.
4. **Push-To-Talk / Pause**:
   * Push Right Option once to talk; push again while speaking to pause/stop playback instantly.
5. **Self-Healing Verification**:
   * Inspect [learned_actions.json](file:///Volumes/WD_Subharup/jev/learned_actions.json) periodically to review auto-generated repairs.
