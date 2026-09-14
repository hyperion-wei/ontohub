# Ontology Hub

本体知识图谱服务 — 通过 MCP SSE 协议暴露，任何 Agent 都能接入。

## 功能

- **本体管理**：创建/修改/删除对象类型、属性、关系
- **实例 CRUD**：增删改查本体实例
- **关系遍历**：单跳关系查询
- **动态 Function 注册**：Agent 上传 Python 代码，动态注册新函数
- **Tool 级别权限**：admin/operator/viewer 三级权限控制
- **图可视化**：D3 force 力导向图展示本体关系
- **MCP SSE 协议**：支持 Qoder、Claude Desktop、Cursor 等 MCP 客户端接入

## 快速开始

### 后端

```bash
# 安装依赖
pip install fastapi uvicorn sse-starlette pyyaml httpx

# 启动服务（端口 8100）
python -m ontohub.main
```

### 前端

```bash
cd frontend
npm install
npm run dev
# 打开 http://localhost:5175
```

## API 端点

| 端点 | 说明 |
|------|------|
| `POST /mcp/message` | MCP JSON-RPC 消息 |
| `GET /mcp/sse` | MCP SSE 长连接 |
| `GET /api/tools` | 列出工具（按角色过滤） |
| `POST /api/tools/call` | 调用工具 |
| `GET /api/graph` | 图可视化数据 |
| `GET /api/schema` | 本体完整定义 |
| `GET /api/roles` | 角色列表 |
| `GET /api/health` | 健康检查 |

## 项目结构

```
ontohub/
├── main.py              # FastAPI 入口
├── mcp_server.py        # MCP 协议处理
├── admin_tools.py       # 18 个管理工具
├── business_tools.py    # 业务工具自动生成
├── dynamic_functions.py # 动态 Function 注册引擎
├── tool_governance.py   # Tool 级别权限控制
├── graph_builder.py     # 图可视化数据构建
├── core/                # 核心层
│   ├── store.py         # 实例存储（SQLite）
│   ├── schema_store.py  # Schema 存储（SQLite）
│   ├── audit.py         # 审计日志
│   └── trace.py         # 追踪事件
├── config/              # 本体配置
│   ├── llmkey_ontology.yaml
│   └── llmkey_seed.yaml
└── frontend/            # React 前端
    └── src/
        ├── App.tsx
        └── components/
            ├── Sidebar.tsx
            ├── GraphPanel.tsx
            ├── SchemaPanel.tsx
            ├── ToolsPanel.tsx
            └── InstancesPanel.tsx
```

## License

MIT
