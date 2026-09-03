#!/usr/bin/env python3
"""chronos 命令行管理器：查看、添加、复制和删除 item/form。"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from chronos_app.model import (
    CATEGORY_KEYS,
    STATE_KEYS,
    Category,
    Database,
    FixFeature,
    Scope,
    category_label,
    scope_of_category,
    state_label,
)

PROJECT_DIR = Path(__file__).resolve().parent
USAGE_DB = PROJECT_DIR / "data" / "chronos.db"
DEV_DB = PROJECT_DIR / "data" / "chronos-dev.db"

CATEGORY_ALIASES = {
    "undefined": Category.UNDEFINED,
    "uncategorized": Category.UNDEFINED,
    "long": Category.LONG_TERM,
    "long-term": Category.LONG_TERM,
    "short": Category.SHORT_TERM,
    "short-term": Category.SHORT_TERM,
    "instant": Category.INSTANT,
    "quick": Category.INSTANT,
    "idea": Category.IDEA,
    "experiment": Category.EXPERIMENT,
}
STATE_ALIASES = {
    "not-started": 0,
    "todo": 0,
    "planned": 1,
    "blocked": 2,
    "done": 3,
}


def enum_value(
    value: str, aliases: dict[str, int], valid: set[int], label: str
) -> int:
    normalized = value.strip().lower()
    if normalized in aliases:
        return aliases[normalized]
    try:
        number = int(normalized)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"未知{label}: {value}") from exc
    if number not in valid:
        raise argparse.ArgumentTypeError(f"{label}必须是 {sorted(valid)} 之一")
    return number


def category_value(value: str) -> int:
    return enum_value(value, CATEGORY_ALIASES, set(CATEGORY_KEYS), "类别")


def state_value(value: str) -> int:
    return enum_value(value, STATE_ALIASES, set(STATE_KEYS), "状态")


def score_value(value: str) -> int:
    try:
        score = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("分值必须是整数 0-7") from exc
    if not 0 <= score <= 7:
        raise argparse.ArgumentTypeError("分值必须在 0-7 之间")
    return score


def resolve_db(args: argparse.Namespace) -> Path:
    if args.db:
        return Path(args.db).expanduser().resolve()
    return DEV_DB if args.dev else USAGE_DB


def item_dict(item) -> dict[str, Any]:
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "category": item.fix.category,
        "category_label": category_label(item.fix.category),
        "priority": item.fix.priority,
        "importance": item.fix.importance,
        "state": item.fix.state,
        "state_label": state_label(item.fix.state),
        "fix_feature": item.fix.encode(),
        "extendable": item.extendable,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "completed_at": item.completed_at,
    }


def form_dict(db: Database, form, include_items: bool = False) -> dict[str, Any]:
    result = asdict(form)
    result.pop("item_ids", None)
    if include_items:
        result["items"] = [item_dict(item) for item in db.form_items(form.id)]
    return result


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def print_table(headers: list[str], rows: list[list[Any]]) -> None:
    if not rows:
        print("(无记录)")
        return
    text_rows = [[str(cell) for cell in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in text_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    fmt = "  ".join(f"{{:<{width}}}" for width in widths)
    print(fmt.format(*headers))
    print(fmt.format(*("-" * width for width in widths)))
    for row in text_rows:
        print(fmt.format(*row))


def require_item(db: Database, item_id: int):
    item = db.get_item(item_id)
    if item is None:
        raise ValueError(f"Item #{item_id} 不存在")
    return item


def require_form(db: Database, form_id: int):
    form = db.get_form(form_id)
    if form is None:
        raise ValueError(f"Form #{form_id} 不存在")
    return form


def confirm_delete(message: str, yes: bool) -> bool:
    if yes:
        return True
    if not sys.stdin.isatty():
        raise ValueError("非交互环境删除必须添加 --yes")
    answer = input(f"{message} [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def cmd_info(db: Database, args: argparse.Namespace) -> None:
    payload = {
        "database": str(db.path.resolve()),
        "items": db._conn.execute("SELECT COUNT(*) FROM items").fetchone()[0],
        "forms": db._conn.execute("SELECT COUNT(*) FROM forms").fetchone()[0],
    }
    if args.json:
        print_json(payload)
    else:
        print(f"数据库: {payload['database']}")
        print(f"Items: {payload['items']}  Forms: {payload['forms']}")


def cmd_item_list(db: Database, args: argparse.Namespace) -> None:
    if args.form is not None:
        require_form(db, args.form)
    items = db.query(
        category=args.category,
        state=args.state,
        keyword=args.search,
        form_id=args.form,
        order="updated_at DESC, id DESC",
        limit=args.limit,
    )
    if args.json:
        print_json([item_dict(item) for item in items])
        return
    print_table(
        ["ID", "名称", "类别", "P", "I", "状态", "更新时间"],
        [
            [
                item.id,
                item.name,
                category_label(item.fix.category),
                item.fix.priority,
                item.fix.importance,
                state_label(item.fix.state),
                item.updated_at,
            ]
            for item in items
        ],
    )


def cmd_item_show(db: Database, args: argparse.Namespace) -> None:
    item = require_item(db, args.id)
    data = item_dict(item)
    memberships = db._conn.execute(
        "SELECT f.id, f.name, f.scope, fi.position FROM forms f "
        "JOIN form_items fi ON fi.form_id=f.id WHERE fi.item_id=? "
        "ORDER BY f.id",
        (item.id,),
    ).fetchall()
    data["forms"] = [dict(row) for row in memberships]
    if args.json:
        print_json(data)
        return
    for key, value in data.items():
        if key in {"extendable", "forms"}:
            print(f"{key}: {json.dumps(value, ensure_ascii=False, indent=2)}")
        else:
            print(f"{key}: {value}")


def cmd_item_add(db: Database, args: argparse.Namespace) -> None:
    form = require_form(db, args.form) if args.form is not None else None
    if form is not None and scope_of_category(args.category) != form.scope:
        raise ValueError(
            f"类别 {category_label(args.category)} 不属于 {form.scope} 表单"
        )
    fix = FixFeature(
        category=args.category,
        priority=args.priority,
        importance=args.importance,
        state=args.state,
    )
    item = db.create_item(args.name, args.description, fix=fix)
    if form is not None and not db.add_to_form(form.id, item.id):
        db.delete_item(item.id)
        raise ValueError("加入表单失败，已回滚新 Item")
    data = item_dict(item)
    if args.json:
        print_json(data)
    else:
        suffix = f"，已加入 Form #{form.id} {form.name}" if form else ""
        print(f"已创建 Item #{item.id}: {item.name}{suffix}")


def cmd_item_delete(db: Database, args: argparse.Namespace) -> None:
    item = require_item(db, args.id)
    if not confirm_delete(f"确认删除 Item #{item.id} {item.name}?", args.yes):
        print("已取消")
        return
    db.delete_item(item.id)
    print(f"已删除 Item #{item.id}: {item.name}")


def cmd_item_copy(db: Database, args: argparse.Namespace) -> None:
    item = require_item(db, args.id)
    copy = db.duplicate_item(item.id, name=args.name or f"{item.name}（副本）")
    if copy is None:
        raise ValueError("复制失败")
    if args.json:
        print_json(item_dict(copy))
    else:
        print(f"已复制 Item #{item.id} → #{copy.id}: {copy.name}")


def cmd_form_list(db: Database, args: argparse.Namespace) -> None:
    forms = db.list_forms(args.scope)
    if args.json:
        print_json([form_dict(db, form) for form in forms])
        return
    print_table(
        ["ID", "名称", "Scope", "条目数", "创建时间"],
        [
            [form.id, form.name, form.scope, len(db.form_items(form.id)), form.created_at]
            for form in forms
        ],
    )


def cmd_form_show(db: Database, args: argparse.Namespace) -> None:
    form = require_form(db, args.id)
    data = form_dict(db, form, include_items=True)
    if args.json:
        print_json(data)
        return
    print(f"Form #{form.id}: {form.name}")
    print(f"description: {form.description}")
    print(f"scope: {form.scope}")
    print_table(
        ["位置", "Item ID", "名称", "类别", "P", "I", "状态"],
        [
            [
                pos,
                item.id,
                item.name,
                category_label(item.fix.category),
                item.fix.priority,
                item.fix.importance,
                state_label(item.fix.state),
            ]
            for pos, item in enumerate(db.form_items(form.id))
        ],
    )


def cmd_form_add(db: Database, args: argparse.Namespace) -> None:
    form = db.create_form(args.name, args.description, scope=args.scope)
    if args.json:
        print_json(form_dict(db, form))
    else:
        print(f"已创建 Form #{form.id}: {form.name} [{form.scope}]")


def cmd_form_delete(db: Database, args: argparse.Namespace) -> None:
    form = require_form(db, args.id)
    if not confirm_delete(
        f"确认删除 Form #{form.id} {form.name}? Item 会保留。", args.yes
    ):
        print("已取消")
        return
    db.delete_form(form.id)
    print(f"已删除 Form #{form.id}: {form.name}（Item 已保留）")


def cmd_form_add_item(db: Database, args: argparse.Namespace) -> None:
    form = require_form(db, args.form_id)
    item = require_item(db, args.item_id)
    if not db.add_to_form(form.id, item.id):
        raise ValueError(
            f"无法加入：Item 类别 {category_label(item.fix.category)} "
            f"与 Form scope {form.scope} 不兼容"
        )
    print(f"已将 Item #{item.id} 加入 Form #{form.id}")


def cmd_form_remove_item(db: Database, args: argparse.Namespace) -> None:
    form = require_form(db, args.form_id)
    item = require_item(db, args.item_id)
    db.remove_from_form(form.id, item.id)
    print(f"已将 Item #{item.id} 从 Form #{form.id} 移除（Item 保留）")


def cmd_form_move_item(db: Database, args: argparse.Namespace) -> None:
    source = require_form(db, args.source_form_id)
    target = require_form(db, args.target_form_id)
    item = require_item(db, args.item_id)
    if source.scope != target.scope:
        raise ValueError(
            f"不能跨类型转移：来源是 {source.scope}，目标是 {target.scope}"
        )
    if not db.transfer_item(item.id, source.id, target.id):
        raise ValueError(
            "转移失败：请确认 Item 属于来源 Form，且类别与 Form scope 兼容"
        )
    print(
        f"已将 Item #{item.id} {item.name} 从 Form #{source.id} {source.name} "
        f"转移到 Form #{target.id} {target.name}"
    )


def add_json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="输出 JSON")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="chronos 命令行管理器（默认操作使用库 data/chronos.db）"
    )
    parser.add_argument("--dev", action="store_true", help="操作开发库 chronos-dev.db")
    parser.add_argument("--db", help="显式指定数据库路径（优先于 --dev）")
    commands = parser.add_subparsers(dest="command", required=True)

    info = commands.add_parser("info", help="显示当前数据库路径和记录数")
    add_json_flag(info)
    info.set_defaults(handler=cmd_info)

    item = commands.add_parser("item", help="管理 Item")
    item_commands = item.add_subparsers(dest="item_command", required=True)

    item_list = item_commands.add_parser("list", help="列出 Item")
    item_list.add_argument("--category", type=category_value)
    item_list.add_argument("--state", type=state_value)
    item_list.add_argument("--search")
    item_list.add_argument("--form", type=int, help="只显示指定 Form 的 Item")
    item_list.add_argument("--limit", type=int)
    add_json_flag(item_list)
    item_list.set_defaults(handler=cmd_item_list)

    item_show = item_commands.add_parser("show", help="查看单个 Item")
    item_show.add_argument("id", type=int)
    add_json_flag(item_show)
    item_show.set_defaults(handler=cmd_item_show)

    item_add = item_commands.add_parser("add", help="添加 Item")
    item_add.add_argument("name")
    item_add.add_argument("--description", default="")
    item_add.add_argument("--category", type=category_value, default=Category.INSTANT)
    item_add.add_argument("--priority", type=score_value, default=3)
    item_add.add_argument("--importance", type=score_value, default=3)
    item_add.add_argument("--state", type=state_value, default=0)
    item_add.add_argument("--form", type=int, help="创建后加入指定 Form")
    add_json_flag(item_add)
    item_add.set_defaults(handler=cmd_item_add)

    item_delete = item_commands.add_parser("delete", help="删除 Item")
    item_delete.add_argument("id", type=int)
    item_delete.add_argument("--yes", action="store_true", help="跳过确认")
    item_delete.set_defaults(handler=cmd_item_delete)

    item_copy = item_commands.add_parser("copy", help="复制 Item")
    item_copy.add_argument("id", type=int)
    item_copy.add_argument("--name", help="指定副本名称")
    add_json_flag(item_copy)
    item_copy.set_defaults(handler=cmd_item_copy)

    form = commands.add_parser("form", help="管理 Form")
    form_commands = form.add_subparsers(dest="form_command", required=True)

    form_list = form_commands.add_parser("list", help="列出 Form")
    form_list.add_argument("--scope", choices=(Scope.PLANNER, Scope.QUICK))
    add_json_flag(form_list)
    form_list.set_defaults(handler=cmd_form_list)

    form_show = form_commands.add_parser("show", help="查看 Form 及其 Item")
    form_show.add_argument("id", type=int)
    add_json_flag(form_show)
    form_show.set_defaults(handler=cmd_form_show)

    form_add = form_commands.add_parser("add", help="添加 Form")
    form_add.add_argument("name")
    form_add.add_argument("--description", default="")
    form_add.add_argument("--scope", choices=(Scope.PLANNER, Scope.QUICK), default=Scope.QUICK)
    add_json_flag(form_add)
    form_add.set_defaults(handler=cmd_form_add)

    form_delete = form_commands.add_parser("delete", help="删除 Form，保留 Item")
    form_delete.add_argument("id", type=int)
    form_delete.add_argument("--yes", action="store_true", help="跳过确认")
    form_delete.set_defaults(handler=cmd_form_delete)

    add_item = form_commands.add_parser("add-item", help="将已有 Item 加入 Form")
    add_item.add_argument("form_id", type=int)
    add_item.add_argument("item_id", type=int)
    add_item.set_defaults(handler=cmd_form_add_item)

    remove_item = form_commands.add_parser("remove-item", help="从 Form 移除 Item")
    remove_item.add_argument("form_id", type=int)
    remove_item.add_argument("item_id", type=int)
    remove_item.set_defaults(handler=cmd_form_remove_item)

    move_item = form_commands.add_parser(
        "move-item", help="将 Item 原子转移到同 scope 的另一个 Form"
    )
    move_item.add_argument("source_form_id", type=int)
    move_item.add_argument("target_form_id", type=int)
    move_item.add_argument("item_id", type=int)
    move_item.set_defaults(handler=cmd_form_move_item)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    db = Database(resolve_db(args))
    try:
        handler: Callable[[Database, argparse.Namespace], None] = args.handler
        handler(db, args)
    except (ValueError, OSError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
