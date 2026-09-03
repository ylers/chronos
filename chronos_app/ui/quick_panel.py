"""及时行动面板: 极简快加 + 即时/短期任务清单(语言感知)。"""

from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from chronos_app.i18n import tr
from chronos_app.model import (
    QUICK_CATEGORIES,
    Category,
    FixFeature,
    Scope,
    State,
    category_choices,
    category_label,
    scope_of_category,
)
from chronos_app.widgets.helpers import (
    ItemDialog,
    SectionHeader,
    add_collapse_action,
    add_parent_menu,
    clear_table,
    confirm,
    make_table,
    hierarchy_rows,
    prompt_text,
    set_score_cell,
    set_cell,
    set_headers,
    set_hierarchy_name,
    small_button,
)

_DEFAULT_PRIORITY = 3
_DEFAULT_IMPORTANCE = 3


def parse_quick_add(text: str) -> tuple[str, FixFeature]:
    """解析快加 DSL: `!N` 优先级、`#N` 类别、`*N` 重要度,其余为名称。"""
    name = text.strip()
    priority = _DEFAULT_PRIORITY
    importance = _DEFAULT_IMPORTANCE
    category = Category.INSTANT

    def take(pattern: str, default: int, clamp: int) -> int:
        nonlocal name
        m = re.search(pattern, name)
        if not m:
            return default
        name = name.replace(m.group(0), "", 1)
        return min(int(m.group(1)), clamp)

    priority = take(r"!(\d+)", _DEFAULT_PRIORITY, 7)
    importance = take(r"\*(\d+)", _DEFAULT_IMPORTANCE, 7)
    raw_category = take(r"#(\d+)", Category.INSTANT, 7)
    if raw_category in {v for v, _ in category_choices()}:
        category = raw_category
    else:
        category = Category.UNDEFINED

    return name.strip(), FixFeature(
        category=category, priority=priority, importance=importance
    )


class QuickPanel(QWidget):
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
        root.setSpacing(8)
        self.header = SectionHeader()
        root.addWidget(self.header)

        # 快加行
        add_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.returnPressed.connect(self._quick_add)
        self.btn_add = small_button("", "Primary")
        self.btn_add.clicked.connect(self._quick_add)
        add_row.addWidget(self.input, 1)
        add_row.addWidget(self.btn_add)
        root.addLayout(add_row)

        # 表单选择行: 快加条目可选落入的表单
        form_row = QHBoxLayout()
        self.form_label = QLabel()
        self.form_combo = QComboBox()
        self.form_combo.setMinimumWidth(180)
        self.form_combo.currentIndexChanged.connect(self.refresh)
        self.btn_new_form = small_button("")
        self.btn_new_form.clicked.connect(self._new_form)
        self.btn_sort_priority = small_button("")
        self.btn_sort_priority.clicked.connect(self._sort_by_priority)
        form_row.addWidget(self.form_label)
        form_row.addWidget(self.form_combo)
        form_row.addWidget(self.btn_new_form)
        form_row.addWidget(self.btn_sort_priority)
        form_row.addStretch(1)
        root.addLayout(form_row)

        # 过滤行
        filter_row = QHBoxLayout()
        self.scope_label = QLabel()
        self.scope = QComboBox()
        self.category = QComboBox()
        self.keyword = QLineEdit()
        self.keyword.setFixedWidth(180)
        self.scope.currentIndexChanged.connect(self.refresh)
        self.category.currentIndexChanged.connect(self.refresh)
        self.keyword.textChanged.connect(self.refresh)
        filter_row.addWidget(self.scope_label)
        filter_row.addWidget(self.scope)
        filter_row.addWidget(self.category)
        filter_row.addWidget(self.keyword)
        filter_row.addStretch(1)
        root.addLayout(filter_row)

        # 表格
        self.table = make_table([""] * 8)
        self.table.setColumnWidth(0, 36)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.cellDoubleClicked.connect(self._edit_item)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_item_menu)
        root.addWidget(self.table, 1)

        # 底部
        bottom = QHBoxLayout()
        self.count_label = QLabel("")
        self.count_label.setObjectName("SectionSub")
        self.btn_done = small_button("")
        self.btn_done.clicked.connect(self._toggle_done)
        self.btn_edit = small_button("")
        self.btn_edit.clicked.connect(self._edit_item)
        self.btn_del = small_button("", "Danger")
        self.btn_del.clicked.connect(self._delete_item)
        bottom.addWidget(self.count_label)
        bottom.addStretch(1)
        bottom.addWidget(self.btn_done)
        bottom.addWidget(self.btn_edit)
        bottom.addWidget(self.btn_del)
        root.addLayout(bottom)

    def retranslate(self) -> None:
        self.header.set_title(tr("Quick Action"))
        self.header.set_subtitle(tr("Quickly jot it down, do it now"))
        self.input.setPlaceholderText(
            tr("Quick add: name !priority #category   e.g. Print file !7 #3  (Enter)")
        )
        self.btn_add.setText(tr("Add"))
        self.form_label.setText(tr("Form"))
        self.btn_new_form.setText(tr("New Form"))
        self.btn_sort_priority.setText(tr("Sort by Priority"))
        self.btn_sort_priority.setToolTip(
            tr("Sort the whole form by priority, then importance")
        )
        self.scope_label.setText(tr("Scope"))
        self.keyword.setPlaceholderText(tr("Search…"))
        self.btn_done.setText(tr("Toggle Done / Restore"))
        self.btn_edit.setText(tr("Edit"))
        self.btn_del.setText(tr("Delete"))
        set_headers(self.table, [
            "✔", tr("Name"), tr("Form"), tr("Category"), tr("Priority"),
            tr("Importance"), tr("State"), tr("Created"),
        ])
        self._rebuild_filters()
        self._rebuild_form_combo()

    def _rebuild_form_combo(self) -> None:
        """重建表单下拉(保留当前选中)。"""
        current = self.form_combo.currentData()
        self.form_combo.blockSignals(True)
        self.form_combo.clear()
        self.form_combo.addItem(tr("No form"), None)
        for form in self.db.list_forms(Scope.QUICK):
            self.form_combo.addItem(form.name, form.id)
        idx = self.form_combo.findData(current)
        self.form_combo.setCurrentIndex(max(0, idx))
        self.btn_sort_priority.setEnabled(self.form_combo.currentData() is not None)
        self.form_combo.blockSignals(False)

    def _new_form(self) -> None:
        """快速新建表单,并选中它,后续快加直接落入。"""
        name, ok = prompt_text(self, tr("New Form"), tr("Form name:"))
        if not ok or not name:
            return
        form = self.db.create_form(name, scope=Scope.QUICK)
        self._rebuild_form_combo()
        idx = self.form_combo.findData(form.id)
        if idx >= 0:
            self.form_combo.setCurrentIndex(idx)
        self.main.notify_items_changed()

    def _rebuild_filters(self) -> None:
        # scope 用 data 区分,不用 label
        self.scope.blockSignals(True)
        current = self.scope.currentIndex()
        self.scope.clear()
        self.scope.addItem(tr("Active"), "active")
        self.scope.addItem(tr("Done"), "done")
        self.scope.addItem(tr("All"), "all")
        self.scope.setCurrentIndex(min(current, 2))
        self.scope.blockSignals(False)

        self.category.blockSignals(True)
        current_cat = self.category.currentData()
        self.category.clear()
        self.category.addItem(tr("All categories"), None)
        for value in sorted(QUICK_CATEGORIES):
            self.category.addItem(category_label(value), value)
        idx = self.category.findData(current_cat)
        self.category.setCurrentIndex(max(0, idx))
        self.category.blockSignals(False)

    # -- 数据 ----------------------------------------------------------------

    def refresh(self) -> None:
        self._rebuild_form_combo()  # 表单可能在其他面板新建/删除
        scope = self.scope.currentData()
        category = self.category.currentData()
        keyword = self.keyword.text().strip()
        form_id = self.form_combo.currentData()  # None=未归档;选中表单则过滤
        unfiled_scope = Scope.QUICK if form_id is None else None

        quick_cats = sorted(QUICK_CATEGORIES)
        if scope == "done":
            items = self.db.query(
                state=State.DONE, category=category, category_in=quick_cats,
                keyword=keyword, form_id=form_id, unfiled_scope=unfiled_scope,
                order="updated_at DESC, id DESC",
            )
        elif scope == "all":
            items = self.db.query(
                category=category, category_in=quick_cats, keyword=keyword,
                form_id=form_id, unfiled_scope=unfiled_scope,
                order="updated_at DESC, id DESC",
            )
        else:  # active
            items = self.db.query(
                state_not=State.DONE, category=category, category_in=quick_cats,
                keyword=keyword, form_id=form_id, unfiled_scope=unfiled_scope,
                order="priority DESC, updated_at DESC, id DESC",
            )

        self._visible_items = items
        rows = hierarchy_rows(items, self.main.collapsed_item_ids)
        clear_table(self.table)
        self.table.setRowCount(len(rows))
        for row, (item, depth) in enumerate(rows):
            check = QCheckBox()
            check.setChecked(item.is_done)
            check.setEnabled(not item.is_done)
            check.toggled.connect(
                lambda on, item_id=item.id: self._checkbox_toggled(item_id, on)
            )
            self.table.setCellWidget(row, 0, check)
            set_hierarchy_name(
                self.table, row, 1, item, depth,
                has_children=bool(self.db.children(item.id)),
                collapsed=item.id in self.main.collapsed_item_ids,
                on_toggle=lambda _checked=False, item_id=item.id: self.main.toggle_item_collapsed(item_id),
            )
            forms = self.db.item_forms(item.id, Scope.QUICK)
            set_cell(self.table, row, 2, ", ".join(f.name for f in forms) or tr("Unfiled"))
            set_cell(self.table, row, 3, item.fix.category_label, Qt.AlignmentFlag.AlignCenter)
            self.table.item(row, 3).setData(Qt.ItemDataRole.UserRole, item.fix.category)
            set_score_cell(
                self.table, row, 4, item.fix.priority,
                lambda value, item_id=item.id: self._set_score(item_id, "priority", value),
            )
            set_score_cell(
                self.table, row, 5, item.fix.importance,
                lambda value, item_id=item.id: self._set_score(item_id, "importance", value),
            )
            set_cell(self.table, row, 6, item.fix.state_label, Qt.AlignmentFlag.AlignCenter)
            set_cell(self.table, row, 7, (item.created_at or "")[:10], Qt.AlignmentFlag.AlignCenter)
            if item.is_done:
                for c in range(1, self.table.columnCount()):
                    cell = self.table.item(row, c)
                    if cell is not None:
                        font = cell.font()
                        font.setStrikeOut(True)
                        cell.setFont(font)

        active = self.db.query(
            state_not=State.DONE, category_in=quick_cats, form_id=form_id,
            unfiled_scope=unfiled_scope,
        )
        self.count_label.setText(
            tr("{active} active · {total} in list", active=len(active), total=len(items))
        )
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
        item = self.table.item(row, 1)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _quick_add(self) -> None:
        text = self.input.text()
        if not text.strip():
            return
        name, fix = parse_quick_add(text)
        if not name:
            QMessageBox.information(self, tr("Add"), tr("Name cannot be empty."))
            return
        item = self.db.create_item(name, fix=fix)
        if scope_of_category(fix.category) == Scope.QUICK:
            form_id = self.form_combo.currentData()
            if form_id is not None:
                self.db.add_to_form(form_id, item.id)
        else:
            QMessageBox.information(
                self, tr("Quick Action"),
                tr(
                    "Item created as {category} — it belongs to Planner / Experiments, "
                    "not here. See All Items.",
                    category=item.fix.category_label,
                ),
            )
        self.input.clear()
        self.refresh()
        self.main.notify_items_changed()

    def _checkbox_toggled(self, item_id: int, checked: bool) -> None:
        self.db.set_state(item_id, State.DONE if checked else State.NOT_STARTED)
        self.refresh()
        self.main.notify_items_changed()

    def _toggle_done(self) -> None:
        item_id = self._selected_item_id()
        if item_id is None:
            return
        item = self.db.get_item(item_id)
        if item is None:
            return
        self.db.set_state(item_id, State.NOT_STARTED if item.is_done else State.DONE)
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
            categories=sorted(QUICK_CATEGORIES),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        if v["name"]:
            self.db.update_item(item_id, name=v["name"], description=v["description"], fix=v["fix"])
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
                if self.table.item(row, 1).data(Qt.ItemDataRole.UserRole) == copy.id:
                    self.table.setCurrentCell(row, 1)
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
        item_id = self._selected_item_id()
        memberships = self.db.item_forms(item_id, Scope.QUICK) if item_id is not None else []
        source_form_id = memberships[0].id if memberships else None
        move_menu = menu.addMenu(tr("Move to Form"))
        targets = [
            form for form in self.db.list_forms(Scope.QUICK)
            if form.id != source_form_id
        ]
        if targets:
            for form in targets:
                action = move_menu.addAction(form.name)
                action.triggered.connect(
                    lambda _checked=False, target_id=form.id: self._transfer_item(target_id)
                )
        else:
            empty_action = move_menu.addAction(tr("No other forms"))
            empty_action.setEnabled(False)
        if source_form_id is not None:
            remove_action = move_menu.addAction(tr("Remove from Form"))
            remove_action.triggered.connect(self._remove_from_form)
        menu.addSeparator()
        up_action = menu.addAction(tr("Move Up"))
        down_action = menu.addAction(tr("Move Down"))
        up_action.triggered.connect(lambda: self._move(-1))
        down_action.triggered.connect(lambda: self._move(1))
        has_form = self.form_combo.currentData() is not None
        up_action.setEnabled(has_form and index.row() > 0)
        down_action.setEnabled(has_form and index.row() < self.table.rowCount() - 1)
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
            categories=sorted(QUICK_CATEGORIES),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        values = dlg.values()
        if not values["name"]:
            return
        child = self.db.create_item(
            values["name"], values["description"], fix=values["fix"], parent_id=parent.id,
        )
        memberships = self.db.item_forms(parent.id, Scope.QUICK)
        if memberships:
            self.db.add_to_form(memberships[0].id, child.id)
        self.refresh()
        self.main.notify_items_changed()

    def _transfer_item(self, target_form_id: int) -> None:
        item_id = self._selected_item_id()
        if item_id is None:
            return
        memberships = self.db.item_forms(item_id, Scope.QUICK)
        source_form_id = memberships[0].id if memberships else None
        changed = (
            self.db.transfer_item(item_id, source_form_id, target_form_id)
            if source_form_id is not None
            else self.db.add_to_form(target_form_id, item_id)
        )
        if changed:
            self.refresh()
            self.main.notify_items_changed()

    def _remove_from_form(self) -> None:
        item_id = self._selected_item_id()
        if item_id is None:
            return
        memberships = self.db.item_forms(item_id, Scope.QUICK)
        if memberships:
            self.db.remove_from_form(memberships[0].id, item_id)
            self.form_combo.setCurrentIndex(0)
            self.refresh()
            self.main.notify_items_changed()

    def _move(self, delta: int) -> None:
        """在当前 quick 表单中按可见相邻项移动；兼容状态/类别/搜索过滤。"""
        form_id = self.form_combo.currentData()
        row = self.table.currentRow()
        if form_id is None or row < 0:
            return
        target = row + delta
        if target < 0 or target >= self.table.rowCount():
            return

        selected = self.table.item(row, 1)
        neighbor = self.table.item(target, 1)
        if selected is None or neighbor is None:
            return
        selected_id = selected.data(Qt.ItemDataRole.UserRole)
        neighbor_id = neighbor.data(Qt.ItemDataRole.UserRole)

        ordered = [item.id for item in self.db.form_items(form_id)]
        try:
            selected_pos = ordered.index(selected_id)
            neighbor_pos = ordered.index(neighbor_id)
        except ValueError:
            return
        ordered[selected_pos], ordered[neighbor_pos] = ordered[neighbor_pos], ordered[selected_pos]
        self.db.set_form_order(form_id, ordered)
        self.refresh()
        for visible_row in range(self.table.rowCount()):
            cell = self.table.item(visible_row, 1)
            if cell is not None and cell.data(Qt.ItemDataRole.UserRole) == selected_id:
                self.table.setCurrentCell(visible_row, 1)
                break

    def _sort_by_priority(self) -> None:
        """重排当前 quick 表单：priority 降序，其次 importance 降序。"""
        form_id = self.form_combo.currentData()
        if form_id is None:
            return
        items = self.db.form_items(form_id)
        ordered = sorted(
            items,
            key=lambda item: (-item.fix.priority, -item.fix.importance),
        )
        self.db.set_form_order(form_id, [item.id for item in ordered])
        self.refresh()
        self.main.notify_items_changed()
