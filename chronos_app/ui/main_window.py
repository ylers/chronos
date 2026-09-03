"""主窗口: 左侧栏 + 四面板堆栈。"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QByteArray, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QWidget,
)

from chronos_app.i18n import set_language, tr
from chronos_app.model import Database
from chronos_app.ui.theme import DEFAULT_SETTINGS, apply_theme

from .all_items_panel import AllItemsPanel
from .experiment_panel import ExperimentPanel
from .planner_panel import PlannerPanel
from .quick_panel import QuickPanel
from .reference_panel import ReferencePanel
from .settings_panel import SettingsPanel
from .sidebar import Sidebar


class MainWindow(QMainWindow):
    def __init__(
        self, db: Database, parent: QWidget | None = None, dev: bool = False
    ) -> None:
        super().__init__(parent)
        self.db = db
        self.dev = dev
        self.settings = self._load_settings()
        set_language(str(self.settings.get("language") or "zh"))
        self.setWindowTitle(self._title())
        self.resize(1080, 680)
        self.collapsed_item_ids: set[int] = set()

        # 主题应用(QApplication 全局)
        from PySide6.QtWidgets import QApplication

        self.palette = apply_theme(QApplication.instance(), self.settings)

        # 面板(顺序须与 sidebar.SECTIONS 一致)
        self.panels: list[QWidget] = [
            PlannerPanel(self.db, self),
            QuickPanel(self.db, self),
            ExperimentPanel(self.db, self),
            ReferencePanel(self.db, self),
            AllItemsPanel(self.db, self),
            SettingsPanel(self.db, self),
        ]
        self.stack = QStackedWidget()
        for panel in self.panels:
            self.stack.addWidget(panel)
        self.stack.currentChanged.connect(self._on_stack_changed)

        # 侧栏
        self.sidebar = Sidebar()
        self.sidebar.section_changed.connect(self._on_section_changed)

        root = QWidget()
        root.setObjectName("Root")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        self.stack.setCurrentIndex(0)
        self._setup_ui_state()

    # -- 界面尺寸持久化 -----------------------------------------------------

    def _setup_ui_state(self) -> None:
        planner, quick, experiment, reference, all_items, _settings = self.panels
        self._persistent_tables: dict[str, QTableWidget] = {
            "planner.items": planner.table,
            "quick.items": quick.table,
            "experiment.items": experiment.table,
            "experiment.params": experiment.params_table,
            "reference.fix": reference.fix_table,
            "reference.settings": reference.settings_table,
            "all_items.items": all_items.table,
        }
        self._persistent_splitters: dict[str, QSplitter] = {
            "planner.main": planner.splitter,
            "experiment.main": experiment.splitter,
        }
        self._restoring_ui_state = True
        self._layout_save_timer = QTimer(self)
        self._layout_save_timer.setSingleShot(True)
        self._layout_save_timer.setInterval(250)
        self._layout_save_timer.timeout.connect(self._save_ui_state)

        for table in self._persistent_tables.values():
            table.horizontalHeader().sectionResized.connect(
                lambda *_args: self._schedule_ui_state_save()
            )
        for splitter in self._persistent_splitters.values():
            splitter.splitterMoved.connect(
                lambda *_args: self._schedule_ui_state_save()
            )
        self.sidebar.section_changed.connect(
            lambda *_args: self._schedule_ui_state_save()
        )
        planner.form_list.currentItemChanged.connect(
            lambda *_args: self._schedule_ui_state_save()
        )
        quick.form_combo.currentIndexChanged.connect(
            lambda *_args: self._schedule_ui_state_save()
        )

        self._restore_ui_state()
        self._restoring_ui_state = False

    def _restore_ui_state(self) -> None:
        state = self.db.get_setting("ui_layout", {})
        if not isinstance(state, dict):
            return

        geometry = state.get("window_geometry")
        if isinstance(geometry, str) and geometry:
            self.restoreGeometry(QByteArray.fromBase64(geometry.encode("ascii")))

        table_sizes = state.get("tables", {})
        if isinstance(table_sizes, dict):
            for key, table in self._persistent_tables.items():
                widths = table_sizes.get(key)
                if not isinstance(widths, list):
                    continue
                for column, width in enumerate(widths[: table.columnCount()]):
                    if isinstance(width, int) and width > 20:
                        table.setColumnWidth(column, width)

        splitter_sizes = state.get("splitters", {})
        if isinstance(splitter_sizes, dict):
            for key, splitter in self._persistent_splitters.items():
                sizes = splitter_sizes.get(key)
                if (
                    isinstance(sizes, list)
                    and len(sizes) == splitter.count()
                    and all(isinstance(size, int) and size >= 0 for size in sizes)
                ):
                    splitter.setSizes(sizes)

        navigation = state.get("navigation", {})
        if isinstance(navigation, dict):
            planner = self.panels[0]
            quick = self.panels[1]

            collapsed = navigation.get("collapsed_item_ids", [])
            if isinstance(collapsed, list):
                self.collapsed_item_ids = {
                    value for value in collapsed if type(value) is int and value > 0
                }
                for panel in self.panels:
                    panel.refresh()

            planner_form_id = navigation.get("planner_form_id")
            if isinstance(planner_form_id, int):
                planner.current_form_id = planner_form_id
                planner.refresh()

            quick_form_id = navigation.get("quick_form_id")
            if isinstance(quick_form_id, int):
                quick.refresh()
                quick_index = quick.form_combo.findData(quick_form_id)
                if quick_index >= 0:
                    quick.form_combo.setCurrentIndex(quick_index)
            elif quick_form_id is None:
                quick.form_combo.setCurrentIndex(0)

            sidebar_index = navigation.get("sidebar_index")
            if isinstance(sidebar_index, int) and 0 <= sidebar_index < len(self.panels):
                self.sidebar.set_current_index(sidebar_index)
                self.stack.setCurrentIndex(sidebar_index)

    def _schedule_ui_state_save(self) -> None:
        if getattr(self, "_restoring_ui_state", True):
            return
        self._layout_save_timer.start()

    def _save_ui_state(self) -> None:
        if not hasattr(self, "_persistent_tables"):
            return
        state = {
            "version": 2,
            "window_geometry": bytes(self.saveGeometry().toBase64()).decode("ascii"),
            "tables": {
                key: [table.columnWidth(i) for i in range(table.columnCount())]
                for key, table in self._persistent_tables.items()
            },
            "splitters": {
                key: splitter.sizes()
                for key, splitter in self._persistent_splitters.items()
            },
            "navigation": {
                "sidebar_index": self.sidebar.current_index(),
                "planner_form_id": self.panels[0].current_form_id,
                "quick_form_id": self.panels[1].form_combo.currentData(),
                "collapsed_item_ids": sorted(self.collapsed_item_ids),
            },
        }
        self.db.set_setting("ui_layout", state)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_layout_save_timer"):
            self._schedule_ui_state_save()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        if hasattr(self, "_layout_save_timer"):
            self._schedule_ui_state_save()

    def closeEvent(self, event) -> None:
        if hasattr(self, "_layout_save_timer"):
            self._layout_save_timer.stop()
            self._save_ui_state()
        super().closeEvent(event)

    # -- 设置与主题 ---------------------------------------------------------

    def _title(self) -> str:
        title = tr("chronos — Daily · Workflow · Experiments")
        return title + " · [dev]" if self.dev else title

    def _load_settings(self) -> dict[str, Any]:
        out = dict(DEFAULT_SETTINGS)
        for key in DEFAULT_SETTINGS:
            value = self.db.get_setting(key, None)
            if value is not None:
                out[key] = value
        return out

    def reapply_theme(self) -> None:
        """设置面板改动后调用: 重新读设置、应用主题、刷新各面板。"""
        from PySide6.QtWidgets import QApplication

        self.settings = self._load_settings()
        self.palette = apply_theme(QApplication.instance(), self.settings)
        for panel in self.panels:
            panel.refresh()

    def reapply_language(self) -> None:
        """语言切换后调用: 更新全局文案与各面板。"""
        self.settings = self._load_settings()
        set_language(str(self.settings.get("language") or "zh"))
        self.setWindowTitle(self._title())
        self.sidebar.retranslate()
        for panel in self.panels:
            if hasattr(panel, "retranslate"):
                panel.retranslate()
            panel.refresh()

    def notify_items_changed(self) -> None:
        """任一面板改了条目后,刷新其余面板。"""
        for panel in self.panels:
            panel.refresh()

    def toggle_item_collapsed(self, item_id: int) -> None:
        if type(item_id) is not int or item_id <= 0:
            return
        self.collapsed_item_ids.discard(False)
        if item_id in self.collapsed_item_ids:
            self.collapsed_item_ids.remove(item_id)
        else:
            self.collapsed_item_ids.add(item_id)
        self._schedule_ui_state_save()
        self.notify_items_changed()

    # -- 侧栏切换 ---------------------------------------------------------

    def _on_section_changed(self, index: int) -> None:
        self.stack.setCurrentIndex(index)

    def _on_stack_changed(self, index: int) -> None:
        panel = self.panels[index]
        if hasattr(panel, "refresh"):
            panel.refresh()
