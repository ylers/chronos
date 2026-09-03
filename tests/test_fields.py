"""FixFeature 位域编解码测试。"""

import unittest

from chronos_app.model.fields import (
    CATEGORY_MASK,
    Category,
    FixFeature,
    State,
)


class TestBitLayout(unittest.TestCase):
    def test_bit_positions(self):
        """验证位域布局: state<<14 | importance<<11 | priority<<8 | category。"""
        f = FixFeature(
            category=Category.EXPERIMENT,  # 5
            priority=7,
            importance=5,
            state=State.DONE,  # 3
        )
        expected = (3 << 14) | (5 << 11) | (7 << 8) | 5
        self.assertEqual(f.encode(), expected)

    def test_roundtrip(self):
        for f in (
            FixFeature(),
            FixFeature(category=1, priority=0, importance=0, state=0),
            FixFeature(category=5, priority=7, importance=7, state=3),
            FixFeature(category=2, priority=3, importance=4, state=2),
        ):
            self.assertEqual(FixFeature.decode(f.encode()), f)

    def test_fields_are_masked(self):
        """越界的值在打包时被截断到各自位宽。"""
        f = FixFeature(category=0x1FF, priority=0xF, importance=0xF, state=0xF)
        packed = f.encode()
        self.assertEqual(packed & CATEGORY_MASK, 0xFF)
        self.assertEqual((packed >> 8) & 0x7, 0x7)
        self.assertEqual((packed >> 11) & 0x7, 0x7)
        self.assertEqual((packed >> 14) & 0x3, 0x3)

    def test_extension_bits_ignored_on_decode(self):
        """高 16 位扩展字在 decode 时被忽略。"""
        f = FixFeature(category=Category.IDEA, priority=2, importance=3, state=1)
        packed = f.encode() | (0xBEEF << 16)  # 预留扩展位
        decoded = FixFeature.decode(packed)
        self.assertEqual(decoded, f)
        self.assertLess(decoded.encode(), 1 << 16)

    def test_invalid_values_rejected(self):
        with self.assertRaises(ValueError):
            FixFeature(category=-1)
        with self.assertRaises(TypeError):
            FixFeature(priority="high")  # type: ignore[arg-type]

    def test_with_changes(self):
        f = FixFeature(category=Category.SHORT_TERM)
        g = f.with_(state=State.DONE, priority=5)
        self.assertEqual(g.state, State.DONE)
        self.assertEqual(g.priority, 5)
        self.assertEqual(g.category, Category.SHORT_TERM)  # 原值不变
        self.assertEqual(f.state, State.NOT_STARTED)  # 原对象不被修改

    def test_labels_bilingual(self):
        from chronos_app.i18n import set_language

        set_language("zh")
        self.assertEqual(FixFeature(category=5).category_label, "实验")
        self.assertEqual(FixFeature(state=3).state_label, "已完成")

        set_language("en")
        self.assertEqual(FixFeature(category=5).category_label, "Experiment")
        self.assertEqual(FixFeature(state=3).state_label, "Done")

        set_language("zh")  # 还原,避免影响其他用例


if __name__ == "__main__":
    unittest.main()
