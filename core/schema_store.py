from __future__ import annotations
import json
import sqlite3
import uuid
from datetime import datetime, timezone


class SchemaStore:
    """本体 Schema 存储 — 从 SQLite 加载/保存对象类型、Function、Action 定义，支持 workspace 隔离。"""

    def __init__(self, db_path: str, workspace: str = "default"):
        self._db_path = db_path
        self._workspace = workspace
        self._init_db()

    def set_workspace(self, workspace: str) -> None:
        """切换当前 workspace。"""
        self._workspace = workspace

    def get_workspace(self) -> str:
        """获取当前 workspace。"""
        return self._workspace

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            # 创建 workspace 表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS workspaces (
                    name TEXT PRIMARY KEY,
                    description TEXT DEFAULT '',
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            # 修改现有表添加 workspace 字段
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ontology_types (
                    name TEXT NOT NULL,
                    workspace TEXT DEFAULT 'default',
                    description TEXT DEFAULT '',
                    properties TEXT DEFAULT '{}',
                    links TEXT DEFAULT '{}',
                    created_at TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (workspace, name)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ontology_functions (
                    name TEXT NOT NULL,
                    workspace TEXT DEFAULT 'default',
                    description TEXT DEFAULT '',
                    params TEXT DEFAULT '{}',
                    returns TEXT DEFAULT '',
                    code TEXT DEFAULT '',
                    permission TEXT DEFAULT '',
                    created_at TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (workspace, name)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ontology_actions (
                    name TEXT NOT NULL,
                    workspace TEXT DEFAULT 'default',
                    description TEXT DEFAULT '',
                    params TEXT DEFAULT '{}',
                    target_type TEXT DEFAULT '',
                    edits TEXT DEFAULT '{}',
                    creates INTEGER DEFAULT 0,
                    requires_confirmation INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (workspace, name)
                )
            """)
            # 确保默认 workspace 存在
            conn.execute(
                "INSERT OR IGNORE INTO workspaces (name, description, created_at, updated_at) VALUES (?, ?, ?, ?)",
                ("default", "默认工作空间", datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat())
            )

    # ── Workspace 管理 ───────────────────────────────────────────────────

    def create_workspace(self, name: str, description: str = "") -> dict:
        """创建新 workspace。"""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            try:
                conn.execute(
                    "INSERT INTO workspaces (name, description, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (name, description, now, now)
                )
                return {"status": "created", "name": name}
            except sqlite3.IntegrityError:
                return {"error": f"Workspace '{name}' already exists"}

    def delete_workspace(self, name: str) -> dict:
        """删除 workspace 及其所有数据。"""
        if name == "default":
            return {"error": "Cannot delete default workspace"}
        with sqlite3.connect(self._db_path) as conn:
            # 删除该 workspace 的所有类型
            conn.execute("DELETE FROM ontology_types WHERE workspace=?", (name,))
            # 删除该 workspace 的所有函数
            conn.execute("DELETE FROM ontology_functions WHERE workspace=?", (name,))
            # 删除该 workspace 的所有操作
            conn.execute("DELETE FROM ontology_actions WHERE workspace=?", (name,))
            # 删除该 workspace 的所有实例数据（避免孤儿记录）
            conn.execute("DELETE FROM objects WHERE workspace=?", (name,))
            # 删除 workspace 本身
            cursor = conn.execute("DELETE FROM workspaces WHERE name=?", (name,))
            if cursor.rowcount > 0:
                return {"status": "deleted", "name": name}
            return {"error": f"Workspace '{name}' not found"}

    def list_workspaces(self) -> list[dict]:
        """列出所有 workspace。"""
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute("SELECT * FROM workspaces ORDER BY name").fetchall()
        return [
            {"name": r[0], "description": r[1], "created_at": r[2], "updated_at": r[3]}
            for r in rows
        ]

    def get_workspace_info(self, name: str) -> dict | None:
        """获取 workspace 信息。"""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute("SELECT * FROM workspaces WHERE name=?", (name,)).fetchone()
        if not row:
            return None
        return {"name": row[0], "description": row[1], "created_at": row[2], "updated_at": row[3]}

    def copy_workspace_schema(self, src_ws: str, dst_ws: str) -> dict:
        """从 src_ws 复制 types/functions/actions 到 dst_ws。

        仅复制 schema 定义，不复制实例数据（objects 表）。
        已存在的同名项会被覆盖。返回复制统计。
        """
        if src_ws == dst_ws:
            return {"error": "source and destination workspace are the same"}
        if not self.get_workspace_info(src_ws):
            return {"error": f"source workspace '{src_ws}' not found"}
        if not self.get_workspace_info(dst_ws):
            return {"error": f"destination workspace '{dst_ws}' not found"}

        original = self._workspace
        try:
            self._workspace = src_ws
            types = self.list_types()
            functions = self.list_functions()
            actions = self.list_actions()

            self._workspace = dst_ws
            for t in types:
                self.save_type(
                    name=t["name"],
                    description=t.get("description", ""),
                    properties=t.get("properties", {}),
                    links=t.get("links", {}),
                )
            for f in functions:
                self.save_function(
                    name=f["name"],
                    description=f.get("description", ""),
                    params=f.get("params", {}),
                    returns=f.get("returns", ""),
                    code=f.get("code", "") or "",
                    permission=f.get("permission", ""),
                )
            for a in actions:
                self.save_action(
                    name=a["name"],
                    description=a.get("description", ""),
                    params=a.get("params", {}),
                    target_type=a.get("target_type", ""),
                    edits=a.get("edits", {}),
                    creates=a.get("creates", False),
                    requires_confirmation=a.get("requires_confirmation", False),
                )
            return {
                "status": "copied",
                "source": src_ws,
                "destination": dst_ws,
                "types": len(types),
                "functions": len(functions),
                "actions": len(actions),
            }
        finally:
            self._workspace = original

    # ── Object Types ─────────────────────────────────────────────────────

    def save_type(self, name: str, description: str, properties: dict, links: dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            existing = conn.execute(
                "SELECT name FROM ontology_types WHERE workspace=? AND name=?",
                (self._workspace, name)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE ontology_types SET description=?, properties=?, links=?, updated_at=? WHERE workspace=? AND name=?",
                    (description, json.dumps(properties, ensure_ascii=False),
                     json.dumps(links, ensure_ascii=False), now, self._workspace, name),
                )
            else:
                conn.execute(
                    "INSERT INTO ontology_types VALUES (?,?,?,?,?,?,?)",
                    (name, self._workspace, description, json.dumps(properties, ensure_ascii=False),
                     json.dumps(links, ensure_ascii=False), now, now),
                )

    def get_type(self, name: str) -> dict | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM ontology_types WHERE workspace=? AND name=?",
                (self._workspace, name)
            ).fetchone()
        if not row:
            return None
        return {
            "name": row[0], "workspace": row[1], "description": row[2],
            "properties": json.loads(row[3]), "links": json.loads(row[4]),
        }

    def delete_type(self, name: str) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM ontology_types WHERE workspace=? AND name=?",
                (self._workspace, name)
            )
            return cursor.rowcount > 0

    def list_types(self) -> list[dict]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM ontology_types WHERE workspace=?",
                (self._workspace,)
            ).fetchall()
        return [
            {"name": r[0], "workspace": r[1], "description": r[2],
             "properties": json.loads(r[3]), "links": json.loads(r[4])}
            for r in rows
        ]

    def get_primary_key(self, type_name: str) -> str:
        t = self.get_type(type_name)
        if not t:
            raise KeyError(f"Unknown type: {type_name}")
        for prop_name, prop_def in t["properties"].items():
            if prop_def.get("primary_key"):
                return prop_name
        raise ValueError(f"No primary key on {type_name}")

    def get_id_prefix(self, type_name: str) -> str:
        """获取自动生成 ID 的前缀。

        优先从主键属性的 id_prefix 字段读取；若未配置则回退到 类型名前 3 位大写。
        避免 Skill 与 SkillExecution 同时使用 SKI- 前缀造成歧义。
        """
        t = self.get_type(type_name)
        if not t:
            return type_name[:3].upper()
        for _prop_name, prop_def in t["properties"].items():
            if prop_def.get("primary_key"):
                prefix = prop_def.get("id_prefix")
                if prefix:
                    return str(prefix)
                break
        return type_name[:3].upper()

    # ── Functions ────────────────────────────────────────────────────────

    def save_function(self, name: str, description: str, params: dict,
                      returns: str, code: str, permission: str = "") -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            existing = conn.execute(
                "SELECT name FROM ontology_functions WHERE workspace=? AND name=?",
                (self._workspace, name)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE ontology_functions SET description=?, params=?, returns=?, code=?, permission=?, updated_at=? WHERE workspace=? AND name=?",
                    (description, json.dumps(params, ensure_ascii=False), returns,
                     code, permission, now, self._workspace, name),
                )
            else:
                conn.execute(
                    "INSERT INTO ontology_functions VALUES (?,?,?,?,?,?,?,?,?)",
                    (name, self._workspace, description, json.dumps(params, ensure_ascii=False),
                     returns, code, permission, now, now),
                )

    def get_function(self, name: str) -> dict | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM ontology_functions WHERE workspace=? AND name=?",
                (self._workspace, name)
            ).fetchone()
        if not row:
            return None
        return {
            "name": row[0], "workspace": row[1], "description": row[2],
            "params": json.loads(row[3]), "returns": row[4],
            "code": row[5], "permission": row[6],
        }

    def delete_function(self, name: str) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM ontology_functions WHERE workspace=? AND name=?",
                (self._workspace, name)
            )
            return cursor.rowcount > 0

    def list_functions(self) -> list[dict]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM ontology_functions WHERE workspace=?",
                (self._workspace,)
            ).fetchall()
        return [
            {"name": r[0], "workspace": r[1], "description": r[2],
             "params": json.loads(r[3]), "returns": r[4],
             "code": r[5], "permission": r[6]}
            for r in rows
        ]

    # ── Actions ──────────────────────────────────────────────────────────

    def save_action(self, name: str, description: str, params: dict,
                    target_type: str, edits: dict, creates: bool,
                    requires_confirmation: bool) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            existing = conn.execute(
                "SELECT name FROM ontology_actions WHERE workspace=? AND name=?",
                (self._workspace, name)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE ontology_actions SET description=?, params=?, target_type=?, edits=?, creates=?, requires_confirmation=?, updated_at=? WHERE workspace=? AND name=?",
                    (description, json.dumps(params, ensure_ascii=False), target_type,
                     json.dumps(edits, ensure_ascii=False), int(creates),
                     int(requires_confirmation), now, self._workspace, name),
                )
            else:
                conn.execute(
                    "INSERT INTO ontology_actions VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (name, self._workspace, description, json.dumps(params, ensure_ascii=False),
                     target_type, json.dumps(edits, ensure_ascii=False),
                     int(creates), int(requires_confirmation), now, now),
                )

    def get_action(self, name: str) -> dict | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM ontology_actions WHERE workspace=? AND name=?",
                (self._workspace, name)
            ).fetchone()
        if not row:
            return None
        return {
            "name": row[0], "workspace": row[1], "description": row[2],
            "params": json.loads(row[3]), "target_type": row[4],
            "edits": json.loads(row[5]), "creates": bool(row[6]),
            "requires_confirmation": bool(row[7]),
        }

    def delete_action(self, name: str) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM ontology_actions WHERE workspace=? AND name=?",
                (self._workspace, name)
            )
            return cursor.rowcount > 0

    def list_actions(self) -> list[dict]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM ontology_actions WHERE workspace=?",
                (self._workspace,)
            ).fetchall()
        return [
            {"name": r[0], "workspace": r[1], "description": r[2],
             "params": json.loads(r[3]), "target_type": r[4],
             "edits": json.loads(r[5]), "creates": bool(r[6]),
             "requires_confirmation": bool(r[7])}
            for r in rows
        ]

    # ── YAML Import ──────────────────────────────────────────────────────

    def import_from_yaml(self, yaml_path: str) -> dict:
        import yaml
        with open(yaml_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        counts = {"types": 0, "functions": 0, "actions": 0}

        for name, defn in raw.get("object_types", {}).items():
            self.save_type(
                name=name,
                description=defn.get("description", ""),
                properties=defn.get("properties", {}),
                links=defn.get("links", {}),
            )
            counts["types"] += 1

        for name, defn in raw.get("functions", {}).items():
            self.save_function(
                name=name,
                description=defn.get("description", ""),
                params=defn.get("params", {}),
                returns=defn.get("returns", "") if isinstance(defn.get("returns"), str) else json.dumps(defn.get("returns", "")),
                code=defn.get("code", "") or "",  # YAML 内嵌的默认实现（若有）
                permission=defn.get("permission", ""),
            )
            counts["functions"] += 1

        for name, defn in raw.get("actions", {}).items():
            self.save_action(
                name=name,
                description=defn.get("description", ""),
                params=defn.get("params", {}),
                target_type=defn.get("target_type", ""),
                edits=defn.get("edits", {}),
                creates=defn.get("creates", False),
                requires_confirmation=defn.get("requires_confirmation", False),
            )
            counts["actions"] += 1

        return counts
