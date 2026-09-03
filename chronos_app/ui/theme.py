"""主题: 从设置(背景色/强调色/明暗/字号)生成 QSS。

背景色可调 → 基于背景色推导整套调色板,而非写死单一皮肤。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

# 默认设置(写入 settings 表的初值)
DEFAULT_SETTINGS: dict[str, Any] = {
    "bg_color": "#1e1e1e",
    "accent_color": "#0ea5e9",
    "dark": True,
    "font_size": 13,
    "language": "zh",
}

_ACCENT_ANCHORS = {
    "light": "#006bb8",
    "dark": "#0ea5e9",
}


# -- 颜色工具 -------------------------------------------------------------

def hex_to_rgb(hexstr: str) -> tuple[int, int, int]:
    hexstr = hexstr.lstrip("#")
    if len(hexstr) == 3:
        hexstr = "".join(c * 2 for c in hexstr)
    return tuple(int(hexstr[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def adjust(hexstr: str, delta: int) -> str:
    """每通道加减 delta(用于推导边框/悬浮等相邻色)。"""
    r, g, b = hex_to_rgb(hexstr)
    clamp = lambda v: max(0, min(255, v))  # noqa: E731
    return rgb_to_hex(clamp(r + delta), clamp(g + delta), clamp(b + delta))


def blend(fg_hex: str, bg_hex: str, t: float) -> str:
    """按比例 t 把 fg 混合进 bg,得到带半透明观感的实色。"""
    fr, fg, fb = hex_to_rgb(fg_hex)
    br, bg_, bb = hex_to_rgb(bg_hex)
    mix = lambda a, b: round(a * t + b * (1 - t))  # noqa: E731
    return rgb_to_hex(mix(fr, br), mix(fg, bg_), mix(fb, bb))


def luminance(hexstr: str) -> float:
    r, g, b = hex_to_rgb(hexstr)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


# -- 调色板 ---------------------------------------------------------------

@dataclass(frozen=True)
class Palette:
    bg: str
    sidebar_bg: str
    panel_bg: str
    header_bg: str
    input_bg: str
    fg: str
    muted: str
    border: str
    accent: str
    accent_hover: str
    selection: str
    hover: str
    danger: str
    success: str
    warn: str
    done_fg: str


def build_palette(bg_color: str, accent_color: str, dark: bool) -> Palette:
    if dark:
        fg = "#e0e0e0"
        muted = adjust(fg, -70)
        border = adjust(bg_color, +14)
        sidebar_bg = adjust(bg_color, -5)
        panel_bg = bg_color
        header_bg = adjust(bg_color, -8)
        input_bg = adjust(bg_color, +6)
        hover = adjust(bg_color, +9)
        done_fg = "#6a6a6a"
    else:
        fg = "#262626"
        muted = adjust(fg, +55)
        border = adjust(bg_color, -18)
        sidebar_bg = adjust(bg_color, -8)
        panel_bg = bg_color
        header_bg = adjust(bg_color, -11)
        input_bg = "#ffffff"
        hover = adjust(bg_color, -6)
        done_fg = "#9a9a9a"

    if not dark:
        accent_color = _ACCENT_ANCHORS["light"]

    return Palette(
        bg=bg_color,
        sidebar_bg=sidebar_bg,
        panel_bg=panel_bg,
        header_bg=header_bg,
        input_bg=input_bg,
        fg=fg,
        muted=muted,
        border=border,
        accent=accent_color,
        accent_hover=adjust(accent_color, +18 if dark else -12),
        selection=blend(accent_color, panel_bg, 0.30),
        hover=hover,
        danger="#f44336",
        success="#4caf50",
        warn="#ffb020",
        done_fg=done_fg,
    )


def build_qss(palette: Palette, font_size: int) -> str:
    p = palette
    return f"""
* {{ font-size: {font_size}px; }}
QMainWindow, QWidget#Root {{ background: {p.bg}; color: {p.fg}; }}
QWidget {{ color: {p.fg}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

/* 侧栏 */
QListWidget#Sidebar {{
    background: {p.sidebar_bg};
    border: none;
    outline: 0;
}}
QListWidget#Sidebar::item {{
    height: 52px;
    border-left: 3px solid transparent;
    color: {p.muted};
}}
QListWidget#Sidebar::item:hover {{ background: {p.hover}; color: {p.fg}; }}
QListWidget#Sidebar::item:selected {{
    background: {p.panel_bg};
    border-left: 3px solid {p.accent};
    color: {p.fg};
}}
QLabel#Brand {{
    background: {p.sidebar_bg};
    color: {p.accent};
    font-size: {font_size + 3}px;
    font-weight: bold;
    qproperty-alignment: AlignCenter;
}}

/* 面板标题 */
QLabel#SectionTitle {{ font-size: {font_size + 5}px; font-weight: bold; }}
QLabel#SectionSub {{ color: {p.muted}; }}

/* 列表 */
QListWidget {{
    background: {p.panel_bg};
    border: 1px solid {p.border};
    border-radius: 4px;
    outline: 0;
}}
QListWidget::item {{ padding: 4px 6px; }}
QListWidget::item:selected {{ background: {p.selection}; color: {p.fg}; }}
QListWidget::item:hover {{ background: {p.hover}; }}

/* 表格 */
QTableWidget, QTableView {{
    background: {p.panel_bg};
    alternate-background-color: {p.hover};
    gridline-color: transparent;
    border: 1px solid {p.border};
    border-radius: 4px;
    selection-background-color: {p.selection};
    selection-color: {p.fg};
}}
QHeaderView::section {{
    background: {p.header_bg};
    color: {p.muted};
    border: none;
    border-bottom: 1px solid {p.border};
    padding: 5px 8px;
}}
QTableWidget::item {{ padding: 3px 6px; }}

/* 按钮 */
QPushButton {{
    background: {p.sidebar_bg};
    color: {p.fg};
    border: 1px solid {p.border};
    border-radius: 4px;
    padding: 5px 14px;
}}
QPushButton:hover {{ background: {p.hover}; border-color: {p.accent}; }}
QPushButton:pressed {{ background: {p.selection}; }}
QPushButton:disabled {{ color: {p.muted}; }}
QPushButton#Primary {{
    background: {p.accent};
    color: white;
    border: none;
    font-weight: bold;
}}
QPushButton#Primary:hover {{ background: {p.accent_hover}; }}
QPushButton#Primary:disabled {{ background: {p.muted}; color: {p.fg}; }}
QPushButton#Danger {{ color: {p.danger}; }}
QPushButton#Ghost {{ border: none; background: transparent; color: {p.muted}; }}
QPushButton#Ghost:hover {{ background: {p.hover}; color: {p.fg}; }}
QToolButton#TreeToggle {{
    background: {p.input_bg};
    color: {p.muted};
    border: 1px solid {p.border};
    border-radius: 11px;
    font-weight: bold;
    padding: 0;
}}
QToolButton#TreeToggle:hover {{
    background: {p.selection};
    color: {p.accent};
    border-color: {p.accent};
}}
QToolButton#TreeToggle:pressed {{ background: {p.accent}; color: white; }}

/* 输入 */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{
    background: {p.input_bg};
    color: {p.fg};
    border: 1px solid {p.border};
    border-radius: 4px;
    padding: 5px 8px;
    selection-background-color: {p.selection};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus {{
    border-color: {p.accent};
}}
QTextEdit, QPlainTextEdit {{
    background: {p.input_bg};
    color: {p.fg};
    border: 1px solid {p.border};
    border-radius: 4px;
    padding: 4px;
    selection-background-color: {p.selection};
}}
QComboBox QAbstractItemView {{
    background: {p.input_bg};
    color: {p.fg};
    selection-background-color: {p.selection};
    border: 1px solid {p.border};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: none; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid {p.muted}; }}

/* 0-7 评分滑条 */
QSlider::groove:horizontal {{
    height: 6px;
    background: {p.border};
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {p.accent};
    border-radius: 3px;
}}
QSlider::add-page:horizontal {{
    background: {p.border};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {p.accent};
    border: 2px solid {p.fg};
    width: 16px;
    margin: -6px 0;
    border-radius: 9px;
}}
QSlider::handle:horizontal:hover {{ background: {p.accent_hover}; }}

/* 分组框 */
QGroupBox {{
    border: 1px solid {p.border};
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 6px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {p.muted};
}}

/* 状态标签 */
QLabel#StateBadge {{ padding: 1px 8px; border-radius: 9px; font-size: {font_size - 1}px; }}

/* 复选框 / 单选框 */
QCheckBox, QRadioButton {{ spacing: 6px; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 15px; height: 15px; }}

/* 滚动条 */
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {p.border}; border-radius: 5px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {p.muted}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {p.border}; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* 工具提示 / 菜单 / 对话框 */
QToolTip {{
    background: {p.header_bg};
    color: {p.fg};
    border: 1px solid {p.border};
    padding: 4px 6px;
}}
QMenu {{
    background: {p.input_bg};
    color: {p.fg};
    border: 1px solid {p.border};
}}
QMenu::item {{ padding: 5px 22px 5px 14px; }}
QMenu::item:selected {{ background: {p.selection}; }}
QDialog {{ background: {p.bg}; }}
QSplitter::handle {{ background: {p.border}; }}
"""


def apply_theme(app: Any, settings: dict[str, Any]) -> Palette:
    """把设置应用到 QApplication,返回当前调色板。"""
    bg = str(settings.get("bg_color") or DEFAULT_SETTINGS["bg_color"])
    accent = str(settings.get("accent_color") or DEFAULT_SETTINGS["accent_color"])
    dark = bool(settings.get("dark", True))
    font_size = int(settings.get("font_size") or DEFAULT_SETTINGS["font_size"])
    palette = build_palette(bg, accent, dark)
    app.setStyleSheet(build_qss(palette, font_size))
    return palette
