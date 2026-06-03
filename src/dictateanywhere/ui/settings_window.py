"""
Settings window — modern configuration UI built with PySide6 (Qt for Python).
All layouts, colors, card styling, and toggles match the approved mockup.
"""

from __future__ import annotations
import logging
import os
import shutil
import threading
import sys
from pathlib import Path
from typing import Callable, Optional

# Enforce PySide6 imports
try:
    from PySide6.QtWidgets import (
        QApplication, QDialog, QVBoxLayout, QHBoxLayout, QWidget,
        QPushButton, QLabel, QComboBox, QLineEdit,
        QCheckBox, QSlider, QSpinBox, QScrollArea, QFrame, QMessageBox,
        QFileDialog, QSizePolicy, QProgressBar, QListWidget, QListWidgetItem,
        QTabWidget
    )
    from PySide6.QtCore import Qt, QSize, QTimer, Signal
    from PySide6.QtGui import QFont, QFontDatabase, QColor, QCursor, QPainter, QBrush, QIcon
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False

logger = logging.getLogger(__name__)

# Constants matching mockup colors and aesthetics
_PRIMARY_COLOR = "#534AB7"
_PRIMARY_HOVER = "#3C3489"
_BACKGROUND_SEC = "#F8F9FA"
_BORDER_COLOR = "#E9ECEF"
_TEXT_COLOR = "#1A1A1A"
_TEXT_MUTED = "#6C757D"
_PAD = 8

# faster-whisper model prefix
_WHISPER_MODEL_PREFIX = "models--Systran--faster-whisper-"


def _get_whisper_cache_dir() -> Path:
    base = os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming"
    return Path(base) / "DictateAnywhere" / "models"


def _find_whisper_models() -> list[dict]:
    cache_dir = _get_whisper_cache_dir()
    results = []
    if not cache_dir.exists():
        return results
    for folder in sorted(cache_dir.iterdir()):
        if folder.is_dir() and folder.name.startswith(_WHISPER_MODEL_PREFIX):
            model_name = folder.name[len(_WHISPER_MODEL_PREFIX):]
            size_bytes = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
            size_mb = size_bytes / (1024 * 1024)
            results.append({"name": model_name, "path": folder, "size_mb": size_mb})
    return results


def _load_fonts() -> None:
    """Load bundled Inter font assets if present."""
    try:
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        fonts_dir = os.path.join(script_dir, "assets", "fonts")
        for font_name in ["Inter-Regular.ttf", "Inter-Medium.ttf", "Inter-Bold.ttf"]:
            font_path = os.path.join(fonts_dir, font_name)
            if os.path.exists(font_path):
                QFontDatabase.addApplicationFont(font_path)
    except Exception as e:
        logger.debug("Failed to load application fonts: %s", e)


# Custom Toggle Switch Widget styled to match the HTML mockup toggle
class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, parent=None, checked=False):
        super().__init__(parent)
        self.setFixedSize(34, 19)
        self._checked = checked
        self.setCursor(QCursor(Qt.PointingHandCursor))

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        if self._checked != checked:
            self._checked = checked
            self.update()
            self.toggled.emit(checked)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.setChecked(not self._checked)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw capsule track
        bg_color = QColor(_PRIMARY_COLOR) if self._checked else QColor("#D1D1D6")
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, self.width(), self.height(), 9.5, 9.5)

        # Draw thumb handle
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        x_pos = 17 if self._checked else 2
        painter.drawEllipse(x_pos, 2, 15, 15)


class SettingsWindow:
    """
    Modal settings dialog controller.
    Wired up to coordinate and launch PySide6 dialog from main Tkinter event thread.
    """
    def __init__(
        self,
        root,
        config_manager,
        secure_storage,
        on_save: Optional[Callable] = None,
        hotkey_validator: Optional[Callable[[str], bool]] = None,
        corrections_manager=None,
        update_checker=None,
    ) -> None:
        self._root = root
        self._cfg = config_manager
        self._sec = secure_storage
        self._on_save = on_save
        self._validate_hotkey = hotkey_validator
        self._corrections = corrections_manager
        self._updater = update_checker
        self._win = None

    def open(self) -> None:
        if not PYSIDE6_AVAILABLE:
            logger.error("PySide6 is not installed. Run scripts\\install.bat again.")
            return

        # Ensure QApplication is initialized
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
            # Apply styling stylesheet globally to settings application context
            app.setStyleSheet(self._get_stylesheet())

        _load_fonts()

        if self._win and self._win.isVisible():
            self._win.raise_()
            self._win.activateWindow()
            return

        # Create settings dialog
        self._win = SettingsDialog(self)
        self._win.show()

    def close(self) -> None:
        if self._win:
            self._win.close()
            self._win = None

    def _get_stylesheet(self) -> str:
        return f"""
        QWidget {{
            font-family: "Inter", "Segoe UI", sans-serif;
            color: {_TEXT_COLOR};
            font-size: 12px;
        }}
        QDialog {{
            background-color: #FFFFFF;
        }}
        QTabWidget::pane {{
            border: none;
            background-color: #FFFFFF;
        }}
        QTabWidget::tab-bar {{
            left: 0px;
        }}
        QTabBar {{
            background-color: {_BACKGROUND_SEC};
            border-bottom: 1px solid {_BORDER_COLOR};
            qproperty-drawBase: 0;
        }}
        QTabBar::tab {{
            background: transparent;
            color: {_TEXT_MUTED};
            padding: 6px 12px;
            font-size: 12px;
            font-weight: 500;
            border-bottom: 2px solid transparent;
        }}
        QTabBar::tab:hover {{
            color: {_TEXT_COLOR};
        }}
        QTabBar::tab:selected {{
            color: {_PRIMARY_COLOR};
            border-bottom: 2px solid {_PRIMARY_COLOR};
            font-weight: bold;
        }}
        QFrame.card {{
            background-color: #FFFFFF;
            border: 1px solid {_BORDER_COLOR};
            border-radius: 8px;
        }}
        QLabel.cardTitle {{
            font-size: 13px;
            font-weight: 600;
            color: {_TEXT_COLOR};
        }}
        QLabel.cardSubtitle {{
            font-size: 11px;
            color: {_TEXT_MUTED};
        }}
        QLabel.fieldLabel {{
            font-size: 10px;
            font-weight: bold;
            color: {_TEXT_MUTED};
            margin-top: 4px;
            margin-bottom: 2px;
        }}
        QLineEdit {{
            background-color: {_BACKGROUND_SEC};
            border: 1px solid {_BORDER_COLOR};
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 12px;
            color: {_TEXT_COLOR};
        }}
        QLineEdit:focus {{
            border: 1px solid {_PRIMARY_COLOR};
        }}
        QComboBox {{
            background-color: {_BACKGROUND_SEC};
            border: 1px solid {_BORDER_COLOR};
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 12px;
            color: {_TEXT_COLOR};
        }}
        QComboBox:focus {{
            border: 1px solid {_PRIMARY_COLOR};
        }}
        QSpinBox {{
            background-color: {_BACKGROUND_SEC};
            border: 1px solid {_BORDER_COLOR};
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 12px;
            color: {_TEXT_COLOR};
        }}
        QSpinBox:focus {{
            border: 1px solid {_PRIMARY_COLOR};
        }}
        QScrollArea {{
            border: none;
            background-color: #FFFFFF;
        }}
        QScrollBar:vertical {{
            border: none;
            background: {_BACKGROUND_SEC};
            width: 8px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: #DEE2E6;
            min-height: 20px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: #ADB5BD;
        }}
        QPushButton.btnGhost {{
            background: transparent;
            border: 1px solid {_BORDER_COLOR};
            border-radius: 6px;
            color: {_TEXT_MUTED};
            padding: 4px 10px;
            font-size: 11px;
        }}
        QPushButton.btnGhost:hover {{
            background-color: {_BACKGROUND_SEC};
            color: {_TEXT_COLOR};
        }}
        QPushButton.btnPrimary {{
            background-color: {_PRIMARY_COLOR};
            border: none;
            border-radius: 6px;
            color: #FFFFFF;
            padding: 4px 14px;
            font-weight: 500;
            font-size: 11px;
        }}
        QPushButton.btnPrimary:hover {{
            background-color: {_PRIMARY_HOVER};
        }}
        QPushButton.btnTest {{
            background: transparent;
            border: 1px solid {_PRIMARY_COLOR};
            border-radius: 6px;
            color: {_PRIMARY_COLOR};
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 500;
        }}
        QPushButton.btnTest:hover {{
            background-color: #EEEDFE;
        }}
        QFrame.warnBanner {{
            background-color: #FAEEDA;
            border: 1px solid #FAC775;
            border-radius: 6px;
        }}
        QLabel.warnText {{
            color: #854F0B;
            font-size: 11px;
        }}
        QFrame#footer {{
            border-top: 1px solid {_BORDER_COLOR};
            background-color: {_BACKGROUND_SEC};
        }}
        """


class SettingsDialog(QDialog):
    def __init__(self, controller: SettingsWindow) -> None:
        super().__init__()
        self.ctrl = controller
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle("DictateAnywhere — Settings")
        self.resize(560, 500)
        self.setMinimumSize(540, 420)

        # Set custom window icon
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            ico_path = os.path.join(base_dir, "assets", "icon.ico")
            if os.path.exists(ico_path):
                self.setWindowIcon(QIcon(ico_path))
        except Exception:
            pass

        self._setup_ui()
        self._load_config()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Tab widget containing all pages
        self.tab_widget = QTabWidget()
        self.tab_widget.setUsesScrollButtons(True)
        self.tab_widget.setTabBarAutoHide(False)
        main_layout.addWidget(self.tab_widget, 1)

        # Tabs config
        self.tabs = [
            ("Engine", self._create_tab_engine),
            ("Audio", self._create_tab_audio),
            ("Hotkeys", self._create_tab_hotkeys),
            ("Floating Button", self._create_tab_widget),
            ("Cloud STT", self._create_tab_cloud_stt),
            ("Advanced", self._create_tab_advanced),
            ("Corrections", self._create_tab_corrections),
            ("Polish", self._create_tab_polish),
            ("App Launcher", self._create_tab_app_launcher),
        ]

        for index, (name, builder) in enumerate(self.tabs):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setStyleSheet("QScrollArea { background-color: #FFFFFF; border: none; }")

            content_widget = QWidget()
            content_widget.setObjectName(f"tab_{index}")
            content_widget.setStyleSheet("QWidget { background-color: #FFFFFF; }")
            content_layout = QVBoxLayout(content_widget)
            content_layout.setContentsMargins(12, 12, 12, 12)
            content_layout.setSpacing(8)

            builder(content_layout)
            content_layout.addStretch()

            scroll.setWidget(content_widget)
            self.tab_widget.addTab(scroll, name)

        # Footer Actions bar
        footer_frame = QFrame()
        footer_frame.setObjectName("footer")
        footer_layout = QHBoxLayout(footer_frame)
        footer_layout.setContentsMargins(12, 8, 12, 8)

        footer_left = QHBoxLayout()
        footer_left.setSpacing(6)
        
        btn_import = QPushButton("Import")
        btn_import.setCursor(QCursor(Qt.PointingHandCursor))
        btn_import.setObjectName("btnImport")
        btn_import.setStyleSheet("QPushButton { padding: 4px 10px; font-size: 11px; }")
        btn_import.clicked.connect(self._import_settings)
        
        btn_export = QPushButton("Export")
        btn_export.setCursor(QCursor(Qt.PointingHandCursor))
        btn_export.setObjectName("btnExport")
        btn_export.setStyleSheet("QPushButton { padding: 4px 10px; font-size: 11px; }")
        btn_export.clicked.connect(self._export_settings)
        
        btn_reset = QPushButton("Reset defaults")
        btn_reset.setCursor(QCursor(Qt.PointingHandCursor))
        btn_reset.setObjectName("btnReset")
        btn_reset.setStyleSheet("QPushButton { padding: 4px 10px; font-size: 11px; }")
        btn_reset.clicked.connect(self._reset_defaults)
        
        footer_left.addWidget(btn_import)
        footer_left.addWidget(btn_export)
        footer_left.addWidget(btn_reset)
        footer_layout.addLayout(footer_left)

        footer_layout.addStretch()

        footer_right = QHBoxLayout()
        footer_right.setSpacing(6)
        
        btn_close = QPushButton("Close")
        btn_close.setCursor(QCursor(Qt.PointingHandCursor))
        btn_close.setObjectName("btnClose")
        btn_close.setStyleSheet("QPushButton { padding: 4px 10px; font-size: 11px; }")
        btn_close.clicked.connect(self.close)
        
        btn_save = QPushButton("Save changes")
        btn_save.setCursor(QCursor(Qt.PointingHandCursor))
        btn_save.setObjectName("btnSave")
        btn_save.setStyleSheet("QPushButton { padding: 4px 14px; font-weight: 500; font-size: 11px; }")
        btn_save.clicked.connect(self._save_settings)
        
        footer_right.addWidget(btn_close)
        footer_right.addWidget(btn_save)
        footer_layout.addLayout(footer_right)

        main_layout.addWidget(footer_frame)

        # Style footers
        btn_import.setProperty("class", "btnGhost")
        btn_export.setProperty("class", "btnGhost")
        btn_reset.setProperty("class", "btnGhost")
        btn_close.setProperty("class", "btnGhost")
        btn_save.setProperty("class", "btnPrimary")

    # ── Tab Builders ──────────────────────────────────────────────────────────

    def _create_tab_engine(self, layout: QVBoxLayout) -> None:
        # Engine Mode card
        card = self._create_card(layout)
        card_lay = card.layout()
        
        self.combo_engine_mode = self._add_combo_field(
            card_lay, "Engine mode", 
            ["hybrid", "local", "azure", "gemini", "sarvam"],
            "Hybrid uses local Whisper first; falls back to Azure if it fails."
        )
        self.combo_model_size = self._add_combo_field(
            card_lay, "Whisper model size", 
            ["tiny", "base", "small", "medium", "large-v2", "large-v3"],
            "small = best CPU/quality balance. medium for maximum accuracy."
        )
        self.combo_compute_type = self._add_combo_field(
            card_lay, "Compute type", 
            ["int8", "float16", "float32"],
            "int8 = fastest on CPU. float16 requires a compatible GPU."
        )
        self.combo_local_device = self._add_combo_field(
            card_lay, "Local device", 
            ["auto", "cpu", "cuda"],
            "auto = detect best device. Select 'cuda' to force NVIDIA GPU."
        )
        self.combo_engine_lang = self._add_combo_field(
            card_lay, "Language", 
            ["en", "es", "fr", "de", "it", "pt", "nl", "pl",
             "ru", "zh", "ja", "ko", "ar", "hi", "auto"],
            "auto = Whisper detects language automatically."
        )

        # Fallbacks card
        card_fb = self._create_card(layout)
        fb_lay = card_fb.layout()
        self.chk_cloud_fallback = self._add_toggle_field(
            fb_lay, "Fall back to cloud on local error", "Triggers cloud STT if local engine fails"
        )
        self.combo_fallback_provider = self._add_combo_field(
            fb_lay, "Preferred fallback provider", ["azure", "gemini", "sarvam"],
            "Which cloud service to use when local Whisper fails."
        )
        self.chk_local_fallback = self._add_toggle_field(
            fb_lay, "Fall back to local on cloud error", "Falls back to local engine if cloud STT fails"
        )

    def _create_tab_audio(self, layout: QVBoxLayout) -> None:
        card = self._create_card(layout)
        card_lay = card.layout()

        card_lay.addWidget(QLabel("MICROPHONE"))
        self.combo_mic = QComboBox()
        card_lay.addWidget(self.combo_mic)
        
        btn_test_mic = QPushButton("Test Microphone")
        btn_test_mic.setProperty("class", "btnGhost")
        btn_test_mic.clicked.connect(self._test_mic)
        btn_test_mic.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        card_lay.addWidget(btn_test_mic)

        self._load_microphones()

        # Constraints card
        card_con = self._create_card(layout)
        con_lay = card_con.layout()

        self.slider_vad = self._add_slider_field(
            con_lay, "VAD aggressiveness", 0, 3,
            "0 = capture everything; 3 = filter aggressively (best for noisy rooms)."
        )
        self.spin_silence = self._add_spin_field(
            con_lay, "Silence timeout (ms)", 300, 5000, 100,
            "Dictation stops after this many ms of silence. 1500 ms recommended."
        )
        self.chk_max_limit = self._add_toggle_field(
            con_lay, "Enable maximum recording limit", "Hard cap to prevent runaway recordings"
        )
        self.spin_max_seconds = self._add_spin_field(
            con_lay, "Max recording length (s)", 5, 120, 5,
            "Only enforced if limit is active."
        )

    def _create_tab_hotkeys(self, layout: QVBoxLayout) -> None:
        card = self._create_card(layout)
        card_lay = card.layout()

        self.txt_hotkey = self._add_line_field(
            card_lay, "Global hotkey", "Examples: ctrl+alt+d  ctrl+shift+space  f9"
        )
        btn_test = QPushButton("Test hotkey")
        btn_test.setProperty("class", "btnGhost")
        btn_test.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_test.clicked.connect(self._test_hotkey)
        card_lay.addWidget(btn_test)

        self.combo_hotkey_mode = self._add_combo_field(
            card_lay, "Hotkey mode", ["toggle", "push_to_talk"],
            "Toggle: press once to start. Push-to-talk: hold to record."
        )

        # Overlay card
        card_ov = self._create_card(layout)
        ov_lay = card_ov.layout()

        self.chk_show_preview = self._add_toggle_field(
            ov_lay, "Show status overlay during dictation", "Fades in a dark status pill"
        )
        self.spin_preview_hide = self._add_spin_field(
            ov_lay, "Auto-hide after (ms)", 0, 30000, 1000,
            "0 keeps overlay open until manually closed."
        )
        self.txt_preview_opacity = self._add_line_field(
            ov_lay, "Overlay Opacity", "1.0 = fully opaque; 0.1 = transparent."
        )

    def _create_tab_widget(self, layout: QVBoxLayout) -> None:
        card = self._create_card(layout)
        card_lay = card.layout()

        self.chk_show_widget = self._add_toggle_field(
            card_lay, "Show floating mic button", "Draggable on-screen shortcut"
        )
        self.chk_widget_on_top = self._add_toggle_field(
            card_lay, "Always on top", "Keep float button above other windows"
        )
        self.spin_widget_size = self._add_spin_field(
            card_lay, "Button size (px)", 32, 128, 8, "Sizing of the floating widget circle."
        )
        self.slider_widget_opacity = self._add_slider_field(
            card_lay, "Opacity", 10, 100, "Transparency of the floating button."
        )

    def _create_tab_cloud_stt(self, layout: QVBoxLayout) -> None:
        # 1. Azure Speech card
        card_az = self._create_card(layout)
        az_lay = card_az.layout()
        
        lbl_az_title = QLabel("Azure Speech")
        lbl_az_title.setProperty("class", "cardTitle")
        lbl_az_sub = QLabel("Microsoft Cognitive Services")
        lbl_az_sub.setProperty("class", "cardSubtitle")
        az_lay.addWidget(lbl_az_title)
        az_lay.addWidget(lbl_az_sub)

        self.txt_azure_key = QLineEdit()
        self.txt_azure_key.setEchoMode(QLineEdit.Password)
        az_lay.addWidget(QLabel("API KEY"))
        az_lay.addWidget(self.txt_azure_key)

        self.combo_azure_region = self._add_combo_field(
            az_lay, "Region", ["eastus", "westus", "westeurope", "centralindia", "southeastasia"],
            "Must match your Azure Speech resources."
        )

        btn_test_az = QPushButton("Test Azure connection")
        btn_test_az.setProperty("class", "btnTest")
        btn_test_az.clicked.connect(self._test_azure)
        az_lay.addWidget(btn_test_az)
        self.lbl_azure_test = QLabel("")
        az_lay.addWidget(self.lbl_azure_test)

        # 2. Sarvam AI card
        card_sa = self._create_card(layout)
        sa_lay = card_sa.layout()

        lbl_sa_title = QLabel("Sarvam AI")
        lbl_sa_title.setProperty("class", "cardTitle")
        lbl_sa_sub = QLabel("Optimized for Indian languages")
        lbl_sa_sub.setProperty("class", "cardSubtitle")
        sa_lay.addWidget(lbl_sa_title)
        sa_lay.addWidget(lbl_sa_sub)

        self.txt_sarvam_key = QLineEdit()
        self.txt_sarvam_key.setEchoMode(QLineEdit.Password)
        sa_lay.addWidget(QLabel("API KEY"))
        sa_lay.addWidget(self.txt_sarvam_key)

        self.combo_sarvam_model = self._add_combo_field(
            sa_lay, "Model", ["saarika:v2.5", "saaras:v3"], "Standard STT model."
        )
        self.combo_sarvam_lang = self._add_combo_field(
            sa_lay, "Language", ["hi-IN", "bn-IN", "gu-IN", "kn-IN", "ml-IN", "mr-IN", "pa-IN", "ta-IN", "te-IN", "en-IN", "auto"],
            "Language of the dictated audio."
        )
        self.chk_sarvam_ws = self._add_toggle_field(
            sa_lay, "WebSocket streaming", "Lower latency real-time previews"
        )

        # Warn banner for Sarvam
        banner = QFrame()
        banner.setProperty("class", "warnBanner")
        banner_lay = QHBoxLayout(banner)
        banner_lay.setContentsMargins(8, 8, 8, 8)
        lbl_warn = QLabel("⚠️ Sarvam has a 30-second limit per dictation session.")
        lbl_warn.setProperty("class", "warnText")
        banner_lay.addWidget(lbl_warn)
        sa_lay.addWidget(banner)

        btn_test_sa = QPushButton("Test Sarvam connection")
        btn_test_sa.setProperty("class", "btnTest")
        btn_test_sa.clicked.connect(self._test_sarvam)
        sa_lay.addWidget(btn_test_sa)
        self.lbl_sarvam_test = QLabel("")
        sa_lay.addWidget(self.lbl_sarvam_test)

        # 3. Google Gemini card
        card_gm = self._create_card(layout)
        gm_lay = card_gm.layout()

        lbl_gm_title = QLabel("Google Gemini")
        lbl_gm_title.setProperty("class", "cardTitle")
        lbl_gm_sub = QLabel("Gemini 2.5 Flash Lite · Latest")
        lbl_gm_sub.setProperty("class", "cardSubtitle")
        gm_lay.addWidget(lbl_gm_title)
        gm_lay.addWidget(lbl_gm_sub)

        self.txt_gemini_key = QLineEdit()
        self.txt_gemini_key.setEchoMode(QLineEdit.Password)
        gm_lay.addWidget(QLabel("API KEY"))
        gm_lay.addWidget(self.txt_gemini_key)

        self.combo_gemini_model = self._add_combo_field(
            gm_lay, "Model", ["gemini-flash-lite-latest", "gemini-2.0-flash-lite"], ""
        )
        self.combo_gemini_lang = self._add_combo_field(
            gm_lay, "Language", ["en", "hi", "es", "fr", "de", "it", "ja", "ko", "zh", "auto"],
            "Language of the audio input."
        )

        btn_test_gm = QPushButton("Test Gemini connection")
        btn_test_gm.setProperty("class", "btnTest")
        btn_test_gm.clicked.connect(self._test_gemini)
        gm_lay.addWidget(btn_test_gm)
        self.lbl_gemini_test = QLabel("")
        gm_lay.addWidget(self.lbl_gemini_test)

    def _create_tab_advanced(self, layout: QVBoxLayout) -> None:
        card = self._create_card(layout)
        card_lay = card.layout()

        self.chk_punctuation = self._add_toggle_field(
            card_lay, "Spoken punctuation", 'Converts verbal words like "period" to "."'
        )
        self.chk_capitalise = self._add_toggle_field(
            card_lay, "Auto-capitalise", "Capitalises start of sentences"
        )
        self.combo_inject = self._add_combo_field(
            card_lay, "Text injection method", ["clipboard", "sendinput"],
            "clipboard = fastest. sendinput = safe char-by-char."
        )
        self.spin_inject_delay = self._add_spin_field(
            card_lay, "Injection delay (ms)", 0, 500, 10,
            "Small clipboard buffer delay. Increase if text pastes late."
        )
        self.chk_windows_start = self._add_toggle_field(
            card_lay, "Start DictateAnywhere with Windows", "Launches app on boot"
        )
        self.combo_log_level = self._add_combo_field(
            card_lay, "Log level", ["DEBUG", "INFO", "WARNING", "ERROR"],
            "Verbose debug logs for diagnostics."
        )

        # Updates card
        card_up = self._create_card(layout)
        up_lay = card_up.layout()
        self.chk_check_updates = self._add_toggle_field(
            up_lay, "Check for updates automatically", "Daily check from GitHub Releases"
        )
        btn_update = QPushButton("Check updates now")
        btn_update.setProperty("class", "btnGhost")
        btn_update.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn_update.clicked.connect(self._check_updates_now)
        up_lay.addWidget(btn_update)
        self.lbl_update_status = QLabel("")
        up_lay.addWidget(self.lbl_update_status)

        # Config dir card
        card_dir = self._create_card(layout)
        dir_lay = card_dir.layout()
        self.lbl_config_path = QLabel("Config folder: ...")
        self.lbl_config_path.setWordWrap(True)
        dir_lay.addWidget(self.lbl_config_path)
        btn_open_dir = QPushButton("Open config folder")
        btn_open_dir.setProperty("class", "btnGhost")
        btn_open_dir.clicked.connect(self._open_config_dir)
        btn_open_dir.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        dir_lay.addWidget(btn_open_dir)

        # Model cache card
        card_cache = self._create_card(layout)
        self.cache_lay = card_cache.layout()
        self.cache_lay.addWidget(QLabel("WHISPER MODEL CACHE"))
        self._refresh_model_cache_list()

    def _create_tab_corrections(self, layout: QVBoxLayout) -> None:
        card = self._create_card(layout)
        card_lay = card.layout()

        lbl_corr_title = QLabel("Word Corrections")
        lbl_corr_title.setProperty("class", "cardTitle")
        lbl_corr_hint = QLabel(
            "Define case-insensitive replacements applied after transcribing.\n"
            "Examples: gonna -> going to  |  acme -> Acme Corp"
        )
        lbl_corr_hint.setProperty("class", "cardSubtitle")
        card_lay.addWidget(lbl_corr_title)
        card_lay.addWidget(lbl_corr_hint)

        # Scroll list of corrections
        self.list_corrections = QListWidget()
        self.list_corrections.setMinimumHeight(110)
        card_lay.addWidget(self.list_corrections)

        # Add corrections layout
        add_lay = QHBoxLayout()
        self.txt_corr_from = QLineEdit()
        self.txt_corr_from.setPlaceholderText("From (Whisper)...")
        self.txt_corr_to = QLineEdit()
        self.txt_corr_to.setPlaceholderText("To (Replacement)...")
        btn_add_corr = QPushButton("Add")
        btn_add_corr.setProperty("class", "btnPrimary")
        btn_add_corr.clicked.connect(self._add_correction)
        
        add_lay.addWidget(self.txt_corr_from)
        add_lay.addWidget(QLabel("→"))
        add_lay.addWidget(self.txt_corr_to)
        add_lay.addWidget(btn_add_corr)
        card_lay.addLayout(add_lay)

        self.lbl_corr_status = QLabel("")
        card_lay.addWidget(self.lbl_corr_status)

        self._refresh_corrections_list()

    def _create_tab_polish(self, layout: QVBoxLayout) -> None:
        card = self._create_card(layout)
        card_lay = card.layout()

        self.chk_enable_polish = self._add_toggle_field(
            card_lay, "Enable Polish mode", "Sends transcribed text to an LLM to rewrite/format"
        )
        self.combo_polish_provider = self._add_combo_field(
            card_lay, "Polish Provider", ["none", "ollama", "gemini"],
            "Ollama = local (private). Gemini = cloud."
        )
        self.combo_polish_action = self._add_combo_field(
            card_lay, "Polish Action", 
            ["Fix Grammar & Spelling", "Make Professional", "Summarize", "Chat", "Custom Prompt"],
            "How should the AI process the transcription."
        )
        self.txt_custom_prompt = QLineEdit()
        card_lay.addWidget(QLabel("CUSTOM PROMPT"))
        card_lay.addWidget(self.txt_custom_prompt)

        # Ollama card
        card_ol = self._create_card(layout)
        ol_lay = card_ol.layout()
        ol_lay.addWidget(QLabel("LOCAL LLM (OLLAMA)"))

        self.txt_ollama_url = QLineEdit()
        ol_lay.addWidget(QLabel("Server URL"))
        ol_lay.addWidget(self.txt_ollama_url)

        self.combo_ollama_model = QComboBox()
        ol_lay.addWidget(QLabel("Model"))
        ol_lay.addWidget(self.combo_ollama_model)

        # Gemini
        card_gm = self._create_card(layout)
        gm_lay = card_gm.layout()
        self.combo_polish_gemini_model = self._add_combo_field(
            gm_lay, "Gemini Model", ["gemini-flash-lite-latest", "gemini-2.0-flash-lite"],
            "Flash Lite is recommended for latency speed."
        )

    def _create_tab_app_launcher(self, layout: QVBoxLayout) -> None:
        card = self._create_card(layout)
        card_lay = card.layout()

        lbl_title = QLabel("App Launcher Commands")
        lbl_title.setProperty("class", "cardTitle")
        lbl_hint = QLabel("Define voice commands to launch local apps immediately.")
        lbl_hint.setProperty("class", "cardSubtitle")
        card_lay.addWidget(lbl_title)
        card_lay.addWidget(lbl_hint)

        self.list_launcher = QListWidget()
        self.list_launcher.setMinimumHeight(110)
        card_lay.addWidget(self.list_launcher)

        # Adding new launch command
        add_lay = QHBoxLayout()
        self.txt_launch_cmd = QLineEdit()
        self.txt_launch_cmd.setPlaceholderText("Voice phrase (e.g. open notepad)...")
        self.txt_launch_path = QLineEdit()
        self.txt_launch_path.setPlaceholderText("Path to app...")
        btn_browse = QPushButton("Browse...")
        btn_browse.setProperty("class", "btnGhost")
        btn_browse.clicked.connect(self._browse_app)
        btn_add = QPushButton("Add")
        btn_add.setProperty("class", "btnPrimary")
        btn_add.clicked.connect(self._add_launcher_command)

        add_lay.addWidget(self.txt_launch_cmd)
        add_lay.addWidget(self.txt_launch_path)
        add_lay.addWidget(btn_browse)
        add_lay.addWidget(btn_add)
        card_lay.addLayout(add_lay)

        self.lbl_launch_status = QLabel("")
        card_lay.addWidget(self.lbl_launch_status)

        self._refresh_launcher_list()

    # ── Helpers for Widget Creation ──────────────────────────────────────────

    def _create_card(self, parent_layout: QVBoxLayout) -> QFrame:
        card = QFrame()
        card.setProperty("class", "card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)
        parent_layout.addWidget(card)
        return card

    def _add_combo_field(self, parent_layout: QVBoxLayout, label: str, items: list[str], hint: str = "") -> QComboBox:
        lbl = QLabel(label.upper())
        lbl.setProperty("class", "fieldLabel")
        parent_layout.addWidget(lbl)
        combo = QComboBox()
        combo.addItems(items)
        parent_layout.addWidget(combo)
        if hint:
            lbl_hint = QLabel(hint)
            lbl_hint.setProperty("class", "cardSubtitle")
            parent_layout.addWidget(lbl_hint)
        return combo

    def _add_line_field(self, parent_layout: QVBoxLayout, label: str, hint: str = "") -> QLineEdit:
        lbl = QLabel(label.upper())
        lbl.setProperty("class", "fieldLabel")
        parent_layout.addWidget(lbl)
        line = QLineEdit()
        parent_layout.addWidget(line)
        if hint:
            lbl_hint = QLabel(hint)
            lbl_hint.setProperty("class", "cardSubtitle")
            parent_layout.addWidget(lbl_hint)
        return line

    def _add_toggle_field(self, parent_layout: QVBoxLayout, label: str, hint: str = "") -> ToggleSwitch:
        row = QHBoxLayout()
        txt_lay = QVBoxLayout()
        txt_lay.setSpacing(1)
        lbl = QLabel(label)
        lbl.setStyleSheet("font-weight: 500; font-size: 12px;")
        txt_lay.addWidget(lbl)
        if hint:
            lbl_hint = QLabel(hint)
            lbl_hint.setProperty("class", "cardSubtitle")
            txt_lay.addWidget(lbl_hint)
        row.addLayout(txt_lay)
        row.addStretch()

        toggle = ToggleSwitch()
        row.addWidget(toggle)
        parent_layout.addLayout(row)
        return toggle

    def _add_slider_field(self, parent_layout: QVBoxLayout, label: str, min_v: int, max_v: int, hint: str = "") -> QSlider:
        lbl = QLabel(label.upper())
        lbl.setProperty("class", "fieldLabel")
        parent_layout.addWidget(lbl)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(min_v, max_v)
        parent_layout.addWidget(slider)
        if hint:
            lbl_hint = QLabel(hint)
            lbl_hint.setProperty("class", "cardSubtitle")
            parent_layout.addWidget(lbl_hint)
        return slider

    def _add_spin_field(self, parent_layout: QVBoxLayout, label: str, min_v: int, max_v: int, step: int, hint: str = "") -> QSpinBox:
        lbl = QLabel(label.upper())
        lbl.setProperty("class", "fieldLabel")
        parent_layout.addWidget(lbl)
        spin = QSpinBox()
        spin.setRange(min_v, max_v)
        spin.setSingleStep(step)
        parent_layout.addWidget(spin)
        if hint:
            lbl_hint = QLabel(hint)
            lbl_hint.setProperty("class", "cardSubtitle")
            parent_layout.addWidget(lbl_hint)
        return spin

    # ── Config Loader & Saver ──────────────────────────────────────────────────

    def _load_config(self) -> None:
        cfg = self.ctrl._cfg
        sec = self.ctrl._sec

        # Engine Tab
        self.combo_engine_mode.setCurrentText(str(cfg.get("engine_mode")))
        self.combo_model_size.setCurrentText(str(cfg.get("model_size")))
        self.combo_compute_type.setCurrentText(str(cfg.get("compute_type")))
        self.combo_local_device.setCurrentText(str(cfg.get("local_device")))
        self.combo_engine_lang.setCurrentText(str(cfg.get("language")))
        self.chk_cloud_fallback.setChecked(bool(cfg.get("cloud_fallback_on_error")))
        self.combo_fallback_provider.setCurrentText(str(cfg.get("cloud_fallback_provider")))
        self.chk_local_fallback.setChecked(bool(cfg.get("local_fallback_on_cloud_error")))

        # Audio Tab
        self.slider_vad.setValue(int(cfg.get("vad_aggressiveness", 2)))
        self.spin_silence.setValue(int(cfg.get("silence_timeout_ms", 1500)))
        self.chk_max_limit.setChecked(bool(cfg.get("enable_max_record_limit", True)))
        self.spin_max_seconds.setValue(int(cfg.get("max_record_seconds", 30)))

        # Hotkeys Tab
        self.txt_hotkey.setText(str(cfg.get("hotkey")))
        self.combo_hotkey_mode.setCurrentText(str(cfg.get("hotkey_mode")))
        self.chk_show_preview.setChecked(bool(cfg.get("show_preview_window")))
        self.spin_preview_hide.setValue(int(cfg.get("preview_hide_after_ms", 8000)))
        self.txt_preview_opacity.setText(str(cfg.get("preview_opacity", 0.85)))

        # Floating Button Tab
        self.chk_show_widget.setChecked(bool(cfg.get("show_floating_widget")))
        self.chk_widget_on_top.setChecked(bool(cfg.get("widget_always_on_top")))
        self.spin_widget_size.setValue(int(cfg.get("widget_size", 64)))
        self.slider_widget_opacity.setValue(int(float(cfg.get("widget_opacity", 0.85)) * 100))

        # Cloud STT Keys
        self.txt_azure_key.setText(sec.get_azure_key() or "")
        self.combo_azure_region.setCurrentText(str(cfg.get("cloud_region", "eastus")))
        self.txt_sarvam_key.setText(sec.get_sarvam_key() or "")
        self.combo_sarvam_model.setCurrentText(str(cfg.get("sarvam_model", "saarika:v2.5")))
        self.combo_sarvam_lang.setCurrentText(str(cfg.get("sarvam_language", "en-IN")))
        self.chk_sarvam_ws.setChecked(bool(cfg.get("enable_sarvam_websocket", False)))
        self.txt_gemini_key.setText(sec.get_gemini_key() or "")
        self.combo_gemini_model.setCurrentText(str(cfg.get("gemini_stt_model", "gemini-flash-lite-latest")))
        self.combo_gemini_lang.setCurrentText(str(cfg.get("gemini_stt_language", "en")))

        # Advanced Tab
        self.chk_punctuation.setChecked(bool(cfg.get("spoken_punctuation", True)))
        self.chk_capitalise.setChecked(bool(cfg.get("auto_capitalise", True)))
        self.combo_inject.setCurrentText(str(cfg.get("inject_method", "clipboard")))
        self.spin_inject_delay.setValue(int(cfg.get("inject_delay_ms", 50)))
        self.chk_windows_start.setChecked(bool(cfg.get("start_with_windows", False)))
        self.combo_log_level.setCurrentText(str(cfg.get("log_level", "INFO")))
        self.chk_check_updates.setChecked(bool(cfg.get("check_updates", True)))
        self.lbl_config_path.setText(f"Config folder: {cfg.config_dir()}")

        # Polish Tab
        self.chk_enable_polish.setChecked(bool(cfg.get("enable_polish", False)))
        self.combo_polish_provider.setCurrentText(str(cfg.get("polish_provider", "none")))
        self.combo_polish_action.setCurrentText(str(cfg.get("polish_action", "Fix Grammar & Spelling")))
        self.txt_custom_prompt.setText(str(cfg.get("custom_polish_prompt", "")))
        self.txt_ollama_url.setText(str(cfg.get("ollama_url", "http://localhost:11434")))
        self.combo_polish_gemini_model.setCurrentText(str(cfg.get("polish_gemini_model", "gemini-flash-lite-latest")))

    def _save_settings(self) -> None:
        cfg = self.ctrl._cfg
        sec = self.ctrl._sec

        # Validate hotkey
        hotkey = self.txt_hotkey.text().strip()
        if self.ctrl._validate_hotkey and not self.ctrl._validate_hotkey(hotkey):
            QMessageBox.critical(self, "Invalid Hotkey", "The configured hotkey is invalid.\nExample: ctrl+alt+d")
            return

        # Core updates
        data = {
            "engine_mode": self.combo_engine_mode.currentText(),
            "model_size": self.combo_model_size.currentText(),
            "compute_type": self.combo_compute_type.currentText(),
            "local_device": self.combo_local_device.currentText(),
            "language": self.combo_engine_lang.currentText(),
            "cloud_fallback_on_error": self.chk_cloud_fallback.isChecked(),
            "cloud_fallback_provider": self.combo_fallback_provider.currentText(),
            "local_fallback_on_cloud_error": self.chk_local_fallback.isChecked(),
            
            "vad_aggressiveness": self.slider_vad.value(),
            "silence_timeout_ms": self.spin_silence.value(),
            "enable_max_record_limit": self.chk_max_limit.isChecked(),
            "max_record_seconds": self.spin_max_seconds.value(),
            
            "hotkey": hotkey,
            "hotkey_mode": self.combo_hotkey_mode.currentText(),
            "show_preview_window": self.chk_show_preview.isChecked(),
            "preview_hide_after_ms": self.spin_preview_hide.value(),
            "preview_opacity": float(self.txt_preview_opacity.text().strip() or 0.85),
            
            "show_floating_widget": self.chk_show_widget.isChecked(),
            "widget_always_on_top": self.chk_widget_on_top.isChecked(),
            "widget_size": self.spin_widget_size.value(),
            "widget_opacity": self.slider_widget_opacity.value() / 100.0,
            
            "cloud_region": self.combo_azure_region.currentText(),
            "sarvam_model": self.combo_sarvam_model.currentText(),
            "sarvam_language": self.combo_sarvam_lang.currentText(),
            "enable_sarvam_websocket": self.chk_sarvam_ws.isChecked(),
            
            "gemini_stt_model": self.combo_gemini_model.currentText(),
            "gemini_stt_language": self.combo_gemini_lang.currentText(),
            
            "spoken_punctuation": self.chk_punctuation.isChecked(),
            "auto_capitalise": self.chk_capitalise.isChecked(),
            "inject_method": self.combo_inject.currentText(),
            "inject_delay_ms": self.spin_inject_delay.value(),
            "start_with_windows": self.chk_windows_start.isChecked(),
            "log_level": self.combo_log_level.currentText(),
            "check_updates": self.chk_check_updates.isChecked(),
            
            "enable_polish": self.chk_enable_polish.isChecked(),
            "polish_provider": self.combo_polish_provider.currentText(),
            "polish_action": self.combo_polish_action.currentText(),
            "custom_polish_prompt": self.txt_custom_prompt.text().strip(),
            "ollama_url": self.txt_ollama_url.text().strip(),
            "polish_gemini_model": self.combo_polish_gemini_model.currentText(),
        }

        # Mic device
        lbl_str = self.combo_mic.currentText()
        if lbl_str == "Default":
            data["mic_device_index"] = -1
        else:
            try:
                data["mic_device_index"] = int(lbl_str.split("]")[0].lstrip("["))
            except Exception:
                data["mic_device_index"] = -1

        # Secure Keys storage
        sec.store_azure_key(self.txt_azure_key.text().strip())
        sec.store_sarvam_key(self.txt_sarvam_key.text().strip())
        sec.store_gemini_key(self.txt_gemini_key.text().strip())

        cfg.update(data)
        cfg.save()
        
        # Trigger live reload in main application
        if self.ctrl._on_save:
            self.ctrl._on_save()
        
        QMessageBox.information(self, "Settings Saved", "Your settings have been saved successfully.")
        self.close()

    # ── Action Methods ────────────────────────────────────────────────────────

    def _load_microphones(self) -> None:
        self.combo_mic.clear()
        self.combo_mic.addItem("Default")
        from ..audio.capture import list_input_devices
        try:
            devices = list_input_devices()
            for d in devices:
                self.combo_mic.addItem(f"[{d['index']}] {d['name']}")
        except Exception:
            pass
        
        # Select current mic index
        current_idx = self.ctrl._cfg.get("mic_device_index", -1)
        if current_idx == -1:
            self.combo_mic.setCurrentIndex(0)
        else:
            for idx in range(self.combo_mic.count()):
                text = self.combo_mic.itemText(idx)
                if f"[{current_idx}]" in text:
                    self.combo_mic.setCurrentIndex(idx)
                    break

    def _test_mic(self) -> None:
        lbl_str = self.combo_mic.currentText()
        device_index = None
        if lbl_str != "Default":
            try:
                device_index = int(lbl_str.split("]")[0].lstrip("["))
            except Exception:
                pass
        # Open live progress-bar level meter test
        _MicTestDialog(self, device_index).exec()

    def _test_azure(self) -> None:
        key = self.txt_azure_key.text().strip()
        if not key:
            self.lbl_azure_test.setText("❌ Please enter an API key first")
            return
        self.lbl_azure_test.setText("⏳ Testing connection...")
        
        def _run():
            from ..transcription.azure_engine import AzureEngine
            engine = AzureEngine()
            engine.update_credentials(key, self.combo_azure_region.currentText())
            ok, msg = engine.test_connection()
            self.lbl_azure_test.setText(f"{'✅' if ok else '❌'} {msg}")
            
        threading.Thread(target=_run, daemon=True).start()

    def _test_sarvam(self) -> None:
        key = self.txt_sarvam_key.text().strip()
        if not key:
            self.lbl_sarvam_test.setText("❌ Please enter an API key first")
            return
        self.lbl_sarvam_test.setText("⏳ Testing connection...")

        def _run():
            from ..transcription.sarvam_engine import SarvamEngine
            engine = SarvamEngine()
            engine.update_credentials(key)
            ok, msg = engine.test_connection()
            self.lbl_sarvam_test.setText(f"{'✅' if ok else '❌'} {msg}")

        threading.Thread(target=_run, daemon=True).start()

    def _test_gemini(self) -> None:
        key = self.txt_gemini_key.text().strip()
        if not key:
            self.lbl_gemini_test.setText("❌ Please enter an API key first")
            return
        self.lbl_gemini_test.setText("⏳ Testing connection...")

        def _run():
            from ..transcription.gemini_engine import GeminiEngine
            engine = GeminiEngine()
            engine.update_credentials(key)
            ok, msg = engine.test_connection()
            self.lbl_gemini_test.setText(f"{'✅' if ok else '❌'} {msg}")

        threading.Thread(target=_run, daemon=True).start()

    def _test_hotkey(self) -> None:
        hk = self.txt_hotkey.text().strip()
        if self.ctrl._validate_hotkey and self.ctrl._validate_hotkey(hk):
            QMessageBox.information(self, "Hotkey Valid", f"✓ '{hk}' is a valid hotkey combination.")
        else:
            QMessageBox.warning(self, "Invalid Hotkey", f"'{hk}' is not a valid combination.")

    def _check_updates_now(self) -> None:
        if not self.ctrl._updater:
            self.lbl_update_status.setText("Update checker unavailable.")
            return
        self.lbl_update_status.setText("Checking...")
        
        def _done(latest, url, is_newer):
            if is_newer:
                self.lbl_update_status.setText(f"Update available: v{latest}")
            else:
                self.lbl_update_status.setText("App is up-to-date.")

        self.ctrl._updater.check_now(_done)

    def _open_config_dir(self) -> None:
        import subprocess
        subprocess.Popen(["explorer", str(self.ctrl._cfg.config_dir())])

    # ── Model Cache List Manager ──────────────────────────────────────────────

    def _refresh_model_cache_list(self) -> None:
        # Clear layout
        while self.cache_lay.count() > 1:
            child = self.cache_lay.takeAt(1)
            if child.widget():
                child.widget().deleteLater()
        
        models = _find_whisper_models()
        if not models:
            self.cache_lay.addWidget(QLabel("No local Whisper models cached."))
            return

        for m in models:
            row = QHBoxLayout()
            lbl = QLabel(f"• {m['name']} ({m['size_mb']:.0f} MB)")
            btn_del = QPushButton("Delete")
            btn_del.setProperty("class", "btnGhost")
            btn_del.setFixedSize(60, 22)
            btn_del.clicked.connect(lambda checked=False, model=m: self._delete_model(model))
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(btn_del)
            self.cache_lay.addLayout(row)

    def _delete_model(self, model: dict) -> None:
        confirm = QMessageBox.question(
            self, "Delete model cache",
            f"Confirm deletion of local '{model['name']}' model folder?\nIt will download again on next hybrid/local launch."
        )
        if confirm == QMessageBox.Yes:
            try:
                shutil.rmtree(model["path"])
                self._refresh_model_cache_list()
            except Exception as e:
                QMessageBox.critical(self, "Delete Failed", f"Failed to delete model: {e}")

    # ── Corrections List Manager ──────────────────────────────────────────────

    def _refresh_corrections_list(self) -> None:
        self.list_corrections.clear()
        if not self.ctrl._corrections:
            return
        for i, (f, t) in enumerate(self.ctrl._corrections.corrections):
            item = QListWidgetItem()
            widget = QWidget()
            lay = QHBoxLayout(widget)
            lay.setContentsMargins(4, 2, 4, 2)
            lay.addWidget(QLabel(f"{f}  →  {t}"))
            lay.addStretch()
            btn_del = QPushButton("Delete")
            btn_del.setProperty("class", "btnGhost")
            btn_del.setFixedSize(60, 22)
            btn_del.clicked.connect(lambda checked=False, idx=i: self._delete_correction(idx))
            lay.addWidget(btn_del)
            item.setSizeHint(widget.sizeHint())
            self.list_corrections.addItem(item)
            self.list_corrections.setItemWidget(item, widget)

    def _add_correction(self) -> None:
        f = self.txt_corr_from.text().strip()
        t = self.txt_corr_to.text().strip()
        if not f:
            return
        corr = self.ctrl._corrections
        if corr:
            existing = corr.corrections
            corr.set_corrections(existing + [(f, t)])
            corr.save()
            self.txt_corr_from.clear()
            self.txt_corr_to.clear()
            self._refresh_corrections_list()

    def _delete_correction(self, idx: int) -> None:
        corr = self.ctrl._corrections
        if corr:
            existing = corr.corrections
            if 0 <= idx < len(existing):
                new_list = [item for i, item in enumerate(existing) if i != idx]
                corr.set_corrections(new_list)
                corr.save()
                self._refresh_corrections_list()

    # ── Launcher commands Manager ──────────────────────────────────────────────

    def _refresh_launcher_list(self) -> None:
        self.list_launcher.clear()
        commands = self.ctrl._cfg.get("app_launcher_commands", {})
        for cmd, path in sorted(commands.items()):
            item = QListWidgetItem()
            widget = QWidget()
            lay = QHBoxLayout(widget)
            lay.setContentsMargins(4, 2, 4, 2)
            short_path = os.path.basename(path)
            lay.addWidget(QLabel(f"'{cmd}'  →  {short_path}"))
            lay.addStretch()
            btn_del = QPushButton("Delete")
            btn_del.setProperty("class", "btnGhost")
            btn_del.setFixedSize(60, 22)
            btn_del.clicked.connect(lambda checked=False, k=cmd: self._delete_launcher_command(k))
            lay.addWidget(btn_del)
            item.setSizeHint(widget.sizeHint())
            self.list_launcher.addItem(item)
            self.list_launcher.setItemWidget(item, widget)

    def _add_launcher_command(self) -> None:
        cmd = self.txt_launch_cmd.text().strip().lower()
        path = self.txt_launch_path.text().strip()
        if not cmd or not path:
            return
        commands = dict(self.ctrl._cfg.get("app_launcher_commands", {}))
        commands[cmd] = path
        self.ctrl._cfg.set("app_launcher_commands", commands)
        self.ctrl._cfg.save()
        self.txt_launch_cmd.clear()
        self.txt_launch_path.clear()
        self._refresh_launcher_list()

    def _delete_launcher_command(self, cmd: str) -> None:
        commands = dict(self.ctrl._cfg.get("app_launcher_commands", {}))
        if cmd in commands:
            commands.pop(cmd)
            self.ctrl._cfg.set("app_launcher_commands", commands)
            self.ctrl._cfg.save()
            self._refresh_launcher_list()

    def _browse_app(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Application to Launch", "",
            "Executables & Scripts (*.exe *.lnk *.bat *.cmd);;All Files (*.*)"
        )
        if path:
            self.txt_launch_path.setText(os.path.normpath(path))

    def _import_settings(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Settings", "", "JSON Files (*.json)")
        if path:
            try:
                import json
                from ..utils.config import Config
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.ctrl._cfg._config = Config.from_dict(data)
                self.ctrl._cfg.save()
                self._load_config()
                QMessageBox.information(self, "Import Success", "Settings imported successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Import Failed", f"Failed to import settings: {e}")

    def _export_settings(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Settings", "", "JSON Files (*.json)")
        if path:
            try:
                import json
                cfg_dict = self.ctrl._cfg.config.to_dict()
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(cfg_dict, f, indent=2)
                QMessageBox.information(self, "Export Success", "Settings exported successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Failed to export settings: {e}")

    def _reset_defaults(self) -> None:
        confirm = QMessageBox.question(self, "Reset Settings", "Reset all settings to default values?")
        if confirm == QMessageBox.Yes:
            self.ctrl._cfg.reset()
            self._load_config()


class _MicTestDialog(QDialog):
    """Real-time microphone level meter dialog using PySide6 QProgressBar."""
    def __init__(self, parent: QWidget, device_index: Optional[int]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Test Microphone")
        self.setFixedSize(360, 200)
        self.device = device_index
        self.running = False
        self.stream = None
        self.peak_rms = 0.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        layout.addWidget(QLabel("MICROPHONE LEVEL METER"))
        self.lbl_dev = QLabel("Default Input Device")
        self.lbl_dev.setStyleSheet("color: gray;")
        layout.addWidget(self.lbl_dev)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #DEE2E6;
                border: none;
                border-radius: 6px;
                height: 20px;
            }}
            QProgressBar::chunk {{
                background-color: {_PRIMARY_COLOR};
                border-radius: 6px;
            }}
        """)
        layout.addWidget(self.bar)

        self.lbl_status = QLabel("Listening...")
        self.lbl_status.setStyleSheet("font-weight: bold; color: gray;")
        layout.addWidget(self.lbl_status)

        btn_close = QPushButton("Close")
        btn_close.setProperty("class", "btnGhost")
        btn_close.clicked.connect(self.close)
        btn_close.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout.addWidget(btn_close, 0, Qt.AlignRight)

        # Level updates timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_meter)
        
        # Queuing RMS values from callback thread
        import queue
        self.rms_queue = queue.Queue()

        self._start_stream()

    def _start_stream(self) -> None:
        import sounddevice as sd
        import numpy as np

        def callback(indata, frames, time_info, status):
            if not self.running:
                return
            rms = float(np.sqrt(np.mean(indata[:, 0] ** 2)))
            self.rms_queue.put(rms)

        try:
            self.stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype="float32",
                device=self.device,
                callback=callback,
                blocksize=1280
            )
            self.stream.start()
            self.running = True
            self.timer.start(50)
        except Exception as e:
            self.lbl_status.setText(f"Error opening mic: {e}")

    def _update_meter(self) -> None:
        rms = 0.0
        while not self.rms_queue.empty():
            try:
                rms = self.rms_queue.get_nowait()
            except Exception:
                break
        
        self.peak_rms = max(self.peak_rms, rms)
        # Log scale: map [0.0001, 0.1] to 0..100%
        import math
        if rms > 1e-9:
            log_val = (math.log10(max(rms, 0.0001)) + 4) / 4
            pct = max(0, min(100, int(log_val * 100)))
        else:
            pct = 0
            
        self.bar.setValue(pct)
        if rms > 0.015:
            self.lbl_status.setText("✓ Good signal — microphone is working correctly")
            self.lbl_status.setStyleSheet("color: green; font-weight: bold;")
        elif rms > 0.001:
            self.lbl_status.setText("Signal detected but quiet")
            self.lbl_status.setStyleSheet("color: orange; font-weight: bold;")
        else:
            self.lbl_status.setText("No signal — is mic muted?")
            self.lbl_status.setStyleSheet("color: red; font-weight: bold;")

    def closeEvent(self, event) -> None:
        self.running = False
        self.timer.stop()
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
        super().closeEvent(event)
