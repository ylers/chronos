"""SQLite 存储层测试。"""

import os
import sqlite3
import tempfile
import unittest

from chronos_app.model import Category, FixFeature, Item, Scope, State
from chronos_app.model.store import Database


class DatabaseTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db = Database(os.path.join(self._tmpdir.name, "test.db"))

    def tearDown(self):
        self.db.close()
        self._tmpdir.cleanup()


class TestMigration(unittest.TestCase):
    def test_old_items_table_adds_parent_before_index(self):
        """旧库没有 parent_id 时，应先加列再建索引，不能在启动阶段失败。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "legacy.db")
            conn = sqlite3.connect(path)
            conn.execute(
                "CREATE TABLE items ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, "
                "description TEXT NOT NULL DEFAULT '', fix_feature INTEGER NOT NULL, "
                "category INTEGER NOT NULL, priority INTEGER NOT NULL, "
                "importance INTEGER NOT NULL, state INTEGER NOT NULL, "
                "extendable TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, "
                "updated_at TEXT NOT NULL)"
            )
            conn.commit()
            conn.close()

            db = Database(path)
            columns = {row[1] for row in db._conn.execute("PRAGMA table_info(items)")}
            indexes = {row[1] for row in db._conn.execute("PRAGMA index_list(items)")}
            self.assertIn("parent_id", columns)
            self.assertIn("completed_at", columns)
            self.assertIn("idx_items_parent", indexes)
            db.close()


class TestItemCRUD(DatabaseTestCase):
    def test_create_and_get(self):
        item = self.db.create_item(
            "读论文",
            description="读完 attention 那篇",
            fix=FixFeature(category=Category.INSTANT, priority=3, importance=4),
        )
        self.assertIsNotNone(item.id)
        got = self.db.get_item(item.id)
        self.assertEqual(got.name, "读论文")
        self.assertEqual(got.fix.category, Category.INSTANT)
        self.assertEqual(got.fix.priority, 3)
        self.assertEqual(got.fix.importance, 4)
        self.assertEqual(got.fix.state, State.NOT_STARTED)
        self.assertNotEqual(got.created_at, "")
        self.assertEqual(got.created_at, got.updated_at)

    def test_mirror_columns_stay_in_sync(self):
        item = self.db.create_item(
            "任务A",
            fix=FixFeature(category=Category.LONG_TERM, priority=5, importance=2, state=2),
        )
        row = self.db._conn.execute(
            "SELECT fix_feature, category, priority, importance, state FROM items WHERE id=?",
            (item.id,),
        ).fetchone()
        f = FixFeature.decode(row["fix_feature"])
        self.assertEqual(row["category"], f.category)
        self.assertEqual(row["priority"], f.priority)
        self.assertEqual(row["importance"], f.importance)
        self.assertEqual(row["state"], f.state)

    def test_update_item(self):
        item = self.db.create_item("旧名")
        updated = self.db.update_item(
            item.id, name="新名", fix=item.fix.with_(state=State.DONE), now="2099-01-01T00:00:00"
        )
        self.assertEqual(updated.name, "新名")
        self.assertEqual(updated.fix.state, State.DONE)
        self.assertEqual(updated.updated_at, "2099-01-01T00:00:00")
        self.assertEqual(updated.created_at, item.created_at)

    def test_set_state(self):
        item = self.db.create_item("任务B")
        done = self.db.set_state(item.id, State.DONE, now="2026-08-19T10:00:00")
        self.assertEqual(done.fix.state, State.DONE)
        self.assertTrue(done.is_done)
        self.assertEqual(done.completed_at, "2026-08-19T10:00:00")

        reopened = self.db.set_state(
            item.id, State.NOT_STARTED, now="2026-08-19T11:00:00"
        )
        self.assertEqual(reopened.completed_at, "2026-08-19T10:00:00")

        done_again = self.db.set_state(
            item.id, State.DONE, now="2026-08-19T12:00:00"
        )
        self.assertEqual(done_again.completed_at, "2026-08-19T12:00:00")

        edited = self.db.update_item(
            item.id, name="任务B-改", now="2026-08-19T13:00:00"
        )
        self.assertEqual(edited.completed_at, "2026-08-19T12:00:00")

    def test_create_done_item_records_completion_time(self):
        item = self.db.create_item(
            "已完成", fix=FixFeature(state=State.DONE), now="2026-08-19T09:00:00"
        )
        self.assertEqual(item.completed_at, "2026-08-19T09:00:00")

    def test_delete(self):
        item = self.db.create_item("将被删除")
        self.assertTrue(self.db.delete_item(item.id))
        self.assertIsNone(self.db.get_item(item.id))
        self.assertFalse(self.db.delete_item(99999))

    def test_update_missing_returns_none(self):
        self.assertIsNone(self.db.update_item(99999, name="x"))
        self.assertIsNone(self.db.set_state(99999, State.DONE))

    def test_extendable_roundtrip(self):
        item = self.db.create_item(
            "实验1",
            fix=FixFeature(category=Category.EXPERIMENT),
            extendable={"parameters": {"温度": 25}, "result": "收敛", "iterations": []},
        )
        got = self.db.get_item(item.id)
        self.assertEqual(got.extendable["parameters"]["温度"], 25)
        self.assertEqual(got.extendable["result"], "收敛")

    def test_duplicate_item_copies_data_and_form_membership(self):
        form = self.db.create_form("即时", scope="quick")
        source = self.db.create_item(
            "原任务",
            description="原描述",
            fix=FixFeature(category=Category.INSTANT, priority=6, importance=5),
            extendable={"parameters": {"x": 1}, "iterations": [{"note": "run"}]},
        )
        tail = self.db.create_item(
            "后续任务", fix=FixFeature(category=Category.INSTANT)
        )
        self.assertTrue(self.db.add_to_form(form.id, source.id))
        self.assertTrue(self.db.add_to_form(form.id, tail.id))

        copy = self.db.duplicate_item(source.id, name="原任务（副本）")

        self.assertIsNotNone(copy)
        self.assertNotEqual(copy.id, source.id)
        self.assertEqual(copy.name, "原任务（副本）")
        self.assertEqual(copy.description, source.description)
        self.assertEqual(copy.fix, source.fix)
        self.assertEqual(copy.extendable, source.extendable)
        self.assertEqual(
            [item.id for item in self.db.form_items(form.id)],
            [source.id, copy.id, tail.id],
        )

    def test_duplicate_missing_item_returns_none(self):
        self.assertIsNone(self.db.duplicate_item(99999))

    def test_parent_child_relationship_and_cycle_guard(self):
        parent = self.db.create_item("父项")
        child_a = self.db.create_item("子项 A")
        child_b = self.db.create_item("子项 B", parent_id=parent.id)

        self.assertTrue(self.db.set_parent(child_a.id, parent.id))
        self.assertEqual(self.db.get_item(child_a.id).parent_id, parent.id)
        self.assertEqual(
            {item.id for item in self.db.children(parent.id)},
            {child_a.id, child_b.id},
        )
        self.assertFalse(self.db.set_parent(parent.id, parent.id))
        self.assertFalse(self.db.set_parent(parent.id, child_a.id))
        self.assertFalse(self.db.set_parent(child_a.id, 99999))

        self.assertTrue(self.db.set_parent(child_a.id, None))
        self.assertIsNone(self.db.get_item(child_a.id).parent_id)

    def test_delete_parent_promotes_children(self):
        parent = self.db.create_item("父项")
        child = self.db.create_item("子项", parent_id=parent.id)
        self.assertTrue(self.db.delete_item(parent.id))
        self.assertIsNone(self.db.get_item(child.id).parent_id)

    def test_duplicate_keeps_same_parent(self):
        parent = self.db.create_item("父项")
        child = self.db.create_item("子项", parent_id=parent.id)
        copied = self.db.duplicate_item(child.id)
        self.assertEqual(copied.parent_id, parent.id)


class TestQuery(DatabaseTestCase):
    def setUp(self):
        super().setUp()
        self.db.create_item("长期技能学习", fix=FixFeature(category=Category.LONG_TERM))
        self.db.create_item(
            "本周作业", fix=FixFeature(category=Category.SHORT_TERM, priority=6)
        )
        self.db.create_item(
            "读篇文章", fix=FixFeature(category=Category.INSTANT, state=State.DONE)
        )
        self.db.create_item(
            "实验A", fix=FixFeature(category=Category.EXPERIMENT, state=State.BLOCKED)
        )

    def test_filter_by_category(self):
        result = self.db.query(category=Category.LONG_TERM)
        self.assertEqual([i.name for i in result], ["长期技能学习"])

    def test_filter_by_state(self):
        result = self.db.query(state=State.DONE)
        self.assertEqual([i.name for i in result], ["读篇文章"])

    def test_filter_by_keyword(self):
        result = self.db.query(keyword="作业")
        self.assertEqual([i.name for i in result], ["本周作业"])
        result2 = self.db.query(keyword="实验")
        self.assertEqual([i.name for i in result2], ["实验A"])

    def test_count(self):
        counts = self.db.counts()
        self.assertEqual(counts[State.DONE], 1)
        self.assertEqual(counts[State.NOT_STARTED], 2)


class TestForm(DatabaseTestCase):
    def test_form_lifecycle(self):
        form = self.db.create_form("读书计划", "每天读一点")
        self.assertEqual(form.name, "读书计划")
        self.assertIsNotNone(self.db.get_form(form.id))

        items = [
            self.db.create_item(f"书{i}", fix=FixFeature(category=Category.LONG_TERM))
            for i in range(3)
        ]
        for it in items:
            self.db.add_to_form(form.id, it.id)

        in_form = self.db.form_items(form.id)
        self.assertEqual([i.name for i in in_form], ["书0", "书1", "书2"])
        # 位置递增
        rows = self.db._conn.execute(
            "SELECT position FROM form_items WHERE form_id=? ORDER BY position", (form.id,)
        ).fetchall()
        self.assertEqual([r["position"] for r in rows], [0, 1, 2])

        # 移除
        self.db.remove_from_form(form.id, items[0].id)
        self.assertEqual(len(self.db.form_items(form.id)), 2)

        # 删除表单不删条目
        self.assertTrue(self.db.delete_form(form.id))
        self.assertEqual(self.db.get_item(items[1].id).name, "书1")

    def test_reorder(self):
        form = self.db.create_form("顺序", scope=Scope.QUICK)
        items = [self.db.create_item(f"x{i}") for i in range(3)]
        for it in items:
            self.db.add_to_form(form.id, it.id)
        self.db.set_form_order(form.id, [items[2].id, items[0].id, items[1].id])
        got = self.db.form_items(form.id)
        self.assertEqual([i.id for i in got], [items[2].id, items[0].id, items[1].id])

    def test_add_to_form_scope_guard(self):
        """planner 表单只收长期/短期,即时/实验类目被拒;quick 表单相反。"""
        planner_form = self.db.create_form("读书", scope=Scope.PLANNER)
        quick_form = self.db.create_form("随手记", scope=Scope.QUICK)

        long_item = self.db.create_item(
            "长期", fix=FixFeature(category=Category.LONG_TERM)
        )
        instant_item = self.db.create_item(
            "即时", fix=FixFeature(category=Category.INSTANT)
        )
        exp_item = self.db.create_item(
            "实验", fix=FixFeature(category=Category.EXPERIMENT)
        )

        # 计划表: 收长期,拒即时/实验
        self.assertTrue(self.db.add_to_form(planner_form.id, long_item.id))
        self.assertFalse(self.db.add_to_form(planner_form.id, instant_item.id))
        self.assertFalse(self.db.add_to_form(planner_form.id, exp_item.id))

        # 及时行动: 收即时,拒长期
        self.assertTrue(self.db.add_to_form(quick_form.id, instant_item.id))
        self.assertFalse(self.db.add_to_form(quick_form.id, long_item.id))

        self.assertEqual(len(self.db.form_items(planner_form.id)), 1)
        self.assertEqual(len(self.db.form_items(quick_form.id)), 1)

    def test_list_forms_by_scope(self):
        self.db.create_form("读书计划", scope=Scope.PLANNER)
        self.db.create_form("随手记", scope=Scope.QUICK)
        self.assertEqual([f.scope for f in self.db.list_forms()].count(Scope.PLANNER), 1)
        self.assertEqual([f.scope for f in self.db.list_forms()].count(Scope.QUICK), 1)
        self.assertEqual([f.name for f in self.db.list_forms(Scope.QUICK)], ["随手记"])
        self.assertEqual(
            [f.name for f in self.db.list_forms(Scope.PLANNER)], ["读书计划"]
        )

    def test_update_item_reconciles_form(self):
        """改类目离开原 scope 后,条目自动移出该表单。"""
        quick_form = self.db.create_form("随手记", scope=Scope.QUICK)
        item = self.db.create_item(
            "即时任务", fix=FixFeature(category=Category.INSTANT)
        )
        self.db.add_to_form(quick_form.id, item.id)
        self.assertEqual(len(self.db.form_items(quick_form.id)), 1)

        # 改成长期 → 离开 quick scope → 移出表单
        self.db.update_item(
            item.id, fix=item.fix.with_(category=Category.LONG_TERM)
        )
        self.assertEqual(len(self.db.form_items(quick_form.id)), 0)

    def test_transfer_item_between_same_scope_forms(self):
        source = self.db.create_form("来源", scope=Scope.QUICK)
        target = self.db.create_form("目标", scope=Scope.QUICK)
        first = self.db.create_item(
            "第一项", fix=FixFeature(category=Category.INSTANT)
        )
        moved = self.db.create_item(
            "待转移", fix=FixFeature(category=Category.IDEA)
        )
        tail = self.db.create_item(
            "最后项", fix=FixFeature(category=Category.INSTANT)
        )
        existing = self.db.create_item(
            "目标已有", fix=FixFeature(category=Category.INSTANT)
        )
        for item in (first, moved, tail):
            self.assertTrue(self.db.add_to_form(source.id, item.id))
        self.assertTrue(self.db.add_to_form(target.id, existing.id))

        self.assertTrue(self.db.transfer_item(moved.id, source.id, target.id))

        self.assertEqual(
            [item.id for item in self.db.form_items(source.id)],
            [first.id, tail.id],
        )
        self.assertEqual(
            [item.id for item in self.db.form_items(target.id)],
            [existing.id, moved.id],
        )
        positions = self.db._conn.execute(
            "SELECT position FROM form_items WHERE form_id=? ORDER BY position",
            (source.id,),
        ).fetchall()
        self.assertEqual([row["position"] for row in positions], [0, 1])

    def test_transfer_item_rejects_cross_scope_and_missing_membership(self):
        quick_a = self.db.create_form("Q1", scope=Scope.QUICK)
        quick_b = self.db.create_form("Q2", scope=Scope.QUICK)
        planner = self.db.create_form("P", scope=Scope.PLANNER)
        item = self.db.create_item(
            "即时", fix=FixFeature(category=Category.INSTANT)
        )
        self.assertTrue(self.db.add_to_form(quick_a.id, item.id))

        self.assertFalse(self.db.transfer_item(item.id, quick_a.id, planner.id))
        self.assertFalse(self.db.transfer_item(item.id, quick_b.id, quick_a.id))
        self.assertFalse(self.db.transfer_item(item.id, quick_a.id, quick_a.id))
        self.assertEqual([x.id for x in self.db.form_items(quick_a.id)], [item.id])

    def test_query_category_in(self):
        self.db.create_item("长期", fix=FixFeature(category=Category.LONG_TERM))
        self.db.create_item("即时", fix=FixFeature(category=Category.INSTANT))
        self.db.create_item("灵感", fix=FixFeature(category=Category.IDEA))
        result = self.db.query(
            category_in=[Category.INSTANT, Category.IDEA]
        )
        self.assertEqual({i.name for i in result}, {"即时", "灵感"})

    def test_query_form_with_multi_param_filter(self):
        """表单查询叠加多参数子句(如 category_in+state)时占位符对齐。"""
        form = self.db.create_form("随手记", scope=Scope.QUICK)
        a = self.db.create_item("即时A", fix=FixFeature(category=Category.INSTANT))
        b = self.db.create_item("即时B", fix=FixFeature(category=Category.INSTANT, state=State.DONE))
        self.db.add_to_form(form.id, a.id)
        self.db.add_to_form(form.id, b.id)
        result = self.db.query(
            form_id=form.id,
            category_in=[Category.INSTANT, Category.IDEA],
            state_not=State.DONE,
        )
        self.assertEqual([i.name for i in result], ["即时A"])


    def test_unfiled_scope_and_item_forms(self):
        quick = self.db.create_form("Q", scope=Scope.QUICK)
        planner = self.db.create_form("P", scope=Scope.PLANNER)
        loose = self.db.create_item("未归档", fix=FixFeature(category=Category.INSTANT))
        filed = self.db.create_item("已归档", fix=FixFeature(category=Category.IDEA))
        planned = self.db.create_item("计划", fix=FixFeature(category=Category.LONG_TERM))
        self.db.add_to_form(quick.id, filed.id)
        self.db.add_to_form(planner.id, planned.id)

        result = self.db.query(
            category_in=[Category.INSTANT, Category.IDEA],
            unfiled_scope=Scope.QUICK,
        )
        self.assertEqual([item.id for item in result], [loose.id])
        self.assertEqual([form.name for form in self.db.item_forms(filed.id)], ["Q"])
        self.assertEqual(
            [form.name for form in self.db.item_forms(filed.id, Scope.PLANNER)], []
        )


class TestSettings(DatabaseTestCase):
    def test_settings_roundtrip(self):
        self.assertIsNone(self.db.get_setting("bg_color"))
        self.assertEqual(self.db.get_setting("missing", "default"), "default")
        self.db.set_setting("bg_color", "#1e1e1e")
        self.assertEqual(self.db.get_setting("bg_color"), "#1e1e1e")
        self.db.set_setting("bg_color", "#2b2b2b")
        self.assertEqual(self.db.get_setting("bg_color"), "#2b2b2b")
        # 复杂值
        self.db.set_setting("theme", {"dark": True, "font": 12})
        self.assertEqual(self.db.get_setting("theme"), {"dark": True, "font": 12})


if __name__ == "__main__":
    unittest.main()
