# NIKO Architecture Refinement & Performance Plan

**Goal:** Eliminate architectural latency bottlenecks, replace slow AppleScript subprocess forks with native macOS Cocoa APIs, optimize Laya intent routing, and integrate the native Rust core daemon.

**Architecture:**
1. **Tiered Intent Routing**: Fast deterministic triage (<1ms) -> Controlled Laya fallback with schema gating -> System 2 LLaMA 3.2 NIM for deep reasoning.
2. **Native Cocoa IPC**: Replace `osascript` process forks with `AppKit.NSWorkspace` and `NSRunningApplication` for instant sub-millisecond app queries and management.
3. **Rust Core Integration**: Auto-launch native `bin/jarvis_core` Unix socket daemon for zero-overhead OS commands.

**Tech Stack:** Python 3.12, PyObjC (AppKit/Cocoa), faster-whisper, Laya, Unix Domain Sockets, Rust.

---

### Task 1: Native Cocoa App Management (`NSWorkspace`)
- **Files**: `action_dispatcher.py`, `platform_adapter.py`
- Replace `osascript -e 'application "X" is running'` with `NSWorkspace.sharedWorkspace().runningApplications()`.
- Replace `open -a` with `NSWorkspace.sharedWorkspace().launchApplication_(name)`.

### Task 2: Tiered Intent Routing Optimization
- **Files**: `laya_engine.py`, `action_dispatcher.py`
- Avoid running 10-question cross-encoder passes when intent is already resolved by deterministic triage.
- Guard fallback queries so open-ended questions bypass rigid classification directly to LLM.

### Task 3: Rust Core Daemon Auto-Start & Socket IPC
- **Files**: `jarvis_rust_client.py`, `siri.py`
- Auto-start `bin/jarvis_core` on assistant boot to handle instant system telemetry, workstation lock, and trash management.

### Task 4: Verification & Daemon Reload
- Test end-to-end latency and verify all queries on live system.
