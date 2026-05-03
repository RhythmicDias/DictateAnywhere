"""
Settings window — full configuration UI built with Tkinter.

All settings are read from ConfigManager and written back on Save.
The Azure API key is routed through SecureStorage (Windows Credential Manager).
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_PAD = 8
_LABEL_W = 26

# faster-whisper stores models here by default
_WHISPER_MODEL_PREFIX = "models--Systran--faster-whisper-"


def _get_whisper_cache_dir() -> Path:
    """
    Return the directory where this app's faster-whisper models are stored.
    Mirrors the MODELS_DIR logic in local_engine.py:
      %APPDATA%\\DictateAnywhere\\models  (Windows)
      ~/Library/Application Support/DictateAnywhere/models  (macOS fallback)
    """
    base = os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming"
    return Path(base) / "DictateAnywhere" / "models"


def _find_whisper_models() -> list[dict]:
    """
    Return a list of dicts:
      { name, path, size_mb }
    for each faster-whisper model found in the app's own models folder.
    """
    cache_dir = _get_whisper_cache_dir()
    results = []
    if not cache_dir.exists():
        return results
    for folder in sorted(cache_dir.iterdir()):
        if folder.is_dir() and folder.name.startswith(_WHISPER_MODEL_PREFIX):
            model_name = folder.name[len(_WHISPER_MODEL_PREFIX):]
            size_bytes  = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
            size_mb     = size_bytes / (1024 * 1024)
            results.append({"name": model_name, "path": folder, "size_mb": size_mb})
    return results


class SettingsWindow:
    """
    Modal settings dialog.

    Instantiate once; call open() to show it, close() to hide.
    The window is destroyed and recreated on each open() call to
    ensure it always reflects the latest config values.
    """

    def __init__(
        self,
        root: tk.Tk,
        config_manager,
        secure_storage,
        on_save: Optional[Callable] = None,
        hotkey_validator: Optional[Callable[[str], bool]] = None,
        corrections_manager=None,
    ) -> None:
        self._root = root
        self._cfg = config_manager
        self._sec = secure_storage
        self._on_save = on_save
        self._validate_hotkey = hotkey_validator
        self._corrections = corrections_manager   # CorrectionsManager | None
        self._win: Optional[tk.Toplevel] = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def open(self) -> None:
        if self._win and self._win.winfo_exists():
            self._win.lift()
            self._win.focus_force()
            return
        self._build()

    def close(self) -> None:
        if self._win and self._win.winfo_exists():
            self._win.destroy()
        self._win = None

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        self._win = tk.Toplevel(self._root)
        self._win.title("DictateAnywhere — Settings")
        self._win.resizable(False, False)
        self._win.grab_set()
        self._win.protocol("WM_DELETE_WINDOW", self.close)

        nb = ttk.Notebook(self._win)
        nb.pack(fill=tk.BOTH, expand=True, padx=_PAD, pady=_PAD)

        self._vars: dict[str, tk.Variable] = {}
        self._azure_key_var = tk.StringVar()
        self._status_var = tk.StringVar(value="")

        self._build_tab_engine(nb)
        self._build_tab_audio(nb)
        self._build_tab_hotkey(nb)
        self._build_tab_widget(nb)
        self._build_tab_cloud(nb)
        self._build_tab_advanced(nb)
        self._build_tab_corrections(nb)

        bar = ttk.Frame(self._win)
        bar.pack(fill=tk.X, padx=_PAD, pady=(0, _PAD))
        ttk.Label(bar, textvariable=self._status_var, foreground="gray").pack(side=tk.LEFT)
        ttk.Button(bar, text="Cancel", command=self.close).pack(side=tk.RIGHT, padx=4)
        ttk.Button(bar, text="Save", command=self._save,
                   style="Accent.TButton").pack(side=tk.RIGHT)
        ttk.Button(bar, text="Reset Defaults", command=self._reset).pack(side=tk.RIGHT, padx=4)

        self._win.update_idletasks()
        self._centre_window()

    # ── Tabs ──────────────────────────────────────────────────────────────────

    def _build_tab_engine(self, nb: ttk.Notebook) -> None:
        f = self._tab(nb, "Engine")
        self._combo(f, "Engine mode", "engine_mode",
                    ["hybrid", "local", "cloud"],
                    "Hybrid uses local Whisper first; falls back to Azure if it fails.")
        self._combo(f, "Whisper model size", "model_size",
                    ["tiny", "base", "small", "medium", "large-v2", "large-v3"],
                    "small = best CPU/quality balance. medium for maximum accuracy.")
        self._combo(f, "Compute type", "compute_type",
                    ["int8", "float16", "float32"],
                    "int8 = fastest on CPU. float16 requires a compatible GPU.")
        self._combo(f, "Language", "language",
                    ["en", "es", "fr", "de", "it", "pt", "nl", "pl",
                     "ru", "zh", "ja", "ko", "ar", "hi", "auto"],
                    "auto = Whisper detects language automatically.")
        self._check(f, "Fall back to cloud on local error", "cloud_fallback_on_error")
        self._check(f, "Fall back to local on cloud error", "local_fallback_on_cloud_error")

    def _build_tab_audio(self, nb: ttk.Notebook) -> None:
        f = self._tab(nb, "Audio")

        from ..audio.capture import list_input_devices
        try:
            devices = list_input_devices()
            device_labels = ["Default"] + [f"[{d['index']}] {d['name']}" for d in devices]
            device_values = [-1] + [d["index"] for d in devices]
        except Exception:
            device_labels = ["Default"]
            device_values = [-1]

        current_idx = self._cfg.get("mic_device_index", -1)
        current_label = "Default"
        for lbl, val in zip(device_labels, device_values):
            if val == current_idx:
                current_label = lbl
                break

        self._vars["mic_device_index_label"] = tk.StringVar(value=current_label)
        self._vars["mic_device_index_values"] = device_values  # type: ignore[assignment]

        _row(f, "Microphone").pack(fill=tk.X)
        self._mic_combo = ttk.Combobox(
            f,
            textvariable=self._vars["mic_device_index_label"],
            values=device_labels,
            state="readonly",
            width=50,
        )
        self._mic_combo.pack(fill=tk.X, padx=_PAD, pady=2)
        self._mic_device_labels = device_labels
        self._mic_device_values = device_values

        ttk.Button(f, text="Test Mic", command=self._test_mic).pack(
            anchor=tk.W, padx=_PAD, pady=(0, 4))
        _hint(f, "Restart DictateAnywhere after changing the microphone.")

        self._scale(f, "VAD aggressiveness", "vad_aggressiveness", 0, 3, 1,
                    "0 = capture everything; 3 = filter aggressively (best for noisy rooms).")
        self._spin(f, "Silence timeout (ms)", "silence_timeout_ms", 300, 5000, 100,
                   "Dictation stops after this many ms of silence. 1500 ms recommended.")
        self._spin(f, "Max recording length (s)", "max_record_seconds", 5, 120, 5,
                   "Hard cap to prevent runaway recordings.")

    def _build_tab_hotkey(self, nb: ttk.Notebook) -> None:
        f = self._tab(nb, "Hotkey")
        ttk.Label(f, text="Global hotkey", font=("", 9, "bold")).pack(
            anchor=tk.W, padx=_PAD, pady=(_PAD, 2))
        _hint(f, "Works even when DictateAnywhere is in the background.\n"
              "Examples: ctrl+alt+d   ctrl+shift+space   f9")
        self._vars["hotkey"] = tk.StringVar(value=self._cfg.get("hotkey", "ctrl+alt+d"))
        ttk.Entry(f, textvariable=self._vars["hotkey"], width=30).pack(
            anchor=tk.W, padx=_PAD, pady=4)
        ttk.Button(f, text="Test hotkey", command=self._test_hotkey).pack(
            anchor=tk.W, padx=_PAD)
        self._combo(f, "Hotkey mode", "hotkey_mode",
                    ["toggle", "push_to_talk"],
                    "Toggle: press once to start, again to stop.\n"
                    "Push-to-talk: hold key to record, release to transcribe.")

    def _build_tab_widget(self, nb: ttk.Notebook) -> None:
        f = self._tab(nb, "Floating Button")
        self._check(f, "Show floating mic button", "show_floating_widget")
        self._check(f, "Always on top", "widget_always_on_top")
        self._spin(f, "Button size (px)", "widget_size", 32, 128, 8,
                   "Width and height of the floating button in pixels.")
        self._scale(f, "Opacity", "widget_opacity", 0.1, 1.0, 0.05,
                    "1.0 = fully opaque; 0.1 = nearly transparent.")
        ttk.Separator(f).pack(fill=tk.X, padx=_PAD, pady=_PAD)
        ttk.Label(f, text="Button position will be saved automatically as you drag it.",
                  foreground="gray").pack(anchor=tk.W, padx=_PAD)

        # ── Transcription preview overlay ──────────────────────────────────
        ttk.Separator(f).pack(fill=tk.X, padx=_PAD, pady=_PAD)
        ttk.Label(f, text="Transcription Preview Overlay",
                  font=("", 9, "bold")).pack(anchor=tk.W, padx=_PAD)
        _hint(f, "A floating dark bar that shows each dictated sentence.\n"
              "Appears at the bottom of the screen and fades away automatically.\n"
              "Drag it by its header to reposition. Toggle anytime from the tray icon.")
        self._check(f, "Show preview overlay after dictation", "show_preview_window")
        self._spin(f, "Auto-hide after (ms)", "preview_hide_after_ms", 0, 30000, 1000,
                   "How long (milliseconds) the overlay stays visible after the last\n"
                   "utterance. Set to 0 to keep it open until manually closed.")

    def _build_tab_cloud(self, nb: ttk.Notebook) -> None:
        f = self._tab(nb, "Azure Cloud")
        ttk.Label(f, text="Azure Speech API Key", font=("", 9, "bold")).pack(
            anchor=tk.W, padx=_PAD, pady=(_PAD, 2))
        _hint(f, "Stored securely in Windows Credential Manager (DPAPI encrypted).\n"
              "Never written to disk in plain text.\n"
              "Free tier: 5 hours/month — https://azure.microsoft.com/free/")

        existing_key = self._sec.get_azure_key() or ""
        display = ("•" * 12 + existing_key[-4:]) if len(existing_key) > 4 else existing_key
        self._azure_key_var.set(display)

        key_frame = ttk.Frame(f)
        key_frame.pack(fill=tk.X, padx=_PAD, pady=4)
        self._key_entry = ttk.Entry(key_frame, textvariable=self._azure_key_var,
                                    width=48, show="•")
        self._key_entry.pack(side=tk.LEFT)
        ttk.Button(key_frame, text="Show",
                   command=self._toggle_key_visibility).pack(side=tk.LEFT, padx=4)
        ttk.Button(key_frame, text="Clear",
                   command=self._clear_azure_key).pack(side=tk.LEFT)

        self._combo(f, "Azure region", "cloud_region",
                    ["eastus", "westus", "westus2", "westeurope", "northeurope",
                     "southeastasia", "australiaeast", "canadacentral",
                     "uksouth", "japaneast", "centralindia", "brazilsouth"],
                    "Must match the region of your Azure Speech resource.")
        ttk.Button(f, text="Test Azure Connection",
                   command=self._test_azure).pack(anchor=tk.W, padx=_PAD, pady=_PAD)
        self._azure_test_label = ttk.Label(f, text="", foreground="gray")
        self._azure_test_label.pack(anchor=tk.W, padx=_PAD)

    def _build_tab_advanced(self, nb: ttk.Notebook) -> None:
        f = self._tab(nb, "Advanced")

        self._check(f, "Spoken punctuation (\"period\" → \".\")", "spoken_punctuation")
        self._check(f, "Auto-capitalise after sentence ends", "auto_capitalise")
        self._combo(f, "Text injection method", "inject_method",
                    ["clipboard", "sendinput"],
                    "clipboard = fastest and most compatible.\n"
                    "sendinput = character-by-character (use if clipboard paste fails).")
        self._spin(f, "Injection delay (ms)", "inject_delay_ms", 0, 500, 10,
                   "Small delay between clipboard copy and Ctrl+V. Increase if text appears late.")
        self._check(f, "Start DictateAnywhere with Windows", "start_with_windows")
        self._combo(f, "Log level", "log_level",
                    ["DEBUG", "INFO", "WARNING", "ERROR"],
                    "Set to DEBUG to capture verbose logs for troubleshooting.")

        ttk.Separator(f).pack(fill=tk.X, padx=_PAD, pady=_PAD)
        ttk.Label(f, text=f"Config folder:  {self._cfg.config_dir()}",
                  foreground="gray").pack(anchor=tk.W, padx=_PAD)
        ttk.Button(f, text="Open config folder",
                   command=self._open_config_dir).pack(anchor=tk.W, padx=_PAD, pady=4)

        # ── Whisper model manager ────────────────────────────────────────────
        ttk.Separator(f).pack(fill=tk.X, padx=_PAD, pady=_PAD)
        ttk.Label(f, text="Whisper model cache", font=("", 9, "bold")).pack(
            anchor=tk.W, padx=_PAD)
        _hint(f, f"Models are stored in:\n{_get_whisper_cache_dir()}\n"
              "Deleting a model forces a fresh download on next use.")

        # Scrollable frame for model rows
        self._model_frame = ttk.Frame(f)
        self._model_frame.pack(fill=tk.X, padx=_PAD, pady=4)
        self._refresh_model_list()

        ttk.Button(f, text="↺  Refresh model list",
                   command=self._refresh_model_list).pack(anchor=tk.W, padx=_PAD, pady=(0, 4))

    def _build_tab_corrections(self, nb: ttk.Notebook) -> None:
        f = self._tab(nb, "Corrections")

        ttk.Label(f, text="Word Corrections", font=("", 10, "bold")).pack(
            anchor=tk.W, padx=_PAD, pady=(_PAD, 2))
        _hint(f,
              "Define replacements applied after every transcription.\n"
              "Use these to fix Whisper mishearings or expand abbreviations.\n"
              "Examples:  gonna → going to     acme → Acme Corp     thier → their\n"
              "Matching is case-insensitive and whole-word.")

        if self._corrections is None:
            ttk.Label(f, text="Corrections manager not available.",
                      foreground="gray").pack(anchor=tk.W, padx=_PAD)
            return

        # ── Scrollable corrections list ────────────────────────────────────
        list_outer = ttk.Frame(f, relief="sunken", borderwidth=1)
        list_outer.pack(fill=tk.BOTH, expand=True, padx=_PAD, pady=(4, 0))

        canvas = tk.Canvas(list_outer, height=200, borderwidth=0,
                           highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_outer, orient="vertical",
                                  command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._corr_inner = ttk.Frame(canvas)
        self._corr_canvas_win = canvas.create_window(
            (0, 0), window=self._corr_inner, anchor="nw")

        def _on_resize(event):
            canvas.itemconfig(self._corr_canvas_win, width=event.width)
        canvas.bind("<Configure>", _on_resize)

        def _update_scroll(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
        self._corr_inner.bind("<Configure>", _update_scroll)

        # Mouse-wheel scrolling
        def _on_wheel(event):
            canvas.yview_scroll(-1 * (event.delta // 120), "units")
        canvas.bind_all("<MouseWheel>", _on_wheel)

        # Column headers
        hdr = ttk.Frame(self._corr_inner)
        hdr.pack(fill=tk.X, padx=4, pady=(4, 0))
        ttk.Label(hdr, text="Whisper says (from)",
                  font=("", 8, "bold"), width=22).pack(side=tk.LEFT)
        ttk.Label(hdr, text="→", width=3).pack(side=tk.LEFT)
        ttk.Label(hdr, text="Replace with (to)",
                  font=("", 8, "bold")).pack(side=tk.LEFT)
        ttk.Separator(self._corr_inner).pack(fill=tk.X, padx=4, pady=2)

        self._corr_canvas = canvas
        self._corr_rows_frame = ttk.Frame(self._corr_inner)
        self._corr_rows_frame.pack(fill=tk.X)
        self._corr_row_widgets: list[dict] = []
        self._refresh_corrections()

        # ── Add new correction row ─────────────────────────────────────────
        ttk.Separator(f).pack(fill=tk.X, padx=_PAD, pady=(6, 2))
        add_row = ttk.Frame(f)
        add_row.pack(fill=tk.X, padx=_PAD, pady=(0, _PAD))
        ttk.Label(add_row, text="From:", width=6).pack(side=tk.LEFT)
        self._corr_from_var = tk.StringVar()
        ttk.Entry(add_row, textvariable=self._corr_from_var,
                  width=20).pack(side=tk.LEFT, padx=2)
        ttk.Label(add_row, text="→").pack(side=tk.LEFT, padx=2)
        ttk.Label(add_row, text="To:", width=4).pack(side=tk.LEFT)
        self._corr_to_var = tk.StringVar()
        ttk.Entry(add_row, textvariable=self._corr_to_var,
                  width=22).pack(side=tk.LEFT, padx=2)
        ttk.Button(add_row, text="Add", width=6,
                   command=self._add_correction).pack(side=tk.LEFT, padx=4)

        self._corr_status_var = tk.StringVar(value="")
        ttk.Label(f, textvariable=self._corr_status_var,
                  foreground="gray").pack(anchor=tk.W, padx=_PAD)

    def _refresh_corrections(self) -> None:
        """Rebuild the list of correction rows from the manager."""
        for w in self._corr_rows_frame.winfo_children():
            w.destroy()
        self._corr_row_widgets.clear()

        if self._corrections is None:
            return

        for i, (from_w, to_w) in enumerate(self._corrections.corrections):
            row = ttk.Frame(self._corr_rows_frame)
            row.pack(fill=tk.X, padx=4, pady=1)

            from_var = tk.StringVar(value=from_w)
            to_var = tk.StringVar(value=to_w)

            ttk.Entry(row, textvariable=from_var, width=22,
                      state="readonly").pack(side=tk.LEFT)
            ttk.Label(row, text="→", width=3).pack(side=tk.LEFT)
            ttk.Entry(row, textvariable=to_var, width=24,
                      state="readonly").pack(side=tk.LEFT)
            ttk.Button(
                row, text="Delete", width=7,
                command=lambda idx=i: self._delete_correction(idx),
            ).pack(side=tk.LEFT, padx=4)

            self._corr_row_widgets.append({"from": from_var, "to": to_var})

        self._corr_rows_frame.update_idletasks()
        if hasattr(self, "_corr_canvas"):
            self._corr_canvas.configure(
                scrollregion=self._corr_canvas.bbox("all"))

    def _add_correction(self) -> None:
        if self._corrections is None:
            return
        from_w = self._corr_from_var.get().strip()
        to_w = self._corr_to_var.get().strip()
        if not from_w:
            self._corr_status_var.set("'From' cannot be empty.")
            return
        existing = self._corrections.corrections
        if any(f.lower() == from_w.lower() for f, _ in existing):
            self._corr_status_var.set(f"'{from_w}' already exists — delete it first.")
            return
        self._corrections.set_corrections(existing + [(from_w, to_w)])
        self._corrections.save()
        self._corr_from_var.set("")
        self._corr_to_var.set("")
        self._corr_status_var.set(f"Added: '{from_w}' → '{to_w}'")
        self._refresh_corrections()

    def _delete_correction(self, index: int) -> None:
        if self._corrections is None:
            return
        existing = self._corrections.corrections
        if 0 <= index < len(existing):
            removed = existing[index]
            new_list = [c for i, c in enumerate(existing) if i != index]
            self._corrections.set_corrections(new_list)
            self._corrections.save()
            self._corr_status_var.set(f"Deleted: '{removed[0]}' → '{removed[1]}'")
            self._refresh_corrections()

    # ── Whisper model helpers ─────────────────────────────────────────────────

    def _refresh_model_list(self) -> None:
        """Clear and repopulate the model rows inside _model_frame."""
        for widget in self._model_frame.winfo_children():
            widget.destroy()

        models = _find_whisper_models()
        if not models:
            ttk.Label(self._model_frame,
                      text="No downloaded models found.",
                      foreground="gray").pack(anchor=tk.W)
            return

        # Header row
        hdr = ttk.Frame(self._model_frame)
        hdr.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(hdr, text="Model", width=14, font=("", 9, "bold")).pack(side=tk.LEFT)
        ttk.Label(hdr, text="Size", width=8,  font=("", 9, "bold")).pack(side=tk.LEFT)
        ttk.Label(hdr, text="Path",           font=("", 9, "bold")).pack(side=tk.LEFT, padx=4)

        ttk.Separator(self._model_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=2)

        for m in models:
            row = ttk.Frame(self._model_frame)
            row.pack(fill=tk.X, pady=2)

            # Model name
            ttk.Label(row, text=m["name"], width=14).pack(side=tk.LEFT)
            # Size
            size_text = (f"{m['size_mb']:.0f} MB" if m["size_mb"] >= 1
                         else f"{m['size_mb']*1024:.0f} KB")
            ttk.Label(row, text=size_text, width=8, foreground="#555").pack(side=tk.LEFT)
            # Path (truncated)
            path_str = str(m["path"])
            display_path = ("…" + path_str[-48:]) if len(path_str) > 50 else path_str
            ttk.Label(row, text=display_path, foreground="gray",
                      font=("Consolas", 8)).pack(side=tk.LEFT, padx=4)

            # Delete button — capture current model in default arg
            ttk.Button(
                row, text="Delete",
                command=lambda model=m: self._delete_model(model),
            ).pack(side=tk.RIGHT)

    def _delete_model(self, model: dict) -> None:
        """Prompt and delete a downloaded Whisper model folder."""
        confirmed = messagebox.askyesno(
            "Delete model",
            f"Delete the '{model['name']}' Whisper model ({model['size_mb']:.0f} MB)?\n\n"
            f"Path:\n{model['path']}\n\n"
            "The model will be re-downloaded automatically the next time it is needed.",
            parent=self._win,
        )
        if not confirmed:
            return
        try:
            shutil.rmtree(model["path"])
            logger.info("Deleted Whisper model: %s", model["path"])
            self._status_var.set(f"Deleted model '{model['name']}'.")
        except Exception as exc:
            logger.error("Failed to delete model %s: %s", model["path"], exc)
            messagebox.showerror("Delete failed",
                                 f"Could not delete model:\n{exc}",
                                 parent=self._win)
        self._refresh_model_list()

    # ── Widget helpers ────────────────────────────────────────────────────────

    def _tab(self, nb: ttk.Notebook, label: str) -> ttk.Frame:
        f = ttk.Frame(nb, padding=_PAD)
        nb.add(f, text=f"  {label}  ")
        return f

    def _combo(self, parent, label: str, key: str,
               values: list, hint: str = "") -> None:
        _row(parent, label).pack(fill=tk.X)
        var = tk.StringVar(value=str(self._cfg.get(key)))
        self._vars[key] = var
        ttk.Combobox(parent, textvariable=var, values=values,
                     state="readonly", width=30).pack(anchor=tk.W, padx=_PAD, pady=2)
        if hint:
            _hint(parent, hint)

    def _check(self, parent, label: str, key: str) -> None:
        var = tk.BooleanVar(value=bool(self._cfg.get(key)))
        self._vars[key] = var
        ttk.Checkbutton(parent, text=label, variable=var).pack(anchor=tk.W, padx=_PAD, pady=2)

    def _scale(self, parent, label: str, key: str,
               from_: float, to: float, resolution: float, hint: str = "") -> None:
        _row(parent, label).pack(fill=tk.X)
        var = tk.DoubleVar(value=float(self._cfg.get(key)))
        self._vars[key] = var
        ttk.Scale(parent, variable=var, from_=from_, to=to,
                  orient=tk.HORIZONTAL, length=300).pack(anchor=tk.W, padx=_PAD, pady=2)
        if hint:
            _hint(parent, hint)

    def _spin(self, parent, label: str, key: str,
              from_: int, to: int, increment: int, hint: str = "") -> None:
        _row(parent, label).pack(fill=tk.X)
        var = tk.IntVar(value=int(self._cfg.get(key)))
        self._vars[key] = var
        ttk.Spinbox(parent, textvariable=var, from_=from_, to=to,
                    increment=increment, width=10).pack(anchor=tk.W, padx=_PAD, pady=2)
        if hint:
            _hint(parent, hint)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _save(self) -> None:
        data: dict = {}
        for key, var in self._vars.items():
            if key in ("mic_device_index_label", "mic_device_index_values"):
                continue
            try:
                data[key] = var.get()
            except Exception:
                pass

        label = self._vars.get("mic_device_index_label")
        values = self._vars.get("mic_device_index_values")
        if label and values:
            lbl_str = label.get()
            try:
                if lbl_str == "Default":
                    data["mic_device_index"] = -1
                else:
                    idx = int(lbl_str.split("]")[0].lstrip("["))
                    data["mic_device_index"] = idx
            except Exception:
                data["mic_device_index"] = -1

        if "hotkey" in data:
            from ..core.hotkey_manager import validate_hotkey
            if not validate_hotkey(str(data["hotkey"])):
                messagebox.showerror(
                    "Invalid hotkey",
                    f"The hotkey {data['hotkey']!r} is not valid.\n"
                    "Example: ctrl+alt+d   ctrl+shift+space   f9",
                    parent=self._win,
                )
                return

        raw_key = self._azure_key_var.get().strip()
        if raw_key and not raw_key.startswith("•"):
            ok = self._sec.store_azure_key(raw_key)
            if not ok:
                messagebox.showwarning(
                    "Credential warning",
                    "Failed to save the Azure API key to Windows Credential Manager.\n"
                    "Check that the keyring service is available.",
                    parent=self._win,
                )

        self._apply_startup(bool(data.get("start_with_windows", False)))
        self._cfg.update(data)
        self._cfg.save()
        self._status_var.set("Settings saved.")
        logger.info("Settings saved by user")
        if self._on_save:
            self._on_save()

    def _reset(self) -> None:
        if messagebox.askyesno("Reset settings",
                               "Reset all settings to defaults? This cannot be undone.",
                               parent=self._win):
            self._cfg.reset()
            self.close()
            self.open()

    def _test_hotkey(self) -> None:
        combo = self._vars.get("hotkey")
        if not combo:
            return
        from ..core.hotkey_manager import validate_hotkey
        if validate_hotkey(combo.get()):
            messagebox.showinfo("Hotkey OK",
                                f"✓ {combo.get()!r} is a valid hotkey.",
                                parent=self._win)
        else:
            messagebox.showerror("Invalid hotkey",
                                 f"{combo.get()!r} is not a valid combination.",
                                 parent=self._win)

    def _test_mic(self) -> None:
        """Open the live microphone level meter dialog."""
        # Resolve selected device index from the combobox
        lbl_str = self._vars["mic_device_index_label"].get()
        device_index: Optional[int] = None   # None = system default
        if lbl_str != "Default":
            try:
                device_index = int(lbl_str.split("]")[0].lstrip("["))
            except Exception:
                device_index = None

        _MicTestDialog(parent=self._win, device_index=device_index)

    def _test_azure(self) -> None:
        self._azure_test_label.config(text="Testing…", foreground="gray")
        self._win.update_idletasks()

        def _run():
            key = self._sec.get_azure_key()
            region_var = self._vars.get("cloud_region")
            region = region_var.get() if region_var else self._cfg.get("cloud_region")
            if not key:
                msg, colour = "No Azure key stored.", "red"
            else:
                from ..transcription.cloud_engine import CloudEngine
                engine = CloudEngine(api_key=key, region=region)
                ok = engine.load()
                msg, colour = (
                    (f"✓ Azure Speech connected (region: {region})", "green") if ok
                    else ("✗ Connection failed — check key and region.", "red")
                )
            self._root.after(0, lambda: self._azure_test_label.config(
                text=msg, foreground=colour))

        threading.Thread(target=_run, daemon=True).start()

    def _toggle_key_visibility(self) -> None:
        current = self._key_entry.cget("show")
        self._key_entry.config(show="" if current == "•" else "•")

    def _clear_azure_key(self) -> None:
        if messagebox.askyesno("Clear API key",
                               "Remove the Azure API key from Windows Credential Manager?",
                               parent=self._win):
            self._sec.delete_azure_key()
            self._azure_key_var.set("")

    def _apply_startup(self, enabled: bool) -> None:
        try:
            import sys
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = "DictateAnywhere"
            exe_path = f'"{sys.executable}" -m dictateanywhere'
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path,
                                0, winreg.KEY_SET_VALUE) as key:
                if enabled:
                    winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
                else:
                    try:
                        winreg.DeleteValue(key, app_name)
                    except FileNotFoundError:
                        pass
        except Exception as exc:
            logger.warning("Could not update startup registry: %s", exc)

    def _open_config_dir(self) -> None:
        import subprocess
        subprocess.Popen(["explorer", str(self._cfg.config_dir())])

    # ── Layout helpers ────────────────────────────────────────────────────────

    def _centre_window(self) -> None:
        w = self._win.winfo_reqwidth()
        h = self._win.winfo_reqheight()
        sw = self._win.winfo_screenwidth()
        sh = self._win.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self._win.geometry(f"+{x}+{y}")


def _row(parent, label: str) -> ttk.Label:
    return ttk.Label(parent, text=label, font=("", 9, "bold"))


def _hint(parent, text: str) -> None:
    ttk.Label(parent, text=text, foreground="gray",
              wraplength=420, justify=tk.LEFT).pack(
        anchor=tk.W, padx=_PAD * 2, pady=(0, 6))


class _MicTestDialog:
    """
    Non-modal dialog that streams live audio from the selected microphone
    and shows a real-time level meter.

    Helps users diagnose:
      - Microphone not producing audio (Windows privacy block, muted, wrong device)
      - Mic too quiet (low gain)
      - Mic working correctly
    """

    _BAR_W = 380
    _BAR_H = 28
    _UPDATE_MS = 80          # UI refresh interval
    _WARN_FLAT_AFTER = 3.0   # seconds of flat signal before showing privacy warning
    _SAMPLE_RATE = 16_000
    _BLOCK_MS = 80           # sounddevice blocksize in ms
    _BLOCK_SAMPLES = int(_SAMPLE_RATE * _BLOCK_MS / 1000)

    # RMS thresholds (float32 normalised to ±1.0)
    _THRESH_NOISE = 0.0005   # below this = effectively silent
    _THRESH_SPEECH = 0.015   # above this = good speech level

    def __init__(self, parent: tk.Toplevel, device_index: Optional[int]) -> None:
        import queue as _queue
        self._device = device_index
        self._rms_queue: "_queue.Queue[float]" = _queue.Queue(maxsize=20)
        self._stream = None
        self._running = False
        self._peak_rms: float = 0.0
        self._flat_since: Optional[float] = None

        self._win = tk.Toplevel(parent)
        self._win.title("Test Microphone")
        self._win.resizable(False, False)
        self._win.grab_set()
        self._win.protocol("WM_DELETE_WINDOW", self._close)

        self._build_ui(device_index)
        self._start_stream()
        self._schedule_update()

    def _build_ui(self, device_index: Optional[int]) -> None:
        import sounddevice as sd
        try:
            if device_index is not None:
                dev_name = sd.query_devices(device_index)["name"]
            else:
                dev_name = sd.query_devices(kind="input")["name"]
        except Exception:
            dev_name = "Default input device"

        pad = _PAD
        frm = ttk.Frame(self._win, padding=pad * 2)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Microphone Level", font=("", 11, "bold")).pack(anchor=tk.W)
        ttk.Label(frm, text=dev_name, foreground="gray").pack(anchor=tk.W, pady=(0, pad))

        ttk.Label(frm, text="Speak into your microphone:", font=("", 9)).pack(anchor=tk.W)

        # ── Level bar ──────────────────────────────────────────────────────────
        bar_frame = ttk.Frame(frm, relief="sunken", borderwidth=1)
        bar_frame.pack(fill=tk.X, pady=(4, 2))
        self._canvas = tk.Canvas(bar_frame, width=self._BAR_W, height=self._BAR_H,
                                 bg="#1e1e1e", highlightthickness=0)
        self._canvas.pack()
        self._bar = self._canvas.create_rectangle(
            0, 0, 0, self._BAR_H, fill="#4caf50", outline="")
        # Threshold markers
        noise_x = int(self._BAR_W * self._THRESH_NOISE / 0.1)
        speech_x = int(self._BAR_W * self._THRESH_SPEECH / 0.1)
        self._canvas.create_line(noise_x, 0, noise_x, self._BAR_H,
                                 fill="#ff9800", width=1, dash=(3, 3))
        self._canvas.create_line(speech_x, 0, speech_x, self._BAR_H,
                                 fill="#4caf50", width=1, dash=(3, 3))

        # ── Numeric readout ────────────────────────────────────────────────────
        num_row = ttk.Frame(frm)
        num_row.pack(fill=tk.X, pady=(2, 0))
        self._rms_var = tk.StringVar(value="RMS: –")
        self._peak_var = tk.StringVar(value="Peak: –")
        ttk.Label(num_row, textvariable=self._rms_var, font=("Consolas", 9)).pack(side=tk.LEFT)
        ttk.Label(num_row, textvariable=self._peak_var, font=("Consolas", 9),
                  foreground="gray").pack(side=tk.RIGHT)

        # ── Status ─────────────────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="Listening…")
        self._status_lbl = ttk.Label(frm, textvariable=self._status_var,
                                     font=("", 9, "bold"), foreground="gray",
                                     wraplength=self._BAR_W)
        self._status_lbl.pack(anchor=tk.W, pady=(pad, 0))

        # ── Privacy warning (hidden until triggered) ───────────────────────────
        self._warn_var = tk.StringVar(value="")
        self._warn_lbl = ttk.Label(frm, textvariable=self._warn_var,
                                   foreground="#c0392b", wraplength=self._BAR_W,
                                   justify=tk.LEFT)
        self._warn_lbl.pack(anchor=tk.W, pady=(2, 0))

        # ── Fix button (always shown — launches Windows Microphone privacy page) ─
        fix_frm = ttk.Frame(frm)
        fix_frm.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(fix_frm, text="If other apps can hear the mic but this one can't:",
                  foreground="gray", font=("", 8)).pack(anchor=tk.W)
        ttk.Button(fix_frm, text="Open Windows Microphone Privacy Settings",
                   command=self._open_privacy_settings).pack(anchor=tk.W, pady=2)
        ttk.Label(fix_frm,
                  text='Enable  "Let desktop apps access your microphone"',
                  foreground="#666666", font=("", 8)).pack(anchor=tk.W)

        ttk.Separator(frm, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(8, 4))
        ttk.Button(frm, text="Close", command=self._close).pack(anchor=tk.E)

    def _start_stream(self) -> None:
        import sounddevice as sd
        import numpy as np
        from ..audio.capture import _find_mme_input_devices, _mme_device_for_name, _get_device_native_rate

        def _callback(indata: np.ndarray, frames: int, time_info, status) -> None:
            if not self._running:
                return
            rms = float(np.sqrt(np.mean(indata[:, 0].astype(np.float32) ** 2)))
            try:
                self._rms_queue.put_nowait(rms)
            except Exception:
                pass

        # Build same MME-first candidate list as AudioCapture.start()
        candidates: list[tuple] = []
        try:
            if self._device is not None:
                req_name = sd.query_devices(self._device)["name"]
            else:
                req_name = sd.query_devices(kind="input")["name"]
            mme_match = _mme_device_for_name(req_name)
            if mme_match is not None:
                candidates.append((mme_match, self._SAMPLE_RATE, f"MME:{mme_match}"))
        except Exception:
            pass

        for mme_idx in _find_mme_input_devices():
            entry = (mme_idx, self._SAMPLE_RATE, f"MME:{mme_idx}")
            if entry not in candidates:
                candidates.append(entry)

        native = _get_device_native_rate(self._device)
        candidates.append((self._device, native, f"WASAPI:{self._device}"))
        candidates.append((None, _get_device_native_rate(None), "WASAPI:default"))

        for device, rate, label in candidates:
            block_samples = int(rate * self._BLOCK_MS / 1000)
            try:
                self._stream = sd.InputStream(
                    samplerate=rate,
                    channels=1,
                    dtype="float32",
                    device=device,
                    blocksize=block_samples,
                    callback=_callback,
                )
                self._stream.start()
                self._running = True
                logger.info("Mic test stream opened: %s rate=%d", label, rate)
                return
            except Exception as exc:
                logger.warning("Mic test %s failed: %s", label, exc)
                try:
                    if self._stream:
                        self._stream.close()
                except Exception:
                    pass
                self._stream = None

        self._status_var.set("Could not open any microphone input.")
        self._warn_var.set(
            "All audio backends failed. Check that the microphone is\n"
            "not in exclusive use by another app (DAW, Zoom, Teams)."
        )

    def _schedule_update(self) -> None:
        if not self._win.winfo_exists():
            return
        self._update_bar()
        self._win.after(self._UPDATE_MS, self._schedule_update)

    def _update_bar(self) -> None:
        import time

        # Drain the queue, keep the latest RMS
        rms = 0.0
        while not self._rms_queue.empty():
            try:
                rms = self._rms_queue.get_nowait()
            except Exception:
                break

        if not self._running:
            return

        self._peak_rms = max(self._peak_rms, rms)

        # Scale bar: 0.0 → 0 px, 0.10 → full width (non-linear for visual clarity)
        import math
        if rms > 1e-9:
            # log scale: map [0.0001, 0.1] → [0, BAR_W]
            log_val = (math.log10(max(rms, 0.0001)) + 4) / 4   # -4..0 → 0..1
            bar_px = max(0, min(self._BAR_W, int(log_val * self._BAR_W)))
        else:
            bar_px = 0

        # Colour based on level
        if rms < self._THRESH_NOISE:
            colour = "#555555"
        elif rms < self._THRESH_SPEECH:
            colour = "#ff9800"   # orange = too quiet
        else:
            colour = "#4caf50"   # green = good

        self._canvas.itemconfig(self._bar, fill=colour)
        self._canvas.coords(self._bar, 0, 0, bar_px, self._BAR_H)

        self._rms_var.set(f"RMS: {rms:.5f}")
        self._peak_var.set(f"Peak: {self._peak_rms:.5f}")

        # Status text
        if rms < self._THRESH_NOISE:
            fg = "#c0392b"
            if self._flat_since is None:
                self._flat_since = time.monotonic()
                status = "No signal — speak now or check mic connections"
            elif time.monotonic() - self._flat_since < self._WARN_FLAT_AFTER:
                status = "Still no signal — is the microphone muted?"
            else:
                status = "No signal after several seconds — likely a privacy block"
                self._warn_var.set(
                    "Windows is blocking microphone access for desktop apps.\n"
                    "Click the button below to open Microphone Privacy Settings\n"
                    "and turn ON  \"Let desktop apps access your microphone\".\n"
                    "Then restart DictateAnywhere."
                )
        elif rms < self._THRESH_SPEECH:
            status = "Signal detected but very quiet — speak louder or raise mic gain"
            fg = "#e67e22"
            self._flat_since = None
            self._warn_var.set("")
        else:
            status = "✓ Good signal — microphone is working correctly"
            fg = "#27ae60"
            self._flat_since = None
            self._warn_var.set("")

        self._status_var.set(status)
        self._status_lbl.config(foreground=fg)

    @staticmethod
    def _open_privacy_settings() -> None:
        """Launch the Windows Microphone Privacy settings page directly."""
        import subprocess
        try:
            # ms-settings URI — works on Windows 10 and 11
            subprocess.Popen(["start", "ms-settings:privacy-microphone"], shell=True)
        except Exception as exc:
            logger.warning("Could not open privacy settings: %s", exc)

    def _close(self) -> None:
        self._running = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._win.winfo_exists():
            self._win.destroy()
