# Coming Soon — Feature Roadmap

> **Project:** DictateAnywhere
> **Last updated:** 2026-05-04

Enhancement ideas ranked by user impact and implementation complexity.

---

---

## ✅ Recently Completed

### E-01 · GPU / CUDA acceleration (RTX 5060)
**Status:** Completed in v1.5.0. 
- Integrated `faster-whisper` with CTranslate2 CUDA backend.
- Automated DLL discovery for NVIDIA libraries on Windows.
- Multi-stage fallback to CPU/int8 on initialization failure.
- Default settings optimized for GPU performance.

### E-02 · Streaming / real-time transcription
**Status:** Completed in v1.4.0.
- Implemented real-time partial results via Sarvam AI WebSockets.
- Integrated live audio processing with the preview overlay.
- Dynamic waveform visualizer for real-time mic monitoring.

---

## 🚀 High Impact — Next Release Candidates

### E-03 · Multi-segment continuous dictation
**Module:** `main.py`, `audio/capture.py`
Currently each recording is capped by `max_record_seconds`. For long-form dictation (medical notes, letters), auto-split into overlapping segments and transcribe/stitch seamlessly.
- No hard timeout for the user — just keep talking
- Stitch overlap regions with confidence-weighted alignment

### E-04 · Per-application language profiles
**Module:** `utils/config.py`, `main.py`
Switch language automatically based on the foreground window.
- Config: `app_language_map: {"WINWORD.EXE": "en", "firefox.exe": "fr"}`
- Read foreground process name via `win32gui.GetForegroundWindow()` + `psutil`
- Fall back to default language if no mapping found

### E-05 · Whisper hallucination guard — confidence-based rejection
**Module:** `transcription/local_engine.py`, `core/punctuation.py`
Even with VAD, Whisper sometimes hallucinates common phrases ("Thank you", "Bye").
- Use segment-level `avg_logprob` and `no_speech_prob` from faster-whisper
- Reject segments with `avg_logprob < -1.0` or `no_speech_prob > 0.7`
- Configurable thresholds in settings

---

## 🔧 Medium Impact — Quality of Life

### E-06 · Rich notification system (toast notifications)
**Module:** NEW `ui/notifications.py`
Replace the update dialog with Windows 10/11 toast notifications (via `win10toast` or `winotify`).
- Non-intrusive — dismisses automatically
- Action buttons: "Download", "Dismiss"
- Can also notify on transcription errors, mic issues

### E-07 · Dictation sound effects
**Module:** NEW `audio/sounds.py`
Play subtle audio cues: beep on start, chime on stop, error tone on failure.
- Use `winsound.PlaySound()` or `sounddevice` to play embedded WAV assets
- Toggle in settings; volume slider
- Helps users know when dictation is active without looking at screen

### E-08 · Hotkey recording widget
**Module:** `ui/settings_window.py`, `core/hotkey_manager.py`
Instead of typing `ctrl+alt+d` by hand, let users press the desired key combination.
- "Press your desired hotkey…" capture dialog
- Display human-readable combo (Ctrl + Alt + D)
- Detect conflicts with known system hotkeys

### E-09 · Export/import settings and corrections
**Module:** `utils/config.py`, `core/corrections.py`
Allow users to share configurations between machines.
- Export: ZIP of `config.json` + `corrections.json`
- Import: merge or replace from ZIP
- Settings button: "Export Settings…" / "Import Settings…"

### E-10 · Persistent session history (SQLite)
**Module:** `ui/history_window.py`, NEW `utils/database.py`
History is currently in-memory and lost on restart.
- SQLite database in `%APPDATA%\DictateAnywhere\history.db`
- Store: timestamp, text, engine_used, duration_ms, confidence
- Searchable across sessions; daily/weekly summaries
- Configurable retention period (30/60/90 days)

### E-11 · Multi-monitor floating widget awareness
**Module:** `ui/floating_widget.py`
The floating button can be dragged off-screen on multi-monitor setups (especially with negative coordinates).
- Clamp position to visible screen bounds on move
- Snap to nearest screen edge
- Remember position per-monitor via display ID

### E-12 · Noise floor auto-calibration
**Module:** `audio/capture.py`, `audio/vad.py`
Record 2 seconds of ambient noise at startup. Compute baseline RMS.
- Set silence gate threshold dynamically above the noise floor
- Works in noisy clinics, coffee shops, etc.
- One-time calibration + periodic re-check

### E-13 · System theme integration (dark/light mode auto-detect)
**Module:** `ui/settings_window.py`, `ui/history_window.py`
Settings and history windows use hardcoded colours.
- Read Windows accent colour and dark mode preference via registry or `winrt`
- Apply `sv_ttk` or `ttkbootstrap` for modern themed widgets
- Respect `theme: "system" | "light" | "dark"` config key (already exists)

### E-14 · Tray icon tooltip with last dictation preview
**Module:** `ui/tray.py`
Currently the tooltip only shows state. Show a truncated preview of the last dictated text.
- `DictateAnywhere — "Hello, how are you..." (12s ago)`
- Helpful to confirm what was just typed without looking at the preview overlay

### E-15 · Custom wake word ("Hey Dictate")
**Module:** NEW `audio/wakeword.py`, `main.py`
Hands-free activation using a lightweight keyword spotting model (Porcupine, OpenWakeWord).
- Runs continuously with minimal CPU
- On detection, auto-starts recording — no hotkey needed
- Configurable keyword

---

## 🌐 Platform & Ecosystem

### E-16 · macOS support (pynput + CoreAudio)
**Module:** Many — `core/text_injector.py`, `ui/tray.py`, `core/hotkey_manager.py`
Replace Windows-only deps (`pywin32`, `keyboard`, `pystray._win32`) with cross-platform alternatives.
- `pynput` for hotkeys and text injection
- `rumps` for macOS menu bar
- `keychain` for macOS credential storage
- Big project — split into a separate branch/milestone

### E-17 · Linux support (X11/Wayland)
Similar to E-16 but targeting Linux.
- `xdotool` / `ydotool` for text injection
- `gnomekeyring` / `secretstorage` for credentials
- `pynput` for global hotkeys (requires `$DISPLAY`)

### E-18 · Browser extension companion
**Module:** NEW standalone extension
A minimal Chrome/Firefox extension that communicates with the running DictateAnywhere app.
- Click-to-dictate button in the browser toolbar
- Inject text directly into `<textarea>` and `contenteditable` elements
- WebSocket or native messaging API

### E-19 · REST API for integration
**Module:** NEW `api/server.py`
Expose DictateAnywhere as a local HTTP service for automation.
- `POST /dictate/start`, `POST /dictate/stop`, `GET /dictate/status`
- `POST /transcribe` — send audio bytes, get text back
- Enables integration with AHK scripts, Stream Deck, etc.

---

## 🎨 UI Polish

### E-20 · Animated state transitions on the floating widget
**Module:** `ui/floating_widget.py`
Smooth colour transitions between idle → active → loading states using interpolated HSL.
- Fade from blue to red over 200 ms instead of instant snap
- Adds a premium feel to the microphone button

### E-22 · Keyboard shortcut cheat sheet overlay
**Module:** NEW `ui/cheatsheet.py`
Toggle a quick-reference overlay showing all spoken commands.
- "Say 'period' for . | 'comma' for , | 'new line' for ↵"
- Triggered by tray menu or hotkey
- Fades out after a configurable delay

### E-23 · Settings search / filter
**Module:** `ui/settings_window.py`
The settings window has 7 tabs with many options. Add a search bar at the top that filters visible settings by keyword.
- Type "mic" → shows only microphone-related settings
- Highlights matching labels

### E-24 · Tray icon badges
**Module:** `ui/tray.py`
Show a small badge (dot) on the tray icon when:
- An update is available (blue dot)
- Last transcription had an error (red dot)
- Currently recording (pulsing red)

---

## 📊 Analytics & Diagnostics

### E-25 · Built-in diagnostic report
**Module:** NEW `utils/diagnostics.py`
One-click "Generate report" button in Settings → Advanced.
- Collects: OS version, Python version, GPU info, audio devices, installed packages, config (sanitized), last 50 log lines
- Saves to `diagnostics_<date>.txt`
- Attach to bug reports for faster triage

### E-26 · Transcription accuracy feedback loop
**Module:** `ui/preview_window.py`, `ui/history_window.py`
Let users mark dictated text as "correct" or "incorrect" in the preview/history.
- Builds a local dataset of corrections
- Could auto-generate correction rules
---

## ⚡ Performance & Snappiness

### E-27 · Latency Fix Plan (Snappy Dictation)
**Module:** `transcription/gemini_engine.py`, `main.py`, `core/polish.py`
Transform the sequential "Batch" workflow into a concurrent "Streaming" pipeline to rival professional solutions.

1.  **WebSocket Migration (Gemini Live API)**:
    - Replace REST `generateContent` with Gemini Multimodal Live API (WebSockets).
    - **Goal:** Real-time partial results as the user speaks (identical to the Sarvam experience).
2.  **Overlapped "Streaming Polish"**:
    - Trigger the Polish AI as soon as the first stable sentence is received from the STT stream.
    - **Goal:** Finish polishing within <500ms of the user releasing the hotkey.
3.  **Instant Visual Feedback (Local/Cloud Hybrid)**:
    - Run `faster-whisper` (tiny/base) locally in parallel with the Cloud engine.
    - Show local text instantly (<100ms) and "swap" it with high-quality Cloud text when ready.
4.  **Opus/AAC Audio Compression**:
    - Encode audio chunks on-the-fly to reduce upload bandwidth by 10-15x.
    - **Goal:** Significant reduction in "Initial Delay" for users with slower upload speeds.
5.  **Partial Injection**:
    - Optional "Live Inject" mode that types text as it arrives, then "fixes" formatting/grammar after the fact.
API (WebSockets).
    - **Goal:** Real-time partial results as the user speaks (identical to the Sarvam experience).
2.  **Overlapped "Streaming Polish"**:
    - Trigger the Polish AI as soon as the first stable sentence is received from the STT stream.
    - **Goal:** Finish polishing within <500ms of the user releasing the hotkey.
3.  **Instant Visual Feedback (Local/Cloud Hybrid)**:
    - Run `faster-whisper` (tiny/base) locally in parallel with the Cloud engine.
    - Show local text instantly (<100ms) and "swap" it with high-quality Cloud text when ready.
4.  **Opus/AAC Audio Compression**:
    - Encode audio chunks on-the-fly to reduce upload bandwidth by 10-15x.
    - **Goal:** Significant reduction in "Initial Delay" for users with slower upload speeds.
5.  **Partial Injection**:
    - Optional "Live Inject" mode that types text as it arrives, then "fixes" formatting/grammar after the fact.
