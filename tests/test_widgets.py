"""共享 Qt 控件测试。"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from chronos_app.model import FixFeature
from chronos_app.widgets.helpers import (
    InlineScoreSlider,
    ItemDialog,
    ScoreSlider,
    hierarchy_rows,
)


class TestScoreSlider(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_slider_and_spin_are_synchronized(self):
        score = ScoreSlider(5)
        self.assertEqual(score.value(), 5)
        self.assertEqual(score.spin.value(), 5)

        score.slider.setValue(2)
        self.assertEqual(score.spin.value(), 2)
        score.spin.setValue(7)
        self.assertEqual(score.slider.value(), 7)

    def test_value_is_clamped_to_bitfield_range(self):
        score = ScoreSlider(-10)
        self.assertEqual(score.value(), 0)
        score.setValue(99)
        self.assertEqual(score.value(), 7)

    def test_item_dialog_returns_slider_values(self):
        dialog = ItemDialog(
            None,
            "test",
            item_name="item",
            fix=FixFeature(priority=6, importance=4),
        )
        self.assertIsInstance(dialog.priority, ScoreSlider)
        self.assertIsInstance(dialog.importance, ScoreSlider)
        dialog.priority.setValue(3)
        dialog.importance.spin.setValue(7)
        values = dialog.values()
        self.assertEqual(values["fix"].priority, 3)
        self.assertEqual(values["fix"].importance, 7)

    def test_inline_slider_reports_each_change(self):
        changed = []
        score = InlineScoreSlider(3, changed.append)
        score.slider.setValue(6)
        self.assertEqual(score.value(), 6)
        self.assertEqual(score.number.text(), "6")
        self.assertEqual(changed, [6])

    def test_hierarchy_rows_places_children_after_parent(self):
        from chronos_app.model import Item

        child = Item(2, "child", parent_id=1)
        grandchild = Item(3, "grandchild", parent_id=2)
        parent = Item(1, "parent")
        other = Item(4, "other")
        rows = hierarchy_rows([child, other, grandchild, parent])
        self.assertEqual(
            [(item.id, depth) for item, depth in rows],
            [(4, 0), (1, 0), (2, 1), (3, 2)],
        )

        collapsed = hierarchy_rows([child, other, grandchild, parent], {parent.id})
        self.assertEqual(
            [(item.id, depth) for item, depth in collapsed],
            [(4, 0), (1, 0)],
        )


if __name__ == "__main__":
    unittest.main()
