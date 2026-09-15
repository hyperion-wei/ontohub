from __future__ import annotations
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from ontohub.core.store import ObjectStore
from ontohub.core.schema_store import SchemaStore
from ontohub.core.audit import AuditLogger
from ontohub.core.token_store import TokenStore
from ontohub.dynamic_functions import DynamicFunctionRegistry
from ontohub.tool_governance import ToolGovernance
from ontohub.admin_tools import AdminTools
from ontohub.business_tools import BusinessTools
from ontohub.mcp_server import MCPServer


DB_PATH = os.environ.get("ONTOHUB_DB", os.path.join(os.path.dirname(__file__), ".ontohub.db"))
CONFIG_DIR = os.environ.get("ONTOHUB_CONFIG", os.path.join(os.path.dirname(__file__), "config"))

# MCP 服务地址配置（优先级：环境变量 > 自动检测）
# 支持多种部署方式：
# - 本地开发: http://localhost:5175 (Vite 代理)
# - 本地直连: http://localhost:8100 (直接访问后端)
# - 域名部署: https://onto.example.com (Nginx 反向代理)
# - IP 部署: http://192.168.1.100:5175
MCP_BASE_URL = os.environ.get("ONTOHUB_MCP_URL", "")

# 默认前端地址（Agent 通过此地址访问，由 Vite/Nginx 代理到后端）
DEFAULT_FRONTEND_URL = "http://localhost:5175"


def get_mcp_base_url(request: Request | None = None) -> str:
    """获取 MCP 基础 URL，支持自动检测和手动配置。
    
    优先级：
    1. 环境变量 ONTOHUB_MCP_URL
    2. X-Forwarded-Host（Nginx 代理）
    3. 默认前端地址（localhost:5175）
    """
    # 1. 优先使用环境变量
    if MCP_BASE_URL:
        return MCP_BASE_URL.rstrip("/")
    
    # 2. 从请求中自动检测（如果通过 Nginx 等反向代理访问）
    if request:
        # 检查 X-Forwarded-Host（Nginx 代理）
        forwarded_host = request.headers.get("x-forwarded-host")
        forwarded_proto = request.headers.get("x-forwarded-proto", "http")
        if forwarded_host:
            return f"{forwarded_proto}://{forwarded_host}".rstrip("/")
    
    # 3. 默认使用前端地址（Agent 通过前端代理访问后端）
    # 注意：即使请求直接到达后端（8100），也返回前端地址（5175）
    # 因为 Agent 应该通过前端代理访问，而不是直接访问后端
    return DEFAULT_FRONTEND_URL


def _sync_functions_from_yaml(schema_store: SchemaStore, ontology_path: str) -> int:
    """将 YAML 中内嵌的 function code 同步到当前 workspace（仅填充空 code 的项）。

    幂等操作：已存在且 code 非空的 function 不会被覆盖（避免覆盖用户自定义实现）。
    返回同步的 function 数量。
    """
    import yaml
    if not os.path.exists(ontology_path):
        return 0
    with open(ontology_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    yaml_fns = raw.get("functions", {}) or {}
    if not yaml_fns:
        return 0
    synced = 0
    for name, defn in yaml_fns.items():
        code = defn.get("code") or ""
        if not code:
            continue
        existing = schema_store.get_function(name)
        if existing and (existing.get("code") or "").strip():
            continue  # 尊重已有实现
        schema_store.save_function(
            name=name,
            description=defn.get("description", "") if not existing else existing.get("description", ""),
            params=defn.get("params", {}) if not existing else existing.get("params", {}),
            returns=(defn.get("returns", "") if isinstance(defn.get("returns"), str) else json.dumps(defn.get("returns", ""))) if not existing else existing.get("returns", ""),
            code=code,
            permission=defn.get("permission", "") if not existing else existing.get("permission", ""),
        )
        synced += 1
    return synced


def _sync_types_from_yaml(schema_store: SchemaStore, ontology_path: str) -> int:
    """将 YAML 中的 object_type 定义同步到当前 workspace（仅新增或补充 id_prefix）。

    已存在的类型会被重新写入，以便 YAML 中新增的 id_prefix 等元数据生效。
    实例数据不会受影响。
    """
    import yaml
    if not os.path.exists(ontology_path):
        return 0
    with open(ontology_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    yaml_types = raw.get("object_types", {}) or {}
    updated = 0
    for name, defn in yaml_types.items():
        schema_store.save_type(
            name=name,
            description=defn.get("description", ""),
            properties=defn.get("properties", {}),
            links=defn.get("links", {}),
        )
        updated += 1
    return updated


def _sync_actions_from_yaml(schema_store: SchemaStore, ontology_path: str) -> int:
    """同步 YAML 中的 action 定义（包含 edits / requires_confirmation 等）。"""
    import yaml
    if not os.path.exists(ontology_path):
        return 0
    with open(ontology_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    yaml_actions = raw.get("actions", {}) or {}
    n = 0
    for name, defn in yaml_actions.items():
        schema_store.save_action(
            name=name,
            description=defn.get("description", ""),
            params=defn.get("params", {}),
            target_type=defn.get("target_type", ""),
            edits=defn.get("edits", {}),
            creates=defn.get("creates", False),
            requires_confirmation=defn.get("requires_confirmation", False),
        )
        n += 1
    return n


def _ensure_default_workspace_instance(store: ObjectStore, schema_store: SchemaStore) -> None:
    """确保每个定义了 Workspace 类型的 workspace 内都有一个同名 Workspace 实例（便于 traverse）。"""
    original_schema_ws = schema_store.get_workspace()
    original_store_ws = store.get_workspace()
    try:
        for ws in schema_store.list_workspaces():
            name = ws["name"]
            # 逐个 workspace 检查，empty 模板的 workspace 没有 Workspace 类型则跳过
            schema_store.set_workspace(name)
            if not schema_store.get_type("Workspace"):
                continue
            try:
                pk = schema_store.get_primary_key("Workspace")
            except (KeyError, ValueError):
                continue
            store.set_workspace(name)
            if store.get("Workspace", name) is None:
                store.create("Workspace", name, {
                    pk: name,
                    "name": name,
                    "description": ws.get("description", ""),
                    "status": "active",
                    "createdAt": ws.get("created_at") or datetime.now(timezone.utc).isoformat(),
                })
    finally:
        schema_store.set_workspace(original_schema_ws)
        store.set_workspace(original_store_ws)


def create_mcp_server(config_dir: str = CONFIG_DIR, db_path: str = DB_PATH) -> MCPServer:
    """初始化所有组件并创建 MCP Server。"""
    store = ObjectStore(db_path)
    schema_store = SchemaStore(db_path)
    audit = AuditLogger(db_path)
    token_store = TokenStore(db_path)
    governance = ToolGovernance()
    functions = DynamicFunctionRegistry(store, schema_store)

    # 从 YAML 导入本体（如果 DB 为空）
    ontology_path = os.path.join(config_dir, "skill_ontology.yaml")
    if os.path.exists(ontology_path) and not schema_store.list_types():
        counts = schema_store.import_from_yaml(ontology_path)
        print(f"Imported ontology: {counts}")
    elif os.path.exists(ontology_path):
        # 已初始化：同步 YAML 中的类型/动作/函数实现（幂等）
        t = _sync_types_from_yaml(schema_store, ontology_path)
        a = _sync_actions_from_yaml(schema_store, ontology_path)
        f = _sync_functions_from_yaml(schema_store, ontology_path)
        if f:
            print(f"Synced from YAML: types={t} actions={a} functions_filled={f}")

    # 确保每个 workspace 内都有同名 Workspace 实例（便于 traverse）
    _ensure_default_workspace_instance(store, schema_store)

    # 加载种子数据（可选）
    seed_path = os.path.join(config_dir, "skill_seed.yaml")
    if os.path.exists(seed_path) and not store.list_types():
        import yaml
        with open(seed_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        for object_type, objects in raw.items():
            if not objects:
                continue
            try:
                pk = schema_store.get_primary_key(object_type)
            except (KeyError, ValueError):
                continue
            for obj in objects:
                object_id = obj.get(pk)
                if object_id:
                    store.create(object_type, object_id, obj)
        print(f"Loaded seed data: {list(raw.keys())}")

    # 从 DB 加载动态注册的 Function
    loaded = functions.load_from_db()
    if loaded:
        print(f"Loaded {loaded} dynamic functions from DB")

    admin_tools = AdminTools(store, schema_store, functions, governance, audit)
    business_tools = BusinessTools(store, schema_store, functions, audit)
    return MCPServer(admin_tools, business_tools, governance)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.mcp = create_mcp_server()
    yield


app = FastAPI(title="Ontology Hub", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── MCP Endpoints ─────────────────────────────────────────────────────────

@app.post("/mcp/message")
async def mcp_message(request: Request):
    """MCP JSON-RPC 消息端点。"""
    body = await request.json()
    session_id = request.headers.get("X-Session-Id") or request.query_params.get("session_id")
    mcp: MCPServer = request.app.state.mcp
    result = mcp.handle_message(body, session_id)
    if result is None:
        return JSONResponse(content={}, status_code=202)
    return result


@app.get("/mcp/sse")
async def mcp_sse(request: Request):
    """MCP SSE 长连接端点（用于工具发现和实时通知）。"""
    mcp: MCPServer = request.app.state.mcp
    
    # 获取请求头中的认证信息
    auth_header = request.headers.get("authorization", "")
    workspace = request.headers.get("x-workspace", "default")
    role = request.headers.get("x-role", "admin")
    
    # 如果有 Authorization header，验证 token
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        token_store = TokenStore(DB_PATH)
        token_info = token_store.validate_token(token)
        if token_info:
            workspace = token_info.get("workspace", workspace)
            role = token_info.get("role", role)
            # 切换 workspace
            mcp._admin._schema_store.set_workspace(workspace)
            mcp._admin._store.set_workspace(workspace)

    async def event_stream():
        # 获取当前状态
        current_workspace = mcp._admin._schema_store.get_workspace()
        all_tools = mcp._get_all_tools()
        types = mcp._admin._schema_store.list_types()
        functions = mcp._admin._schema_store.list_functions()
        actions = mcp._admin._schema_store.list_actions()
        
        # 统计 Skill 数量
        skill_count = 0
        try:
            skills = mcp._admin._store.query("Skill", None, None)
            skill_count = len(skills)
        except:
            pass
        
        # 发送 endpoint 事件（MCP 协议要求）
        yield {
            "event": "endpoint",
            "data": json.dumps({
                "endpoint": "/mcp/message",
            }),
        }
        
        # 发送初始化提示
        instructions = f"""# Ontology Hub MCP Server

欢迎！你是一个 AI Agent，已连接到 Ontology Hub。

## 当前状态
- Workspace: {current_workspace}
- 可用工具: {len(all_tools)} 个
- 对象类型: {len(types)} 个
- Skill 数量: {skill_count} 个

## 快速开始
1. 调用 `ontology_get_schema` 了解本体结构
2. 调用 `function:searchSkills` 或 `function:listSkillsByWorkspace` 查看可用的 Skill
3. 根据 Skill 的 prompt 执行任务

## 工具类型
- `ontology_*`: Admin 工具（管理本体结构）
- `function:*`: 查询函数（只读）
- `action:*`: 操作（修改数据）
"""
        yield {
            "event": "instructions",
            "data": json.dumps({"instructions": instructions}, ensure_ascii=False),
        }
        
        # 发送工具列表
        admin_tools = [t for t in all_tools if t["name"].startswith("ontology_")]
        function_tools = [t for t in all_tools if t["name"].startswith("function:")]
        action_tools = [t for t in all_tools if t["name"].startswith("action:")]
        
        yield {
            "event": "tools",
            "data": json.dumps({
                "tools": all_tools,
                "summary": {
                    "total": len(all_tools),
                    "admin": len(admin_tools),
                    "function": len(function_tools),
                    "action": len(action_tools),
                },
                "hints": {
                    "admin": "ontology_* 工具用于管理本体结构",
                    "function": "function:* 工具用于查询数据（只读）",
                    "action": "action:* 工具用于修改数据",
                }
            }, ensure_ascii=False),
        }
        
        # 发送本体结构概览
        yield {
            "event": "schema",
            "data": json.dumps({
                "workspace": current_workspace,
                "types": [{"name": t["name"], "description": t.get("description", "")} for t in types],
                "functions": [{"name": f["name"], "description": f.get("description", "")} for f in functions],
                "actions": [{"name": a["name"], "description": a.get("description", "")} for a in actions],
            }, ensure_ascii=False),
        }
        
        # 保持连接（发送心跳）
        import asyncio
        while True:
            await asyncio.sleep(30)
            yield {
                "event": "ping",
                "data": json.dumps({"timestamp": datetime.now(timezone.utc).isoformat()}),
            }

    return EventSourceResponse(event_stream())


# ── 管理端点（非 MCP，直接 HTTP） ──────────────────────────────────────────

@app.get("/api/tools")
async def list_tools(request: Request, role: str = "admin"):
    """列出所有可用工具（按角色过滤）。"""
    mcp: MCPServer = request.app.state.mcp
    all_tools = mcp._get_all_tools()
    filtered = mcp._governance.filter_tools(role, all_tools)
    return {"tools": filtered, "total": len(filtered), "role": role}


@app.post("/api/tools/call")
async def call_tool(request: Request):
    """直接调用工具（非 MCP 协议，方便测试）。"""
    body = await request.json()
    tool_name = body.get("name", "")
    arguments = body.get("arguments", {})
    role = body.get("role", "admin")
    user_id = body.get("user_id", "api")

    mcp: MCPServer = request.app.state.mcp

    if not mcp._governance.can_use_tool(role, tool_name):
        return {"error": f"Permission denied: role '{role}' cannot use tool '{tool_name}'"}

    try:
        if tool_name.startswith("ontology_"):
            result = mcp._admin.call(tool_name, arguments, user_id)
        elif tool_name.startswith("function:") or tool_name.startswith("action:"):
            result = mcp._business.call(tool_name, arguments, user_id)
        else:
            return {"error": f"Unknown tool: {tool_name}"}
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/graph")
async def get_graph(request: Request):
    """获取图可视化数据。"""
    mcp: MCPServer = request.app.state.mcp
    return mcp._admin._get_graph({})


@app.get("/api/schema")
async def get_schema(request: Request):
    """获取本体完整定义。"""
    mcp: MCPServer = request.app.state.mcp
    return mcp._admin._get_schema({})


@app.get("/api/roles")
async def list_roles(request: Request):
    """列出所有角色。"""
    mcp: MCPServer = request.app.state.mcp
    return mcp._admin._list_roles({})


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "ontohub"}


# ── Workspace 管理端点 ───────────────────────────────────────────────────

@app.get("/api/workspaces")
async def list_workspaces(request: Request):
    """列出所有工作空间。"""
    mcp: MCPServer = request.app.state.mcp
    return mcp._admin._list_workspaces({})


@app.post("/api/workspaces")
async def create_workspace(request: Request):
    """创建新工作空间（可选模板：empty / default / yaml）。"""
    body = await request.json()
    name = body.get("name", "")
    description = body.get("description", "")
    template = body.get("template", "empty")
    mcp: MCPServer = request.app.state.mcp
    return mcp._admin._create_workspace({
        "name": name,
        "description": description,
        "template": template,
    })


@app.delete("/api/workspaces/{name}")
async def delete_workspace(name: str, request: Request):
    """删除工作空间。"""
    mcp: MCPServer = request.app.state.mcp
    return mcp._admin._delete_workspace({"name": name})


@app.post("/api/workspaces/switch")
async def switch_workspace(request: Request):
    """切换当前工作空间。"""
    body = await request.json()
    name = body.get("name", "")
    mcp: MCPServer = request.app.state.mcp
    return mcp._admin._switch_workspace({"name": name})


@app.get("/api/workspaces/current")
async def get_current_workspace(request: Request):
    """获取当前工作空间。"""
    mcp: MCPServer = request.app.state.mcp
    return mcp._admin._get_current_workspace({})


# ── MCP Token 管理 ───────────────────────────────────────────────────────

@app.post("/api/mcp/token")
async def generate_mcp_token(request: Request):
    """生成 MCP Token（基于 workspace + role + 自定义工具）。"""
    body = await request.json()
    workspace = body.get("workspace", "default")
    role = body.get("role", "admin")
    custom_tools = body.get("tools")  # 自定义工具列表
    description = body.get("description", "")
    expires_in_days = body.get("expires_in_days")
    custom_base_url = body.get("base_url")  # 自定义域名
    
    mcp: MCPServer = request.app.state.mcp
    token_store = TokenStore(DB_PATH)
    
    # 获取 MCP 基础 URL
    base_url = custom_base_url.rstrip("/") if custom_base_url else get_mcp_base_url(request)
    
    # 获取该角色可用的工具列表
    all_tools = mcp._get_all_tools()
    if custom_tools:
        # 使用自定义工具列表
        allowed_tools = [t for t in all_tools if t["name"] in custom_tools]
        tool_names = custom_tools
    else:
        # 使用角色默认权限
        allowed_tools = mcp._governance.filter_tools(role, all_tools)
        tool_names = [t["name"] for t in allowed_tools]
    
    # 创建 token
    token_info = token_store.create_token(
        workspace=workspace,
        role=role,
        tools=tool_names if custom_tools else None,
        description=description,
        expires_in_days=expires_in_days,
    )
    
    # 生成 MCP 配置（使用 HTTP POST 模式，兼容性更好）
    config = {
        "mcpServers": {
            f"ontohub-{workspace}": {
                "url": f"{base_url}/mcp/message",
                "headers": {
                    "Authorization": f"Bearer {token_info['token']}",
                    "X-Workspace": workspace,
                    "X-Role": role
                }
            }
        }
    }
    
    return {
        "token": token_info["token"],
        "workspace": workspace,
        "role": role,
        "tools": tool_names,
        "toolCount": len(tool_names),
        "description": description,
        "expires_at": token_info.get("expires_at"),
        "base_url": base_url,
        "config": config,
        "configJson": json.dumps(config, indent=2, ensure_ascii=False)
    }


@app.get("/api/mcp/tokens")
async def list_mcp_tokens(request: Request, workspace: str | None = None):
    """列出所有 MCP Token。"""
    token_store = TokenStore(DB_PATH)
    tokens = token_store.list_tokens(workspace)
    return {"tokens": tokens, "count": len(tokens)}


@app.delete("/api/mcp/token/{token}")
async def delete_mcp_token(token: str, request: Request):
    """删除 MCP Token。"""
    token_store = TokenStore(DB_PATH)
    deleted = token_store.delete_token(token)
    if deleted:
        return {"status": "deleted", "token": token[:20] + "..."}
    return {"error": "Token not found"}


@app.get("/api/mcp/token/{token}")
async def get_mcp_token(token: str, request: Request):
    """获取 MCP Token 详情。"""
    token_store = TokenStore(DB_PATH)
    info = token_store.get_token(token)
    if not info:
        return {"error": "Token not found"}
    
    # 获取基础 URL（支持自动检测）
    base_url = get_mcp_base_url(request)
    
    # 生成配置（使用 HTTP POST 模式）
    config = {
        "mcpServers": {
            f"ontohub-{info['workspace']}": {
                "url": f"{base_url}/mcp/message",
                "headers": {
                    "Authorization": f"Bearer {info['token']}",
                    "X-Workspace": info["workspace"],
                    "X-Role": info["role"]
                }
            }
        }
    }
    info["configJson"] = json.dumps(config, indent=2, ensure_ascii=False)
    info["base_url"] = base_url
    return info


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
