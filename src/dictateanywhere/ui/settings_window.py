"""
Settings window — full configuration UI built with Tkinter.

All settings are read from ConfigManager and written back on Save.
The Azure API key is routed through SecureStorage (Windows Credential Manager).
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_PAD = 8
_LABEL_W = 26


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
        config_manager,          # ConfigManager instance
        secure_storage,          # SecureStorage instance
        on_save: Optional[Callable] = None,   # called after settings saved
        hotkey_validator: Optional[Callable[[str], bool]] = None,
    ) -> None:
        self._root = root
        self._cfg = config_manager
        self._sec = secure_storage
        self._on_save = on_save
        self._validate_hotkey = hotkey_validator
        self._win: Optional[tk.Toplevel] = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def open(self) -> None:
        """Build and display the settings window."""
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
        self._win.grab_set()                      # modal
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

        # Bottom bar
        bar = ttk.Frame(self._win)
        bar.pack(fill=tk.X, padx=_PAD, pady=(0, _PAD))
        ttk.Label(bar, textvariable=self._status_var, foreground="gray").pack(
            side=tk.LEFT
        )
        ttk.Button(bar, text="Cancel", command=self.close).pack(side=tk.RIGHT, padx=4)
        ttk.Button(bar, text="Save", command=self._save, style="Accent.TButton").pack(
            side=tk.RIGHT
        )
        ttk.Button(bar, text="Reset Defaults", command=self._reset).pack(
            side=tk.RIGHT, padx=4
        )

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
        ttk.Combobox(
            f,
            textvariable=self._vars["mic_device_index_label"],
            values=device_labels,
            state="readonly",
            width=50,
        ).pack(fill=tk.X, padx=_PAD, pady=2)
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
            anchor=tk.W, padx=_PAD, pady=(_PAD, 2)
        )
        _hint(f, "Works even when DictateAnywhere is in the background.\n"
              "Examples: ctrl+alt+d   ctrl+shift+space   f9")

        self._vars["hotkey"] = tk.StringVar(value=self._cfg.get("hotkey", "ctrl+alt+d"))
        hk_entry = ttk.Entry(f, textvariable=self._vars["hotkey"], width=30)
        hk_entry.pack(anchor=tk.W, padx=_PAD, pady=4)

        ttk.Button(f, text="Test hotkey", command=self._test_hotkey).pack(
            anchor=tk.W, padx=_PAD
        )

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

    def _build_tab_cloud(self, nb: ttk.Notebook) -> None:
        f = self._tab(nb, "Azure Cloud")

        ttk.Label(f, text="Azure Speech API Key", font=("", 9, "bold")).pack(
            anchor=tk.W, padx=_PAD, pady=(_PAD, 2)
        )
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
        ttk.Button(key_frame, text="Show", command=self._toggle_key_visibility).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(key_frame, text="Clear", command=self._clear_azure_key).pack(
            side=tk.LEFT
        )

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
        ttk.Label(f, text=f"Config file: {self._cfg.config_dir()}",
                  foreground="gray").pack(anchor=tk.W, padx=_PAD)
        ttk.Button(f, text="Open config folder",
                   command=self._open_config_dir).pack(anchor=tk.W, padx=_PAD, pady=4)

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
                     state="readonly", width=30).pack(
            anchor=tk.W, padx=_PAD, pady=2
        )
        if hint:
            _hint(parent, hint)

    def _check(self, parent, label: str, key: str) -> None:
        var = tk.BooleanVar(value=bool(self._cfg.get(key)))
        self._vars[key] = var
        ttk.Checkbutton(parent, text=label, variable=var).pack(
            anchor=tk.W, padx=_PAD, pady=2
        )

    def _scale(self, parent, label: str, key: str,
               from_: float, to: float, resolution: float, hint: str = "") -> None:
        _row(parent, label).pack(fill=tk.X)
        var = tk.DoubleVar(value=float(self._cfg.get(key)))
        self._vars[key] = var
        ttk.Scale(parent, variable=var, from_=from_, to=to,
                  orient=tk.HORIZONTAL, length=300).pack(
            anchor=tk.W, padx=_PAD, pady=2
        )
        if hint:
            _hint(parent, hint)

    def _spin(self, parent, label: str, key: str,
              from_: int, to: int, increment: int, hint: str = "") -> None:
        _row(parent, label).pack(fill=tk.X)
        var = tk.IntVar(value=int(self._cfg.get(key)))
        self._vars[key] = var
        ttk.Spinbox(parent, textvariable=var, from_=from_, to=to,
                    increment=increment, width=10).pack(
            anchor=tk.W, padx=_PAD, pady=2
        )
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

        # Resolve mic device index from label
        label = self._vars.get("mic_device_index_label")
        values = self._vars.get("mic_device_index_values")
        if label and values:
            lbl_str = label.get()
            labels = (["Default"] +
                      [f"[{v}] " for v in (values if isinstance(values, list) else [])])
            try:
                if lbl_str == "Default":
                    data["mic_device_index"] = -1
                else:
                    idx = int(lbl_str.split("]")[0].lstrip("["))
                    data["mic_device_index"] = idx
            except Exception:
                data["mic_device_index"] = -1

        # Validate hotkey before saving
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

        # Save Azure key separately through secure storage
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

        # Apply start-with-windows registry setting
        self._apply_startup(bool(data.get("start_with_windows", False)))

        self._cfg.update(data)
        self._cfg.save()
        self._status_var.set("Settings saved.")
        logger.info("Settings saved by user")

        if self._on_save:
            self._on_save()

    def _reset(self) -> None:
        if messagebox.askyesno(
            "Reset settings",
            "Reset all settings to defaults? This cannot be undone.",
            parent=self._win,
        ):
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
                if ok:
                    msg, colour = f"✓ Azure Speech connected (region: {region})", "green"
                else:
                    msg, colour = "✗ Connection failed — check key and region.", "red"
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
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            app_name = "DictateAnywhere"
            import sys
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
              wraplength=400, justify=tk.LEFT).pack(
        anchor=tk.W, padx=_PAD * 2, pady=(0, 6)
    )
