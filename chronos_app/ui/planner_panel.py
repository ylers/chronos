"""计划表面板: 表单(集合)管理 + 条目表格(语言感知)。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from chronos_app.i18n import tr
from chronos_app.model import PLANNER_CATEGORIES, Category, FixFeature, Scope, State
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


class PlannerPanel(QWidget):
    def __init__(self, db, main: QWidget) -> None:
        super().__init__()
        self.db = db
        self.main = main
        self.current_form_id: int | None = None

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

        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左: 表单列表
        left_widget = QWidget()
        left = QVBoxLayout(left_widget)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(6)
        self.forms_label = QLabel()
        left.addWidget(self.forms_label)
        self.form_list = QListWidget()
        self.form_list.setMinimumWidth(130)
        self.form_list.setWordWrap(True)
        self.form_list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.form_list.currentItemChanged.connect(self._on_form_selected)
        left.addWidget(self.form_list, 1)

        form_btns = QHBoxLayout()
        self.btn_new_form = small_button("", "Primary")
        self.btn_new_form.clicked.connect(self._new_form)
        self.btn_del_form = small_button("")
        self.btn_del_form.clicked.connect(self._delete_form)
        form_btns.addWidget(self.btn_new_form)
        form_btns.addWidget(self.btn_del_form)
        left.addLayout(form_btns)
        self.splitter.addWidget(left_widget)

        # 右: 条目表格
        right_widget = QWidget()
        right = QVBoxLayout(right_widget)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(6)
        self.form_title = QLabel("—")
        self.form_title.setObjectName("SectionTitle")
        right.addWidget(self.form_title)

        self.table = make_table([""] * 6)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(self._edit_item)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_item_menu)
        right.addWidget(self.table, 1)

        item_btns = QHBoxLayout()
        self.btn_add = small_button("", "Primary")
        self.btn_add.clicked.connect(self._add_item)
        self.btn_edit = small_button("")
        self.btn_edit.clicked.connect(self._edit_item)
        self.btn_done = small_button("")
        self.btn_done.clicked.connect(self._toggle_done)
        self.btn_up = small_button("")
        self.btn_up.clicked.connect(lambda: self._move(-1))
        self.btn_down = small_button("")
        self.btn_down.clicked.connect(lambda: self._move(1))
        self.btn_del = small_button("", "Danger")
        self.btn_del.clicked.connect(self._delete_item)
        for b in (self.btn_add, self.btn_edit, self.btn_done, self.btn_up, self.btn_down, self.btn_del):
            item_btns.addWidget(b)
        item_btns.addStretch(1)
        right.addLayout(item_btns)
        self.splitter.addWidget(right_widget)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([220, 820])
        root.addWidget(self.splitter, 1)

    def retranslate(self) -> None:
        self.header.set_title(tr("Planner"))
        self.header.set_subtitle(tr("Organize long/mid-term goals into forms, item by item"))
        self.forms_label.setText(tr("Forms"))
        self.btn_new_form.setText(tr("New Form"))
        self.btn_del_form.setText(tr("Delete"))
        self.btn_add.setText(tr("+ Add Item"))
        self.btn_edit.setText(tr("Edit"))
        self.btn_done.setText(tr("Toggle Done"))
        self.btn_up.setText(tr("Move Up"))
        self.btn_down.setText(tr("Move Down"))
        self.btn_del.setText(tr("Delete Item"))
        set_headers(self.table, [
            tr("Name"), tr("Category"), tr("Priority"),
            tr("Importance"), tr("State"), tr("Created"),
        ])
        if self.current_form_id is None:
            self.form_title.setText(tr("No forms yet — click \"New Form\" to start"))

    # -- 数据 ----------------------------------------------------------------

    def refresh(self) -> None:
        forms = self.db.list_forms(Scope.PLANNER)
        current_id = self.current_form_id
        if current_id not in [f.id for f in forms] and forms:
            current_id = forms[0].id

        self.form_list.blockSignals(True)
        self.form_list.clear()
        for f in forms:
            item = QListWidgetItem(f.name)
            item.setData(Qt.ItemDataRole.UserRole, f.id)
            if f.description:
                item.setToolTip(f.description)
            self.form_list.addItem(item)
        self.form_list.blockSignals(False)

        if forms:
            for i in range(self.form_list.count()):
                if self.form_list.item(i).data(Qt.ItemDataRole.UserRole) == current_id:
                    self.form_list.setCurrentRow(i)
                    break
            else:
                self.form_list.setCurrentRow(0)
            current_id = self.form_list.currentItem().data(Qt.ItemDataRole.UserRole)
        else:
            self.form_list.setCurrentRow(-1)
            current_id = None

        self.current_form_id = current_id
        self._reload_items()

    def _reload_items(self) -> None:
        clear_table(self.table)
        if self.current_form_id is None:
            self.form_title.setText(tr("No forms yet — click \"New Form\" to start"))
            return

        form = self.db.get_form(self.current_form_id)
        if form is None:
            return
        self.form_title.setText(form.name + (f"  ·  {form.description}" if form.description else ""))

        items = self.db.form_items(self.current_form_id)
        self._visible_items = items
        rows = hierarchy_rows(items, self.main.collapsed_item_ids)
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
            if item.is_done:
                for c in range(self.table.columnCount()):
                    cell = self.table.item(row, c)
                    if cell is not None:
                        font = cell.font()
                        font.setStrikeOut(True)
                        cell.setFont(font)
        self.table.resizeRowsToContents()

    def _set_score(self, item_id: int, field: str, value: int) -> None:
        item = self.db.get_item(item_id)
        if item is not None and getattr(item.fix, field) != value:
            self.db.update_item(item_id, fix=item.fix.with_(**{field: value}))

    # -- 表单操作 ----------------------------------------------------------------

    def _new_form(self) -> None:
        name, ok = prompt_text(self, tr("New Form"), tr("Form name:"))
        if not ok or not name:
            return
        desc, _ = prompt_text(self, tr("New Form"), tr("Description (optional)"))
        form = self.db.create_form(name, desc, scope=Scope.PLANNER)
        self.current_form_id = form.id
        self.refresh()

    def _delete_form(self) -> None:
        if self.current_form_id is None:
            return
        if not confirm(self, tr("Delete form"), tr("Delete this form (items are kept)? This cannot be undone.")):
            return
        self.db.delete_form(self.current_form_id)
        self.current_form_id = None
        self.refresh()

    def _on_form_selected(self, current, _previous) -> None:
        if current is None:
            return
        self.current_form_id = current.data(Qt.ItemDataRole.UserRole)
        self._reload_items()

    # -- 条目操作 ----------------------------------------------------------------

    def _selected_item_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _add_item(self) -> None:
        if self.current_form_id is None:
            QMessageBox.information(self, tr("Add Item"), tr("Create a form first."))
            return
        dlg = ItemDialog(
            self, tr("Add Item"),
            fix=FixFeature(category=Category.SHORT_TERM),
            categories=sorted(PLANNER_CATEGORIES),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        if not v["name"]:
            return
        item = self.db.create_item(v["name"], v["description"], fix=v["fix"])
        self.db.add_to_form(self.current_form_id, item.id)
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
            categories=sorted(PLANNER_CATEGORIES),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        if not v["name"]:
            return
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
        move_menu = menu.addMenu(tr("Move to Form"))
        targets = [
            form for form in self.db.list_forms(Scope.PLANNER)
            if form.id != self.current_form_id
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
            move_menu.setEnabled(False)
        menu.addSeparator()
        up_action = menu.addAction(tr("Move Up"))
        down_action = menu.addAction(tr("Move Down"))
        up_action.triggered.connect(lambda: self._move(-1))
        down_action.triggered.connect(lambda: self._move(1))
        up_action.setEnabled(index.row() > 0)
        down_action.setEnabled(index.row() < self.table.rowCount() - 1)
        menu.addSeparator()
        delete_action = menu.addAction(tr("Delete Item"))
        delete_action.triggered.connect(self._delete_item)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _new_child_item(self) -> None:
        parent_id = self._selected_item_id()
        parent = self.db.get_item(parent_id) if parent_id is not None else None
        if parent is None or self.current_form_id is None:
            return
        dlg = ItemDialog(
            self, tr("New Child Item"), fix=parent.fix.with_(state=State.NOT_STARTED),
            categories=sorted(PLANNER_CATEGORIES),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        values = dlg.values()
        if not values["name"]:
            return
        child = self.db.create_item(
            values["name"], values["description"], fix=values["fix"], parent_id=parent.id,
        )
        self.db.add_to_form(self.current_form_id, child.id)
        self.refresh()
        self.main.notify_items_changed()

    def _transfer_item(self, target_form_id: int) -> None:
        item_id = self._selected_item_id()
        if item_id is None or self.current_form_id is None:
            return
        if self.db.transfer_item(item_id, self.current_form_id, target_form_id):
            self.refresh()
            self.main.notify_items_changed()

    def _move(self, delta: int) -> None:
        """表单内条目上移/下移。"""
        if self.current_form_id is None:
            return
        row = self.table.currentRow()
        target = row + delta
        if row < 0 or target < 0 or target >= self.table.rowCount():
            return
        selected_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        target_id = self.table.item(target, 0).data(Qt.ItemDataRole.UserRole)
        ordered = [i.id for i in self.db.form_items(self.current_form_id)]
        selected_pos, target_pos = ordered.index(selected_id), ordered.index(target_id)
        ordered[selected_pos], ordered[target_pos] = ordered[target_pos], ordered[selected_pos]
        self.db.set_form_order(self.current_form_id, ordered)
        self.refresh()
        for visible_row in range(self.table.rowCount()):
            if self.table.item(visible_row, 0).data(Qt.ItemDataRole.UserRole) == selected_id:
                self.table.setCurrentCell(visible_row, 0)
                break
