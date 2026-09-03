"""设置面板: 语言 / 背景色 / 强调色 / 明暗 / 字号,实时生效。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from chronos_app.i18n import SUPPORTED_LANGUAGES, tr
from chronos_app.ui.theme import DEFAULT_SETTINGS
from chronos_app.widgets.helpers import SectionHeader


class SettingsPanel(QWidget):
    def __init__(self, db, main: QWidget) -> None:
        super().__init__()
        self.db = db
        self.main = main
        self._build_ui()
        self.retranslate()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 10)
        root.setSpacing(12)
        self.header = SectionHeader()
        root.addWidget(self.header)

        # -- 外观 ------------------------------------------------------------
        appearance = QGroupBox()
        form = QVBoxLayout(appearance)
        form.setSpacing(8)

        lang_row = QHBoxLayout()
        self.lang_label = QLabel()
        self.lang_combo = QComboBox()
        for code, name in SUPPORTED_LANGUAGES.items():
            self.lang_combo.addItem(name, code)
        self.lang_combo.currentIndexChanged.connect(self._apply_language)
        lang_row.addWidget(self.lang_label)
        lang_row.addStretch(1)
        lang_row.addWidget(self.lang_combo)
        form.addLayout(lang_row)

        bg_row = QHBoxLayout()
        self.bg_label = QLabel()
        bg_row.addWidget(self.bg_label)
        bg_row.addStretch(1)
        self.bg_btn = QPushButton()
        self.bg_btn.setFixedSize(110, 28)
        self.bg_btn.clicked.connect(self._pick_color)
        bg_row.addWidget(self.bg_btn)
        form.addLayout(bg_row)

        accent_row = QHBoxLayout()
        self.accent_label = QLabel()
        accent_row.addWidget(self.accent_label)
        accent_row.addStretch(1)
        self.accent_btn = QPushButton()
        self.accent_btn.setFixedSize(110, 28)
        self.accent_btn.clicked.connect(self._pick_accent)
        accent_row.addWidget(self.accent_btn)
        form.addLayout(accent_row)

        dark_row = QHBoxLayout()
        self.dark_check = QCheckBox()
        self.dark_check.toggled.connect(self._apply_dark)
        dark_row.addWidget(self.dark_check)
        dark_row.addStretch(1)
        form.addLayout(dark_row)

        font_row = QHBoxLayout()
        self.font_label = QLabel()
        font_row.addWidget(self.font_label)
        font_row.addStretch(1)
        self.font_spin = QSpinBox()
        self.font_spin.setRange(10, 22)
        self.font_spin.valueChanged.connect(self._apply_font)
        font_row.addWidget(self.font_spin)
        form.addLayout(font_row)

        self._appearance_box = appearance
        root.addWidget(appearance)

        # -- 数据 ------------------------------------------------------------
        data_box = QGroupBox()
        data_layout = QVBoxLayout(data_box)
        self.path_label = QLabel()
        self.path_label.setWordWrap(True)
        self.path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        data_layout.addWidget(self.path_label)
        self._data_box = data_box
        root.addWidget(data_box)

        root.addStretch(1)

        self.hint = QLabel()
        self.hint.setObjectName("SectionSub")
        root.addWidget(self.hint)

    def retranslate(self) -> None:
        self.header.set_title(tr("Settings"))
        self.header.set_subtitle(tr("Appearance and data, changes apply instantly"))
        self._appearance_box.setTitle(tr("Appearance"))
        self.lang_label.setText(tr("Language"))
        self.bg_label.setText(tr("Background color"))
        self.accent_label.setText(tr("Accent color"))
        self.dark_check.setText(tr("Dark theme"))
        self.font_label.setText(tr("Font size"))
        self._data_box.setTitle(tr("Data"))
        self.hint.setText(
            tr("Settings are stored in the local SQLite settings table; changes apply immediately.")
        )

    # -- 数据 ----------------------------------------------------------------

    def refresh(self) -> None:
        s = self.main.settings
        bg = str(s.get("bg_color") or DEFAULT_SETTINGS["bg_color"])
        accent = str(s.get("accent_color") or DEFAULT_SETTINGS["accent_color"])
        dark = bool(s.get("dark", True))
        font_size = int(s.get("font_size") or DEFAULT_SETTINGS["font_size"])
        language = str(s.get("language") or "zh")

        self.bg_btn.setStyleSheet(
            f"background-color: {bg}; border: 1px solid {bg}; border-radius: 4px;"
        )
        self.bg_btn.setToolTip(tr("bg color {color}", color=bg))
        self.accent_btn.setStyleSheet(
            f"background-color: {accent}; border: 1px solid {accent}; border-radius: 4px;"
        )
        self.accent_btn.setToolTip(tr("accent color {color}", color=accent))

        self.dark_check.blockSignals(True)
        self.dark_check.setChecked(dark)
        self.dark_check.blockSignals(False)

        self.font_spin.blockSignals(True)
        self.font_spin.setValue(font_size)
        self.font_spin.blockSignals(False)

        self.lang_combo.blockSignals(True)
        idx = self.lang_combo.findData(language)
        self.lang_combo.setCurrentIndex(max(0, idx))
        self.lang_combo.blockSignals(False)

        self.path_label.setText(tr("Data file: {path}", path=Path(self.db.path).resolve()))

    # -- 操作 ----------------------------------------------------------------

    def _apply_language(self, _index: int) -> None:
        lang = self.lang_combo.currentData()
        self.db.set_setting("language", lang)
        self.main.reapply_language()

    def _pick_color(self) -> None:
        current = str(self.main.settings.get("bg_color") or DEFAULT_SETTINGS["bg_color"])
        color = QColorDialog.getColor(QColor(current), self, tr("Pick background color"))
        if color.isValid():
            self.db.set_setting("bg_color", color.name())
            self.main.reapply_theme()

    def _pick_accent(self) -> None:
        current = str(self.main.settings.get("accent_color") or DEFAULT_SETTINGS["accent_color"])
        color = QColorDialog.getColor(QColor(current), self, tr("Pick accent color"))
        if color.isValid():
            self.db.set_setting("accent_color", color.name())
            self.main.reapply_theme()

    def _apply_dark(self, checked: bool) -> None:
        self.db.set_setting("dark", bool(checked))
        self.main.reapply_theme()

    def _apply_font(self, size: int) -> None:
        self.db.set_setting("font_size", size)
        self.main.reapply_theme()
