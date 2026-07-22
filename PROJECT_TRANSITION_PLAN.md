# DictateAnywhere → Tauri v2 + React Conversion Plan

**Status:** ✅ All architectural decisions locked. Ready to execute.

---

## Decisions Locked

| Question | Decision |
|---|---|
| **Q1 — Local Whisper engine** | **Option A — Python Sidecar.** Bundle existing Python audio/transcription core as a PyInstaller `.exe`. Tauri (Rust) spawns it as a subprocess and communicates via stdin/stdout JSON lines. Reuses all current engine code. CUDA/RTX 5060 acceleration preserved. |
| **Q2 — Floating Widget** | **React/CSS circular button** in a Tauri transparent, decoration-free, always-on-top secondary window. |
| **Q3 — App Entry Point** | **System tray is the primary entry point.** App starts hidden (no main window). Tray icon → right-click menu is the main UI surface. |

---

## Architecture Overview

```
DictateAnywhere.exe  (Tauri v2 — Rust + WebView2)
│
├── Rust Core (src-tauri/)
│   ├── Config  ── reads/writes %APPDATA%\DictateAnywhere\config.json
│   ├── SecureStorage ── Windows DPAPI via tauri-plugin-stronghold
│   ├── Tray    ── tauri-plugin-tray  (primary entry point, always-on)
│   ├── Hotkey  ── tauri-plugin-global-shortcut (toggle + push-to-talk)
│   ├── Inject  ── enigo crate  (clipboard paste + SendInput char injection)
│   ├── Updater ── reqwest → GitHub Releases API
│   └── Bridge  ── spawns whisper_sidecar.exe, JSON IPC via stdin/stdout
│
├── whisper_sidecar.exe  (PyInstaller bundle — Python 3.11)
│   ├── audio/capture.py   (sounddevice MME/WASAPI)
│   ├── audio/vad.py       (webrtcvad)
│   ├── transcription/     (local faster-whisper, Azure, Gemini, Sarvam)
│   ├── core/punctuation.py
│   ├── core/corrections.py
│   └── core/polish.py
│
└── React Frontend (src/)
    ├── FloatingWidget window  (64×64, transparent, always-on-top, draggable)
    ├── Settings window        (9 tabs — replaces PySide6 subprocess dialog)
    ├── PreviewOverlay window  (transparent status pill)
    └── History window         (session transcription list)
```

**IPC flow:**
```
User presses hotkey
  → Rust (global-shortcut) fires
  → Rust writes {"cmd":"start"} to sidecar stdin
  → Sidecar captures audio + transcribes
  → Sidecar writes {"type":"result","text":"Hello"} to stdout
  → Rust receives → calls inject_text()
  → Rust emits Tauri event → React UI updates state
```

---

## Project Structure (Target)

```
DictateAnywhere/
├── src-tauri/
│   ├── src/
│   │   ├── main.rs
│   │   ├── lib.rs
│   │   ├── commands/
│   │   │   ├── config.rs        ← get_config / save_config
│   │   │   ├── hotkey.rs        ← register / unregister global shortcut
│   │   │   ├── injection.rs     ← inject_text (clipboard + sendinput)
│   │   │   ├── tray.rs          ← tray icon + menu
│   │   │   ├── sidecar.rs       ← spawn + IPC bridge for whisper_sidecar
│   │   │   ├── updater.rs       ← GitHub release check
│   │   │   └── storage.rs       ← secure API key get/set
│   │   └── models/
│   │       └── config.rs        ← Config struct mirroring Python dataclass
│   ├── icons/                   ← copied from assets/
│   ├── Cargo.toml
│   └── tauri.conf.json
├── src/                         ← React (TypeScript + Vite)
│   ├── main.tsx
│   ├── App.tsx                  ← routes to correct window by ?window= param
│   ├── windows/
│   │   ├── FloatingWidget/
│   │   │   ├── FloatingWidget.tsx
│   │   │   └── FloatingWidget.css
│   │   ├── Settings/
│   │   │   ├── SettingsWindow.tsx
│   │   │   └── tabs/
│   │   │       ├── TabEngine.tsx
│   │   │       ├── TabAudio.tsx
│   │   │       ├── TabHotkeys.tsx
│   │   │       ├── TabWidget.tsx
│   │   │       ├── TabCloudSTT.tsx
│   │   │       ├── TabAdvanced.tsx
│   │   │       ├── TabCorrections.tsx
│   │   │       ├── TabPolish.tsx
│   │   │       └── TabAppLauncher.tsx
│   │   ├── Preview/
│   │   │   └── PreviewOverlay.tsx
│   │   └── History/
│   │       └── HistoryWindow.tsx
│   ├── components/
│   │   ├── ToggleSwitch.tsx
│   │   ├── Card.tsx
│   │   ├── FieldLabel.tsx
│   │   └── index.ts
│   ├── store/
│   │   ├── dictationStore.ts    ← idle | active | loading | error | injecting
│   │   ├── configStore.ts
│   │   └── historyStore.ts
│   └── lib/
│       ├── commands.ts          ← typed invoke() wrappers
│       └── events.ts            ← Tauri event listeners
├── sidecar/
│   ├── whisper_sidecar.py       ← stripped Python core (audio+transcription only)
│   ├── requirements.txt
│   └── build.spec               ← PyInstaller spec → whisper_sidecar.exe
├── PROJECT_TRANSITION_PLAN.md   ← this file
├── package.json
└── pyproject.toml               ← kept for sidecar dependency metadata
```

---

## Proposed Changes (Component Detail)

---

### Phase 1 — Tauri Project Scaffold + Tray + Hotkey

#### [NEW] `src-tauri/tauri.conf.json`
- `identifier`: `com.rhythmicdias.dictateanywhere`
- `windows`: no default window on startup (`visible: false` for main)
- Secondary windows declared: `floating-widget`, `settings`, `preview`, `history`
- `bundle.targets`: `["msi", "nsis"]`
- `bundle.icon`: existing `assets/icon.ico` + `assets/icon.png`
- `bundle.externalBin`: `["sidecar/whisper_sidecar"]`

#### [NEW] `src-tauri/Cargo.toml` — crates
```toml
tauri = { version = "2", features = ["tray-icon", "image-ico", "image-png"] }
tauri-plugin-global-shortcut = "2"
tauri-plugin-stronghold = "2"
enigo = "0.2"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
tokio = { version = "1", features = ["full"] }
reqwest = { version = "0.12", features = ["json"] }
```

#### [NEW] `src-tauri/src/commands/tray.rs`
- Creates tray with `assets/icon.ico`
- Menu: Start Dictation, Stop Dictation, ─, Toggle Widget, Toggle Preview, History, Settings, ─, Quit
- App starts with tray only (main window hidden)

#### [NEW] `src-tauri/src/commands/hotkey.rs`
- `register_hotkey(hotkey: String, mode: String)` — wraps `tauri-plugin-global-shortcut`
- `unregister_hotkey(hotkey: String)`
- Toggle mode: single press → emits `dictation://toggle` event
- Push-to-talk: press/release → emits `dictation://start` / `dictation://stop`

#### [NEW] `src/windows/FloatingWidget/FloatingWidget.tsx`
- SVG circle button (64×64), states: idle (blue `#2D7DD2`) → active (red `#E63946`) → loading (amber `#F4A261`) → error (grey `#6C757D`)
- CSS `@keyframes pulse` ring animation for active state
- SVG `stroke-dashoffset` countdown arc
- Draggable: `appWindow.startDragging()` on `mousedown`
- Right-click context menu (React state-driven)
- Listens to Tauri events: `dictation://state-changed`

---

### Phase 2 — Python Sidecar Build

#### [NEW] `sidecar/whisper_sidecar.py`
Stripped-down IPC-based runner. Retains:
- `audio/capture.py` (full, unchanged)
- `audio/vad.py` (full, unchanged)
- `transcription/` all 5 engines (full, unchanged)
- `core/punctuation.py`, `core/corrections.py`, `core/polish.py`
- `utils/config.py`, `utils/secure_storage.py`

**Removes:** all UI (tkinter, pystray, floating widget, settings window)

Protocol (newline-delimited JSON):
```
stdin  → {"cmd": "start", "device_index": -1, "engine": "hybrid", "language": "en", ...}
stdin  → {"cmd": "stop"}
stdin  → {"cmd": "ping"}
stdout ← {"type": "audio_level", "rms": 0.012}
stdout ← {"type": "state", "state": "active"}
stdout ← {"type": "result", "text": "Hello world", "engine": "local"}
stdout ← {"type": "error", "message": "..."}
stdout ← {"type": "pong"}
```

#### [NEW] `sidecar/build.spec`
PyInstaller one-file spec. Bundles:
- faster-whisper + NVIDIA CUDA DLLs
- sounddevice / PortAudio
- webrtcvad
- requests / azure-cognitiveservices-speech
- All `src/dictateanywhere/` modules except `ui/`

Output: `sidecar/whisper_sidecar.exe` → copied to `src-tauri/binaries/`

#### [NEW] `src-tauri/src/commands/sidecar.rs`
- `start_sidecar()` — spawns `whisper_sidecar.exe` via `tauri::process::Command::new_sidecar`
- Async reader thread: parses stdout JSON lines → emits Tauri events to frontend
- `send_command(cmd: Value)` — writes JSON line to sidecar stdin
- `stop_sidecar()` — sends `{"cmd":"stop"}` + kills process

---

### Phase 3 — Text Injection + Secure Storage

#### [NEW] `src-tauri/src/commands/injection.rs`
- `inject_text(text: String, method: String)` Tauri command
- `method = "clipboard"`: uses `enigo` → set clipboard → Ctrl+V with 50 ms delay; restores clipboard after 1 s
- `method = "sendinput"`: uses `enigo` key_sequence for char-by-char injection
- Windows-only: release modifier keys before injecting (same logic as Python `_release_modifiers`)

#### [NEW] `src-tauri/src/commands/storage.rs`
- `get_api_key(service: String) → Option<String>`
- `set_api_key(service: String, key: String)`
- Services: `azure`, `gemini`, `sarvam`
- Backend: `tauri-plugin-stronghold` (encrypts to `%APPDATA%\DictateAnywhere\stronghold.hold`)

#### [MODIFY] `sidecar/whisper_sidecar.py`
- Remove `SecureStorage` / `keyring` dependency from sidecar
- Accept API keys via the IPC `start` command payload instead:
  `{"cmd": "start", ..., "api_keys": {"azure": "...", "gemini": "..."}}`

---

### Phase 4 — Settings Window (React)

#### [NEW] `src/windows/Settings/SettingsWindow.tsx`
Direct port of `settings_window.py` (1586 lines → clean React). Same 9 tabs:

| Tab | Key widgets |
|---|---|
| Engine | Mode combo, model size, compute type, device, language, fallback toggles |
| Audio | Mic device dropdown (populated via `list_audio_devices` command), VAD slider, silence timeout spin, max record |
| Hotkeys | Hotkey text input + validate button, mode combo, preview overlay toggles |
| Floating Button | Show toggle, always-on-top, size spin, opacity slider |
| Cloud STT | Azure key (masked) + region + test btn; Sarvam key + model + language + WS toggle + test btn; Gemini key + model + test btn |
| Advanced | Punctuation toggle, auto-capitalise, injection method, delay, start-with-Windows, log level |
| Corrections | Editable list of word → replacement pairs |
| Polish | Enable toggle, provider combo (Ollama/Gemini), action combo, custom prompt textarea, Ollama URL + model |
| App Launcher | Voice command → file path pairs + Browse button |

**Footer:** Import / Export / Reset Defaults / Close / **Save Changes**

Save flow: React → `invoke('save_config', config)` → Rust writes JSON → emits `config://changed` → Rust re-registers hotkey / notifies sidecar.

---

### Phase 5 — Preview Overlay + History Window

#### [NEW] `src/windows/Preview/PreviewOverlay.tsx`
- Replaces `preview_window.py`
- Always-on-top, transparent background, no decorations
- Shows: current state pill (🎙 Listening… / ✓ text / ⚠ Error)
- Audio level bar (driven by `audio_level` Tauri events)
- Auto-hides after `preview_hide_after_ms` ms

#### [NEW] `src/windows/History/HistoryWindow.tsx`
- Replaces `history_window.py`
- Scrollable list of timestamped transcription entries
- Copy-to-clipboard button per entry
- Clear all button
- History persisted in Zustand + localStorage

---

### Phase 6 — Updater + Installer

#### [NEW] `src-tauri/src/commands/updater.rs`
- `check_for_updates() → UpdateInfo`
- Queries `https://api.github.com/repos/RhythmicDias/DictateAnywhere/releases/latest`
- Returns `{ latest: "v1.8.0", url: "...", is_newer: true }`
- Respects `skipped_update_version` from config (same logic as `updater.py`)

#### [MODIFY] `src-tauri/tauri.conf.json` — Installer config
```json
"bundle": {
  "targets": ["msi", "nsis"],
  "windows": {
    "wix": {
      "language": "en-US",
      "upgradeCode": "<fixed-guid>"
    },
    "nsis": { "installMode": "currentUser" }
  },
  "externalBin": ["binaries/whisper_sidecar"]
}
```

---

## Verification Plan

### Automated Tests
- `cargo test` — Rust unit tests (config serialization, injection helpers, hotkey parsing)
- `npm run test` (Vitest) — Zustand store + React component snapshots

### Manual Verification Checklist
1. ✅ Fresh `.msi` install on clean Windows 11 VM — tray icon appears on startup, no visible window
2. ✅ `Ctrl+Alt+D` → widget pulses red → speak → text appears at cursor (clipboard mode)
3. ✅ `Ctrl+Alt+D` again → recording stops → idle blue
4. ✅ Push-to-talk mode: hold hotkey → release → text injected
5. ✅ Settings → Engine → switch to Azure → Save → dictation uses Azure
6. ✅ API keys saved/retrieved via secure storage (not in config.json)
7. ✅ Existing `%APPDATA%\DictateAnywhere\config.json` from old Python version loads correctly
8. ✅ RTX 5060 CUDA inference: local Whisper model loads on GPU, `device=cuda` in settings
9. ✅ Text injection: both clipboard and sendinput methods in Notepad, VS Code, Word
10. ✅ Update dialog appears for a mock newer version
11. ✅ Uninstall via Settings → Apps removes app but leaves user config (standard WiX behavior)

---

## Phased Delivery — Execution Plan

### Phase 1 — Tauri Scaffold + Tray + Floating Widget
**Goal:** App boots, shows tray icon, floating widget opens/closes from tray.

- [ ] `npm create tauri-app@latest` in project root (React + TypeScript + Vite)
- [ ] Configure `tauri.conf.json`: no main window, tray-only startup, 4 window declarations
- [ ] Add crates: `tauri-plugin-global-shortcut`, `tauri-plugin-tray`, `enigo`, `serde_json`
- [ ] `tray.rs`: create icon + context menu (hardcoded actions for now)
- [ ] `hotkey.rs`: register `Ctrl+Alt+D` toggle, emit events to frontend
- [ ] FloatingWidget React window: SVG button, 5 states, pulse animation, drag
- [ ] Wire tray "Toggle Widget" to show/hide floating window
- [ ] Wire hotkey event → widget state update
- **Deliverable:** `.exe` that shows tray, toggles widget, widget changes colour on hotkey

---

### Phase 2 — Python Sidecar: Audio + Transcription IPC
**Goal:** Press hotkey → real speech captured → transcribed text returned to Rust.

- [ ] Create `sidecar/whisper_sidecar.py` (strip all UI, add JSON IPC loop)
- [ ] Implement IPC protocol (start/stop/ping commands, result/level/state/error responses)
- [ ] Test sidecar standalone: `echo '{"cmd":"start",...}' | python whisper_sidecar.py`
- [ ] `sidecar.rs`: spawn sidecar, async stdout reader, stdin writer
- [ ] Rust: on hotkey start → send `start` to sidecar; on result → log text
- [ ] Build `whisper_sidecar.exe` with PyInstaller (test CUDA loads correctly)
- [ ] Add `externalBin` to tauri.conf, test sidecar spawns from Tauri app
- **Deliverable:** Hotkey → speech captured → transcription result logged in Rust console

---

### Phase 3 — Text Injection + Secure Storage
**Goal:** Transcribed text appears at the cursor in any app.

- [ ] `injection.rs`: clipboard method (set + Ctrl+V + restore)
- [ ] `injection.rs`: sendinput method (enigo key sequence)
- [ ] `injection.rs`: modifier release before inject (port `_release_modifiers` logic)
- [ ] `storage.rs`: `tauri-plugin-stronghold` get/set API keys
- [ ] Sidecar: accept `api_keys` in start command instead of reading keyring
- [ ] Migrate existing keyring secrets → stronghold on first run
- [ ] End-to-end test: hotkey → dictate → text at cursor in Notepad
- **Deliverable:** Full dictation loop works end-to-end

---

### Phase 4 — Settings Window (9 tabs)
**Goal:** All settings configurable and persisted via the React settings window.

- [ ] `config.rs`: `get_config()` and `save_config(config)` Tauri commands
- [ ] `configStore.ts`: Zustand store mirroring `Config` dataclass
- [ ] `SettingsWindow.tsx` scaffold: tab layout, footer (Import/Export/Reset/Save)
- [ ] `TabEngine.tsx`: mode, model size, compute type, device, language, fallbacks
- [ ] `TabAudio.tsx`: mic list (via `list_audio_devices` command), VAD, silence, max record
- [ ] `TabHotkeys.tsx`: hotkey input + live validation, mode, preview settings
- [ ] `TabWidget.tsx`: show/hide toggle, size, opacity, always-on-top
- [ ] `TabCloudSTT.tsx`: Azure, Sarvam, Gemini — keys (masked), test buttons, region/model/language
- [ ] `TabAdvanced.tsx`: punctuation, capitalise, injection method, delay, startup, log level
- [ ] `TabCorrections.tsx`: add/remove/edit correction pairs
- [ ] `TabPolish.tsx`: enable, provider, action, custom prompt, Ollama URL/model
- [ ] `TabAppLauncher.tsx`: voice command → path pairs + file browser
- [ ] Wire Save → `invoke('save_config')` → re-apply hotkey + notify sidecar
- **Deliverable:** Full settings window functional; settings persist across restarts

---

### Phase 5 — Preview Overlay + History Window
**Goal:** Visual feedback during dictation; session history accessible.

- [ ] `PreviewOverlay.tsx`: transparent pill, state colours, audio level bar, auto-hide timer
- [ ] Wire `audio_level` events from sidecar → level bar in preview
- [ ] `HistoryWindow.tsx`: timestamped list, copy button, clear all
- [ ] `historyStore.ts`: in-memory + localStorage persistence
- [ ] Wire transcription results → history store
- [ ] Tray menu "History" → open/focus history window
- **Deliverable:** Preview overlay shows during dictation; history window shows past transcriptions

---

### Phase 6 — Updater + Windows Installer
**Goal:** Distributable `.msi` and `.exe` installer; update notifications.

- [ ] `updater.rs`: GitHub Releases API check, skip-version logic
- [ ] Update dialog in React (replaces `_show_update_dialog` Tkinter code)
- [ ] Build PyInstaller sidecar with full CUDA deps → `binaries/whisper_sidecar.exe`
- [ ] Configure WiX (`.msi`) with fixed `upgradeCode` GUID
- [ ] Configure NSIS (`.exe`) with `currentUser` install mode
- [ ] Add Start-with-Windows registry key write/remove (via Rust, `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`)
- [ ] Run `cargo tauri build` → verify `.msi` installs, runs, uninstalls cleanly
- [ ] Test upgrade path: install old `.msi`, install new `.msi`, config preserved
- **Deliverable:** Signed/unsigned `.msi` and `.exe` distributable

---

### Phase 7 — Polish, GPU Validation & Final QA
**Goal:** Production-ready release.

- [ ] RTX 5060 CUDA validation: `device=cuda`, `compute_type=float16` in sidecar
- [ ] All 4 engine modes tested end-to-end (local, azure, gemini, sarvam)
- [ ] Push-to-talk tested vs toggle mode
- [ ] Both injection methods (clipboard, sendinput) tested in: Notepad, VS Code, Word, Chrome
- [ ] Config migration: load existing Python `config.json` → all settings apply
- [ ] API key migration: `keyring` → `stronghold` on first Tauri run
- [ ] Spoken punctuation + auto-capitalise verified
- [ ] App launcher voice command tested
- [ ] Text polish (Ollama + Gemini) tested
- [ ] Accessibility: tray keyboard navigation
- [ ] Finalise `CHANGELOG.md` entry for Tauri release
- **Deliverable:** v2.0.0 release candidate

---

## Pre-Requisites (Before Phase 1)

Verify the following are installed on your dev machine:

```powershell
# Rust toolchain
rustup --version        # needs 1.77+
cargo --version

# Node / npm
node --version          # needs 18+
npm --version

# Tauri CLI
cargo install tauri-cli --version "^2"

# WebView2 (already present on Windows 11)
# Visual Studio C++ Build Tools (for Rust)

# PyInstaller (for sidecar build)
pip install pyinstaller
```
