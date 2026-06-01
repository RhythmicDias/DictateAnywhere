# Changelog

All notable changes to DictateAnywhere are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.7.0] - 2026-06-01

### Added

#### Profile Import & Export (`ui/settings_window.py`)
- **Import/Export Settings**: Added buttons to backup and load application settings profile to and from a JSON file.

#### Voice App Launcher (`ui/settings_window.py`, `main.py`)
- **Voice App Launcher**: Introduced a setting allowing users to bind custom voice triggers (e.g. "open notepad") to system application paths for instantaneous launch.

#### Premium App Branding (`ui/settings_window.py`, `ui/history_window.py`, `ui/tray.py`, `assets/`)
- **App Icons**: Integrated glowing neon microphone window icons into the settings and history dialog title bars and taskbar icons.
- **App Logo Header**: Integrated a typography wordmark logo into the Settings Window header.
- **Tray Status Dots**: Upgraded the system tray icon to use the high-quality glowing microphone icon, overlaid with neon status indicator dots corresponding to system states (Idle, Recording, Loading, Error).
- **Standalone Icon compilation**: Configured `build.bat` to package the compiled `.exe` using the official `.ico` asset.

### Fixed

#### Windows Taskbar Grouping (`main.py`)
- **Explicit App ID**: Set the process AppUserModelID on Windows, resolving a native grouping issue where Windows grouped the application under Python's default launcher icon in the taskbar.

#### Notepad Alt-Key Focus Activation (`core/text_injector.py`)
- **Alt-Key Suppression**: Resolved an issue where releasing hotkeys simulated Alt key releases that triggered Windows menu bar focus (especially in Notepad) and interrupted subsequent text injection.

---

## [1.6.1] - 2026-05-11

### Fixed

#### Focus Stability (`ui/preview_window.py`, `ui/floating_widget.py`)
- **Non-Activating Windows**: Implemented `WS_EX_NOACTIVATE` via Win32 API for the preview overlay and floating mic button. This prevents these windows from stealing keyboard focus from the target application (e.g., Notepad, WhatsApp) when they appear or are clicked.
- **Focus Stealing Prevention**: Reinforced UI components with the `-noactivate` attribute to ensure that showing/hiding the overlay doesn't interrupt the user's cursor position or text injection process.

---

## [1.6.0] - 2026-05-08

### Added

#### Overlay Customization (`ui/settings_window.py`, `ui/preview_window.py`)
- **Visual Controls**: Added new settings to control the transparency (opacity) and text color of the transcription preview overlay.
- **Manual Entry**: Opacity can now be set via manual numeric entry with a "Set" button for immediate live feedback.
- **Color Picker**: Integrated a native color chooser for the overlay text, allowing for personalized themes (e.g., high-contrast or branded colors).
- **Tab Realignment**: Moved all "Transcription Preview Overlay" settings to the **Hotkey** tab for better feature grouping.

### Fixed

#### Injection Stability (`core/text_injector.py`)
- **WhatsApp Compatibility**: Fixed an issue where text injection failed in WhatsApp Desktop/Web by removing silent `Escape` key signals.
- **Silent Key Suppression**: Removed redundant "Esc" presses that were inadvertently clearing input fields or closing search bars in modern messaging applications.

---

## [1.5.0] - 2026-05-08

### Added

#### GPU-Accelerated Local Transcription (`transcription/local_engine.py`, `main.py`)
- **CUDA/cuBLAS Support**: Enabled full hardware acceleration for the `faster-whisper` engine, leveraging NVIDIA RTX GPUs (e.g., RTX 5060) for near-instant transcription.
- **Automated DLL Discovery**: Implemented a Windows-specific DLL injector in `main.py` that automatically scans the virtual environment for NVIDIA libraries (`cublas`, `cudnn`) and registers them with the system path.
- **Robust Fallback Engine**: Enhanced the `LocalEngine` with a multi-stage fallback strategy. If CUDA initialization or execution fails (due to missing drivers or DLLs), the engine now automatically downgrades to **CPU / int8** mode without crashing.
- **Real-Time Concurrency Locking**: Added thread synchronization to prevent race conditions when simultaneous real-time and final transcriptions access the same model instance.

#### Optimal Defaults & Performance
- **New Default Configuration**: Updated the standard out-of-the-box settings to the "Sweet Spot" for performance:
  - **Model**: `tiny` (blazing fast)
  - **Compute**: `int8` (memory efficient)
  - **Device**: `cuda` (GPU prioritized with auto-fallback)
- **Environment Stabilisation**: Forced `OMP_NUM_THREADS=1` and `MKL_NUM_THREADS=1` to prevent library-level deadlocks common on multi-core Windows machines.

### Fixed
- **Settings Sync**: Resolved a critical bug where changes to the `local_device` setting in the UI were not being propagated to the running transcription engine.
- **MKL Hangs**: Implemented `KMP_DUPLICATE_LIB_OK` fixes to resolve silent hangs during model initialization on Windows.

---

## [1.4.0] - 2026-05-07

### Added

#### Real-Time Streaming Transcription (`main.py`, `ui/preview_window.py`)
- **Live Previews**: Dictated text now appears instantaneously in the preview overlay as you speak, before you even finish the sentence.
- **Engine-Level Streaming**: Integrated **Sarvam AI WebSocket** support for ultra-low latency real-time transcription.
- **Configurable Frequency**: Users can adjust how often the real-time preview updates (default 800ms) in Settings → Advanced.
- **UI Persistence**: The preview overlay now intelligently remains visible through the entire lifecycle: Listening → Transcribing → LLM Polishing → Text Injection.

#### Sarvam AI Enhancements (`transcription/sarvam_engine.py`)
- **WebSocket Protocol**: Fully transitioned the Sarvam engine from polling (REST) to persistent streaming (WebSockets).
- **Language Mapping**: Automatic conversion of short codes (e.g., `hi`, `ml`) to Sarvam-compatible `-IN` codes (`hi-IN`, `ml-IN`).
- **Connection Diagnostics**: Added a "Test Sarvam Connection" button in settings to verify API keys and network status.

### Fixed
- **Overlay Flicker**: Resolved an issue where the preview window would disappear prematurely during heavy LLM polishing.
- **Installation Issues**: Fixed a "poisoned" `requirements.txt` that contained absolute machine paths and incorrect encoding.

---

## [1.3.0] - 2026-05-06

### Added

#### LLM Text Polishing (`core/polish.py`)
- Automatically polish transcribed text using an LLM before injection
- Local Ollama integration (`llama3`, `mistral`, `gemma`, `phi3`, etc.)
- Third-party cloud integration stubs (`gemini`, `gpt-4o`, `claude-3.5-sonnet`)
- Configurable actions: "Fix Grammar & Spelling", "Make Professional", "Summarize", "Chat", "Custom Prompt"
- "Chat" action enables conversational mode where the LLM responds directly to your dictated prompt
- Settings → Polish tab: Full UI to enable/disable, test server connection, and dynamically fetch/refresh installed Ollama models

### Changed

#### UI Refinements
- Redesigned the floating mic icons to a modern, crisp aesthetic, removing harsh black borders and corners
- Upgraded the preview window microphone level meter from a 16-segment LED bar to a smooth live waveform visualizer

---

## [1.2.0] - 2026-05-03

### Added

#### Auto-update checker (`core/updater.py`)
- Silently checks GitHub Releases API at startup with a 15-second delay
- Throttled to once per 24 hours — uses `last_update_check` (ISO date) in config
- Three-button notification dialog: **Download** (opens browser), **Skip this version** (persists to config), **Remind me later** (dismiss)
- Skip preference stored in `skipped_update_version` config key — suppresses future alerts for that release
- Settings → Advanced → Updates: "Check for updates automatically" toggle and **Check now** button with inline result label
- `check_now()` method performs an immediate no-throttle check for the Settings button

#### Countdown ring on the floating mic button (`ui/floating_widget.py`)
- A sweep arc rendered inside the button tracks remaining recording time against `max_record_seconds`
- Sweeps clockwise from 12 o'clock; full arc = time remaining, empty arc = limit reached
- Color shifts automatically: green `#4CAF50` (>50% remaining) → amber `#FFC107` (20–50%) → red `#FF5252` (<20%)
- Dim background track always visible for clear ring framing
- Remaining seconds displayed as small text at the top of the button (suppressed on buttons < 48 px)
- Ring resets instantly when recording ends; updates every 50 ms (tied to the existing pulse animation loop — no extra thread)

#### Live microphone level meter in the preview overlay (`ui/preview_window.py`)
- 16-segment LED bar displayed in the preview overlay header, right of "● Listening…"
- Segments light up left-to-right proportionally to current mic amplitude
- Log-scale response (`log₁₀(1 + rms × 150)`) — quiet room noise shows at 2–3, normal speech at 8–11
- Color-coded: green (segs 0–9 — normal), amber (10–12 — moderate), red (13–15 — loud/clipping risk)
- All segments dim (`#333333`) when not recording; resets to zero the instant recording ends
- Draggable like the rest of the header bar
- RMS computed in the sounddevice audio callback, throttled to ≤60 ms intervals (~16 fps) to avoid flooding the UI event queue
- Thread-safe: callback marshalled onto the tkinter main thread via `root.after(0, ...)`

### Changed
- `audio/capture.py` — `AudioCapture` and `TimedCapture` accept `on_level: Callable[[float], None]` callback
- `utils/config.py` — two new fields: `last_update_check: str` and `skipped_update_version: str`
- `main.py` — `_apply_state()` calls `start_countdown` / `stop_countdown` on the floating widget; wires `on_level` lambda to preview

---

## [1.1.0] - 2026-04-15

### Added

#### Word corrections (`core/corrections.py`)
- Persistent find-and-replace rules applied after every transcription (after spoken-punctuation processing)
- Rules stored in `%APPDATA%\DictateAnywhere\corrections.json` — separate from main config
- `CorrectionsManager`: load, save, apply (case-insensitive whole-word matching)
- Settings → **Corrections tab**: add, edit, remove rules via an inline table UI

#### Transcription preview overlay (`ui/preview_window.py`)
- Frameless always-on-top dark floating bar (540 px wide) positioned at the bottom-centre of the primary screen
- Shows the last 3 dictated utterances (newest white, older grey)
- "● Listening…" indicator in the header while recording is active
- Draggable via the header bar; ✕ close button
- Auto-hides after a configurable delay (`preview_hide_after_ms`, default 8 s) — stays open while actively listening
- Never steals keyboard focus
- Toggle from tray icon → **Toggle Preview**
- Settings → **Preview tab** to enable/disable and adjust auto-hide delay

#### Session history window (`ui/history_window.py`)
- Searchable log of every utterance dictated in the current session
- Filter by keyword with the search box
- **Copy** selected entry to clipboard
- **Export** full history to a `.txt` file
- **Clear** the list
- Opened from tray icon → **Session History**
- History is in-memory; resets on restart

### Changed
- `main.py` — pipeline order in `_transcribe_and_inject`: `clean_whisper_artifacts` → `process_text` → `corrections.apply()` → inject → preview → history
- `utils/config.py` — new fields: `show_preview_window`, `preview_hide_after_ms`
- `ui/tray.py` — Session History and Toggle Preview added to context menu

---

## [1.0.0] - 2026-03-01

### Added
- Hybrid STT: faster-whisper (offline) + Azure Speech (cloud) with automatic fallback logic
- System tray icon with Start / Stop / Settings / Quit menu
- Draggable floating mic button (always-on-top, configurable opacity & size, pulsing ring while active)
- Global configurable hotkey (default `Ctrl+Alt+D`) — toggle and push-to-talk modes
- Text injection at cursor via Windows clipboard and SendInput API
- Voice Activity Detection (WebRTC VAD) — CPU active only while you speak
- Spoken punctuation: "period", "comma", "new line", "question mark", "exclamation mark", etc.
- Automatic sentence capitalisation
- Secure API key storage via Windows Credential Manager (DPAPI)
- Settings window: Engine, Audio, Hotkey, Floating Button, Azure Cloud, Advanced tabs
- Start with Windows option (HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run)
- PyInstaller build script for standalone `.exe` (no Python required on target machine)
- Full venv-based install scripts (`create_venv.bat`, `install.bat`, `run.bat`, `run_dev.bat`, `build.bat`, `test.bat`)
- MME host-API fallback for microphone capture (bypasses Realtek/Dolby WASAPI suppression on many laptops)
- GitHub Actions CI workflow (lint + test on push/PR)

---

[Unreleased]: https://github.com/RhythmicDias/DictateAnywhere/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/RhythmicDias/DictateAnywhere/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/RhythmicDias/DictateAnywhere/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/RhythmicDias/DictateAnywhere/releases/tag/v1.0.0
