# Changelog

All notable changes to DictateAnywhere are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Custom vocabulary / word corrections
- Per-app language profiles
- Dictation history panel
- Multi-monitor floating widget support

---

## [1.0.0] - 2025-01-01

### Added
- Hybrid STT: faster-whisper (offline) + Azure Speech (cloud) with fallback logic
- System tray icon with start / stop / settings / quit menu
- Draggable floating mic button (always-on-top, configurable opacity & size)
- Global configurable hotkey (default `Ctrl+Alt+D`) for push-to-talk toggle
- Text injection at cursor via Windows clipboard + SendInput API
- Voice Activity Detection (WebRTC VAD) — CPU active only while you speak
- Spoken punctuation: "period", "comma", "new line", "question mark", etc.
- Automatic sentence capitalisation
- Secure API key storage via Windows Credential Manager (DPAPI)
- Settings window: model size, microphone, language, hotkey, Azure region/key
- Start with Windows option (HKCU Run registry key)
- PyInstaller build script for standalone `.exe`
- Full venv-based install scripts for Windows

[Unreleased]: https://github.com/yourusername/DictateAnywhere/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/yourusername/DictateAnywhere/releases/tag/v1.0.0
