"""及时行动面板的快加 DSL 解析测试。"""

import unittest

from chronos_app.model import Category
from chronos_app.ui.quick_panel import parse_quick_add


class TestParseQuickAdd(unittest.TestCase):
    def test_plain_name_defaults(self):
        name, fix = parse_quick_add("读篇文章")
        self.assertEqual(name, "读篇文章")
        self.assertEqual(fix.category, Category.INSTANT)
        self.assertEqual(fix.priority, 3)
        self.assertEqual(fix.importance, 3)

    def test_priority_and_category(self):
        name, fix = parse_quick_add("打印文件 !7 #2")
        self.assertEqual(name, "打印文件")
        self.assertEqual(fix.priority, 7)
        self.assertEqual(fix.category, Category.SHORT_TERM)

    def test_importance(self):
        name, fix = parse_quick_add("任务 *5 !2")
        self.assertEqual(name, "任务")
        self.assertEqual(fix.importance, 5)
        self.assertEqual(fix.priority, 2)

    def test_whitespace_cleaned(self):
        name, fix = parse_quick_add("  收快递  #3  ")
        self.assertEqual(name, "收快递")
        self.assertEqual(fix.category, Category.INSTANT)

    def test_unknown_category_falls_back(self):
        name, fix = parse_quick_add("未知 #9")
        self.assertEqual(name, "未知")
        self.assertEqual(fix.category, Category.UNDEFINED)

    def test_priority_clamped(self):
        name, fix = parse_quick_add("极限 !99")
        self.assertEqual(name, "极限")
        self.assertEqual(fix.priority, 7)


if __name__ == "__main__":
    unittest.main()
