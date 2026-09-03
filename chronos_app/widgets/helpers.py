"""跨面板复用的控件与对话框(语言感知)。"""

from __future__ import annotations

from typing import Any, Callable, Iterable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from chronos_app.i18n import tr
from chronos_app.model import FixFeature, State, category_choices, state_choices, state_label
from chronos_app.model import Item


# -- 颜色 ---------------------------------------------------------------

def color_to_hex(color: QColor) -> str:
    return color.name()


# -- 标题头 ---------------------------------------------------------------

class SectionHeader(QWidget):
    """面板标题 + 副标题,支持运行时改文案(retranslate)。"""

    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = QLabel(title)
        self._title.setObjectName("SectionTitle")
        self._subtitle = QLabel(subtitle)
        self._subtitle.setObjectName("SectionSub")
        self._subtitle.setVisible(bool(subtitle))
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 8)
        box.setSpacing(2)
        box.addWidget(self._title)
        box.addWidget(self._subtitle)

    def set_title(self, text: str) -> None:
        self._title.setText(text)

    def set_subtitle(self, text: str) -> None:
        self._subtitle.setText(text)
        self._subtitle.setVisible(bool(text))

    def title_text(self) -> str:
        return self._title.text()

    def subtitle_text(self) -> str:
        return self._subtitle.text()


# -- 表格工具 ---------------------------------------------------------------

def make_table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setMinimumSectionSize(34)
    table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    table.setWordWrap(True)
    table.setTextElideMode(Qt.TextElideMode.ElideNone)
    table.setShowGrid(False)
    return table


def set_headers(table: QTableWidget, headers: list[str]) -> None:
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)


def clear_table(table: QTableWidget) -> None:
    table.setRowCount(0)


def set_cell(table: QTableWidget, row: int, col: int, text: str,
             align: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft) -> None:
    item = QTableWidgetItem(text)
    item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
    table.setItem(row, col, item)


def hierarchy_rows(
    items: Iterable[Item], collapsed_ids: set[int] | None = None
) -> list[tuple[Item, int]]:
    """将当前可见 Item 排成父项在前的深度优先列表，并返回缩进深度。"""
    ordered = list(items)
    by_id = {item.id: item for item in ordered}
    children: dict[int, list[Item]] = {}
    roots: list[Item] = []
    for item in ordered:
        if item.parent_id in by_id and item.parent_id != item.id:
            children.setdefault(item.parent_id, []).append(item)
        else:
            roots.append(item)

    result: list[tuple[Item, int]] = []
    visited: set[int] = set()
    collapsed_ids = collapsed_ids or set()

    def visit(item: Item, depth: int) -> None:
        if item.id in visited:
            return
        visited.add(item.id)
        result.append((item, depth))
        if item.id in collapsed_ids:
            stack = list(children.get(item.id, []))
            while stack:
                hidden = stack.pop()
                if hidden.id in visited:
                    continue
                visited.add(hidden.id)
                stack.extend(children.get(hidden.id, []))
            return
        for child in children.get(item.id, []):
            visit(child, depth + 1)

    for root in roots:
        visit(root, 0)
    # 防御旧库中的异常循环：仍展示，不让条目消失。
    for item in ordered:
        visit(item, 0)
    return result


def set_hierarchy_name(
    table: QTableWidget,
    row: int,
    col: int,
    item: Item,
    depth: int,
    *,
    has_children: bool = False,
    collapsed: bool = False,
    on_toggle: Callable[[], None] | None = None,
) -> None:
    # 单元格本体只承载 ID/深度；可见名称由 cell widget 绘制，避免双重文字。
    set_cell(table, row, col, "")
    cell = table.item(row, col)
    cell.setData(Qt.ItemDataRole.UserRole, item.id)
    cell.setData(Qt.ItemDataRole.UserRole + 1, depth)

    container = QWidget(table)
    layout = QHBoxLayout(container)
    layout.setContentsMargins(6 + depth * 18, 1, 4, 1)
    layout.setSpacing(5)

    if has_children:
        toggle = QToolButton(container)
        toggle.setObjectName("TreeToggle")
        toggle.setText("▸" if collapsed else "▾")
        toggle.setFixedSize(22, 22)
        toggle.setToolTip(tr("Expand Children") if collapsed else tr("Collapse Children"))
        if on_toggle is not None:
            toggle.clicked.connect(on_toggle)
        layout.addWidget(toggle, 0, Qt.AlignmentFlag.AlignVCenter)
    else:
        spacer = QWidget(container)
        spacer.setFixedWidth(22)
        layout.addWidget(spacer)

    label = QLabel(item.name, container)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    if item.is_done:
        font = label.font()
        font.setStrikeOut(True)
        label.setFont(font)
    layout.addWidget(label, 1)
    container.name_label = label
    table.setCellWidget(row, col, container)


def add_collapse_action(
    menu: QMenu,
    db: Any,
    item_id: int,
    collapsed_ids: set[int],
    on_changed: Callable[[], None],
) -> None:
    if not db.children(item_id):
        return
    collapsed = item_id in collapsed_ids
    action = menu.addAction(tr("Expand Children") if collapsed else tr("Collapse Children"))

    def toggle() -> None:
        if collapsed:
            collapsed_ids.discard(item_id)
        else:
            collapsed_ids.add(item_id)
        on_changed()

    action.triggered.connect(toggle)


def add_parent_menu(
    menu: QMenu,
    db: Any,
    item_id: int,
    candidates: Iterable[Item],
    on_changed: Callable[[], None],
) -> None:
    """向右键菜单加入设置/移除父项操作。"""
    item = db.get_item(item_id)
    if item is None:
        return

    parent_menu = menu.addMenu(tr("Set Parent Item"))
    available = []
    for candidate in candidates:
        if candidate.id == item_id:
            continue
        cursor = candidate
        invalid = False
        seen: set[int] = set()
        while cursor is not None and cursor.id not in seen:
            if cursor.id == item_id:
                invalid = True
                break
            seen.add(cursor.id)
            cursor = db.get_item(cursor.parent_id) if cursor.parent_id is not None else None
        if not invalid:
            available.append(candidate)
    for candidate in available:
        action = parent_menu.addAction(candidate.name)
        action.triggered.connect(
            lambda _checked=False, parent_id=candidate.id: (
                on_changed() if db.set_parent(item_id, parent_id) else None
            )
        )
    if not available:
        action = parent_menu.addAction(tr("No available parent items"))
        action.setEnabled(False)
        parent_menu.setEnabled(False)

    if item.parent_id is not None:
        remove_action = menu.addAction(tr("Remove Parent Item"))
        remove_action.triggered.connect(
            lambda: on_changed() if db.set_parent(item_id, None) else None
        )


# -- 状态徽章 ---------------------------------------------------------------

def state_badge(state: int) -> QLabel:
    badge = QLabel(f" {state_label(state)} ")
    badge.setObjectName("StateBadge")
    colors = {
        State.NOT_STARTED: "#6e7681",
        State.PLANNED: "#0ea5e9",
        State.BLOCKED: "#f97316",
        State.DONE: "#4caf50",
    }
    base = colors.get(state, "#6e7681")
    badge.setStyleSheet(f"background-color: {base}; color: #ffffff;")
    return badge


# -- 常用控件 ---------------------------------------------------------------

def category_combo() -> QComboBox:
    combo = QComboBox()
    for value, label in category_choices():
        combo.addItem(label, value)
    return combo


def state_combo() -> QComboBox:
    combo = QComboBox()
    for value, label in state_choices():
        combo.addItem(label, value)
    return combo


class ScoreSlider(QWidget):
    """0-7 横向滑条 + 数字框；拖动、滚轮、键盘均可调整。"""

    def __init__(self, value: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 7)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(1)
        self.slider.setTickInterval(1)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.setMinimumWidth(230)
        self.slider.setToolTip(tr("Drag or use mouse wheel (0-7)"))

        self.spin = QSpinBox()
        self.spin.setRange(0, 7)
        self.spin.setFixedWidth(58)
        self.spin.setToolTip(tr("Drag or use mouse wheel (0-7)"))

        self.slider.valueChanged.connect(self.spin.setValue)
        self.spin.valueChanged.connect(self.slider.setValue)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(QLabel("0"))
        layout.addWidget(self.slider, 1)
        layout.addWidget(QLabel("7"))
        layout.addWidget(self.spin)
        self.setValue(value)

    def value(self) -> int:
        return self.slider.value()

    def setValue(self, value: int) -> None:
        self.slider.setValue(max(0, min(7, int(value))))


class InlineScoreSlider(QWidget):
    """表格单元格中的紧凑评分滑条，改变时立即调用保存回调。"""

    def __init__(
        self,
        value: int,
        on_change: Callable[[int], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 7)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(1)
        self.slider.setMinimumWidth(72)
        self.slider.setToolTip(tr("Drag or use mouse wheel (0-7)"))
        self.number = QLabel(str(value))
        self.number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number.setFixedWidth(16)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(4)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.number)

        self.slider.setValue(max(0, min(7, int(value))))
        self.slider.valueChanged.connect(self.number.setNum)
        self.slider.valueChanged.connect(on_change)

    def value(self) -> int:
        return self.slider.value()


def set_score_cell(
    table: QTableWidget,
    row: int,
    col: int,
    value: int,
    on_change: Callable[[int], None],
) -> InlineScoreSlider:
    score = InlineScoreSlider(value, on_change, table)
    table.setCellWidget(row, col, score)
    return score


def small_button(text: str, object_name: str = "") -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName(object_name)
    return btn


def rebuild_combo(combo: QComboBox, items: list[tuple[Any, str]], current_data: Any = None) -> Any:
    """按 (data, label) 重建 combo,尽量恢复选中项;返回恢复的 data。"""
    if current_data is None and combo.count() > 0:
        current_data = combo.currentData()
    combo.blockSignals(True)
    combo.clear()
    for data, label in items:
        combo.addItem(label, data)
    idx = combo.findData(current_data)
    if idx < 0:
        idx = 0
    combo.setCurrentIndex(idx)
    combo.blockSignals(False)
    return combo.currentData()


# -- 条目编辑对话框 ---------------------------------------------------------------

class ItemDialog(QDialog):
    """新建/编辑条目的通用对话框(按当前语言构造文案)。"""

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        *,
        item_name: str = "",
        description: str = "",
        fix: FixFeature | None = None,
        readonly_category: bool = False,
        categories: Iterable[int] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(540)
        fix = fix or FixFeature()

        name_edit = QLineEdit(item_name)
        name_edit.setPlaceholderText(tr("Item name *"))

        desc_edit = QPlainTextEdit(description)
        desc_edit.setPlaceholderText(tr("Description (optional)"))
        desc_edit.setFixedHeight(70)

        if categories is not None:
            allowed = set(categories)
            self.category = category_combo()
            self.category.blockSignals(True)
            for i in range(self.category.count() - 1, -1, -1):
                if self.category.itemData(i) not in allowed:
                    self.category.removeItem(i)
            self.category.blockSignals(False)
        else:
            self.category = category_combo()
        self.category.setCurrentIndex(max(0, self.category.findData(fix.category)))
        self.category.setEnabled(not readonly_category)

        self.priority = ScoreSlider(fix.priority)

        self.importance = ScoreSlider(fix.importance)

        self.state = state_combo()
        self.state.setCurrentIndex(max(0, self.state.findData(fix.state)))

        form = QFormLayout()
        form.addRow(tr("Name"), name_edit)
        form.addRow(tr("Description"), desc_edit)
        form.addRow(tr("Category"), self.category)
        form.addRow(tr("Priority"), self.priority)
        form.addRow(tr("Importance"), self.importance)
        form.addRow(tr("State"), self.state)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("OK"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        self._name = name_edit
        self._desc = desc_edit

    def values(self) -> dict[str, Any]:
        return {
            "name": self._name.text().strip(),
            "description": self._desc.toPlainText().strip(),
            "fix": FixFeature(
                category=int(self.category.currentData()),
                priority=self.priority.value(),
                importance=self.importance.value(),
                state=int(self.state.currentData()),
            ),
        }


# -- 对话框助手 ---------------------------------------------------------------

def prompt_text(parent: QWidget, title: str, label: str, default: str = "") -> tuple[str, bool]:
    """可翻译按钮的单行输入对话框。返回 (文本, 是否确认)。"""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumWidth(360)
    edit = QLineEdit(default)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("OK"))
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr("Cancel"))

    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel(label))
    layout.addWidget(edit)
    layout.addWidget(buttons)

    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    edit.returnPressed.connect(dlg.accept)

    ok = dlg.exec() == QDialog.DialogCode.Accepted
    return edit.text().strip(), ok


def confirm(parent: QWidget, title: str, text: str) -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Warning)
    yes = box.addButton(tr("Delete"), QMessageBox.ButtonRole.DestructiveRole)
    box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
    box.exec()
    return box.clickedButton() is yes
