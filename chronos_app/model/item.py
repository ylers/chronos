"""条目 (Item) 与 extendable feature。

extendable feature 是「变长」的 key-value 参数,随类别不同而不同,
以 JSON 字典存储,部分参数由 fix feature 派生(如实验类默认带 parameters)。
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from .fields import Category, FixFeature

# 每类条目的默认 extendable 参数模板
DEFAULT_EXTENDABLE_TEMPLATES: dict[int, dict[str, Any]] = {
    Category.EXPERIMENT: {
        "parameters": {},  # 实验参数: {"温度": 25, "迭代": 1000, ...}
        "result": "",      # 结论
        "iterations": [],  # 运行记录: [{"time": ..., "note": ...}, ...]
    },
    Category.IDEA: {
        "tags": [],
    },
    Category.LONG_TERM: {
        "deadline": None,  # 期望完成时间(ISO 字符串)
        "progress": 0,     # 0-100
    },
    Category.SHORT_TERM: {
        "deadline": None,
    },
    Category.INSTANT: {
        "due": None,  # 期望即时完成的时间
    },
    Category.UNDEFINED: {
        "tags": [],
    },
}


def default_extendable(category: int) -> dict[str, Any]:
    """返回某类别条目的 extendable 参数副本(深拷贝,互不影响)。"""
    return copy.deepcopy(DEFAULT_EXTENDABLE_TEMPLATES.get(category, {}))


@dataclass
class Item:
    """一条完整记录: id + name + description + fix feature + extendable feature。"""

    id: int | None
    name: str
    description: str = ""
    fix: FixFeature = field(default_factory=FixFeature)
    extendable: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    completed_at: str | None = None
    parent_id: int | None = None

    # -- 便捷 ---------------------------------------------------------------

    @property
    def is_done(self) -> bool:
        return self.fix.state == 3  # State.DONE

    def touch(self, now: str | None = None) -> None:
        """更新 updated_at;创建时同时补 created_at。"""
        if not now:
            now = _now()
        self.updated_at = now
        if not self.created_at:
            self.created_at = now

    def extendable_get(self, key: str, default: Any = None) -> Any:
        return self.extendable.get(key, default)

    def extendable_set(self, key: str, value: Any) -> None:
        self.extendable[key] = value


def _now() -> str:
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")
