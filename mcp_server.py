from __future__ import annotations
import json
import uuid
from typing import Any

from ontohub.admin_tools import AdminTools
from ontohub.business_tools import BusinessTools
from ontohub.tool_governance import ToolGovernance


class MCPServer:
    """MCP 协议服务器 — 处理工具发现、工具调用、权限过滤。"""

    def __init__(
        self,
        admin_tools: AdminTools,
        business_tools: BusinessTools,
        governance: ToolGovernance,
    ):
        self._admin = admin_tools
        self._business = business_tools
        self._governance = governance
        self._sessions: dict[str, dict] = {}

    # ── MCP 协议处理 ─────────────────────────────────────────────────────

    def handle_message(self, message: dict, session_id: str | None = None) -> dict:
        """处理 MCP JSON-RPC 消息。"""
        method = message.get("method", "")
        msg_id = message.get("id")
        params = message.get("params", {})

        if method == "initialize":
            return self._handle_initialize(msg_id, params, session_id)
        elif method == "tools/list":
            return self._handle_tools_list(msg_id, session_id)
        elif method == "tools/call":
            return self._handle_tools_call(msg_id, params, session_id)
        elif method == "notifications/initialized":
            return None  # 无需响应
        else:
            return self._error(msg_id, -32601, f"Method not found: {method}")

    def _handle_initialize(self, msg_id: Any, params: dict, session_id: str | None) -> dict:
        sid = session_id or str(uuid.uuid4())
        self._sessions[sid] = {
            "role": params.get("role", "admin"),
            "user_id": params.get("user_id", "anonymous"),
            "initialized": True,
        }
        return self._result(msg_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": True},
            },
            "serverInfo": {
                "name": "ontohub",
                "version": "0.1.0",
            },
            "sessionId": sid,
        })

    def _handle_tools_list(self, msg_id: Any, session_id: str | None) -> dict:
        role = self._get_role(session_id)
        all_tools = self._get_all_tools()
        filtered = self._governance.filter_tools(role, all_tools)
        return self._result(msg_id, {"tools": filtered})

    def _handle_tools_call(self, msg_id: Any, params: dict, session_id: str | None) -> dict:
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        role = self._get_role(session_id)
        user_id = self._get_user_id(session_id)

        # 权限检查
        if not self._governance.can_use_tool(role, tool_name):
            return self._error(msg_id, -32600, f"Permission denied: role '{role}' cannot use tool '{tool_name}'")

        # 路由到对应的工具集
        try:
            if tool_name.startswith("ontology_"):
                result = self._admin.call(tool_name, arguments, user_id)
            elif tool_name.startswith("function:") or tool_name.startswith("action:"):
                result = self._business.call(tool_name, arguments, user_id)
            else:
                return self._error(msg_id, -32601, f"Unknown tool: {tool_name}")

            return self._result(msg_id, {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, ensure_ascii=False, indent=2, default=str),
                    }
                ],
                "isError": isinstance(result, dict) and "error" in result,
            })
        except Exception as e:
            return self._result(msg_id, {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "isError": True,
            })

    # ── 工具列表 ─────────────────────────────────────────────────────────

    def _get_all_tools(self) -> list[dict]:
        return self._admin.get_tool_definitions() + self._business.get_tool_definitions()

    def refresh_tools(self) -> int:
        """刷新工具列表（注册新 function 后调用）。返回工具总数。"""
        return len(self._get_all_tools())

    # ── 会话管理 ─────────────────────────────────────────────────────────

    def _get_role(self, session_id: str | None) -> str:
        if not session_id or session_id not in self._sessions:
            return "admin"  # 默认 admin（无会话时）
        return self._sessions[session_id].get("role", "admin")

    def _get_user_id(self, session_id: str | None) -> str:
        if not session_id or session_id not in self._sessions:
            return "system"
        return self._sessions[session_id].get("user_id", "system")

    # ── JSON-RPC 辅助 ────────────────────────────────────────────────────

    def _result(self, msg_id: Any, result: Any) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def _error(self, msg_id: Any, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}
