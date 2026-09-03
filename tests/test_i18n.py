"""i18n 翻译层测试。"""

import unittest

from chronos_app import i18n
from chronos_app.i18n import SUPPORTED_LANGUAGES, set_language, tr


class TestI18n(unittest.TestCase):
    def tearDown(self):
        set_language("zh")

    def test_supported_languages(self):
        self.assertEqual(set(SUPPORTED_LANGUAGES), {"zh", "en"})

    def test_missing_key_falls_back_to_english(self):
        set_language("zh")
        self.assertEqual(tr("Something untranslated"), "Something untranslated")

    def test_zh_translation(self):
        set_language("zh")
        self.assertEqual(tr("Planner"), "计划表")
        self.assertEqual(tr("Quick Action"), "及时行动")

    def test_en_uses_key(self):
        set_language("en")
        self.assertEqual(tr("Planner"), "Planner")
        self.assertEqual(tr("Quick Action"), "Quick Action")

    def test_kwargs_formatting(self):
        set_language("zh")
        self.assertEqual(tr("Delete \"{name}\"?", name="x"), "删除「x」?")
        set_language("en")
        self.assertEqual(tr("Delete \"{name}\"?", name="x"), "Delete \"x\"?")

    def test_invalid_language_falls_back(self):
        set_language("fr")
        self.assertEqual(i18n.get_language(), "zh")

    def test_full_catalog_has_both_languages(self):
        """目录里每个条目都应有 zh 文案。"""
        for key, entry in i18n._CATALOG.items():
            self.assertIn("zh", entry, f"missing zh for {key!r}")

    def test_all_source_tr_keys_in_catalog(self):
        """源码里每个 tr("...") 键都必须存在于目录。

        否则 tr() 静默回退英文(如 placeholder 键拼写与目录不一致),
        zh 界面会悄悄显示英文。历史 bug: 及时行动占位符键 `#2`/`#3` 失配。
        """
        import ast
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        keys: set[str] = set()
        for path in [*root.joinpath("chronos_app").rglob("*.py"), root / "run.py"]:
            if ".venv" in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "tr"
                ):
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            keys.add(arg.value)
        missing = {k for k in keys if k not in i18n._CATALOG}
        self.assertFalse(missing, f"tr() 键不在目录中: {sorted(missing)}")


if __name__ == "__main__":
    unittest.main()
