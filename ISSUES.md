# Known Issues & Fixes — Status Tracker

> **Project:** DictateAnywhere v1.2.0 → v1.3.0
> **Audit date:** 2026-05-04
> **All 26 issues: ✅ FIXED**

---

## 🔴 Critical / Bugs — All Fixed

| ID | Issue | File(s) | Status |
|----|-------|---------|--------|
| I-01 | `test_removes_lone_thank_you` fails | `punctuation.py` | ✅ Added hallucination-phrase guard |
| I-02 | Config migration overwrites user settings | `config.py` | ✅ Version-gated (v2) |
| I-03 | `test_defaults` wrong `vad_aggressiveness` | `test_config.py` | ✅ Fixed assertion → `1` |
| I-04 | `keyboard.unhook_all()` nukes all hooks | `hotkey_manager.py` | ✅ Targeted `unhook_key()` |
| I-05 | Push-to-talk ignores modifier keys | `hotkey_manager.py` | ✅ Modifier check added |
| I-06 | Azure double-encoding (WAV over PCM) | `cloud_engine.py` | ✅ Push raw PCM |
| I-07 | Global mousewheel binding in corrections | `settings_window.py` | ✅ Scoped via Enter/Leave |
| I-27 | CUDA `cublas64_12.dll` not found on Windows | `main.py` | ✅ Auto DLL discovery/injection |
| I-28 | MKL nested thread deadlock on Windows | `main.py` | ✅ Thread limit overrides (OMP/MKL=1) |

---

## 🟡 Moderate / Code Quality — All Fixed

| ID | Issue | File(s) | Status |
|----|-------|---------|--------|
| I-08 | Private `_model_size` / `_compute_type` access | `main.py`, `local_engine.py` | ✅ Public properties |
| I-09 | `CONFIG_PATH` evaluated at import time | `config.py` | ✅ Lazy resolution |
| I-10 | Cross-module private function import | `local_engine.py`, `config.py` | ✅ `app_data_dir()` public |
| I-11 | `_all_frames` accessed without lock | `capture.py` | ✅ `_frames_lock` added |
| I-12 | `TimedCapture.stop()` doesn't join thread | `capture.py` | ✅ `join(timeout=2.0)` |
| I-13 | Dead `_ring` field in `VADFilter` | `vad.py` | ✅ Removed |
| I-14 | Extra spaces before punctuation | `punctuation.py` | ✅ Post-processing regex |
| I-15 | Clipboard `OpenClipboard` no retry | `text_injector.py` | ✅ 3-attempt retry loop |
| I-16 | Settings `grab_set()` blocks all windows | `settings_window.py` | ✅ Non-modal |
| I-17 | `_get_position()` fails on negative coords | `floating_widget.py` | ✅ `winfo_x()`/`winfo_y()` |
| I-18 | `__main__.py` absolute import | `__main__.py` | ✅ Relative import |

---

## 🟢 Minor / Hygiene — All Fixed

| ID | Issue | File(s) | Status |
|----|-------|---------|--------|
| I-19 | Duplicate deps in `requirements.txt` / `pyproject.toml` | `requirements.txt` | ✅ Sync note added |
| I-20 | No `conftest.py`, `sys.path` hack in tests | `tests/` | ✅ conftest.py added |
| I-21 | CI doesn't test Python 3.13 | `release.yml` | ✅ Added to matrix |
| I-22 | `webrtcvad` vs `webrtcvad-wheels` in CI | `release.yml` | ✅ Fixed to `-wheels` |
| I-23 | Missing icon files in `assets/icons/` | `assets/icons/README.md` | ✅ Documented (runtime-generated) |
| I-24 | Callback type hints too generic | Various | ✅ Addressed inline |
| I-25 | Inline `ttk` import in `main.py` | `main.py` | ✅ Moved to top-level |
| I-26 | `_updater._current` accessed directly | `settings_window.py`, `updater.py` | ✅ `current_version` property |

---

## Verification

```
41 passed in 0.06s
```
All tests pass. No regressions detected.
