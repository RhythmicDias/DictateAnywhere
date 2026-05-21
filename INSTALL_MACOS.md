# DictateAnywhere — macOS Installation & Usage Guide

This guide provides instructions on how to install, configure, run, and uninstall **DictateAnywhere** on macOS (including M1/M2/M3 Apple Silicon and Intel Macs).

---

## 1. Prerequisites

Before running the installation scripts, ensure you have the following installed:

1. **Xcode Command Line Tools** (required to build Python dependencies):
   ```bash
   xcode-select --install
   ```
2. **Homebrew** (required to install `portaudio` for audio capture):
   If you don't have Homebrew, install it from [brew.sh](https://brew.sh), then run:
   ```bash
   brew install portaudio
   ```
3. **Python 3.11, 3.12, or 3.13**:
   You can install Python using Homebrew:
   ```bash
   brew install python
   ```

---

## 2. Installation

We provide two simple scripts to prepare your environment. Open your terminal, navigate to the project directory, and run:

1. **Create the Virtual Environment**:
   ```bash
   chmod +x scripts/*.sh
   ./scripts/create_venv.sh
   ```
   *This checks your Python version and creates a `.venv` directory.*

2. **Install Dependencies**:
   ```bash
   ./scripts/install.sh
   ```
   *This automatically installs `portaudio` via Homebrew if missing, upgrades pip, and installs the required packages (using platform-conditional markers so Windows-specific packages are skipped).*

---

## 3. Critical macOS Permissions

Because DictateAnywhere intercepts a global hotkey (default: `ctrl+alt+d`) and dynamically injects text by simulating keyboard input, **macOS requires you to grant Accessibility permissions**.

### How to Grant Permissions:
1. Open **System Settings** on your Mac.
2. Navigate to **Privacy & Security** > **Accessibility**.
3. Click the `+` button.
4. Add your **Terminal** app (e.g., Terminal, iTerm2, or VS Code, depending on where you run the script).
5. Ensure the toggle next to the app is turned **ON**.
6. *Note*: If you run the application in the background (`run.sh`), macOS might prompt you to allow `python3` or the terminal. Click **Open System Settings** and enable it.

---

## 4. Running DictateAnywhere

You can launch the app in two modes:

### Background Mode (Recommended)
To run the app silently in the background:
```bash
./scripts/run.sh
```
The application will start, and you will see the floating microphone widget.

### Development / Debug Mode
To run the app in the foreground and see live logs (useful for troubleshooting):
```bash
./scripts/run_dev.sh
```

---

## 5. UI & Controls on macOS

Because macOS prevents running both `pystray` (system tray) and `tkinter` (floating widget/settings windows) UI event loops on separate threads (which causes a main-thread deadlock/freeze), **the system tray icon is disabled on macOS**.

Instead, control the app directly using the **Floating Widget**:

* **Draggable Mic Button**: Drag the circular mic button anywhere on your screen. Its position is automatically saved.
* **Single Click**: Toggles dictation on/off.
* **Right-Click (Button-2 / Button-3)**: Opens the **Context Menu** with the following options:
  * **Start Dictation** / **Stop Dictation**
  * **Toggle Preview Overlay** (shows real-time transcription)
  * **Session History...** (view past transcriptions)
  * **Settings...** (configure API keys, local vs. cloud engines, hotkeys, etc.)
  * **Quit** (closes the application completely)

---

## 6. Running Tests

To verify that the application and its test suite work as expected:
```bash
./scripts/test.sh
```

---

## 7. Uninstallation

If you wish to remove DictateAnywhere and all its configurations, run:
```bash
./scripts/uninstall.sh
```
This script will:
1. Terminate any running DictateAnywhere processes.
2. Remove stored credentials (Azure, Sarvam, Gemini keys) from the macOS Keychain.
3. Remove the App Data folder (`~/Library/Application Support/DictateAnywhere`).
4. Delete the virtual environment (`.venv`).
5. Optionally delete the project source folder itself.
