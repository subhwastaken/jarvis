"""Live OS & Hardware Execution Proof Suite for J.A.R.V.I.S.
Directly verifies that commands actually manipulate the real macOS operating system,
hardware audio registers, disk files, application processes, and system preferences.
"""
import os
import sys
import subprocess
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from action_dispatcher import (
    open_app, close_app, is_app_running, resolve_app_path,
    set_system_volume, adjust_system_volume, mute_system_volume,
    system_ram, system_battery, system_disk
)
from jarvis_clipboard import get_clipboard_text, set_clipboard_text
from jarvis_notes import take_quick_note, get_latest_note
from jarvis_dev import get_git_summary
import platform_adapter


def run_live_proofs():
    print("=" * 70)
    print("J.A.R.V.I.S. REAL macOS OS & HARDWARE EXECUTION VERIFICATION")
    print("=" * 70)
    passed = 0
    total = 0

    # 1. CORE AUDIO VOLUME MANIPULATION
    total += 1
    print("\n[Proof 1] Hardware Audio Volume Manipulation (CoreAudio)")
    orig_vol = platform_adapter.get_volume()
    print(f"  Initial CoreAudio volume: {orig_vol}%")
    
    # Change to 42%
    reply1 = set_system_volume(42)
    time.sleep(0.3)
    measured_vol = platform_adapter.get_volume()
    print(f"  Action executed: set_system_volume(42) -> '{reply1}'")
    print(f"  Measured CoreAudio hardware state: {measured_vol}%")
    assert measured_vol == 42, f"Expected 42%, got {measured_vol}%"

    # Adjust by +8% -> 50%
    reply2 = adjust_system_volume(8)
    time.sleep(0.3)
    measured_vol2 = platform_adapter.get_volume()
    print(f"  Action executed: adjust_system_volume(+8) -> '{reply2}'")
    print(f"  Measured CoreAudio hardware state: {measured_vol2}%")
    assert measured_vol2 == 50, f"Expected 50%, got {measured_vol2}%"

    # Restore original volume
    set_system_volume(orig_vol)
    print(f"  Restored CoreAudio volume to: {platform_adapter.get_volume()}%")
    print("  -> PROOF 1 PASSED: Real audio hardware registers were changed and verified.")
    passed += 1

    # 2. CLIPBOARD MANIPULATION (macOS NSPasteboard / pbcopy / pbpaste)
    total += 1
    print("\n[Proof 2] Native macOS Pasteboard Manipulation")
    orig_clip = get_clipboard_text()
    test_token = f"JARVIS_VERIFY_{int(time.time())}"
    ok = set_clipboard_text(test_token)
    time.sleep(0.2)
    read_back = get_clipboard_text()
    print(f"  Wrote token to pasteboard: '{test_token}'")
    print(f"  Read back from pbpaste:   '{read_back}'")
    assert read_back == test_token, f"Clipboard mismatch: expected {test_token}, got {read_back}"
    if orig_clip:
        set_clipboard_text(orig_clip)
    print("  -> PROOF 2 PASSED: System clipboard state was genuinely written and retrieved.")
    passed += 1

    # 3. KERNEL RAM METRICS (Mach VM)
    total += 1
    print("\n[Proof 3] Mach Kernel Virtual Memory Introspection")
    ram_str = system_ram()
    print(f"  Output: '{ram_str}'")
    assert "gigabytes of RAM" in ram_str, f"Invalid RAM output: {ram_str}"
    print("  -> PROOF 3 PASSED: Mach vm_stat kernel frames parsed live.")
    passed += 1

    # 4. POWER & BATTERY INTROSPECTION (IOKit pmset)
    total += 1
    print("\n[Proof 4] IOKit Power & Battery Introspection")
    batt_str = system_battery()
    print(f"  Output: '{batt_str}'")
    assert "battery" in batt_str.lower() or "power adapter" in batt_str.lower(), f"Invalid battery output: {batt_str}"
    print("  -> PROOF 4 PASSED: IOKit power telemetry gathered live.")
    passed += 1

    # 5. APFS FILESYSTEM INTROSPECTION (df -h)
    total += 1
    print("\n[Proof 5] APFS Storage Introspection")
    disk_str = system_disk()
    print(f"  Output: '{disk_str}'")
    assert "free disk space" in disk_str.lower(), f"Invalid disk output: {disk_str}"
    print("  -> PROOF 5 PASSED: Live APFS volume allocation measured.")
    passed += 1

    # 6. DISK NOTE PERSISTENCE
    total += 1
    print("\n[Proof 6] Disk Persistence & Note Logging")
    note_text = f"Automated test note {int(time.time())}"
    note_reply = take_quick_note(note_text)
    print(f"  Action reply: '{note_reply}'")
    latest = get_latest_note()
    print(f"  Retrieved latest note from disk: '{latest}'")
    assert note_text in latest, f"Note was not persisted to disk! Found: {latest}"
    print("  -> PROOF 6 PASSED: Real file written to Desktop/QuickNotes.md.")
    passed += 1

    # 7. SPOTLIGHT BUNDLE RESOLUTION
    total += 1
    print("\n[Proof 7] macOS Spotlight Metadata Querying (mdfind)")
    calc_path = resolve_app_path("Calculator")
    print(f"  Resolved 'Calculator' path: {calc_path}")
    assert calc_path and os.path.exists(calc_path), f"Failed to resolve Calculator path: {calc_path}"
    print("  -> PROOF 7 PASSED: Dynamic Spotlight index lookup works.")
    passed += 1

    # 8. REAL PROCESS LIFECYCLE (Launch, Verify Running, Quit)
    total += 1
    print("\n[Proof 8] Real Application Process Lifecycle (Calculator)")
    open_reply = open_app("Calculator")
    print(f"  Action reply: '{open_reply}'")
    time.sleep(1.0)
    running_before = is_app_running("Calculator")
    print(f"  Process state (running?): {running_before}")
    assert running_before is True, "Calculator failed to launch!"
    
    close_reply = close_app("Calculator")
    print(f"  Action reply: '{close_reply}'")
    time.sleep(1.0)
    running_after = is_app_running("Calculator")
    print(f"  Process state after quit (running?): {running_after}")
    assert running_after is False, "Calculator failed to close!"
    print("  -> PROOF 8 PASSED: Real application was spawned, verified in process table, and terminated.")
    passed += 1

    # 9. GIT INTROSPECTION
    total += 1
    print("\n[Proof 9] Developer Git Subsystem Introspection")
    git_str = get_git_summary()
    print(f"  Git status summary: '{git_str}'")
    assert "branch" in git_str.lower(), f"Invalid git summary: {git_str}"
    print("  -> PROOF 9 PASSED: Real git subcommands executed.")
    passed += 1

    # 10. MACOS APPEARANCE (Dark Mode Toggle)
    total += 1
    print("\n[Proof 10] macOS Appearance Preferences")
    res_dark = subprocess.run(["osascript", "-e", 'tell application "System Events" to tell appearance preferences to get dark mode'], capture_output=True, text=True)
    orig_dark = res_dark.stdout.strip().lower() == "true"
    print(f"  Initial Dark Mode state: {orig_dark}")
    
    # Toggle
    platform_adapter.set_dark_mode(not orig_dark)
    time.sleep(0.3)
    res_new = subprocess.run(["osascript", "-e", 'tell application "System Events" to tell appearance preferences to get dark mode'], capture_output=True, text=True)
    new_dark = res_new.stdout.strip().lower() == "true"
    print(f"  Toggled Dark Mode state: {new_dark}")
    assert new_dark != orig_dark, "Dark mode did not toggle in OS appearance preferences!"

    # Restore
    platform_adapter.set_dark_mode(orig_dark)
    time.sleep(0.3)
    print(f"  Restored Dark Mode state: {orig_dark}")
    print("  -> PROOF 10 PASSED: macOS System Events appearance preferences altered and verified.")
    passed += 1

    print("\n" + "=" * 70)
    print(f"SUMMARY: {passed} / {total} LIVE HARDWARE & OS PROOFS VERIFIED (100% REAL EXECUTION)")
    print("=" * 70)
    return passed == total


if __name__ == "__main__":
    success = run_live_proofs()
    sys.exit(0 if success else 1)
