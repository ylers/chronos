"""chronos_cli 命令行为测试。"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from chronos_app.model import Database
from chronos_cli import main


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "cli.db")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args: str) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(["--db", self.path, *args])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_item_add_list_show_delete(self):
        code, out, _ = self.run_cli(
            "item", "add", "CLI任务", "--category", "instant",
            "--priority", "7", "--importance", "5",
        )
        self.assertEqual(code, 0)
        self.assertIn("已创建 Item", out)

        db = Database(self.path)
        item = db.query()[0]
        db.close()

        code, out, _ = self.run_cli("item", "show", str(item.id), "--json")
        self.assertEqual(code, 0)
        self.assertIn('"priority": 7', out)
        self.assertIn('"importance": 5', out)

        code, out, _ = self.run_cli("item", "list", "--search", "CLI")
        self.assertEqual(code, 0)
        self.assertIn("CLI任务", out)

        code, out, _ = self.run_cli("item", "delete", str(item.id), "--yes")
        self.assertEqual(code, 0)
        self.assertIn("已删除", out)

    def test_form_scope_and_membership(self):
        self.assertEqual(
            self.run_cli("form", "add", "即时表", "--scope", "quick")[0], 0
        )
        db = Database(self.path)
        form = db.list_forms()[0]
        db.close()

        code, _, err = self.run_cli(
            "item", "add", "长期任务", "--category", "long", "--form", str(form.id)
        )
        self.assertEqual(code, 2)
        self.assertIn("不属于 quick 表单", err)

        db = Database(self.path)
        self.assertEqual(db.query(), [])  # scope 失败不能留下半成品 Item
        db.close()

        code, _, _ = self.run_cli(
            "item", "add", "即时任务", "--category", "3", "--form", str(form.id)
        )
        self.assertEqual(code, 0)
        db = Database(self.path)
        self.assertEqual([item.name for item in db.form_items(form.id)], ["即时任务"])
        db.close()

    def test_item_copy(self):
        self.run_cli("item", "add", "原件", "--category", "idea")
        db = Database(self.path)
        source = db.query()[0]
        db.close()
        code, out, _ = self.run_cli("item", "copy", str(source.id))
        self.assertEqual(code, 0)
        self.assertIn("原件（副本）", out)

    def test_form_move_item_same_scope_only(self):
        self.run_cli("form", "add", "来源", "--scope", "quick")
        self.run_cli("form", "add", "目标", "--scope", "quick")
        self.run_cli("form", "add", "计划", "--scope", "planner")
        self.run_cli("item", "add", "待转移", "--category", "instant", "--form", "1")

        code, out, _ = self.run_cli("form", "move-item", "1", "2", "1")
        self.assertEqual(code, 0)
        self.assertIn("转移到 Form #2", out)
        db = Database(self.path)
        self.assertEqual(db.form_items(1), [])
        self.assertEqual([item.id for item in db.form_items(2)], [1])
        db.close()

        code, _, err = self.run_cli("form", "move-item", "2", "3", "1")
        self.assertEqual(code, 2)
        self.assertIn("不能跨类型转移", err)
        db = Database(self.path)
        self.assertEqual([item.id for item in db.form_items(2)], [1])
        db.close()


if __name__ == "__main__":
    unittest.main()
