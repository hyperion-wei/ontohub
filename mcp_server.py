from __future__ import annotations
import json
import uuid
from typing import Any

from ontohub.admin_tools import AdminTools
from ontohub.business_tools import BusinessTools
from ontohub.tool_governance import ToolGovernance


# MCP 初始化提示 — 帮助 Agent 了解本体结构和使用方法
# 该常量为唯一说明源，SSE 端点与 initialize 响应均复用之，避免文案漂移
MCP_INSTRUCTIONS = """
# Ontology Hub MCP Server

你是一个 AI Agent，已连接到 Ontology Hub（本体管理中心）。

## 架构分层（执行层 vs 展示层）

Ontology Hub 采用「执行层 + Web 面板」双端完全分离的设计：

- **执行层（本 MCP 服务）**：对外通过 HTTP / SSE / MCP 协议接入各类 Agent（Codex、Claude Desktop、Qoder、Cursor 等），承担实际的工具调用、数据读写、本体推理与权限校验。
- **Web 面板（展示层）**：只负责数据的存储与可视化展示（本体浏览、Skill 编辑、Token 生成、审计查看、图谱呈现），不参与任何 Agent 执行链路。

两端共享同一份 SQLite 数据源：面板改动即时落库，执行层实时读取，互不干扰。

## 核心概念

### 本体（Ontology）
本体是知识的结构化表示，包含：
- **对象类型（Object Type / Class）**：定义实体的属性、关系与约束，如 Skill、Workspace
- **实例（Instance）**：对象类型的具体实例，继承所属类型的规则
- **函数（Function）**：只读查询逻辑，无副作用
- **操作（Action）**：数据变更操作，可能需要确认

### 工作空间（Workspace）
- 每个 Workspace 是独立的本体空间，数据完全隔离
- 使用 `ontology_list_workspaces` 查看所有工作空间
- 使用 `ontology_switch_workspace` 切换工作空间

### Skill = 本体里的一个类（Class / Object Type）
Skill **不是硬编码的路由表**，而是直接作为本体里的一个 Object Type 建模：
- 类属性：`trigger`（触发条件）、`prompt`（提示词模板）、`tools`（依赖工具）、`status`、`version` 等
- 每条具体技能就是 Skill 类的一个实例，天然享有本体的所有能力：可查询、可遍历、可版本化、可权限控制、可审计
- 新增或修改 Skill **无需改代码**，通过 `action:createSkill` / `action:updateSkill` / `action:deleteSkill` 即可完成

## 建模原则（Ontology Modeling Principle）

**万物皆为本体**，但建模时必须区分「实体（Entity / Object Type）」与「属性（Property / Literal）」：

### 判定规则（二选一）
- **字面量 → 属性**：数字 / 字符串 / 布尔值 / 时间戳 / 枚举等「终点值」，本身没有更多要描述的，直接作为字段挂在实体上
- **有一堆属性要描述 → 实体**：一旦你想给一个概念加上其他描述（状态 / 时间 / 备注 / 外键 / 生命周期），它就自动升格为独立 Object Type

### 示例对照（LLM 领域）
| 概念 | 判定 | 理由 |
|------|------|------|
| `baseUrl`（URL 字符串） | 属性 | 只是字面量，一个 URL 就够 |
| `region` / `label` / `rateLimit` | 属性 | 字面量 |
| `keyValue`（密钥字符串本身） | 属性 | 字面量 |
| **ApiKey**（密钥的完整生命周期） | **实体** | 有 status / scopes / expiresAt / rotatedFrom / lastUsedAt / createdBy 等一堆要描述 |
| **Provider**（提供商） | **实体** | 有官网域名 / 客服联系方式 / 公司总部 / 是否支持国内访问等一堆要描述 |
| **Endpoint**（接入点上下文） | **实体** | 有 baseUrl / region / rateLimit / status / notes 等一堆要描述 |

### 反面原则
- **不要过度联想**：只关注当前需要的功能，不为想象中的未来需求提前建实体
- **不要过度扁平**：一旦某字段开始承载「生命周期 / 状态 / 权限 / 历史 / 轮换」，立刻拆出独立类型

### 建模决策流程
1. 列出需要记录的信息点
2. 逐项问自己：「它自己还有一堆属性要描述吗？」
   - 否 → 归为实体的属性
   - 是 → 升格为独立 Object Type，建外键 link 回上一层
3. 校验关系基数（1-1 / 1-N / N-N），确定 link 方向与 foreign_key
4. 主键命名：`<类型缩写>Id`，配 `id_prefix`（如 PRV / EP / KEY / MOD）

## 工具暴露策略（MCP Tool 分层）

Function 与 Action 全部作为 MCP Tool 对外暴露；本体 schema 修改与 workspace 管理归入 Admin Tool，只在建设阶段使用。

| 前缀 | 类别 | 面向对象 | 说明 |
|------|------|---------|------|
| `function:*` | Function Tool | **业务 Agent（运行期）** | 只读查询，无副作用 |
| `action:*` | Action Tool | **业务 Agent（运行期）** | 数据变更操作，可能需 `confirmed=true` |
| `ontology_*` | Admin Tool | **建设者（建设期）** | 修改本体 schema、类型、实例、workspace，运行期 Agent 不应持有 |

### 千人千面 Token（Workspace + 角色 → Tool 集合）
- MCP Token 按 **workspace + 角色** 分配可用工具集合，不同 Agent 拿到的 tool 列表不同，实现千人千面
- Web 面板「工具管理」页支持**一键复制 MCP 配置**（包含 URL、Authorization、X-Workspace、X-Role 头），粘进 Codex / Claude Desktop / Qoder 的 `mcp.json` 即可直接使用
- 运行期 Agent 的 Token 通常只包含 `function:*` + `action:*`；`ontology_*` 需在建设期显式授予，投产前应回收

## 校验规则 / 公理（Axiom）

规则不是外挂的独立校验器，而是**内嵌在本体、Function、Action 三层**，形成完整约束链：

- **本体层**：Object Type 的 `properties` 定义字段类型 / 必填 / 枚举；`links` 定义关系约束（例如「Skill 必须属于某个 Workspace」）
- **Function 层**：查询逻辑内嵌前置条件与过滤公理（例如 `function:findSkillByTrigger` 只返回 `status=active` 的 Skill）
- **Action 层**：变更逻辑内嵌 `edits` 字段白名单与 `requires_confirmation` 门禁（例如 `action:deleteSkill` 必须 `confirmed=true`）
- **实例继承 + 覆写**：实例默认继承所属 Object Type 的全部规则，同时允许在实例级别附加自身独有的规则字段（例如某个 Skill 特有的 cooldown、白名单、生效时间窗）

## 快速开始

### 1. 了解当前本体结构
```
调用 ontology_get_schema 获取完整的本体定义
调用 ontology_list_types 查看所有对象类型
```

### 2. 查看可用的 Skill
```
调用 function:searchSkills 搜索技能
调用 function:listSkillsByWorkspace 列出当前工作空间中的技能
调用 function:getSkillDetail 获取指定 Skill 的完整定义
```

### 3. 执行 Skill
```
根据 Skill 的 prompt 指导执行相应操作
使用 action:recordExecution 记录执行结果
```

## 注意事项

1. **权限控制**：Token 决定可见的工具集合，越权调用会返回 `Permission denied`
2. **确认机制**：`requires_confirmation=true` 的 Action 必须显式传入 `confirmed=true` 才会执行
3. **Workspace 隔离**：所有查询与变更都限定在当前 Workspace，切换前先确认目标空间
4. **审计日志**：所有工具调用都会落审计表，可回溯
5. **Admin Tool 慎用**：`ontology_*` 会改变本体结构本身，运行期 Agent 不应调用；建设期使用后建议回收 Token

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
