"""全部条目面板: 一处展示与管理所有类别条目(语言感知)。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from chronos_app.i18n import tr
from chronos_app.model import Category, FixFeature, State, category_choices, state_choices
from chronos_app.widgets.helpers import (
    ItemDialog,
    SectionHeader,
    add_collapse_action,
    add_parent_menu,
    clear_table,
    confirm,
    make_table,
    hierarchy_rows,
    set_score_cell,
    set_cell,
    set_headers,
    set_hierarchy_name,
    small_button,
)

# 排序选项: (data, 查询 order 子句)
_SORTS = [
    ("updated", "updated_at DESC, id DESC"),
    ("created", "created_at DESC, id DESC"),
    ("priority", "priority DESC, updated_at DESC, id DESC"),
    ("importance", "importance DESC, updated_at DESC, id DESC"),
]


class AllItemsPanel(QWidget):
    def __init__(self, db, main: QWidget) -> None:
        super().__init__()
        self.db = db
        self.main = main
        self._build_ui()
        self.retranslate()
        self.refresh()

    # -- UI ----------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 10)
        root.setSpacing(8)
        self.header = SectionHeader()
        root.addWidget(self.header)

        # 过滤行
        filter_row = QHBoxLayout()
        self.keyword = QLineEdit()
        self.keyword.setPlaceholderText("")
        self.keyword.setFixedWidth(220)
        self.keyword.textChanged.connect(self.refresh)

        self.state_label = QLabel()
        self.state_combo = QComboBox()
        self.state_combo.currentIndexChanged.connect(self.refresh)

        self.category_label = QLabel()
        self.category_combo = QComboBox()
        self.category_combo.currentIndexChanged.connect(self.refresh)

        self.sort_label = QLabel()
        self.sort_combo = QComboBox()
        self.sort_combo.currentIndexChanged.connect(self.refresh)

        filter_row.addWidget(self.keyword)
        filter_row.addWidget(self.state_label)
        filter_row.addWidget(self.state_combo)
        filter_row.addWidget(self.category_label)
        filter_row.addWidget(self.category_combo)
        filter_row.addWidget(self.sort_label)
        filter_row.addWidget(self.sort_combo)
        filter_row.addStretch(1)
        root.addLayout(filter_row)

        # 表格
        self.table = make_table([""] * 8)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.cellDoubleClicked.connect(self._edit_item)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_item_menu)
        root.addWidget(self.table, 1)

        # 底部按钮
        bottom = QHBoxLayout()
        self.count_label = QLabel("")
        self.count_label.setObjectName("SectionSub")
        self.btn_add = small_button("", "Primary")
        self.btn_add.clicked.connect(self._add_item)
        self.btn_edit = small_button("")
        self.btn_edit.clicked.connect(self._edit_item)
        self.btn_done = small_button("")
        self.btn_done.clicked.connect(self._toggle_done)
        self.btn_del = small_button("", "Danger")
        self.btn_del.clicked.connect(self._delete_item)
        bottom.addWidget(self.count_label)
        bottom.addStretch(1)
        bottom.addWidget(self.btn_add)
        bottom.addWidget(self.btn_edit)
        bottom.addWidget(self.btn_done)
        bottom.addWidget(self.btn_del)
        root.addLayout(bottom)

    def retranslate(self) -> None:
        self.header.set_title(tr("All Items"))
        self.header.set_subtitle(tr("Browse and manage every item in one place"))
        self.keyword.setPlaceholderText(tr("Search…"))
        self.state_label.setText(tr("State"))
        self.category_label.setText(tr("Category"))
        self.sort_label.setText(tr("Sort"))
        self.btn_add.setText(tr("+ Add Item"))
        self.btn_edit.setText(tr("Edit"))
        self.btn_done.setText(tr("Toggle Done"))
        self.btn_del.setText(tr("Delete Item"))
        set_headers(self.table, [
            tr("Name"), tr("Category"), tr("Priority"),
            tr("Importance"), tr("State"), tr("Created"), tr("Updated"), tr("Completed"),
        ])
        self._rebuild_filters()

    def _rebuild_filters(self) -> None:
        # 状态
        self.state_combo.blockSignals(True)
        cur_state = self.state_combo.currentData()
        self.state_combo.clear()
        self.state_combo.addItem(tr("All states"), None)
        for value, label in state_choices():
            self.state_combo.addItem(label, value)
        idx = self.state_combo.findData(cur_state)
        self.state_combo.setCurrentIndex(max(0, idx))
        self.state_combo.blockSignals(False)

        # 类别
        self.category_combo.blockSignals(True)
        cur_cat = self.category_combo.currentData()
        self.category_combo.clear()
        self.category_combo.addItem(tr("All categories"), None)
        for value, label in category_choices():
            self.category_combo.addItem(label, value)
        idx = self.category_combo.findData(cur_cat)
        self.category_combo.setCurrentIndex(max(0, idx))
        self.category_combo.blockSignals(False)

        # 排序
        self.sort_combo.blockSignals(True)
        cur_sort = self.sort_combo.currentData()
        self.sort_combo.clear()
        for data, _ in _SORTS:
            self.sort_combo.addItem(self._sort_label(data), data)
        idx = self.sort_combo.findData(cur_sort)
        self.sort_combo.setCurrentIndex(max(0, idx))
        self.sort_combo.blockSignals(False)

    @staticmethod
    def _sort_label(data: str) -> str:
        return {
            "updated": tr("By updated"),
            "created": tr("By created"),
            "priority": tr("By priority"),
            "importance": tr("By importance"),
        }[data]

    # -- 数据 ----------------------------------------------------------------

    def refresh(self) -> None:
        self._rebuild_filters()

        category = self.category_combo.currentData()
        state = self.state_combo.currentData()
        keyword = self.keyword.text().strip()
        order = dict(_SORTS)[self.sort_combo.currentData()]

        items = self.db.query(
            category=category, state=state, keyword=keyword, order=order,
        )

        self._visible_items = items
        rows = hierarchy_rows(items, self.main.collapsed_item_ids)
        clear_table(self.table)
        self.table.setRowCount(len(rows))
        for row, (item, depth) in enumerate(rows):
            set_hierarchy_name(
                self.table, row, 0, item, depth,
                has_children=bool(self.db.children(item.id)),
                collapsed=item.id in self.main.collapsed_item_ids,
                on_toggle=lambda _checked=False, item_id=item.id: self.main.toggle_item_collapsed(item_id),
            )
            set_cell(self.table, row, 1, item.fix.category_label, Qt.AlignmentFlag.AlignCenter)
            set_score_cell(
                self.table, row, 2, item.fix.priority,
                lambda value, item_id=item.id: self._set_score(item_id, "priority", value),
            )
            set_score_cell(
                self.table, row, 3, item.fix.importance,
                lambda value, item_id=item.id: self._set_score(item_id, "importance", value),
            )
            set_cell(self.table, row, 4, item.fix.state_label, Qt.AlignmentFlag.AlignCenter)
            set_cell(self.table, row, 5, (item.created_at or "")[:10], Qt.AlignmentFlag.AlignCenter)
            set_cell(self.table, row, 6, (item.updated_at or "")[:10], Qt.AlignmentFlag.AlignCenter)
            set_cell(self.table, row, 7, (item.completed_at or "")[:16], Qt.AlignmentFlag.AlignCenter)
            if item.is_done:
                for c in range(self.table.columnCount()):
                    cell = self.table.item(row, c)
                    if cell is not None:
                        font = cell.font()
                        font.setStrikeOut(True)
                        cell.setFont(font)

        self.count_label.setText(tr("{total} items", total=len(items)))
        self.table.resizeRowsToContents()

    def _set_score(self, item_id: int, field: str, value: int) -> None:
        item = self.db.get_item(item_id)
        if item is not None and getattr(item.fix, field) != value:
            self.db.update_item(item_id, fix=item.fix.with_(**{field: value}))

    # -- 操作 ----------------------------------------------------------------

    def _selected_item_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _add_item(self) -> None:
        dlg = ItemDialog(self, tr("Add Item"), fix=FixFeature(category=Category.SHORT_TERM))
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        if not v["name"]:
            return
        self.db.create_item(v["name"], v["description"], fix=v["fix"])
        self.refresh()
        self.main.notify_items_changed()

    def _edit_item(self, _row: int | None = None) -> None:
        item_id = self._selected_item_id()
        if item_id is None:
            return
        item = self.db.get_item(item_id)
        if item is None:
            return
        dlg = ItemDialog(
            self, tr("Edit Item"),
            item_name=item.name, description=item.description, fix=item.fix,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        if v["name"]:
            self.db.update_item(item_id, name=v["name"], description=v["description"], fix=v["fix"])
            self.refresh()
            self.main.notify_items_changed()

    def _toggle_done(self) -> None:
        item_id = self._selected_item_id()
        if item_id is None:
            return
        item = self.db.get_item(item_id)
        if item is None:
            return
        new_state = State.NOT_STARTED if item.is_done else State.DONE
        self.db.set_state(item_id, new_state)
        self.refresh()
        self.main.notify_items_changed()

    def _delete_item(self) -> None:
        item_id = self._selected_item_id()
        if item_id is None:
            return
        item = self.db.get_item(item_id)
        if item is None:
            return
        if not confirm(self, tr("Delete Item"), tr("Delete \"{name}\"?", name=item.name)):
            return
        self.db.delete_item(item_id)
        self.refresh()
        self.main.notify_items_changed()

    def _duplicate_item(self) -> None:
        item_id = self._selected_item_id()
        item = self.db.get_item(item_id) if item_id is not None else None
        if item is None:
            return
        copy = self.db.duplicate_item(item.id, name=tr("{name} (Copy)", name=item.name))
        self.refresh()
        if copy is not None:
            for row in range(self.table.rowCount()):
                if self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == copy.id:
                    self.table.setCurrentCell(row, 0)
                    break
        self.main.notify_items_changed()

    def _show_item_menu(self, pos) -> None:
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        self.table.selectRow(index.row())
        menu = QMenu(self)
        copy_action = menu.addAction(tr("Copy"))
        copy_action.triggered.connect(self._duplicate_item)
        child_action = menu.addAction(tr("New Child Item"))
        child_action.triggered.connect(self._new_child_item)
        add_collapse_action(
            menu, self.db, self._selected_item_id(), self.main.collapsed_item_ids,
            lambda: (self.main._schedule_ui_state_save(), self.main.notify_items_changed()),
        )
        add_parent_menu(
            menu, self.db, self._selected_item_id(), self._visible_items,
            lambda: (self.refresh(), self.main.notify_items_changed()),
        )
        menu.addSeparator()
        delete_action = menu.addAction(tr("Delete Item"))
        delete_action.triggered.connect(self._delete_item)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _new_child_item(self) -> None:
        parent_id = self._selected_item_id()
        parent = self.db.get_item(parent_id) if parent_id is not None else None
        if parent is None:
            return
        dlg = ItemDialog(
            self, tr("New Child Item"), fix=parent.fix.with_(state=State.NOT_STARTED),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        values = dlg.values()
        if not values["name"]:
            return
        child = self.db.create_item(
            values["name"], values["description"], fix=values["fix"], parent_id=parent.id,
        )
        # 同 scope 的表单归属跟随父项，父子关系本身仍独立存在。
        for form in self.db.item_forms(parent.id):
            self.db.add_to_form(form.id, child.id)
        self.refresh()
        self.main.notify_items_changed()
