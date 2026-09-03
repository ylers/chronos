"""实验管理面板: 实验列表 + 参数/结论/运行记录编辑(语言感知)。"""

from __future__ import annotations

import json
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from chronos_app.i18n import tr
from chronos_app.model import Category, FixFeature, State
from chronos_app.widgets.helpers import (
    ItemDialog,
    SectionHeader,
    add_collapse_action,
    add_parent_menu,
    clear_table,
    confirm,
    hierarchy_rows,
    make_table,
    set_hierarchy_name,
    prompt_text,
    set_cell,
    set_headers,
    small_button,
)


class ExperimentPanel(QWidget):
    def __init__(self, db, main: QWidget) -> None:
        super().__init__()
        self.db = db
        self.main = main
        self.current_id: int | None = None
        self._build_ui()
        self.retranslate()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 10)
        root.setSpacing(8)
        self.header = SectionHeader()
        root.addWidget(self.header)

        splitter = self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左: 实验列表
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)
        self.table = make_table([""] * 4)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.currentCellChanged.connect(self._on_select)
        self.table.cellDoubleClicked.connect(self._edit_meta)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_item_menu)
        left_layout.addWidget(self.table, 1)

        list_btns = QHBoxLayout()
        self.btn_new = small_button("", "Primary")
        self.btn_new.clicked.connect(self._new_experiment)
        self.btn_del = small_button("", "Danger")
        self.btn_del.clicked.connect(self._delete_experiment)
        list_btns.addWidget(self.btn_new)
        list_btns.addWidget(self.btn_del)
        list_btns.addStretch(1)
        left_layout.addLayout(list_btns)
        splitter.addWidget(left)

        # 右: 详情
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        self.detail_title = QLabel("")
        self.detail_title.setObjectName("SectionTitle")
        right_layout.addWidget(self.detail_title)

        self.name_label = QLabel("")
        self.name_edit = QPlainTextEdit()
        self.name_edit.setFixedHeight(38)
        self.desc_label = QLabel("")
        self.desc_edit = QPlainTextEdit()
        self.desc_edit.setFixedHeight(60)
        right_layout.addWidget(self.name_label)
        right_layout.addWidget(self.name_edit)
        right_layout.addWidget(self.desc_label)
        right_layout.addWidget(self.desc_edit)

        # 参数键值表
        params_head = QHBoxLayout()
        self.params_label = QLabel("")
        params_head.addWidget(self.params_label)
        params_head.addStretch(1)
        self.btn_add_param = small_button("")
        self.btn_add_param.clicked.connect(self._add_param_row)
        self.btn_rm_param = small_button("")
        self.btn_rm_param.clicked.connect(self._remove_param_row)
        params_head.addWidget(self.btn_add_param)
        params_head.addWidget(self.btn_rm_param)
        right_layout.addLayout(params_head)

        self.params_table = QTableWidget(0, 2)
        self.params_table.verticalHeader().setVisible(False)
        self.params_table.horizontalHeader().setStretchLastSection(True)
        self.params_table.setColumnWidth(0, 120)
        right_layout.addWidget(self.params_table)

        self.result_label = QLabel("")
        right_layout.addWidget(self.result_label)
        self.result_edit = QPlainTextEdit()
        self.result_edit.setFixedHeight(70)
        right_layout.addWidget(self.result_edit)

        # 运行记录
        iter_head = QHBoxLayout()
        self.iter_label = QLabel("")
        iter_head.addWidget(self.iter_label)
        iter_head.addStretch(1)
        self.btn_add_iter = small_button("")
        self.btn_add_iter.clicked.connect(self._add_iteration)
        iter_head.addWidget(self.btn_add_iter)
        right_layout.addLayout(iter_head)
        self.iter_list = QListWidget()
        right_layout.addWidget(self.iter_list)

        # 保存
        save_row = QHBoxLayout()
        save_row.addStretch(1)
        self.btn_save = small_button("", "Primary")
        self.btn_save.clicked.connect(self._save_detail)
        save_row.addWidget(self.btn_save)
        right_layout.addLayout(save_row)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([420, 560])

        root.addWidget(splitter, 1)

    def retranslate(self) -> None:
        self.header.set_title(tr("Experiments"))
        self.header.set_subtitle(tr("Record parameters, conclusions and runs"))
        set_headers(self.table, [
            tr("Name"), tr("State"), tr("Result Summary"), tr("Updated"),
        ])
        self.btn_new.setText(tr("New Experiment"))
        self.btn_del.setText(tr("Delete Experiment"))
        self.detail_title.setText(tr("Select an experiment to view details"))
        self.name_label.setText(tr("Name"))
        self.name_edit.setPlaceholderText(tr("Experiment name"))
        self.desc_label.setText(tr("Description"))
        self.desc_edit.setPlaceholderText(tr("Experiment description (optional)"))
        self.params_label.setText(tr("Parameters"))
        self.result_label.setText(tr("Result"))
        self.iter_label.setText(tr("Runs"))
        self.result_edit.setPlaceholderText(tr("Experiment conclusion…"))
        self.btn_add_param.setText(tr("+ Key/Value"))
        self.btn_rm_param.setText(tr("− Key/Value"))
        self.btn_add_iter.setText(tr("+ Add Run"))
        self.btn_save.setText(tr("Save Changes"))
        self.params_table.setHorizontalHeaderLabels([tr("Key"), tr("Value")])
        if self.current_id is None:
            self.detail_title.setText(tr("Select an experiment to view details"))

    # -- 数据 ----------------------------------------------------------------

    def refresh(self) -> None:
        items = self.db.query(category=Category.EXPERIMENT, order="updated_at DESC, id DESC")
        self._visible_items = items
        rows = hierarchy_rows(items, self.main.collapsed_item_ids)
        clear_table(self.table)
        self.table.setRowCount(len(rows))
        for row, (item, depth) in enumerate(rows):
            result = item.extendable_get("result", "")
            summary = (result if isinstance(result, str) else str(result)).replace("\n", " ")[:20]
            set_hierarchy_name(
                self.table, row, 0, item, depth,
                has_children=bool(self.db.children(item.id)),
                collapsed=item.id in self.main.collapsed_item_ids,
                on_toggle=lambda _checked=False, item_id=item.id: self.main.toggle_item_collapsed(item_id),
            )
            set_cell(self.table, row, 1, item.fix.state_label, Qt.AlignmentFlag.AlignCenter)
            set_cell(self.table, row, 2, summary)
            set_cell(self.table, row, 3, (item.updated_at or "")[:16], Qt.AlignmentFlag.AlignCenter)

        self.table.resizeRowsToContents()

        if self.current_id is not None:
            for row in range(self.table.rowCount()):
                if self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == self.current_id:
                    self.table.setCurrentCell(row, 0)
                    self._load_detail(self.current_id)
                    return
        self.current_id = None
        self._clear_detail()

    def _selected_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def _on_select(self, _r, _c, _pr, _pc) -> None:
        item_id = self._selected_id()
        if item_id is not None and item_id != self.current_id:
            self.current_id = item_id
            self._load_detail(item_id)

    # -- 详情编辑 ----------------------------------------------------------------

    def _clear_detail(self) -> None:
        self.detail_title.setText(tr("Select an experiment to view details"))
        self.name_edit.clear()
        self.desc_edit.clear()
        self.result_edit.clear()
        self.params_table.setRowCount(0)
        self.iter_list.clear()

    def _load_detail(self, item_id: int) -> None:
        item = self.db.get_item(item_id)
        if item is None:
            return
        self.detail_title.setText(
            tr("Experiment #{id} · {state}", id=item_id, state=item.fix.state_label)
        )
        self.name_edit.setPlainText(item.name)
        self.desc_edit.setPlainText(item.description)
        self.result_edit.setPlainText(item.extendable_get("result", ""))

        params = item.extendable_get("parameters", {})
        self.params_table.setRowCount(len(params))
        for row, (key, value) in enumerate(params.items()):
            self.params_table.setItem(row, 0, QTableWidgetItem(str(key)))
            self.params_table.setItem(row, 1, QTableWidgetItem(str(value)))

        self.iter_list.clear()
        for entry in item.extendable_get("iterations", []):
            time = entry.get("time", "?") if isinstance(entry, dict) else "?"
            note = entry.get("note", "") if isinstance(entry, dict) else str(entry)
            self.iter_list.addItem(QListWidgetItem(f"[{time}] {note}"))

    def _save_detail(self) -> None:
        if self.current_id is None:
            return
        item = self.db.get_item(self.current_id)
        if item is None:
            return

        # 参数: 字符串尽量转成 JSON 原生类型
        parameters: dict = {}
        for row in range(self.params_table.rowCount()):
            key_item = self.params_table.item(row, 0)
            val_item = self.params_table.item(row, 1)
            key = key_item.text().strip() if key_item else ""
            if not key:
                continue
            value = val_item.text() if val_item else ""
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass
            parameters[key] = value

        extendable = dict(item.extendable)
        extendable["parameters"] = parameters
        extendable["result"] = self.result_edit.toPlainText()

        self.db.update_item(
            self.current_id,
            name=self.name_edit.toPlainText().strip() or item.name,
            description=self.desc_edit.toPlainText().strip(),
            extendable=extendable,
        )
        self.refresh()
        self.main.notify_items_changed()

    # -- 实验 CRUD ----------------------------------------------------------------

    def _new_experiment(self) -> None:
        dlg = ItemDialog(
            self, tr("New Experiment"),
            fix=FixFeature(category=Category.EXPERIMENT, importance=3),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        v = dlg.values()
        if not v["name"]:
            return
        item = self.db.create_item(v["name"], v["description"], fix=v["fix"])
        self.current_id = item.id
        self.refresh()
        self.main.notify_items_changed()

    def _edit_meta(self, _row: int | None = None) -> None:
        item_id = self._selected_id()
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

    def _delete_experiment(self) -> None:
        item_id = self._selected_id()
        if item_id is None:
            return
        item = self.db.get_item(item_id)
        if item is None:
            return
        if not confirm(
            self, tr("Delete Experiment"),
            tr("Delete experiment \"{name}\" and all its records?", name=item.name),
        ):
            return
        self.db.delete_item(item_id)
        if self.current_id == item_id:
            self.current_id = None
        self.refresh()
        self.main.notify_items_changed()

    def _duplicate_experiment(self) -> None:
        item_id = self._selected_id()
        item = self.db.get_item(item_id) if item_id is not None else None
        if item is None:
            return
        copy = self.db.duplicate_item(item.id, name=tr("{name} (Copy)", name=item.name))
        if copy is not None:
            self.current_id = copy.id
        self.refresh()
        self.main.notify_items_changed()

    def _show_item_menu(self, pos) -> None:
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        self.table.selectRow(index.row())
        menu = QMenu(self)
        copy_action = menu.addAction(tr("Copy"))
        copy_action.triggered.connect(self._duplicate_experiment)
        child_action = menu.addAction(tr("New Child Item"))
        child_action.triggered.connect(self._new_child_item)
        add_collapse_action(
            menu, self.db, self._selected_id(), self.main.collapsed_item_ids,
            lambda: (self.main._schedule_ui_state_save(), self.main.notify_items_changed()),
        )
        add_parent_menu(
            menu, self.db, self._selected_id(), self._visible_items,
            lambda: (self.refresh(), self.main.notify_items_changed()),
        )
        menu.addSeparator()
        delete_action = menu.addAction(tr("Delete Item"))
        delete_action.triggered.connect(self._delete_experiment)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _new_child_item(self) -> None:
        parent_id = self._selected_id()
        parent = self.db.get_item(parent_id) if parent_id is not None else None
        if parent is None:
            return
        dlg = ItemDialog(
            self, tr("New Child Item"),
            fix=parent.fix.with_(category=Category.EXPERIMENT, state=State.NOT_STARTED),
            readonly_category=True,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        values = dlg.values()
        if not values["name"]:
            return
        child = self.db.create_item(
            values["name"], values["description"], fix=values["fix"], parent_id=parent.id,
        )
        self.current_id = child.id
        self.refresh()
        self.main.notify_items_changed()

    # -- 参数/记录 ----------------------------------------------------------------

    def _add_param_row(self) -> None:
        self.params_table.insertRow(self.params_table.rowCount())

    def _remove_param_row(self) -> None:
        row = self.params_table.currentRow()
        if row >= 0:
            self.params_table.removeRow(row)

    def _add_iteration(self) -> None:
        if self.current_id is None:
            return
        note, ok = prompt_text(self, tr("Record run"), tr("Note for this run:"))
        if not ok:
            return
        item = self.db.get_item(self.current_id)
        if item is None:
            return
        extendable = dict(item.extendable)
        iterations = list(extendable.get("iterations", []))
        iterations.append({
            "time": datetime.now().isoformat(timespec="seconds"),
            "note": note,
        })
        extendable["iterations"] = iterations
        self.db.update_item(self.current_id, extendable=extendable)
        self.refresh()
        self.main.notify_items_changed()
