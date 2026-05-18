# DictateAnywhere

**Hybrid voice dictation for Windows** — types anywhere your cursor is using offline faster-whisper and Azure/Sarvam cloud backends.

Powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (offline, CPU-efficient) with optional [Azure Speech](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) or [Sarvam AI](https://www.sarvam.ai/) cloud fallback for maximum accuracy and multi-language support.

---

## Features

| Feature | Details |
|---|---|
| **Hybrid STT** | Offline faster-whisper (CPU/GPU) + Azure Speech / Sarvam AI cloud fallback |
| **GPU Accelerated** | High-performance transcription via CUDA/cuBLAS for NVIDIA RTX GPUs |
| **Real-Time Previews** | Live text appears in the overlay as you speak (sub-second latency) |
| **Sarvam AI Support** | High-performance STT for Indian languages via WebSocket streaming |
| **LLM Text Polishing** | Integrated with local Ollama to automatically fix grammar, rewrite, or act as a conversational assistant |
| **Always available** | System tray icon — lives quietly in your taskbar |
| **Floating mic button** | Draggable, always-on-top toggle with modern, crisp icons for all states |
| **Countdown ring** | Sweep arc on the mic button shows remaining recording time (green → amber → red) |
| **Global hotkey** | Configurable (default `Ctrl+Alt+D`), toggle or push-to-talk |
| **Types anywhere** | Injects text at your cursor in any Windows app |
| **Transcription preview** | Floating dark overlay shows live tentative text and last 3 dictated lines |
| **Live level meter** | smooth live waveform visualizer in the preview overlay shows mic amplitude |
| **Spoken punctuation** | "period" → `.`  "comma" → `,`  "new line" → `↵`  etc. |
| **Auto-capitalisation** | Capitalises after sentence endings automatically |
| **Word corrections** | Persistent find-and-replace rules applied after every transcription |
| **Session history** | Searchable log of every dictated utterance — copy, export, or clear |
| **Auto-update checker** | Silently checks GitHub Releases at startup; notifies when a new version is available |
| **VAD filtering** | WebRTC Voice Activity Detection — CPU only active while you speak |
| **Secure key storage** | API keys stored in Windows Credential Manager (DPAPI) |
| **Model selector** | tiny / base / **small** (recommended) / medium / large |
| **Multi-language** | 20+ languages via Whisper; specialized Indian support via Sarvam |
| **Start with Windows** | Optional registry key entry |
| **Standalone .exe** | Build with PyInstaller — no Python install needed for end-users |

---

## Quick Start

### Requirements

- **Windows 10 / 11** (x64)
- **Python 3.11, 3.12, or 3.13** — [python.org/downloads](https://www.python.org/downloads/)
- A microphone

### Install

```bat
git clone https://github.com/RhythmicDias/DictateAnywhere.git
cd DictateAnywhere

scripts\create_venv.bat
scripts\install.bat
```

### Run

```bat
scripts\run.bat
```

DictateAnywhere starts silently and appears in the system tray (bottom-right of your taskbar).

---

## Usage

| Action | How |
|---|---|
| Start / stop dictation | Press `Ctrl+Alt+D` (configurable) |
| Start / stop dictation | Click the floating mic button |
| Start / stop dictation | Right-click tray icon → Start / Stop |
| Open settings | Right-click tray icon → Settings… |
| View session history | Right-click tray icon → Session History |
| Toggle preview overlay | Right-click tray icon → Toggle Preview |
| Move floating button | Click and drag it anywhere on screen |
| Quit | Right-click tray icon → Quit |

### Transcription preview overlay

While recording, a dark floating bar appears at the bottom of your screen showing:

- **● Listening…** status with a **smooth live waveform visualizer** to show your microphone activity
- The last three dictated lines (newest is white; older lines dim)

The overlay auto-hides a few seconds after dictation ends. You can drag it anywhere and close it with ✕. The hide delay is configurable in Settings → Advanced.

### Countdown ring on the floating button

When recording is active, a sweep arc appears inside the mic button tracking how much of the maximum recording time has been used:

| Ring colour | Meaning |
|---|---|
| Green | > 50% of time remaining |
| Amber | 20–50% of time remaining |
| Red | < 20% remaining — wrapping up soon |

A small seconds counter appears at the top of the button. The ring and counter disappear instantly when recording ends.

### Spoken punctuation commands

| Say | Gets typed |
|---|---|
| "period" / "full stop" | `.` |
| "comma" | `,` |
| "question mark" | `?` |
| "exclamation mark" | `!` |
| "new line" | line break |
| "new paragraph" | blank line |
| "semicolon" | `;` |
| "colon" | `:` |
| "open quote" / "close quote" | `"` |
| "dash" | `—` |
| "ellipsis" | `…` |
| "delete that" / "scratch that" | removes the spoken word |

### Word corrections

Open **Settings → Corrections** to define find-and-replace rules applied after every transcription.

| Column | Description |
|---|---|
| Find | The word or phrase Whisper tends to get wrong |
| Replace | What you actually want typed |

Rules are case-insensitive by default. They are stored in `%APPDATA%\DictateAnywhere\corrections.json` and apply on top of Whisper's output after spoken punctuation processing.

**Example rules:**

| Find | Replace |
|---|---|
| `colour` | `color` |
| `Starbucks` | `Starburst` |
| `gonna` | `going to` |

---

## Configuration

Open **Settings** from the tray icon menu. Changes take effect immediately.

### Engine tab
- **Engine mode** — `hybrid` (recommended), `local`, or `cloud`
- **Whisper model size** — `tiny` is the fastest; `small` is the best CPU/accuracy tradeoff
- **Compute type** — `int8` (efficient) or `float16` (fastest for GPU)
- **Local device** — `cuda` (recommended for NVIDIA) or `cpu`
- **Language** — BCP-47 code (`en`, `fr`, `de`, `auto`, …)

### Audio tab
- Choose microphone device
- VAD aggressiveness (0–3)
- Silence timeout before auto-stop
- Max recording length

### Hotkey tab
- Set any key combination (e.g. `ctrl+alt+d`, `f9`, `ctrl+shift+space`)
- Choose between **toggle** and **push-to-talk** modes

### Floating Button tab
- Show / hide the floating button
- Size and opacity
- Always-on-top toggle

### Preview tab
- Enable or disable the transcription preview overlay
- Configure the auto-hide delay (ms)
- **Opacity & Color** — customize the overlay's transparency and text color for better visibility

### Corrections tab
- Add, edit, and remove word correction rules
- Rules are applied after every transcription in the order listed

### Azure Cloud tab
- Azure Speech API key (stored securely in Windows Credential Manager)
- Azure region
- Test connection button

### Advanced tab
- Toggle spoken punctuation
- Toggle auto-capitalisation
- Text injection method (clipboard or SendInput)
- Start with Windows
- Log level
- **Updates section** — enable/disable automatic update checks; "Check now" button for an on-demand check

---

## AI Text Polishing (Ollama & Gemini)

Transform your speech in real-time using Large Language Models.

### Local via Ollama
1. Install [Ollama](https://ollama.com/)
2. Download a model (e.g., `ollama run llama3`)
3. In DictateAnywhere **Settings → Polish**, select `ollama` and pick your model.

### Cloud via Google Gemini
1. Get an API key from [Google AI Studio](https://aistudio.google.com/)
2. In DictateAnywhere **Settings → Cloud STT**, paste your Gemini API key.
3. In **Settings → Polish**, select `gemini` and choose a model (e.g., `gemini-flash-lite-latest`).

### Translation & Custom Prompts
Use the **Custom Prompt** action to turn DictateAnywhere into a real-time translator or specialized assistant.
- **Example Prompt:** "Translate the following text to Spanish and output ONLY the translation."
- **Example Prompt:** "Format the following text as a SQL query."

---

## Google Gemini (Cloud STT)

DictateAnywhere supports Google's Gemini models for highly accurate, multi-language cloud transcription.

1. Get a free-tier API key from [Google AI Studio](https://aistudio.google.com/).
2. Paste the key in the **Cloud STT** tab.
3. Switch your **Engine Mode** to `gemini` in the Engine tab.

---

## Azure Speech (optional cloud backend)

The free tier of Azure Speech gives you **5 hours of transcription per month at no cost**.

1. Create a free Azure account at [azure.microsoft.com/free](https://azure.microsoft.com/free/)
2. Create a **Speech** resource (Free tier F0)
3. Copy your **Key 1** and **Region**
4. In DictateAnywhere Settings → Azure Cloud tab, paste the key and set the region
5. The key is encrypted by Windows and never touches disk in plain text

---

## Sarvam AI (Indian Language specialized STT)

For the best experience with Hindi, Malayalam, Tamil, etc., DictateAnywhere integrates with [Sarvam AI](https://www.sarvam.ai/).

1. Get an API key from the [Sarvam AI Dashboard](https://www.sarvam.ai/).
2. In DictateAnywhere **Settings → Sarvam AI** tab:
   - Paste your **API Key** (stored securely in Windows Credential Manager).
   - Select your preferred model (e.g., `saaras:v3`).
   - Enable **WebSocket Streaming** for ultra-low latency real-time transcription.
3. Switch the **Engine Mode** to `sarvam` in the Engine tab.

---

## Auto-update checker

DictateAnywhere silently checks [GitHub Releases](https://github.com/RhythmicDias/DictateAnywhere/releases) at startup (after a 15-second delay) and shows a notification if a newer version is available.

- **At most once per day** — subsequent launches that day skip the check
- **Three choices when a new version is found:**
  - **Download** — opens your browser to the GitHub release page
  - **Skip this version** — suppresses notifications for that specific release (persisted to config)
  - **Remind me later** — dismisses; will show again on the next daily check
- **Manual check** — Settings → Advanced → Updates → **Check now**
- **Disable entirely** — uncheck "Check for updates automatically"

---

## Session history

Right-click the tray icon → **Session History** to open a log of every utterance dictated in the current run.

| Control | Action |
|---|---|
| Search box | Filter utterances by text |
| Copy | Copies selected entry to clipboard |
| Export | Saves full history as a `.txt` file |
| Clear | Wipes the history list |

History is in-memory only and resets on restart. Use Export to save anything you need to keep.

---

## Build a standalone .exe

No Python required on the target machine after building.

```bat
scripts\build.bat
```

Output: `dist\DictateAnywhere\DictateAnywhere.exe`

---

## Development

```bat
# Activate the venv
.venv\Scripts\activate

# Run tests
scripts\test.bat

# Run in dev mode (console visible)
scripts\run_dev.bat

# Lint
pip install ruff
ruff check src\
```

### Project layout

```
DictateAnywhere/
├── src/dictateanywhere/
│   ├── main.py                  ← entry point & orchestrator
│   ├── __init__.py              ← version string
│   ├── audio/
│   │   ├── capture.py           ← mic input, RMS level callback, TimedCapture
│   │   └── vad.py               ← WebRTC voice activity detection
│   ├── transcription/
│   │   ├── engine.py            ← abstract STT base class
│   │   ├── local_engine.py      ← faster-whisper (offline)
│   │   └── cloud_engine.py      ← Azure Speech SDK (cloud)
│   ├── core/
│   │   ├── hotkey_manager.py    ← global hotkey registration
│   │   ├── text_injector.py     ← types text at cursor (clipboard / SendInput)
│   │   ├── punctuation.py       ← spoken → symbol conversion
│   │   ├── corrections.py       ← word correction rules (corrections.json)
│   │   └── updater.py           ← GitHub Releases update checker
│   ├── ui/
│   │   ├── tray.py              ← system tray icon (pystray)
│   │   ├── floating_widget.py   ← draggable mic button + countdown ring
│   │   ├── preview_window.py    ← transcription overlay + level meter
│   │   ├── history_window.py    ← session history viewer
│   │   └── settings_window.py   ← tabbed settings dialog (tkinter)
│   └── utils/
│       ├── config.py            ← JSON config in %APPDATA%\DictateAnywhere\
│       └── secure_storage.py    ← API key → Windows Credential Manager
├── tests/                       ← pytest test suite
├── scripts/                     ← install, run, build, test .bat files
├── assets/icons/                ← .ico / .png for tray and .exe
├── .github/workflows/           ← CI + release workflow
├── requirements.txt
├── pyproject.toml
└── README.md
```

### Key data files (per-user, `%APPDATA%\DictateAnywhere\`)

| File | Contents |
|---|---|
| `config.json` | All settings (hotkey, engine, UI prefs, update state) |
| `corrections.json` | Word correction rules |
| `dictateanywhere.log` | Rolling application log |

---

## Roadmap

- [ ] Per-app language profiles (e.g. English for Word, French for LibreOffice)
- [ ] Multi-monitor floating widget awareness
- [ ] macOS / Linux support (pynput instead of pywin32)
- [x] Real-time streaming transcription (Local & Sarvam WebSocket)
- [x] GPU acceleration support (CUDA via CTranslate2)
- [ ] Noise floor auto-calibration
- [ ] Custom wake word to start recording hands-free

---

## Contributing

Pull requests are welcome! Please:

1. Fork the repo and create a feature branch
2. Run `scripts\test.bat` and make sure all tests pass
3. Follow the existing code style (type hints, docstrings, no `print()`, use the `logger`)
4. Open a pull request with a clear description

---

## License

MIT — see [LICENSE](LICENSE).

---

## Acknowledgements

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Optimised Whisper inference by SYSTRAN
- [OpenAI Whisper](https://github.com/openai/whisper) — The original speech recognition model
- [Azure Cognitive Services Speech](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text)
- [pystray](https://github.com/moses-palmer/pystray) — System tray icon library
- [webrtcvad](https://github.com/wiseman/py-webrtcvad) — WebRTC voice activity detection
- [sounddevice](https://python-sounddevice.readthedocs.io/) — PortAudio bindings for Python
