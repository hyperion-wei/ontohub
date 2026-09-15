from __future__ import annotations
import json
import sqlite3
import hashlib
import secrets
from datetime import datetime, timezone


class TokenStore:
    """MCP Token 存储 — 管理 Token 的创建、验证、删除。"""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS mcp_tokens (
                    token TEXT PRIMARY KEY,
                    workspace TEXT NOT NULL,
                    role TEXT NOT NULL,
                    tools TEXT DEFAULT '[]',
                    description TEXT DEFAULT '',
                    created_at TEXT,
                    expires_at TEXT,
                    last_used_at TEXT,
                    is_active INTEGER DEFAULT 1
                )
            """)

    def create_token(
        self,
        workspace: str,
        role: str,
        tools: list[str] | None = None,
        description: str = "",
        expires_in_days: int | None = None,
    ) -> dict:
        """创建新 Token。"""
        # 生成随机 token
        random_part = secrets.token_hex(16)
        token = f"mcp_{workspace}_{role}_{random_part}"
        
        now = datetime.now(timezone.utc).isoformat()
        expires_at = None
        if expires_in_days:
            from datetime import timedelta
            expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).isoformat()
        
        # 如果没有指定 tools，根据 role 获取默认工具
        if tools is None:
            tools = []  # 空列表表示使用角色默认权限
        
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO mcp_tokens 
                   (token, workspace, role, tools, description, created_at, expires_at, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (token, workspace, role, json.dumps(tools), description, now, expires_at, 1),
            )
        
        return {
            "token": token,
            "workspace": workspace,
            "role": role,
            "tools": tools,
            "description": description,
            "created_at": now,
            "expires_at": expires_at,
        }

    def get_token(self, token: str) -> dict | None:
        """获取 Token 信息。"""
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM mcp_tokens WHERE token=? AND is_active=1",
                (token,)
            ).fetchone()
        if not row:
            return None
        return {
            "token": row[0],
            "workspace": row[1],
            "role": row[2],
            "tools": json.loads(row[3]),
            "description": row[4],
            "created_at": row[5],
            "expires_at": row[6],
            "last_used_at": row[7],
            "is_active": bool(row[8]),
        }

    def validate_token(self, token: str) -> dict | None:
        """验证 Token 是否有效。"""
        info = self.get_token(token)
        if not info:
            return None
        
        # 检查是否过期
        if info["expires_at"]:
            expires = datetime.fromisoformat(info["expires_at"].replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > expires:
                return None
        
        # 更新最后使用时间
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "UPDATE mcp_tokens SET last_used_at=? WHERE token=?",
                (datetime.now(timezone.utc).isoformat(), token)
            )
        
        return info

    def list_tokens(self, workspace: str | None = None) -> list[dict]:
        """列出所有 Token。"""
        with sqlite3.connect(self._db_path) as conn:
            if workspace:
                rows = conn.execute(
                    "SELECT * FROM mcp_tokens WHERE workspace=? AND is_active=1 ORDER BY created_at DESC",
                    (workspace,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM mcp_tokens WHERE is_active=1 ORDER BY created_at DESC"
                ).fetchall()
        
        return [
            {
                "token": r[0],
                "workspace": r[1],
                "role": r[2],
                "tools": json.loads(r[3]),
                "toolCount": len(json.loads(r[3])) if json.loads(r[3]) else 0,
                "description": r[4],
                "created_at": r[5],
                "expires_at": r[6],
                "last_used_at": r[7],
            }
            for r in rows
        ]

    def delete_token(self, token: str) -> bool:
        """删除 Token（软删除）。"""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "UPDATE mcp_tokens SET is_active=0 WHERE token=?",
                (token,)
            )
            return cursor.rowcount > 0

    def revoke_token(self, token: str) -> bool:
        """撤销 Token（硬删除）。"""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM mcp_tokens WHERE token=?",
                (token,)
            )
            return cursor.rowcount > 0

    def update_token_tools(self, token: str, tools: list[str]) -> bool:
        """更新 Token 的工具权限。"""
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(
                "UPDATE mcp_tokens SET tools=? WHERE token=?",
                (json.dumps(tools), token)
            )
            return cursor.rowcount > 0
