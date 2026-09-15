from __future__ import annotations
import json
import uuid
from typing import Any

from ontohub.admin_tools import AdminTools
from ontohub.business_tools import BusinessTools
from ontohub.tool_governance import ToolGovernance


# MCP 初始化提示 — 帮助 Agent 了解本体结构和使用方法
MCP_INSTRUCTIONS = """
# Ontology Hub MCP Server

你是一个 AI Agent，已连接到 Ontology Hub（本体管理中心）。

## 核心概念

### 本体（Ontology）
本体是知识的结构化表示，包含：
- **对象类型（Object Type）**：定义实体的属性和关系，如 Skill、Workspace
- **实例（Instance）**：对象类型的具体实例
- **函数（Function）**：只读查询逻辑，无副作用
- **操作（Action）**：数据变更操作，可能需要确认

### 工作空间（Workspace）
- 每个 Workspace 是独立的本体空间
- 不同 Workspace 的数据完全隔离
- 使用 `ontology_list_workspaces` 查看所有工作空间
- 使用 `ontology_switch_workspace` 切换工作空间

### Skill（技能）
Skill 是 AI Agent 的能力定义，包含：
- `trigger`: 触发条件（何时使用此技能）
- `prompt`: 提示词模板（如何执行）
- `tools`: 依赖的工具列表

## 快速开始

### 1. 了解当前本体结构
```
调用 ontology_get_schema 获取完整的本体定义
调用 ontology_list_types 查看所有对象类型
```

### 2. 查看可用的 Skill
```
调用 function:searchSkills 搜索技能
调用 function:listSkillsByWorkspace 列出工作空间中的技能
```

### 3. 执行 Skill
```
根据 Skill 的 prompt 指导执行相应操作
使用 action:recordExecution 记录执行结果
```

## 工具命名规则

| 前缀 | 类型 | 说明 |
|------|------|------|
| `ontology_*` | Admin Tool | 本体管理工具（创建类型、实例等） |
| `function:*` | Function | 只读查询函数 |
| `action:*` | Action | 数据变更操作 |

## 注意事项

1. **权限控制**：不同角色有不同的工具权限
2. **确认机制**：某些 Action 需要 `confirmed=true` 确认后执行
3. **Workspace 隔离**：确保在正确的 Workspace 中操作
4. **审计日志**：所有操作都会记录审计日志

## 当前状态

- 当前 Workspace: {workspace}
- 可用工具数量: {tool_count}
- 对象类型数量: {type_count}
- Skill 数量: {skill_count}
"""


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
        
        # 获取当前状态信息
        workspace = self._admin._schema_store.get_workspace()
        all_tools = self._get_all_tools()
        types = self._admin._schema_store.list_types()
        
        # 统计 Skill 数量
        skill_count = 0
        try:
            skills = self._admin._store.query("Skill", None, None)
            skill_count = len(skills)
        except:
            pass
        
        # 生成个性化提示
        instructions = MCP_INSTRUCTIONS.format(
            workspace=workspace,
            tool_count=len(all_tools),
            type_count=len(types),
            skill_count=skill_count,
        )
        
        return self._result(msg_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": True},
            },
            "serverInfo": {
                "name": "ontohub",
                "version": "0.1.0",
                "description": "Ontology Hub - AI Agent 本体管理中心",
            },
            "sessionId": sid,
            "instructions": instructions,
        })

    def _handle_tools_list(self, msg_id: Any, session_id: str | None) -> dict:
        role = self._get_role(session_id)
        all_tools = self._get_all_tools()
        filtered = self._governance.filter_tools(role, all_tools)
        
        # 按类型分组工具
        admin_tools = [t for t in filtered if t["name"].startswith("ontology_")]
        function_tools = [t for t in filtered if t["name"].startswith("function:")]
        action_tools = [t for t in filtered if t["name"].startswith("action:")]
        
        return self._result(msg_id, {
            "tools": filtered,
            "summary": {
                "total": len(filtered),
                "admin": len(admin_tools),
                "function": len(function_tools),
                "action": len(action_tools),
            },
            "hints": {
                "admin": "ontology_* 工具用于管理本体结构（类型、实例、工作空间）",
                "function": "function:* 工具用于查询数据（只读，无副作用）",
                "action": "action:* 工具用于修改数据（可能需要确认）",
            }
        })

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
