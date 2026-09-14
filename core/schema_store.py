from __future__ import annotations
import json
import sqlite3
import uuid
from datetime import datetime, timezone


class SchemaStore:
    """本体 Schema 存储 — 从 SQLite 加载/保存对象类型、Function、Action 定义。"""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ontology_types (
                    name TEXT PRIMARY KEY,
                    description TEXT DEFAULT '',
                    properties TEXT DEFAULT '{}',
                    links TEXT DEFAULT '{}',
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ontology_functions (
                    name TEXT PRIMARY KEY,
                    description TEXT DEFAULT '',
                    params TEXT DEFAULT '{}',
                    returns TEXT DEFAULT '',
                    code TEXT DEFAULT '',
                    permission TEXT DEFAULT '',
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ontology_actions (
                    name TEXT PRIMARY KEY,
                    description TEXT DEFAULT '',
                    params TEXT DEFAULT '{}',
                    target_type TEXT DEFAULT '',
                    edits TEXT DEFAULT '{}',
                    creates INTEGER DEFAULT 0,
                    requires_confirmation INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)

    # ── Object Types ─────────────────────────────────────────────────────

    def save_type(self, name: str, description: str, properties: dict, links: dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            existing = conn.execute("SELECT name FROM ontology_types WHERE name=?", (name,)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE ontology_types SET description=?, properties=?, links=?, updated_at=? WHERE name=?",
                    (description, json.dumps(properties, ensure_ascii=False),
                     json.dumps(links, ensure_ascii=False), now, name),
                )
            else:
                conn.execute(
                    "INSERT INTO ontology_types VALUES (?,?,?,?,?,?)",
                    (name, description, json.dumps(properties, ensure_ascii=False),
                     json.dumps(links, ensure_ascii=False), now, now),
                )

    def get_type(self, name: str) -> dict | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute("SELECT * FROM ontology_types WHERE name=?", (name,)).fetchone()
        if not row:
            return None
        return {
            "name": row[0], "description": row[1],
            "properties": json.loads(row[2]), "links": json.loads(row[3]),
        }

    def delete_type(self, name: str) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute("DELETE FROM ontology_types WHERE name=?", (name,))
            return cursor.rowcount > 0

    def list_types(self) -> list[dict]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute("SELECT * FROM ontology_types").fetchall()
        return [
            {"name": r[0], "description": r[1],
             "properties": json.loads(r[2]), "links": json.loads(r[3])}
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

    # ── Functions ────────────────────────────────────────────────────────

    def save_function(self, name: str, description: str, params: dict,
                      returns: str, code: str, permission: str = "") -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            existing = conn.execute("SELECT name FROM ontology_functions WHERE name=?", (name,)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE ontology_functions SET description=?, params=?, returns=?, code=?, permission=?, updated_at=? WHERE name=?",
                    (description, json.dumps(params, ensure_ascii=False), returns,
                     code, permission, now, name),
                )
            else:
                conn.execute(
                    "INSERT INTO ontology_functions VALUES (?,?,?,?,?,?,?,?)",
                    (name, description, json.dumps(params, ensure_ascii=False),
                     returns, code, permission, now, now),
                )

    def get_function(self, name: str) -> dict | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute("SELECT * FROM ontology_functions WHERE name=?", (name,)).fetchone()
        if not row:
            return None
        return {
            "name": row[0], "description": row[1],
            "params": json.loads(row[2]), "returns": row[3],
            "code": row[4], "permission": row[5],
        }

    def delete_function(self, name: str) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute("DELETE FROM ontology_functions WHERE name=?", (name,))
            return cursor.rowcount > 0

    def list_functions(self) -> list[dict]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute("SELECT * FROM ontology_functions").fetchall()
        return [
            {"name": r[0], "description": r[1],
             "params": json.loads(r[2]), "returns": r[3],
             "code": r[4], "permission": r[5]}
            for r in rows
        ]

    # ── Actions ──────────────────────────────────────────────────────────

    def save_action(self, name: str, description: str, params: dict,
                    target_type: str, edits: dict, creates: bool,
                    requires_confirmation: bool) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            existing = conn.execute("SELECT name FROM ontology_actions WHERE name=?", (name,)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE ontology_actions SET description=?, params=?, target_type=?, edits=?, creates=?, requires_confirmation=?, updated_at=? WHERE name=?",
                    (description, json.dumps(params, ensure_ascii=False), target_type,
                     json.dumps(edits, ensure_ascii=False), int(creates),
                     int(requires_confirmation), now, name),
                )
            else:
                conn.execute(
                    "INSERT INTO ontology_actions VALUES (?,?,?,?,?,?,?,?,?)",
                    (name, description, json.dumps(params, ensure_ascii=False),
                     target_type, json.dumps(edits, ensure_ascii=False),
                     int(creates), int(requires_confirmation), now, now),
                )

    def get_action(self, name: str) -> dict | None:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute("SELECT * FROM ontology_actions WHERE name=?", (name,)).fetchone()
        if not row:
            return None
        return {
            "name": row[0], "description": row[1],
            "params": json.loads(row[2]), "target_type": row[3],
            "edits": json.loads(row[4]), "creates": bool(row[5]),
            "requires_confirmation": bool(row[6]),
        }

    def delete_action(self, name: str) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute("DELETE FROM ontology_actions WHERE name=?", (name,))
            return cursor.rowcount > 0

    def list_actions(self) -> list[dict]:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute("SELECT * FROM ontology_actions").fetchall()
        return [
            {"name": r[0], "description": r[1],
             "params": json.loads(r[2]), "target_type": r[3],
             "edits": json.loads(r[4]), "creates": bool(r[5]),
             "requires_confirmation": bool(r[6])}
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
                code="",  # YAML 里没有代码，只有签名
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
