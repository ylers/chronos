#!/usr/bin/env python3
"""chronos 启动入口。

开发与使用分离,各用独立数据库:
    uv run python run.py               # 使用库 data/chronos.db(真实数据)
    uv run python run.py --dev         # 开发库 data/chronos-dev.db
    uv run python run.py --demo        # 向开发库重置并写入演示数据后启动(幂等)
    uv run python run.py --dev --demo  # 同 --demo
    uv run python run.py --smoke       # 临时库自动截图各面板后退出(验证用)
    uv run python run.py --db PATH     # 显式指定库(绕过默认分离)
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_DB = PROJECT_DIR / "data" / "chronos.db"
DEV_DB = PROJECT_DIR / "data" / "chronos-dev.db"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="chronos — 日常 · 工作流 · 实验")
    parser.add_argument("--db", default=None, help="SQLite 数据文件路径(显式指定时绕过默认分离)")
    parser.add_argument("--dev", action="store_true", help="开发模式: 使用独立开发库 data/chronos-dev.db")
    parser.add_argument("--demo", action="store_true", help="重置并写入演示数据(幂等,只进开发库)")
    parser.add_argument("--smoke", action="store_true", help="自动截图各面板后退出(验证)")
    return parser.parse_args()


def resolve_db(args: argparse.Namespace) -> tuple[str, bool]:
    """返回 (数据库路径, 是否开发模式)。smoke 用临时库,demo 只进开发库。"""
    if args.smoke:
        return str(Path(tempfile.mkdtemp(prefix="chronos_smoke_")) / "smoke.db"), True
    if args.db:  # 显式 --db 优先
        return args.db, False
    if args.dev or args.demo:
        return str(DEV_DB), True
    return str(DEFAULT_DB), False


def seed_demo(db) -> None:
    """重置条目/表单并写入一批演示数据(幂等,重复运行不会累积重复)。"""
    from chronos_app.model import Category, FixFeature, Scope, State

    db.clear_all()

    # 表单
    reading = db.create_form("读书计划", "每天读一点")
    week = db.create_form("本周安排", "短期任务")

    # 长期
    learn = db.create_item(
        "系统学习 Python 异步",
        "asyncio + 并发模型",
        fix=FixFeature(category=Category.LONG_TERM, priority=5, importance=6),
    )
    db.add_to_form(reading.id, learn.id)
    read_book = db.create_item(
        "读完《设计数据密集型应用》",
        fix=FixFeature(category=Category.LONG_TERM, priority=4, importance=5),
    )
    db.add_to_form(reading.id, read_book.id)
    db.set_parent(read_book.id, learn.id)

    # 短期
    hw = db.create_item(
        "完成本周作业",
        fix=FixFeature(category=Category.SHORT_TERM, priority=7, importance=6),
    )
    db.add_to_form(week.id, hw.id)
    print_pdf = db.create_item(
        "打印实验报告",
        fix=FixFeature(category=Category.SHORT_TERM, priority=5, importance=4),
    )
    db.add_to_form(week.id, print_pdf.id)
    db.set_parent(print_pdf.id, hw.id)

    # 即时(及时行动,可与 quick 表单关联)
    quick_form = db.create_form("随手记", "即时想法", scope=Scope.QUICK)
    jot = db.create_item(
        "读这篇文章: State of JS 2025",
        fix=FixFeature(category=Category.INSTANT, priority=6, importance=4),
    )
    db.add_to_form(quick_form.id, jot.id)
    done = db.create_item(
        "回复导师邮件",
        fix=FixFeature(category=Category.INSTANT, priority=4, importance=3),
    )
    db.set_state(done.id, State.DONE)
    blocked = db.create_item(
        "等实验跑完(预计 2h)",
        fix=FixFeature(category=Category.INSTANT, priority=5, importance=5),
    )
    db.set_state(blocked.id, State.BLOCKED)
    db.add_to_form(quick_form.id, blocked.id)

    # 灵感
    db.create_item(
        "把 chronos 的数据导出做成 JSON",
        description="方便同步到网盘",
        fix=FixFeature(category=Category.IDEA, priority=2, importance=2),
    )

    # 实验
    exp1 = db.create_item(
        "SGD 学习率对比",
        "对比 lr ∈ {1e-3, 1e-4} 在 CIFAR-10 上的收敛曲线",
        fix=FixFeature(category=Category.EXPERIMENT, priority=5, importance=5, state=State.BLOCKED),
        extendable={
            "parameters": {"lr": "1e-3, 1e-4", "epochs": "50", "batch_size": "128"},
            "result": "1e-4 收敛更稳,1e-3 震荡明显",
            "iterations": [
                {"time": "2026-08-12T10:20:00", "note": "lr=1e-3 跑完,loss 震荡"},
                {"time": "2026-08-13T09:40:00", "note": "lr=1e-4 跑完,收敛"},
            ],
        },
    )
    exp2 = db.create_item(
        "温度采样参数扫描",
        "temperature ∈ {0.5, 0.8, 1.0}",
        fix=FixFeature(category=Category.EXPERIMENT, priority=4, importance=4),
        extendable={
            "parameters": {"temperature": "0.5, 0.8, 1.0", "top_p": "0.9"},
            "result": "",
            "iterations": [{"time": "2026-08-14T08:00:00", "note": "第一批 10 条完成"}],
        },
    )
    # 实验不挂在表单里,由实验管理面板按类别查询
    _ = (exp1, exp2)


def main() -> int:
    args = parse_args()

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("chronos")

    from chronos_app.model import Database

    db_path, is_dev = resolve_db(args)
    if args.smoke:
        args.demo = True

    db = Database(db_path)
    if args.demo:
        seed_demo(db)

    from chronos_app.ui.main_window import MainWindow

    win = MainWindow(db, dev=is_dev)
    win.show()

    if args.smoke:
        return _run_smoke(app, win)

    return app.exec()


def _run_smoke(app: QApplication, win) -> int:
    from PySide6.QtCore import QTimer

    shots = PROJECT_DIR / "shots"
    shots.mkdir(exist_ok=True)
    names = ["planner", "quick", "experiment", "reference", "all_items", "settings"]
    passes = [("zh", ""), ("en", "_en")]
    checks: dict[str, bool] = {}

    def verify(lang: str) -> None:
        """结构 + 语言校验: 侧栏项数、各面板数据行、主题、文案语言、scope 隔离。"""
        from PySide6.QtWidgets import QApplication as QA

        from chronos_app.model import QUICK_CATEGORIES

        prefix = f"[{lang}] "
        checks[prefix + "sidebar_6_items"] = win.sidebar.list.count() == 6
        checks[prefix + "theme_applied"] = bool(QA.instance().styleSheet())

        planner = win.panels[0]
        quick = win.panels[1]
        experiment = win.panels[2]
        reference = win.panels[3]
        all_items = win.panels[4]
        settings = win.panels[5]
        checks[prefix + "planner_forms"] = planner.form_list.count() >= 2
        checks[prefix + "planner_items"] = planner.table.rowCount() >= 2
        checks[prefix + "all_items_rows"] = all_items.table.rowCount() >= 5
        checks[prefix + "quick_items"] = quick.table.rowCount() >= 1
        checks[prefix + "experiment_items"] = experiment.table.rowCount() >= 2
        checks[prefix + "reference_fields"] = reference.fix_table.rowCount() == 4
        checks[prefix + "reference_settings"] = reference.settings_table.rowCount() == 5
        checks[prefix + "settings_loaded"] = win.settings.get("bg_color") == "#1e1e1e"
        main_tables = [planner.table, quick.table, experiment.table, all_items.table]
        checks[prefix + "adaptive_item_rows"] = all(
            table.wordWrap() and table.verticalHeader().minimumSectionSize() >= 34
            for table in main_tables
        )
        hierarchy_depths = [
            table.item(row, name_col).data(257)
            for table, name_col in ((planner.table, 0), (quick.table, 1))
            for row in range(table.rowCount())
            if table.item(row, name_col) is not None
        ]
        checks[prefix + "child_item_indentation"] = any(
            isinstance(depth, int) and depth > 0 for depth in hierarchy_depths
        )
        win._save_ui_state()
        saved_layout = win.db.get_setting("ui_layout", {})
        checks[prefix + "layout_sizes_saved"] = (
            isinstance(saved_layout, dict)
            and len(saved_layout.get("tables", {})) == 7
            and len(saved_layout.get("splitters", {})) == 2
            and bool(saved_layout.get("window_geometry"))
        )
        navigation = saved_layout.get("navigation", {}) if isinstance(saved_layout, dict) else {}
        checks[prefix + "navigation_state_saved"] = (
            isinstance(navigation, dict)
            and navigation.get("sidebar_index") == win.sidebar.current_index()
            and navigation.get("planner_form_id") == planner.current_form_id
            and navigation.get("quick_form_id") == quick.form_combo.currentData()
        )

        # scope 隔离: 计划表表单与及时行动表单不重叠;及时行动条目全为 quick 类目
        planner_form_ids = {
            planner.form_list.item(i).data(256) for i in range(planner.form_list.count())
        }
        quick_form_ids = {
            quick.form_combo.itemData(i)
            for i in range(quick.form_combo.count())
            if quick.form_combo.itemData(i) is not None
        }
        checks[prefix + "forms_not_shared"] = not (planner_form_ids & quick_form_ids)
        checks[prefix + "quick_all_quick_scope"] = all(
            quick.table.item(r, 3).data(256) in QUICK_CATEGORIES
            for r in range(quick.table.rowCount())
        )

        # 语言校验: 侧栏 tooltip 与面板标题
        expected_tooltip = {"zh": "计划表", "en": "Planner"}[lang]
        expected_quick_title = {"zh": "及时行动", "en": "Quick Action"}[lang]
        expected_reference_title = {"zh": "参考", "en": "Reference"}[lang]
        checks[prefix + "sidebar_tooltip"] = (
            win.sidebar.list.item(0).toolTip() == expected_tooltip
        )
        checks[prefix + "quick_title"] = quick.header.title_text() == expected_quick_title
        checks[prefix + "reference_title"] = (
            reference.header.title_text() == expected_reference_title
        )

        for name_, ok in checks.items():
            if name_.startswith(prefix):
                print(f"  [{'✓' if ok else '✗'}] {name_}")

    def check_form_filter() -> None:
        """及时行动切换表单后,列表只显示该表单的条目。"""
        from PySide6.QtCore import Qt

        quick = win.panels[1]
        combo = quick.form_combo
        form_id = next(
            (combo.itemData(i) for i in range(combo.count()) if combo.itemData(i) is not None),
            None,
        )
        if form_id is None:
            checks["form_filter_works"] = False
            print("  [✗] form_filter_works")
            return
        combo.setCurrentIndex(combo.findData(form_id))
        quick.refresh()
        shown = {
            quick.table.item(r, 1).data(Qt.ItemDataRole.UserRole)
            for r in range(quick.table.rowCount())
            if quick.table.item(r, 1) is not None
        }
        expected = {i.id for i in win.db.form_items(form_id)}
        checks["form_filter_works"] = bool(shown) and shown == expected
        combo.setCurrentIndex(0)  # 还原为全部
        quick.refresh()
        print(f"  [{'✓' if checks['form_filter_works'] else '✗'}] form_filter_works")

    def check_quick_move() -> None:
        """及时行动选中表单后可按 position 上移，且使用条目 ID 而非可见行号。"""
        from PySide6.QtCore import Qt

        quick = win.panels[1]
        combo = quick.form_combo
        form_id = next(
            (combo.itemData(i) for i in range(combo.count()) if combo.itemData(i) is not None),
            None,
        )
        if form_id is None:
            checks["quick_move_works"] = False
            print("  [✗] quick_move_works")
            return
        combo.setCurrentIndex(combo.findData(form_id))
        quick.refresh()
        if quick.table.rowCount() < 2:
            checks["quick_move_works"] = False
            print("  [✗] quick_move_works")
            return

        original = [item.id for item in win.db.form_items(form_id)]
        selected_id = quick.table.item(1, 1).data(Qt.ItemDataRole.UserRole)
        neighbor_id = quick.table.item(0, 1).data(Qt.ItemDataRole.UserRole)
        quick.table.setCurrentCell(1, 1)
        quick._move(-1)
        moved = [item.id for item in win.db.form_items(form_id)]
        checks["quick_move_works"] = (
            moved.index(selected_id) < moved.index(neighbor_id)
            and quick.table.currentRow() == 0
        )
        win.db.set_form_order(form_id, original)  # 还原 smoke 数据
        combo.setCurrentIndex(0)
        quick.refresh()
        print(f"  [{'✓' if checks['quick_move_works'] else '✗'}] quick_move_works")

    def check_quick_priority_sort() -> None:
        """整张 quick 表单按 priority DESC, importance DESC 稳定排序。"""
        quick = win.panels[1]
        combo = quick.form_combo
        form_id = next(
            (combo.itemData(i) for i in range(combo.count()) if combo.itemData(i) is not None),
            None,
        )
        if form_id is None:
            checks["quick_priority_sort_works"] = False
            print("  [✗] quick_priority_sort_works")
            return

        combo.setCurrentIndex(combo.findData(form_id))
        original = win.db.form_items(form_id)
        scrambled = list(reversed(original))
        win.db.set_form_order(form_id, [item.id for item in scrambled])
        quick.refresh()
        quick._sort_by_priority()
        actual = win.db.form_items(form_id)
        expected = sorted(
            scrambled,
            key=lambda item: (-item.fix.priority, -item.fix.importance),
        )
        checks["quick_priority_sort_works"] = (
            [item.id for item in actual] == [item.id for item in expected]
            and quick.btn_sort_priority.isEnabled()
        )
        win.db.set_form_order(form_id, [item.id for item in original])
        combo.setCurrentIndex(0)
        quick.refresh()
        print(
            f"  [{'✓' if checks['quick_priority_sort_works'] else '✗'}] "
            "quick_priority_sort_works"
        )

    def check_tree_toggle_button() -> None:
        """真实触发 QToolButton.clicked(bool)，防止 bool 覆盖闭包中的 item_id。"""
        from PySide6.QtWidgets import QToolButton

        planner = win.panels[0]
        before = planner.table.rowCount()
        widget = planner.table.cellWidget(0, 0) if before else None
        button = widget.findChild(QToolButton) if widget is not None else None
        if button is None:
            checks["tree_toggle_button_works"] = False
        else:
            button.click()
            collapsed = planner.table.rowCount()
            valid_ids = all(
                type(value) is int and value > 0 for value in win.collapsed_item_ids
            )
            restored_widget = planner.table.cellWidget(0, 0)
            restored_button = (
                restored_widget.findChild(QToolButton)
                if restored_widget is not None else None
            )
            if restored_button is not None:
                restored_button.click()
            checks["tree_toggle_button_works"] = (
                collapsed < before
                and planner.table.rowCount() == before
                and valid_ids
                and not win.collapsed_item_ids
            )
        print(
            f"  [{'✓' if checks['tree_toggle_button_works'] else '✗'}] "
            "tree_toggle_button_works"
        )

    def grab_all(pass_idx: int = 0, index: int = 0) -> None:
        if pass_idx >= len(passes):
            check_form_filter()
            check_quick_move()
            check_quick_priority_sort()
            check_tree_toggle_button()
            ok = all(checks.values())
            print(f"smoke {'通过' if ok else '失败'} — 截图在 {shots}/")
            app.exit(0 if ok else 1)
            return

        lang, suffix = passes[pass_idx]
        if index == 0:
            win.db.set_setting("language", lang)
            win.reapply_language()
            verify(lang)
        if index >= len(names):
            grab_all(pass_idx + 1, 0)
            return

        win.sidebar.set_current_index(index)
        QTimer.singleShot(
            200, lambda: _grab(shots / f"{names[index]}{suffix}.png", win, pass_idx, index)
        )

    def _grab(path: Path, win, pass_idx: int, index: int) -> None:
        win.grab().save(str(path))
        print(f"  {path} ✓")
        grab_all(pass_idx, index + 1)

    QTimer.singleShot(400, lambda: grab_all(0))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
