"""轻量 i18n: 英文为规范键, 按当前语言取文案。

用法:
    from chronos_app.i18n import set_language, tr
    set_language("en")
    tr("Planner")            -> "Planner"
    tr("Delete \\"{name}\\"?", name="x") -> 按语言格式化
"""

from __future__ import annotations

SUPPORTED_LANGUAGES = {
    "zh": "中文",
    "en": "English",
}

# key(英文) -> {语言: 文案}; 缺失时回退到英文键本身
_CATALOG: dict[str, dict[str, str]] = {
    # -- 侧栏 / 窗口 --
    "Planner": {"zh": "计划表"},
    "All Items": {"zh": "全部条目"},
    "Quick Action": {"zh": "及时行动"},
    "Experiments": {"zh": "实验管理"},
    "Reference": {"zh": "参考"},
    "Settings": {"zh": "设置"},
    "chronos — Daily · Workflow · Experiments": {"zh": "chronos — 日常 · 工作流 · 实验"},

    # -- 参考页 --
    "Settings and field meanings": {"zh": "设置与字段含义"},
    "Fix Feature Fields": {"zh": "fix feature 字段"},
    "Field": {"zh": "字段"},
    "Bits": {"zh": "位宽"},
    "Values": {"zh": "取值"},
    "Meaning": {"zh": "含义"},
    "Encoding: state<<14 | importance<<11 | priority<<8 | category": {
        "zh": "编码: state<<14 | importance<<11 | priority<<8 | category"
    },
    "Reserved: bits 16-31 for future fields": {"zh": "预留: 16-31 位留给未来字段"},
    "Category of the item": {"zh": "条目类别"},
    "Task priority, 0-7 (higher is more urgent)": {"zh": "任务优先级, 0-7(越大越紧急)"},
    "How important it is, 0-7 (higher is more important)": {
        "zh": "重要程度, 0-7(越大越重要)"
    },
    "Current workflow state": {"zh": "当前进度状态"},
    "Current Settings": {"zh": "当前设置"},
    "Setting": {"zh": "设置项"},
    "Current value": {"zh": "当前值"},
    "Interface language": {"zh": "界面语言"},
    "Main background color": {"zh": "主背景色"},
    "Accent color for selection & highlights": {"zh": "选中与高亮的强调色"},
    "Dark theme switch": {"zh": "深色主题开关"},
    "Base font size (px)": {"zh": "基础字号(px)"},
    "Yes": {"zh": "是"},
    "No": {"zh": "否"},
    "Item & Quick-add": {"zh": "条目与快加"},
    "Item structure: id · name · description · fix feature · extendable params": {
        "zh": "条目结构: id · 名称 · 描述 · fix feature · extendable 参数"
    },
    "Quick-add syntax: name !priority #category *importance": {
        "zh": "快加语法: 名称 !优先级 #类别 *重要度"
    },
    "Scopes: long/short → Planner · instant/idea → Quick · experiment → Experiments": {
        "zh": "归属: 长期/短期 → 计划表 · 即时/灵感 → 及时行动 · 实验 → 实验管理"
    },

    # -- 全部条目 --
    "Browse and manage every item in one place": {"zh": "一处浏览与管理所有条目"},
    "All states": {"zh": "全部状态"},
    "Sort": {"zh": "排序"},
    "By updated": {"zh": "按更新时间"},
    "By created": {"zh": "按创建时间"},
    "By priority": {"zh": "按优先级"},
    "By importance": {"zh": "按重要度"},
    "{total} items": {"zh": "共 {total} 条"},

    # -- 类别 / 状态 --
    "Uncategorized": {"zh": "未分类"},
    "Long-term Task": {"zh": "长期任务"},
    "Short-term Task": {"zh": "短期任务"},
    "Instant Task": {"zh": "即时任务"},
    "Idea": {"zh": "灵感"},
    "Experiment": {"zh": "实验"},
    "Not started": {"zh": "未开始"},
    "Planned": {"zh": "准备做"},
    "Blocked": {"zh": "遇障碍"},
    "Done": {"zh": "已完成"},

    # -- 通用 --
    "Delete": {"zh": "删除"},
    "Copy": {"zh": "复制"},
    "{name} (Copy)": {"zh": "{name}（副本）"},
    "Cancel": {"zh": "取消"},
    "OK": {"zh": "确定"},
    "Name": {"zh": "名称"},
    "Description": {"zh": "描述"},
    "Category": {"zh": "类别"},
    "Priority": {"zh": "优先级"},
    "Importance": {"zh": "重要度"},
    "Drag or use mouse wheel (0-7)": {"zh": "拖动滑条或使用鼠标滚轮调整（0-7）"},
    "State": {"zh": "状态"},
    "Completed": {"zh": "完成时间"},
    "Add": {"zh": "添加"},
    "Edit": {"zh": "编辑"},
    "Save": {"zh": "保存"},
    "Item name *": {"zh": "条目名称 *"},
    "Description (optional)": {"zh": "描述(可选)"},

    # -- 计划表 --
    "Organize long/mid-term goals into forms, item by item": {
        "zh": "把长期/中期目标组织成表单,逐项推进"
    },
    "Forms": {"zh": "表单"},
    "Form": {"zh": "表单"},
    "No form": {"zh": "未归档"},
    "Unfiled": {"zh": "未归档"},
    "Remove from Form": {"zh": "移出表单"},
    "Set Parent Item": {"zh": "设为子项（选择父项）"},
    "New Child Item": {"zh": "新建子项"},
    "Remove Parent Item": {"zh": "移出父项"},
    "No available parent items": {"zh": "没有可用的父项"},
    "Collapse Children": {"zh": "折叠子项"},
    "Expand Children": {"zh": "展开子项"},
    "New Form": {"zh": "新建表单"},
    "Form name:": {"zh": "表单名称:"},
    "+ Add Item": {"zh": "+ 添加条目"},
    "Add Item": {"zh": "添加条目"},
    "Edit Item": {"zh": "编辑条目"},
    "Toggle Done": {"zh": "完成↔未开始"},
    "Move Up": {"zh": "上移"},
    "Move Down": {"zh": "下移"},
    "Move to Form": {"zh": "转移到表单"},
    "No other forms": {"zh": "没有其他表单"},
    "Sort by Priority": {"zh": "按优先级排序"},
    "Sort the whole form by priority, then importance": {
        "zh": "整个表单按优先级降序；优先级相同时按重要度降序"
    },
    "Delete Item": {"zh": "删除条目"},
    "Delete form": {"zh": "删除表单"},
    "Delete this form (items are kept)? This cannot be undone.": {
        "zh": "删除该表单(条目本身保留)?此操作不可撤销。"
    },
    "Delete \"{name}\"?": {"zh": "删除「{name}」?"},
    "Create a form first.": {"zh": "先新建一个表单。"},
    "No forms yet — click \"New Form\" to start": {"zh": "还没有表单 — 点「新建表单」开始"},
    "Created": {"zh": "创建时间"},

    # -- 及时行动 --
    "Quickly jot it down, do it now": {"zh": "一句话记下来,现在就能做"},
    "Quick add: name !priority #category   e.g. Print file !7 #3  (Enter)": {
        "zh": "快速添加: 任务名 !优先级 #类别  例: 打印文件 !7 #3  (回车即加)"
    },
    "Active": {"zh": "进行中"},
    "All": {"zh": "全部"},
    "All categories": {"zh": "全部类别"},
    "Search…": {"zh": "搜索…"},
    "Scope": {"zh": "范围"},
    "{active} active · {total} in list": {"zh": "进行中 {active} 条 · 当前列表 {total} 条"},
    "Toggle Done / Restore": {"zh": "完成 / 恢复"},
    "Name cannot be empty.": {"zh": "名称不能为空。"},
    "Item created as {category} — it belongs to Planner / Experiments, not here. See All Items.": {
        "zh": "已按「{category}」创建,它属于计划表/实验类目,不在此显示,请到全部条目查看。"
    },

    # -- 实验管理 --
    "Record parameters, conclusions and runs": {"zh": "记录参数、结论与每次运行"},
    "Result Summary": {"zh": "结论摘要"},
    "Updated": {"zh": "更新时间"},
    "Select an experiment to view details": {"zh": "选择左侧实验查看详情"},
    "Experiment #{id} · {state}": {"zh": "实验 #{id} · {state}"},
    "New Experiment": {"zh": "+ 新建实验"},
    "Delete Experiment": {"zh": "删除实验"},
    "Parameters": {"zh": "参数"},
    "Result": {"zh": "结论"},
    "Runs": {"zh": "运行记录"},
    "Key": {"zh": "键"},
    "Value": {"zh": "值"},
    "+ Key/Value": {"zh": "+ 键值"},
    "− Key/Value": {"zh": "− 键值"},
    "+ Add Run": {"zh": "+ 记录一次"},
    "Save Changes": {"zh": "保存修改"},
    "Experiment name": {"zh": "实验名称"},
    "Experiment description (optional)": {"zh": "实验描述(可选)"},
    "Experiment conclusion…": {"zh": "实验结论…"},
    "Record run": {"zh": "记录运行"},
    "Note for this run:": {"zh": "本次运行备注:"},
    "Delete experiment \"{name}\" and all its records?": {
        "zh": "删除实验「{name}」及其全部记录?"
    },

    # -- 设置 --
    "Appearance and data, changes apply instantly": {"zh": "外观与数据,改动即时生效"},
    "Appearance": {"zh": "外观"},
    "Background color": {"zh": "背景色"},
    "Accent color": {"zh": "强调色"},
    "Dark theme": {"zh": "深色主题"},
    "Font size": {"zh": "字号"},
    "Language": {"zh": "语言"},
    "Data": {"zh": "数据"},
    "Data file: {path}": {"zh": "数据文件: {path}"},
    "Settings are stored in the local SQLite settings table; changes apply immediately.": {
        "zh": "设置保存在本地 SQLite 的 settings 表中,改动立即应用。"
    },
    "Pick background color": {"zh": "选择背景色"},
    "Pick accent color": {"zh": "选择强调色"},
    "bg color {color}": {"zh": "背景色 {color}"},
    "accent color {color}": {"zh": "强调色 {color}"},
}

_current = "zh"


def set_language(lang: str) -> None:
    global _current
    _current = lang if lang in SUPPORTED_LANGUAGES else "zh"


def get_language() -> str:
    return _current


def tr(key: str, **kwargs) -> str:
    entry = _CATALOG.get(key)
    text = entry.get(_current) if entry else None
    if text is None:
        text = key
    return text.format(**kwargs) if kwargs else text
