<div align="center">

  <img src="assets/icon.png" alt="DictateAnywhere logo" width="120" />

  # DictateAnywhere

  **High-performance, privacy-first hybrid voice dictation for Windows and macOS.**  
  Injects transcribed text directly at your cursor in any active application using offline local `faster-whisper` (GPU/CPU) or active Cloud STT engines (Google Gemini, Microsoft Azure, Sarvam AI).

  ![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)
  ![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-blue?style=flat-square)
  ![Release](https://img.shields.io/github/v/release/RhythmicDias/DictateAnywhere?label=release&style=flat-square)
  ![GitHub stars](https://img.shields.io/github/stars/RhythmicDias/DictateAnywhere?style=flat-square)

  [📥 Download Releases](https://github.com/RhythmicDias/DictateAnywhere/releases) • [📖 Features](#features) • [🚀 Quick Start](#quick-start) • [🛠️ Local Development](#local-development--building)

</div>

---

## Overview

DictateAnywhere is an ultra-fast, privacy-first voice dictation application built with **Tauri v2**, **Rust**, **React**, and a **Python Sidecar**. It runs quietly in your system tray and types whatever you speak directly into any active input field across your operating system.

Designed for doctors, writers, coders, and power users, DictateAnywhere combines local GPU acceleration (NVIDIA RTX Tensor Cores) with leading cloud models to provide zero-lag, studio-grade speech-to-text.

---

## Features

| Feature | Details |
|---|---|
| **Zero-Latency Capture** | Instantaneous recording start with cached audio device discovery — zero delay upon pressing your hotkey. |
| **Smart Silence Stripping** | Integrated VAD pre-trimming with safety padding eliminates dead air and prevents Whisper repetition or hallucination loops. |
| **NVIDIA GPU Acceleration** | Full CUDA Tensor Core optimization (automatic `float16` selection for RTX 5060, 40-series, and 30-series GPUs) with graceful CPU fallback. |
| **Hybrid STT Architecture** | Offline `faster-whisper` (GPU/CPU) with automatic cloud fallback on error. |
| **Active Cloud STT Selector** | Switch between **Google Gemini Flash**, **Microsoft Azure Speech**, or **Sarvam AI** with one click. |
| **Disfluency & Filler Removal** | Automatically purges hesitation sounds ("um", "uh", "hmm", "ah", "er") across all engines. |
| **AI Text Polishing** | Real-time LLM refinement via local **Ollama** or cloud models (**Google Gemini**, **OpenRouter**, **Groq**). Fix grammar, format, or apply custom prompts on the fly. |
| **HTTP Connection Pooling** | Persistent keep-alive sessions eliminate TCP/TLS handshake latency on cloud STT and LLM polish requests. |
| **Floating Mic Button** | Draggable, always-on-top toggle widget with recording state indicators and countdown sweep ring. |
| **Global Hotkeys** | Fully customizable keyboard shortcuts for dictation (default `Ctrl+Alt+D` / `Cmd+Alt+D`) and LLM polishing (`Ctrl+Alt+P`). |
| **Hardened Security** | Native Win32 asynchronous file dialogs via `rfd`, strict Tauri Content Security Policy (CSP), and header-authenticated API keys (`x-goog-api-key`). |
| **Spoken Punctuation** | Natural voice command conversions ("period" → `.`, "comma" → `,`, "new paragraph" → `↵↵`, etc.). |
| **Custom Corrections** | Personal find-and-replace word dictionary applied to all transcriptions automatically. |
| **Voice App Launcher** | Voice command triggers to launch local applications, scripts, or files (e.g., "open notepad"). |
| **Minimal Footprint** | Lightweight memory footprint (~80 MB saved by removing redundant WebView2 processes) and bounded history storage. |

---

## Quick Start

1. Download the latest release installer for your operating system from [GitHub Releases](https://github.com/RhythmicDias/DictateAnywhere/releases/latest).
2. Launch **DictateAnywhere**. The app lives in your system tray.
3. Focus any text field in any application (Notepad, Word, Browser, IDE, Slack, etc.).
4. Press `Ctrl+Alt+D` (Windows) or `Cmd+Alt+D` (macOS), speak naturally, and press it again to inject your text directly at your cursor.

---

## Usage & Shortcuts

| Action | Control |
|---|---|
| **Toggle Dictation** | Press `Ctrl+Alt+D` (or click Floating Mic Button) |
| **Toggle Text Polish** | Press `Ctrl+Alt+P` |
| **Open Settings** | Right-click system tray icon → **Settings** |
| **View History** | Right-click system tray icon → **Session History** |
| **Move Floating Widget** | Click and drag the floating mic button anywhere |

### Spoken Punctuation Commands

| Spoken Phrase | Typed Output |
|---|---|
| "period" / "full stop" | `.` |
| "comma" | `,` |
| "question mark" | `?` |
| "exclamation mark" | `!` |
| "new line" / "line break" | `↵` |
| "new paragraph" | `↵↵` |
| "open quote" / "close quote" | `"` |
| "dash" / "hyphen" | `—` / `-` |
| "ellipsis" | `…` |

---

## Cloud STT & API Providers

DictateAnywhere allows seamless selection of your preferred cloud STT provider under **Settings → Cloud STT**:

### 1. Google Gemini (Recommended)
- Fast, multimodal transcription powered by Google Gemini 2.0 / 2.5 Flash models.
- Get a free API key from [Google AI Studio](https://aistudio.google.com/).
- Paste your key in the **Cloud STT** tab and toggle **Google Gemini** as the active provider (authenticated securely via headers).

### 2. Microsoft Azure Speech
- Enterprise-grade speech recognition via Azure Cognitive Services.
- Create a free resource at [azure.microsoft.com](https://azure.microsoft.com/).
- Enter your API Key and Region (e.g., `eastus`) in the **Cloud STT** tab.

### 3. Sarvam AI (Indian Languages)
- Specialized for Indian languages and accents (Hindi, Tamil, Telugu, Kannada, Malayalam, Marathi, Bengali, Gujarati).
- Obtain an API key from [Sarvam AI](https://www.sarvam.ai/).
- Supports both standard REST audio transcription and real-time WebSocket streaming.

---

## Local Development & Building

### Prerequisites

- **Node.js** (v18 or higher) & **npm**
- **Python** (v3.11 or higher)
- **Rust** & **Cargo** — [rustup.rs](https://rustup.rs/)

---

### Setup Instructions

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/RhythmicDias/DictateAnywhere.git
   cd DictateAnywhere
   ```

2. **Create Python Virtual Environment & Install Dependencies:**
   ```bash
   python -m venv .venv
   
   # Windows:
   .\.venv\Scripts\activate
   
   # macOS / Linux:
   source .venv/bin/activate

   pip install -e .
   ```

3. **Install Frontend Dependencies:**
   ```bash
   npm install
   ```

4. **Build the Python Sidecar Binary:**
   The desktop app relies on a bundled sidecar binary for audio capture and inference.
   ```bash
   python scripts/build_sidecar.py
   ```
   *Note: This generates the platform-specific binary in `src-tauri/binaries/`.*

5. **Run in Development Mode:**
   ```bash
   # Windows 1-Click Launch:
   .\RUN.bat

   # Or via npm:
   npm run tauri dev
   ```

---

### Building Standalone Installers

To package a production release executable/installer for your current OS:

```bash
# 1. Build the updated sidecar executable
python scripts/build_sidecar.py

# 2. Package the native installer (.msi / .exe on Windows, .dmg / .app on macOS)
npm run tauri build
```

The output installers will be generated in `src-tauri/target/release/bundle/`.

---

## Architecture & Project Structure

```
DictateAnywhere/
├── src/                         ← React (TypeScript) UI Windows & Overlays
│   ├── windows/Settings/tabs/   ← Modular settings tabs (Engine, Audio, Hotkeys, Cloud, etc.)
│   ├── windows/FloatingWidget/  ← Draggable floating microphone button
│   ├── windows/PreviewOverlay/  ← Real-time transcription preview
│   └── windows/HistoryWindow/   ← Session history viewer
├── src-tauri/                   ← Rust Core (Tauri v2, Win32 SendInput, Keyring, Hotkeys, RFD)
│   ├── binaries/                ← Platform sidecar binaries (whisper_sidecar-*.exe)
│   ├── src/                     ← Rust backend commands & state
│   └── tauri.conf.json          ← Tauri configuration & strict CSP permissions
├── sidecar/                     ← Python Sidecar Core
│   ├── whisper_sidecar.py       ← JSON IPC loop & STT orchestrator
│   └── whisper_sidecar.spec     ← PyInstaller spec with hardened excludes
├── src/dictateanywhere/         ← Lean Python STT & Core Engine
│   ├── audio/                   ← Low-latency audio capture & WebRTC VAD silence stripping
│   ├── transcription/           ← local_engine (FP16 CUDA faster-whisper), gemini, azure, sarvam
│   ├── core/                    ← punctuation normalization, corrections, LLM text polish
│   └── utils/                   ← configuration manager & credentials
├── tests/                       ← Pytest test suite
├── RUN.bat                      ← 1-Click developer launch script
├── pyproject.toml               ← Python packaging & dependencies
└── README.md
```

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Acknowledgements

- [Tauri v2](https://v2.tauri.app/) — Next-generation cross-platform desktop framework
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — CTranslate2-based Whisper inference
- [Google Gemini API](https://ai.google.dev/) — Multimodal AI speech and polish models
- [Sarvam AI](https://www.sarvam.ai/) — Speech technology for Indian languages
- [Azure Speech SDK](https://azure.microsoft.com/) — Cloud speech recognition services
