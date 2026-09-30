# Cross-Platform macOS & Windows Architecture Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable Hey-Jev / J.A.R.V.I.S. to run seamlessly on both macOS and Windows, making both the Dynamic Island Floating Orb HUD and all OS Automations cross-platform.

**Architecture:** 
1. Build `platform_adapter.py` as an OS-agnostic hardware and system automation abstraction layer. Automatically routes commands to AppleScript/Cocoa on macOS, and Win32/PowerShell/Registry on Windows for volume, media, app launching, power, telemetry, and dark mode.
2. Build `jarvis_hud.py` as a universal floating Dynamic Island window controller that renders `assets/dynamic_island.html` at the top center of the screen on both macOS (via Cocoa WKWebView) and Windows (via WebView2/pywebview frameless transparent window).
3. Update `secrets_store.py` with Windows Credential Vault support alongside macOS Keychain.
4. Update `siri.py` `ACTIONS` to route through `platform_adapter.py`.

**Tech Stack:** Python 3, macOS Cocoa / AppleScript, Windows Win32 / PowerShell / Registry, HTML5/CSS3 Dynamic Island Siri Orb.

---

### Task 1: Create `platform_adapter.py` (OS Automation Abstraction)
- Implement universal methods:
  - `set_volume(level)` / `get_volume()` / `mute_volume(mute)`
  - `open_app(name)` / `close_app(name)`
  - `media_play()` / `media_pause()` / `media_next()` / `media_previous()` / `media_volume(delta, level, mute)`
  - `toggle_dark_mode(state)`
  - `lock_screen()` / `sleep_system()`
  - `get_ram()` / `get_battery()` / `get_disk()`
  - `take_screenshot(output_path)` / `empty_trash()`
- On macOS: dispatches to AppleScript / native system calls.
- On Windows: dispatches to PowerShell, Win32 commands, Windows Registry, and Windows Media keys.

### Task 2: Cross-Platform Secrets Store (`secrets_store.py`)
- Keep macOS Keychain as default on macOS (`security`).
- Add Windows Credential Manager / PowerShell fallback on Windows (`cmdkey` / Windows Vault).

### Task 3: Universal Dynamic Island HUD (`jarvis_hud.py`)
- Position frameless, transparent, always-on-top pill window (270px x 38px) docked at top center on both macOS and Windows.
- Provide clean API: `init_hud()`, `update_hud(state, detail)`, `close_hud()`.

### Task 4: Integrate `platform_adapter` into `siri.py`
- Refactor `ACTIONS` in `siri.py` to route through `platform_adapter`.

### Task 5: Testing & Verification
- Add cross-platform test cases in `scratch/test_cross_platform.py` and run tests.
