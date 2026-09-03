"""fix feature 位域编码。

GUI/功能等「定长」信息用一个 16 位整数紧凑表达 (state<<14 | importance<<11 | priority<<8 | category):

    bits  0-7   category   条目类别   (8 bits, 0-5 已定义)
    bits  8-10  priority   优先级    (3 bits, 0-7)
    bits 11-13  importance 重要度    (3 bits, 0-7)
    bits 14-15  state      状态      (2 bits, 0-3)

bits 16-31 预留为扩展字(deadline / repeat 等未来固定字段)。
"""

from __future__ import annotations

from dataclasses import dataclass, replace


class Category:
    """条目类别。"""

    UNDEFINED = 0
    LONG_TERM = 1
    SHORT_TERM = 2
    INSTANT = 3
    IDEA = 4
    EXPERIMENT = 5


class State:
    """条目状态。"""

    NOT_STARTED = 0
    PLANNED = 1
    BLOCKED = 2
    DONE = 3


class Scope:
    """面板归属(Planner 与 Quick Action 互斥,表单按 scope 隔离)。"""

    PLANNER = "planner"  # 长期 + 短期 → 计划表
    QUICK = "quick"      # 即时 + 灵感 + 未分类 → 及时行动


# 各面板可容纳的类目
PLANNER_CATEGORIES = frozenset({Category.LONG_TERM, Category.SHORT_TERM})
QUICK_CATEGORIES = frozenset({Category.UNDEFINED, Category.INSTANT, Category.IDEA})


def scope_of_category(category: int) -> str | None:
    """条目类目属于哪个面板 scope;实验等不属于任何表单面板,返回 None。"""
    if category in PLANNER_CATEGORIES:
        return Scope.PLANNER
    if category in QUICK_CATEGORIES:
        return Scope.QUICK
    return None


# 规范键(英文),经 i18n 取当前语言文案
CATEGORY_KEYS = {
    Category.UNDEFINED: "Uncategorized",
    Category.LONG_TERM: "Long-term Task",
    Category.SHORT_TERM: "Short-term Task",
    Category.INSTANT: "Instant Task",
    Category.IDEA: "Idea",
    Category.EXPERIMENT: "Experiment",
}

STATE_KEYS = {
    State.NOT_STARTED: "Not started",
    State.PLANNED: "Planned",
    State.BLOCKED: "Blocked",
    State.DONE: "Done",
}

VALID_CATEGORIES = frozenset(CATEGORY_KEYS)

PRIORITY_LABELS = {i: str(i) for i in range(8)}
IMPORTANCE_LABELS = {i: str(i) for i in range(8)}


def category_label(category: int) -> str:
    from chronos_app.i18n import tr

    return tr(CATEGORY_KEYS.get(category, f"Category {category}"))


def state_label(state: int) -> str:
    from chronos_app.i18n import tr

    return tr(STATE_KEYS.get(state, f"State {state}"))


def category_choices() -> list[tuple[int, str]]:
    return [(v, category_label(v)) for v in sorted(CATEGORY_KEYS)]


def state_choices() -> list[tuple[int, str]]:
    return [(v, state_label(v)) for v in sorted(STATE_KEYS)]

# 位域掩码
CATEGORY_MASK = 0xFF
PRIORITY_MASK = 0x7
IMPORTANCE_MASK = 0x7
STATE_MASK = 0x3

_PRIORITY_SHIFT = 8
_IMPORTANCE_SHIFT = 11
_STATE_SHIFT = 14

# 有效位总掩码(低 16 位),高 16 位留给扩展字
_FIX_MASK = 0xFFFF


@dataclass(frozen=True)
class FixFeature:
    """条目定长特征: category + priority + importance + state。"""

    category: int = Category.UNDEFINED
    priority: int = 0
    importance: int = 0
    state: int = State.NOT_STARTED

    def __post_init__(self) -> None:
        for name, value in (
            ("category", self.category),
            ("priority", self.priority),
            ("importance", self.importance),
            ("state", self.state),
        ):
            if not isinstance(value, int):
                raise TypeError(f"{name} 必须是整数, got {value!r}")
            if value < 0:
                raise ValueError(f"{name} 不能为负: {value}")

    # -- 编解码 -------------------------------------------------------------

    def encode(self) -> int:
        """打包为 16 位整数。"""
        return (
            (self.state & STATE_MASK) << _STATE_SHIFT
            | (self.importance & IMPORTANCE_MASK) << _IMPORTANCE_SHIFT
            | (self.priority & PRIORITY_MASK) << _PRIORITY_SHIFT
            | (self.category & CATEGORY_MASK)
        )

    @classmethod
    def decode(cls, packed: int) -> "FixFeature":
        """从 16 位整数还原。高位扩展字会被忽略。"""
        packed &= _FIX_MASK
        return cls(
            category=packed & CATEGORY_MASK,
            priority=(packed >> _PRIORITY_SHIFT) & PRIORITY_MASK,
            importance=(packed >> _IMPORTANCE_SHIFT) & IMPORTANCE_MASK,
            state=(packed >> _STATE_SHIFT) & STATE_MASK,
        )

    def with_(self, **changes: int) -> "FixFeature":
        """返回改动了指定字段的新实例。"""
        return replace(self, **changes)

    # -- 便捷 ---------------------------------------------------------------

    @property
    def category_label(self) -> str:
        return category_label(self.category)

    @property
    def state_label(self) -> str:
        return state_label(self.state)

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return (
            f"FixFeature(category={self.category}/{self.category_label}, "
            f"priority={self.priority}, importance={self.importance}, "
            f"state={self.state}/{self.state_label})"
        )
