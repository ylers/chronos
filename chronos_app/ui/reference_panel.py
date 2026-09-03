"""参考面板: 展示 fix feature 字段含义与当前设置值(只读,随设置实时刷新)。"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QLabel,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from chronos_app.i18n import SUPPORTED_LANGUAGES, tr
from chronos_app.model import category_choices, state_choices
from chronos_app.ui.theme import DEFAULT_SETTINGS
from chronos_app.widgets.helpers import SectionHeader, make_table, set_headers


def _join_choices(choices: list[tuple[int, str]]) -> str:
    return "  ·  ".join(f"{value} {label}" for value, label in choices)


class ReferencePanel(QWidget):
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

        # 滚动区域,容纳三块说明
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setObjectName("ReferenceContent")
        box = QVBoxLayout(content)
        box.setContentsMargins(0, 0, 6, 0)
        box.setSpacing(12)

        # -- fix feature 字段 -------------------------------------------------
        fix_box = QGroupBox()
        fix_layout = QVBoxLayout(fix_box)
        self.encoding_label = QLabel()
        self.encoding_label.setObjectName("SectionSub")
        self.encoding_label.setWordWrap(True)
        fix_layout.addWidget(self.encoding_label)

        self.fix_table = make_table([tr("Field"), tr("Bits"), tr("Values"), tr("Meaning")])
        self.fix_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.fix_table.setColumnWidth(0, 120)
        self.fix_table.setColumnWidth(1, 60)
        self.fix_table.setColumnWidth(2, 320)
        self.fix_table.verticalHeader().setDefaultSectionSize(30)
        fix_layout.addWidget(self.fix_table)

        self.scope_label = QLabel()
        self.scope_label.setObjectName("SectionSub")
        self.scope_label.setWordWrap(True)
        fix_layout.addWidget(self.scope_label)

        self.reserved_label = QLabel()
        self.reserved_label.setObjectName("SectionSub")
        fix_layout.addWidget(self.reserved_label)
        self._fix_box = fix_box
        box.addWidget(fix_box)

        # -- 当前设置 ----------------------------------------------------------
        settings_box = QGroupBox()
        settings_layout = QVBoxLayout(settings_box)
        self.settings_table = make_table(
            [tr("Setting"), tr("Current value"), tr("Meaning")]
        )
        self.settings_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.settings_table.setColumnWidth(0, 140)
        self.settings_table.setColumnWidth(1, 150)
        self.settings_table.verticalHeader().setDefaultSectionSize(28)
        settings_layout.addWidget(self.settings_table)
        self._settings_box = settings_box
        box.addWidget(settings_box)

        # -- 条目与快加 --------------------------------------------------------
        item_box = QGroupBox()
        item_layout = QVBoxLayout(item_box)
        self.item_label = QLabel()
        self.item_label.setWordWrap(True)
        item_layout.addWidget(self.item_label)
        self.quick_label = QLabel()
        self.quick_label.setObjectName("SectionSub")
        self.quick_label.setWordWrap(True)
        item_layout.addWidget(self.quick_label)
        self._item_box = item_box
        box.addWidget(item_box)

        box.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

    # -- 语言 / 数据 ---------------------------------------------------------

    def retranslate(self) -> None:
        self.header.set_title(tr("Reference"))
        self.header.set_subtitle(tr("Settings and field meanings"))
        self._fix_box.setTitle(tr("Fix Feature Fields"))
        self.encoding_label.setText(
            tr("Encoding: state<<14 | importance<<11 | priority<<8 | category")
        )
        self.scope_label.setText(
            tr("Scopes: long/short → Planner · instant/idea → Quick · experiment → Experiments")
        )
        self.reserved_label.setText(tr("Reserved: bits 16-31 for future fields"))
        self._settings_box.setTitle(tr("Current Settings"))
        self._item_box.setTitle(tr("Item & Quick-add"))
        self.item_label.setText(
            tr("Item structure: id · name · description · fix feature · extendable params")
        )
        self.quick_label.setText(
            tr("Quick-add syntax: name !priority #category *importance")
        )
        set_headers(
            self.fix_table, [tr("Field"), tr("Bits"), tr("Values"), tr("Meaning")]
        )
        set_headers(
            self.settings_table,
            [tr("Setting"), tr("Current value"), tr("Meaning")],
        )
        self.refresh()

    def refresh(self) -> None:
        s = self.main.settings

        # fix feature 字段表
        rows = [
            (
                tr("Category"),
                "8",
                _join_choices(category_choices()),
                tr("Category of the item"),
            ),
            (
                tr("Priority"),
                "3",
                "0-7",
                tr("Task priority, 0-7 (higher is more urgent)"),
            ),
            (
                tr("Importance"),
                "3",
                "0-7",
                tr("How important it is, 0-7 (higher is more important)"),
            ),
            (
                tr("State"),
                "2",
                _join_choices(state_choices()),
                tr("Current workflow state"),
            ),
        ]
        self.fix_table.setRowCount(len(rows))
        for row, (field, bits, values, meaning) in enumerate(rows):
            for col, text in enumerate((field, bits, values, meaning)):
                self.fix_table.setItem(row, col, QTableWidgetItem(text))

        # 当前设置表
        language = str(s.get("language") or DEFAULT_SETTINGS["language"])
        bg = str(s.get("bg_color") or DEFAULT_SETTINGS["bg_color"])
        accent = str(s.get("accent_color") or DEFAULT_SETTINGS["accent_color"])
        dark = bool(s.get("dark", True))
        font_size = int(s.get("font_size") or DEFAULT_SETTINGS["font_size"])
        setting_rows = [
            (tr("Language"), SUPPORTED_LANGUAGES.get(language, language), tr("Interface language")),
            (tr("Background color"), bg, tr("Main background color"), bg),
            (tr("Accent color"), accent, tr("Accent color for selection & highlights"), accent),
            (tr("Dark theme"), tr("Yes") if dark else tr("No"), tr("Dark theme switch")),
            (tr("Font size"), str(font_size), tr("Base font size (px)")),
        ]
        self.settings_table.setRowCount(len(setting_rows))
        for row, parts in enumerate(setting_rows):
            setting, value, meaning = parts[0], parts[1], parts[2]
            self.settings_table.setItem(row, 0, QTableWidgetItem(setting))
            value_item = QTableWidgetItem(value)
            if len(parts) > 3:  # 颜色行: 值格子着当前色
                value_item.setBackground(QColor(parts[3]))
            self.settings_table.setItem(row, 1, value_item)
            self.settings_table.setItem(row, 2, QTableWidgetItem(meaning))
