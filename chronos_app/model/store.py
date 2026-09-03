"""SQLite 持久化层。

`items.fix_feature` 是紧凑位域(规范表示);category/priority/importance/state
为镜像列,由本层单点写入保持同步,用于索引与查询。extendable 以 JSON 文本存储。
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .fields import FixFeature, Scope, State, scope_of_category
from .item import Item, default_extendable

_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    parent_id   INTEGER REFERENCES items(id) ON DELETE SET NULL,
    description TEXT NOT NULL DEFAULT '',
    fix_feature INTEGER NOT NULL,
    category    INTEGER NOT NULL,
    priority    INTEGER NOT NULL,
    importance  INTEGER NOT NULL,
    state       INTEGER NOT NULL,
    extendable  TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    completed_at TEXT DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
CREATE INDEX IF NOT EXISTS idx_items_state ON items(state);
CREATE INDEX IF NOT EXISTS idx_items_state_category ON items(state, category);

CREATE TABLE IF NOT EXISTS forms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    scope       TEXT NOT NULL DEFAULT 'planner',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS form_items (
    form_id  INTEGER NOT NULL REFERENCES forms(id) ON DELETE CASCADE,
    item_id  INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    position INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (form_id, item_id)
);
CREATE INDEX IF NOT EXISTS idx_form_items_form ON form_items(form_id, position);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_ITEM_COLUMNS = (
    "id, name, parent_id, description, fix_feature, category, priority, importance, "
    "state, extendable, created_at, updated_at, completed_at"
)


@dataclass
class Form:
    """一个表单;scope 决定它属于计划表还是及时行动,互不共享。"""

    id: int
    name: str
    description: str = ""
    scope: str = "planner"
    created_at: str = ""

    item_ids: list[int] = field(default_factory=list)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _load(text: str, default: Any = None) -> Any:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


class Database:
    """chronos 的 SQLite 数据访问层。"""

    def __init__(self, path: str | Path, create: bool = True) -> None:
        self.path = Path(path)
        if create and not self.path.parent.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        if create:
            self._conn.executescript(_SCHEMA)
            self._migrate()
            self._conn.commit()

    def _migrate(self) -> None:
        """旧库升级：补充后续版本新增的列。"""
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(forms)").fetchall()}
        if "scope" not in cols:
            self._conn.execute(
                "ALTER TABLE forms ADD COLUMN scope TEXT NOT NULL DEFAULT 'planner'"
            )
        item_cols = {
            r[1] for r in self._conn.execute("PRAGMA table_info(items)").fetchall()
        }
        if "parent_id" not in item_cols:
            self._conn.execute("ALTER TABLE items ADD COLUMN parent_id INTEGER DEFAULT NULL")
        if "completed_at" not in item_cols:
            self._conn.execute("ALTER TABLE items ADD COLUMN completed_at TEXT DEFAULT NULL")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_items_parent ON items(parent_id)")

    def close(self) -> None:
        self._conn.close()

    # -- 内部工具 -----------------------------------------------------------

    @staticmethod
    def _pack(fix: FixFeature) -> tuple[int, int, int, int, int]:
        """打包 fix feature 为 (fix_feature, category, priority, importance, state)。"""
        return fix.encode(), fix.category, fix.priority, fix.importance, fix.state

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> Item:
        extendable = _load(row["extendable"], {}) or {}
        return Item(
            id=row["id"],
            name=row["name"],
            parent_id=row["parent_id"],
            description=row["description"],
            fix=FixFeature.decode(row["fix_feature"]),
            extendable=extendable,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
        )

    # -- 条目 CRUD -----------------------------------------------------------

    def create_item(
        self,
        name: str,
        description: str = "",
        fix: FixFeature | None = None,
        extendable: dict[str, Any] | None = None,
        parent_id: int | None = None,
        now: str | None = None,
    ) -> Item:
        fix = fix or FixFeature()
        extendable = extendable if extendable is not None else default_extendable(fix.category)
        now = now or _now()
        packed, cat, pri, imp, state = self._pack(fix)
        completed_at = now if fix.state == State.DONE else None
        cur = self._conn.execute(
            f"INSERT INTO items ({_ITEM_COLUMNS}) VALUES "
            "(NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                name.strip(),
                parent_id if self.get_item(parent_id) is not None else None,
                description,
                packed,
                cat,
                pri,
                imp,
                state,
                _dump(extendable),
                now,
                now,
                completed_at,
            ),
        )
        self._conn.commit()
        return self.get_item(cur.lastrowid)  # type: ignore[return-value]

    def get_item(self, item_id: int) -> Item | None:
        row = self._conn.execute(
            f"SELECT {_ITEM_COLUMNS} FROM items WHERE id = ?", (item_id,)
        ).fetchone()
        return self._row_to_item(row) if row else None

    def update_item(
        self,
        item_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        fix: FixFeature | None = None,
        extendable: dict[str, Any] | None = None,
        now: str | None = None,
    ) -> Item | None:
        existing = self.get_item(item_id)
        if existing is None:
            return None

        name = existing.name if name is None else name.strip()
        description = existing.description if description is None else description
        fix = existing.fix if fix is None else fix
        extendable = existing.extendable if extendable is None else extendable

        packed, cat, pri, imp, state = self._pack(fix)
        update_time = now or _now()
        completed_at = existing.completed_at
        if fix.state == State.DONE and existing.fix.state != State.DONE:
            completed_at = update_time
        self._conn.execute(
            "UPDATE items SET name=?, description=?, fix_feature=?, category=?, "
            "priority=?, importance=?, state=?, extendable=?, updated_at=?, "
            "completed_at=? WHERE id=?",
            (
                name,
                description,
                packed,
                cat,
                pri,
                imp,
                state,
                _dump(extendable),
                update_time,
                completed_at,
                item_id,
            ),
        )
        self._reconcile_form_membership(item_id)
        self._conn.commit()
        return self.get_item(item_id)

    def _reconcile_form_membership(self, item_id: int) -> None:
        """类目变化后,把条目从 scope 不匹配的表单中移除(维持互斥不变式)。"""
        item = self.get_item(item_id)
        if item is None:
            return
        item_scope = scope_of_category(item.fix.category)
        rows = self._conn.execute(
            "SELECT form_id FROM form_items WHERE item_id = ?", (item_id,)
        ).fetchall()
        for r in rows:
            form = self.get_form(r["form_id"])
            if form is None or form.scope != item_scope:
                self._conn.execute(
                    "DELETE FROM form_items WHERE form_id = ? AND item_id = ?",
                    (r["form_id"], item_id),
                )

    def set_state(self, item_id: int, state: int, now: str | None = None) -> Item | None:
        existing = self.get_item(item_id)
        if existing is None:
            return None
        return self.update_item(item_id, fix=existing.fix.with_(state=state), now=now)

    def delete_item(self, item_id: int) -> bool:
        with self._conn:
            self._conn.execute(
                "UPDATE items SET parent_id = NULL WHERE parent_id = ?", (item_id,)
            )
            cur = self._conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        return cur.rowcount > 0

    def children(self, parent_id: int) -> list[Item]:
        rows = self._conn.execute(
            f"SELECT {_ITEM_COLUMNS} FROM items WHERE parent_id = ? ORDER BY id",
            (parent_id,),
        ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def set_parent(self, item_id: int, parent_id: int | None) -> bool:
        """设置唯一父项；拒绝不存在、自引用和任何祖先循环。None 表示移出父项。"""
        item = self.get_item(item_id)
        if item is None:
            return False
        if parent_id is None:
            self._conn.execute(
                "UPDATE items SET parent_id = NULL, updated_at = ? WHERE id = ?",
                (_now(), item_id),
            )
            self._conn.commit()
            return True
        if parent_id == item_id or self.get_item(parent_id) is None:
            return False

        cursor: int | None = parent_id
        seen: set[int] = set()
        while cursor is not None:
            if cursor == item_id or cursor in seen:
                return False
            seen.add(cursor)
            ancestor = self.get_item(cursor)
            cursor = ancestor.parent_id if ancestor is not None else None

        self._conn.execute(
            "UPDATE items SET parent_id = ?, updated_at = ? WHERE id = ?",
            (parent_id, _now(), item_id),
        )
        self._conn.commit()
        return True

    def duplicate_item(self, item_id: int, *, name: str | None = None) -> Item | None:
        """复制条目及其表单归属，并把副本排在原条目之后。"""
        source = self.get_item(item_id)
        if source is None:
            return None

        now = _now()
        packed, cat, pri, imp, state = self._pack(source.fix)
        with self._conn:
            cur = self._conn.execute(
                f"INSERT INTO items ({_ITEM_COLUMNS}) VALUES "
                "(NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    (name if name is not None else source.name).strip(),
                    source.parent_id,
                    source.description,
                    packed,
                    cat,
                    pri,
                    imp,
                    state,
                    _dump(source.extendable),
                    now,
                    now,
                    source.completed_at,
                ),
            )
            new_id = cur.lastrowid

            memberships = self._conn.execute(
                "SELECT form_id, position FROM form_items WHERE item_id = ?",
                (item_id,),
            ).fetchall()
            for membership in memberships:
                form_id = membership["form_id"]
                position = membership["position"] + 1
                self._conn.execute(
                    "UPDATE form_items SET position = position + 1 "
                    "WHERE form_id = ? AND position >= ?",
                    (form_id, position),
                )
                self._conn.execute(
                    "INSERT INTO form_items (form_id, item_id, position) VALUES (?, ?, ?)",
                    (form_id, new_id, position),
                )

        return self.get_item(new_id)

    def query(
        self,
        *,
        category: int | None = None,
        category_in: Iterable[int] | None = None,
        state: int | None = None,
        state_not: int | None = None,
        keyword: str | None = None,
        form_id: int | None = None,
        unfiled_scope: str | None = None,
        order: str = "updated_at DESC, id DESC",
        limit: int | None = None,
    ) -> list[Item]:
        where: list[str] = []
        params: list = []
        if category is not None:
            where.append("category = ?")
            params.append(category)
        if category_in is not None:
            where.append(f"category IN ({','.join('?' * len(category_in))})")
            params.extend(int(c) for c in category_in)
        if state is not None:
            where.append("state = ?")
            params.append(state)
        if state_not is not None:
            where.append("state != ?")
            params.append(state_not)
        if keyword:
            where.append("(name LIKE ? OR description LIKE ?)")
            kw = f"%{keyword}%"
            params.extend((kw, kw))
        if unfiled_scope is not None:
            where.append(
                "NOT EXISTS (SELECT 1 FROM form_items ufi "
                "JOIN forms uf ON uf.id = ufi.form_id "
                "WHERE ufi.item_id = items.id AND uf.scope = ?)"
            )
            params.append(unfiled_scope)

        if form_id is not None:
            sql, all_params = self._query_form_sql(where, params, form_id, order, limit)
            rows = self._conn.execute(sql, all_params).fetchall()
        else:
            sql = f"SELECT {_ITEM_COLUMNS} FROM items"
            if where:
                sql += " WHERE " + " AND ".join(where)
            sql += f" ORDER BY {order}"
            if limit:
                sql += f" LIMIT {limit}"
            rows = self._conn.execute(sql, params).fetchall()

        return [self._row_to_item(r) for r in rows]

    @staticmethod
    def _query_form_sql(
        where: list[str], params: list, form_id: int, order: str, limit: int | None
    ) -> tuple[str, list]:
        sql = (
            f"SELECT {_ITEM_COLUMNS} FROM items "
            "JOIN form_items fi ON fi.item_id = items.id "
            f"WHERE fi.form_id = ?"
        )
        for w in where:
            sql += " AND " + w
        sql += f" ORDER BY fi.position, {order}"
        if limit:
            sql += f" LIMIT {limit}"
        # params 是扁平列表,按出现顺序全部追加(一个子句可含多个占位符)
        return sql, [form_id, *params]

    # -- 表单 ---------------------------------------------------------------

    def create_form(
        self, name: str, description: str = "", scope: str = Scope.PLANNER
    ) -> Form:
        if scope not in (Scope.PLANNER, Scope.QUICK):
            scope = Scope.PLANNER
        now = _now()
        cur = self._conn.execute(
            "INSERT INTO forms (name, description, scope, created_at) VALUES (?, ?, ?, ?)",
            (name.strip(), description, scope, now),
        )
        self._conn.commit()
        return Form(
            id=cur.lastrowid, name=name.strip(), description=description,
            scope=scope, created_at=now,
        )

    def delete_form(self, form_id: int) -> bool:
        cur = self._conn.execute("DELETE FROM forms WHERE id = ?", (form_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def list_forms(self, scope: str | None = None) -> list[Form]:
        if scope:
            rows = self._conn.execute(
                "SELECT id, name, description, scope, created_at FROM forms "
                "WHERE scope = ? ORDER BY id",
                (scope,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, name, description, scope, created_at FROM forms ORDER BY id"
            ).fetchall()
        return [Form(**dict(r)) for r in rows]

    def get_form(self, form_id: int) -> Form | None:
        row = self._conn.execute(
            "SELECT id, name, description, scope, created_at FROM forms WHERE id = ?",
            (form_id,),
        ).fetchone()
        return Form(**dict(row)) if row else None

    def item_forms(self, item_id: int, scope: str | None = None) -> list[Form]:
        """返回条目所属表单；可按 Planner / Quick scope 限定。"""
        sql = (
            "SELECT f.id, f.name, f.description, f.scope, f.created_at "
            "FROM forms f JOIN form_items fi ON fi.form_id = f.id "
            "WHERE fi.item_id = ?"
        )
        params: list = [item_id]
        if scope is not None:
            sql += " AND f.scope = ?"
            params.append(scope)
        sql += " ORDER BY f.id"
        return [Form(**dict(row)) for row in self._conn.execute(sql, params).fetchall()]

    def add_to_form(self, form_id: int, item_id: int) -> bool:
        """把条目放入表单;scope 不匹配(如即时条目进计划表)则拒绝。返回是否成功。"""
        form = self.get_form(form_id)
        item = self.get_item(item_id)
        if form is None or item is None:
            return False
        if scope_of_category(item.fix.category) != form.scope:
            return False
        row = self._conn.execute(
            "SELECT COALESCE(MAX(position), -1) FROM form_items WHERE form_id = ?",
            (form_id,),
        ).fetchone()
        position = row[0] + 1
        self._conn.execute(
            "INSERT OR IGNORE INTO form_items (form_id, item_id, position) VALUES (?, ?, ?)",
            (form_id, item_id, position),
        )
        self._conn.commit()
        return True

    def remove_from_form(self, form_id: int, item_id: int) -> None:
        self._conn.execute(
            "DELETE FROM form_items WHERE form_id = ? AND item_id = ?", (form_id, item_id)
        )
        self._conn.commit()

    def transfer_item(
        self, item_id: int, source_form_id: int, target_form_id: int
    ) -> bool:
        """把 Item 从源 Form 原子转移到同 scope 的目标 Form。"""
        if source_form_id == target_form_id:
            return False
        source = self.get_form(source_form_id)
        target = self.get_form(target_form_id)
        item = self.get_item(item_id)
        if source is None or target is None or item is None:
            return False
        if source.scope != target.scope:
            return False
        if scope_of_category(item.fix.category) != source.scope:
            return False
        membership = self._conn.execute(
            "SELECT 1 FROM form_items WHERE form_id = ? AND item_id = ?",
            (source_form_id, item_id),
        ).fetchone()
        if membership is None:
            return False

        with self._conn:
            target_membership = self._conn.execute(
                "SELECT 1 FROM form_items WHERE form_id = ? AND item_id = ?",
                (target_form_id, item_id),
            ).fetchone()
            if target_membership is None:
                row = self._conn.execute(
                    "SELECT COALESCE(MAX(position), -1) FROM form_items WHERE form_id = ?",
                    (target_form_id,),
                ).fetchone()
                self._conn.execute(
                    "INSERT INTO form_items (form_id, item_id, position) VALUES (?, ?, ?)",
                    (target_form_id, item_id, row[0] + 1),
                )
            self._conn.execute(
                "DELETE FROM form_items WHERE form_id = ? AND item_id = ?",
                (source_form_id, item_id),
            )
            remaining = self._conn.execute(
                "SELECT item_id FROM form_items WHERE form_id = ? ORDER BY position, item_id",
                (source_form_id,),
            ).fetchall()
            for position, row in enumerate(remaining):
                self._conn.execute(
                    "UPDATE form_items SET position = ? WHERE form_id = ? AND item_id = ?",
                    (position, source_form_id, row["item_id"]),
                )
        return True

    def form_items(self, form_id: int) -> list[Item]:
        return self.query(form_id=form_id, order="id ASC")

    def set_form_order(self, form_id: int, ordered_item_ids: Iterable[int]) -> None:
        with self._conn:
            for position, item_id in enumerate(ordered_item_ids):
                self._conn.execute(
                    "UPDATE form_items SET position = ? WHERE form_id = ? AND item_id = ?",
                    (position, form_id, item_id),
                )

    # -- 设置 ---------------------------------------------------------------

    def get_setting(self, key: str, default: Any = None) -> Any:
        row = self._conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return default
        return _load(row["value"], row["value"])

    def set_setting(self, key: str, value: Any) -> None:
        self._conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, _dump(value)),
        )
        self._conn.commit()

    # -- 清理 ---------------------------------------------------------------

    def clear_all(self) -> None:
        """清空条目与表单(表单关联级联),保留 settings。供 --demo 幂等重置。"""
        self._conn.execute("DELETE FROM form_items")
        self._conn.execute("DELETE FROM items")
        self._conn.execute("DELETE FROM forms")
        self._conn.commit()

    # -- 统计 ---------------------------------------------------------------

    def counts(self) -> dict[str, int]:
        """按 state 统计条目数(用于及时行动面板角标)。"""
        rows = self._conn.execute(
            "SELECT state, COUNT(*) FROM items GROUP BY state"
        ).fetchall()
        out = {State.NOT_STARTED: 0, State.PLANNED: 0, State.BLOCKED: 0, State.DONE: 0}
        for r in rows:
            out[r["state"]] = r["COUNT(*)"]
        return out

    # -- 生命周期 -----------------------------------------------------------

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
