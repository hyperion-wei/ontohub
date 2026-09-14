from __future__ import annotations
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from ontohub.core.store import ObjectStore
from ontohub.core.schema_store import SchemaStore
from ontohub.core.audit import AuditLogger
from ontohub.dynamic_functions import DynamicFunctionRegistry
from ontohub.tool_governance import ToolGovernance
from ontohub.admin_tools import AdminTools
from ontohub.business_tools import BusinessTools
from ontohub.mcp_server import MCPServer


DB_PATH = os.environ.get("ONTOHUB_DB", os.path.join(os.path.dirname(__file__), ".ontohub.db"))
CONFIG_DIR = os.environ.get("ONTOHUB_CONFIG", os.path.join(os.path.dirname(__file__), "config"))


def create_mcp_server(config_dir: str = CONFIG_DIR, db_path: str = DB_PATH) -> MCPServer:
    """初始化所有组件并创建 MCP Server。"""
    store = ObjectStore(db_path)
    schema_store = SchemaStore(db_path)
    audit = AuditLogger(db_path)
    governance = ToolGovernance()
    functions = DynamicFunctionRegistry(store, schema_store)

    # 从 YAML 导入本体（如果 DB 为空）
    ontology_path = os.path.join(config_dir, "llmkey_ontology.yaml")
    if os.path.exists(ontology_path) and not schema_store.list_types():
        counts = schema_store.import_from_yaml(ontology_path)
        print(f"Imported ontology: {counts}")

    # 加载种子数据
    seed_path = os.path.join(config_dir, "llmkey_seed.yaml")
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

    async def event_stream():
        # 发送 server info
        yield {
            "event": "endpoint",
            "data": json.dumps({"endpoint": "/mcp/message"}),
        }
        # 发送工具列表
        tools = mcp._get_all_tools()
        yield {
            "event": "tools",
            "data": json.dumps({"tools": tools}, ensure_ascii=False),
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
