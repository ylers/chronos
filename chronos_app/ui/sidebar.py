"""VSCode 式左侧图标栏(语言感知)。"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from chronos_app.i18n import tr

SECTIONS = [
    ("Planner", "🗒"),
    ("Quick Action", "⚡"),
    ("Experiments", "🧪"),
    ("Reference", "📖"),
    ("All Items", "🗂"),
    ("Settings", "⚙"),
]


class Sidebar(QWidget):
    """窄条图标栏: 点击切换 section,索引与 QStackedWidget 对应。"""

    section_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(60)

        brand = QLabel("ch")
        brand.setObjectName("Brand")

        self.list = QListWidget()
        self.list.setObjectName("Sidebar")
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._items: list[QListWidgetItem] = []
        for _label, icon in SECTIONS:
            item = QListWidgetItem(icon)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setSizeHint(QSize(self.width(), 52))
            self.list.addItem(item)
            self._items.append(item)
        self.list.setCurrentRow(0)
        self.list.currentRowChanged.connect(self.section_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(brand)
        layout.addWidget(self.list, 1)

        self.retranslate()

    def retranslate(self) -> None:
        for item, (key, _icon) in zip(self._items, SECTIONS):
            item.setToolTip(tr(key))

    def current_index(self) -> int:
        return self.list.currentRow()

    def set_current_index(self, index: int) -> None:
        self.list.setCurrentRow(index)
