# Security Hardening, Portability & Reliability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate critical Remote Code Execution (RCE) vulnerabilities, decouple machine-specific hardcoded paths, fix path traversal risks, and implement audio device recovery in J.A.R.V.I.S.

**Architecture:** Replace un-sandboxed dynamic shell execution in `jarvis_self_healing.py` with a strict allowlist runner (`shlex.split`, `shell=False`, no chaining/redirection, banning `do shell script` in AppleScript). Standardize project root detection in `jarvis_dev.py` with dynamic user directories and `os.path.commonpath` boundary checks. Enhance the audio `Recorder` in `siri.py` with an auto-recovery watchdog for audio device changes and stream drops.

**Tech Stack:** Python 3, macOS Cocoa/PyObjC, shlex, subprocess, sounddevice, faster-whisper.

---

### Task 1: Harden Self-Healing Execution Engine (Fix RCE)

**Files:**
- Modify: `jarvis_self_healing.py:270-301`
- Test: `scratch/test_validation.py`

**Step 1: Implement safe command validation and runner**
- Remove `shell=True` from `subprocess.run` on line 292.
- Introduce `SAFE_BASH_BINARIES = {"open", "pkill", "defaults", "afplay", "pmset", "killall", "screencapture"}`.
- Block dangerous shell meta-characters (`;`, `&&`, `||`, `|`, `>`, `<`, `` ` ``, `$`).
- For `applescript`, inspect and block any scripts containing `do shell script`.

**Step 2: Run verification tests to ensure malicious scripts are rejected and safe repairs succeed.**

---

### Task 2: Eliminate Hardcoded Machine Paths & Fix Path Traversal in Project Tools

**Files:**
- Modify: `jarvis_dev.py:7-13, 87-96`
- Modify: `jarvis_memory.py`
- Test: `scratch/test_validation.py`

**Step 1: Replace hardcoded `/Volumes/WD_Subharup/...` with dynamic directories**
- Update `DEFAULT_PROJECT_DIRS` to dynamically scan `~/Developer`, `~/Projects`, `~/Documents`, current working directory, and check `JARVIS_PROJECT_DIRS` environment variable.
- Replace `target_path.startswith(path)` with `os.path.commonpath([path, target_path]) == path` to prevent directory prefix traversal collisions.

**Step 2: Run verification tests on path resolution and boundary enforcement.**

---

### Task 3: Audio Stream Watchdog & Recovery in `siri.py`

**Files:**
- Modify: `siri.py:1915-1975`
- Test: `scratch/test_validation.py`

**Step 1: Add stream health check & auto-restart in `Recorder`**
- Handle `status` flags in the PortAudio callback.
- Add `ensure_stream_active()` method to `Recorder` that safely recreates the `sd.InputStream` if closed or stopped by an audio device change (AirPods disconnect, sleep/wake).

---

### Task 4: Regression & Validation Test Suite Execution

**Files:**
- Modify: `scratch/test_validation.py`
- Execute via `.venv/bin/python scratch/test_validation.py`
- Verify 100% of syntax, security, path traversal, and volume tests pass cleanly.
