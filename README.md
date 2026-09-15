# Ontology Hub

<div align="center">

**AI Agent 本体管理中心**

一个基于 MCP (Model Context Protocol) 的 AI Native 本体管理系统，让 AI Agent 能够发现、学习和执行 Skill。

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![React](https://img.shields.io/badge/react-18+-61dafb.svg)](https://reactjs.org/)
[![MCP](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)

</div>

---

## 什么是 Ontology Hub？

Ontology Hub 是一个 **AI Native** 的本体管理中心，它将 Skill（技能）作为本体（Ontology）进行建模和管理，通过 MCP 协议向 AI Agent 暴露工具，实现：

- **Skill 发现**：Agent 可以搜索和浏览可用的 Skill
- **Skill 执行**：Agent 根据 Skill 的 prompt 指导执行任务
- **Workspace 隔离**：不同项目/领域的 Skill 完全隔离
- **千人千面**：每个 Token 可以有独立的工具权限

## 核心概念

```
┌─────────────────────────────────────────────────────────────┐
│                        AI Agents                            │
│              (Claude, Codex, Cursor, etc.)                  │
└─────────────────────┬───────────────────────────────────────┘
                      │ MCP Protocol (HTTP POST)
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Ontology Hub                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ MCP Server  │  │ Admin Tools │  │   Business Tools    │  │
│  │             │  │ (ontology_*)│  │ (function:/action:) │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ SchemaStore │  │ ObjectStore │  │    TokenStore       │  │
│  │ (workspace) │  │ (workspace) │  │    (MCP Token)      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                      │ HTTP API
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Web Panel (React)                        │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │  图谱   │ │  结构   │ │  实例   │ │  工具   │           │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘           │
└─────────────────────────────────────────────────────────────┘
```

### 本体（Ontology）

本体是知识的结构化表示，包含：

| 概念 | 说明 | 示例 |
|------|------|------|
| **Object Type** | 定义实体的属性和关系 | Skill, Workspace, SkillExecution |
| **Instance** | 对象类型的具体实例 | 一个具体的 Skill |
| **Function** | 只读查询逻辑，无副作用 | searchSkills, listSkillsByWorkspace |
| **Action** | 数据变更操作 | createSkill, updateSkill, deleteSkill |

### Skill（技能）

Skill 是 AI Agent 的能力定义：

```yaml
Skill:
  skillId: SKI-001           # 唯一标识
  name: 代码审查              # 技能名称
  trigger: 当需要审查代码质量时  # 触发条件
  prompt: 请审查以下代码...    # 提示词模板
  tools: []                  # 依赖的工具
  workspace: default         # 所属工作空间
  status: active             # 状态
```

### Workspace（工作空间）

- 每个 Workspace 是独立的本体空间
- 不同 Workspace 的数据完全隔离
- 可以按项目、领域或团队划分

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- Windows / Linux / macOS

### 安装

```bash
# 克隆项目
git clone https://github.com/your-username/ontology-hub.git
cd ontology-hub

# 安装后端依赖
pip install -r requirements.txt

# 安装前端依赖
cd frontend
npm install
cd ..
```

### 启动服务

```bash
# 启动后端（端口 8100）
python -m uvicorn ontohub.main:app --host 0.0.0.0 --port 8100

# 启动前端（端口 5175）
cd frontend
npm run dev
```

### 访问

- **Web 面板**: http://localhost:5175
- **API 文档**: http://localhost:8100/docs

## MCP 接入

### 1. 生成 MCP Token

在 Web 面板中：
1. 进入 **工具管理** → **MCP Token**
2. 点击 **新建 Token**
3. 选择 Workspace 和角色
4. （可选）自定义工具权限
5. 点击 **生成 Token**
6. 点击 **一键复制** 复制配置

### 2. 配置到 Agent

#### Claude Desktop

编辑配置文件：
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "ontohub-default": {
      "url": "http://localhost:5175/mcp/message",
      "headers": {
        "Authorization": "Bearer mcp_default_admin_xxx",
        "X-Workspace": "default",
        "X-Role": "admin"
      }
    }
  }
}
```

#### Qoder / Cursor

编辑 `~/.qoder/mcp.json` 或 `~/.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "ontohub-default": {
      "url": "http://localhost:5175/mcp/message",
      "headers": {
        "Authorization": "Bearer mcp_default_admin_xxx",
        "X-Workspace": "default",
        "X-Role": "admin"
      }
    }
  }
}
```

### 3. 验证连接

重启 Agent 后，你应该能看到 Ontology Hub 的工具列表。

## 工具说明

### 工具命名规则

| 前缀 | 类型 | 说明 |
|------|------|------|
| `ontology_*` | Admin Tool | 本体管理工具（创建类型、实例等） |
| `function:*` | Function | 只读查询函数 |
| `action:*` | Action | 数据变更操作 |

### Admin Tools（23个）

| 工具 | 说明 |
|------|------|
| `ontology_create_workspace` | 创建工作空间 |
| `ontology_delete_workspace` | 删除工作空间 |
| `ontology_list_workspaces` | 列出所有工作空间 |
| `ontology_switch_workspace` | 切换工作空间 |
| `ontology_create_type` | 创建对象类型 |
| `ontology_update_type` | 更新对象类型 |
| `ontology_delete_type` | 删除对象类型 |
| `ontology_create_instance` | 创建实例 |
| `ontology_update_instance` | 更新实例 |
| `ontology_delete_instance` | 删除实例 |
| `ontology_get_instance` | 获取实例 |
| `ontology_query_instances` | 查询实例 |
| `ontology_traverse` | 关系遍历 |
| `ontology_register_function` | 注册函数 |
| `ontology_unregister_function` | 注销函数 |
| `ontology_list_functions` | 列出函数 |
| `ontology_get_schema` | 获取本体结构 |
| `ontology_list_types` | 列出类型 |
| `ontology_get_graph` | 获取图数据 |
| `ontology_assign_tools` | 分配工具权限 |
| `ontology_revoke_tools` | 撤销工具权限 |
| `ontology_list_roles` | 列出角色 |

### Functions（5个）

| 函数 | 说明 |
|------|------|
| `function:searchSkills` | 搜索 Skill |
| `function:listSkillsByWorkspace` | 列出工作空间中的 Skill |
| `function:getSkillDetail` | 获取 Skill 详情 |
| `function:getSkillExecutionHistory` | 获取 Skill 执行历史 |
| `function:findSkillByTrigger` | 根据触发条件查找 Skill |

### Actions（7个）

| 操作 | 说明 |
|------|------|
| `action:createSkill` | 创建 Skill |
| `action:updateSkill` | 更新 Skill |
| `action:deleteSkill` | 删除 Skill |
| `action:activateSkill` | 激活 Skill |
| `action:createWorkspace` | 创建工作空间 |
| `action:archiveWorkspace` | 归档工作空间 |
| `action:recordExecution` | 记录执行结果 |

## 使用示例

### Agent 对话示例

```
用户：帮我查看一下有哪些可用的 Skill

Agent：我来帮你查看可用的 Skill。

[调用 function:searchSkills]

目前有以下 Skill：
1. 代码审查 - 当需要审查代码质量时使用
2. 文档生成 - 当需要生成技术文档时使用

你想了解哪个 Skill 的详情？
```

### API 调用示例

```bash
# 获取本体结构
curl -X POST http://localhost:5175/mcp/message \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mcp_default_admin_xxx" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "ontology_get_schema",
      "arguments": {}
    }
  }'

# 创建 Skill
curl -X POST http://localhost:5175/mcp/message \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer mcp_default_admin_xxx" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "action:createSkill",
      "arguments": {
        "name": "代码审查",
        "trigger": "当需要审查代码质量时",
        "prompt": "请审查以下代码...",
        "workspace": "default"
      }
    }
  }'
```

## 部署

### 本地开发

```bash
# 后端
python -m uvicorn ontohub.main:app --host 0.0.0.0 --port 8100 --reload

# 前端
cd frontend && npm run dev
```

### 生产部署（Nginx）

```nginx
server {
    listen 443 ssl;
    server_name onto.example.com;
    
    location / {
        proxy_pass http://localhost:5175;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /api/ {
        proxy_pass http://localhost:8100;
    }
    
    location /mcp/ {
        proxy_pass http://localhost:8100;
    }
}
```

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ONTOHUB_DB` | 数据库文件路径 | `.ontohub.db` |
| `ONTOHUB_CONFIG` | 配置文件目录 | `config/` |
| `ONTOHUB_MCP_URL` | MCP 服务地址 | 自动检测 |

## 项目结构

```
ontohub/
├── core/                   # 核心模块
│   ├── store.py           # 实例存储（支持 workspace 隔离）
│   ├── schema_store.py    # Schema 存储（支持 workspace 隔离）
│   ├── token_store.py     # MCP Token 存储
│   └── audit.py           # 审计日志
├── frontend/              # React 前端
│   ├── src/
│   │   ├── components/    # UI 组件
│   │   └── App.tsx        # 主应用
│   └── vite.config.ts     # Vite 配置
├── config/                # 配置文件
│   └── skill_ontology.yaml # Skill 本体定义
├── admin_tools.py         # Admin 工具
├── business_tools.py      # 业务工具
├── mcp_server.py          # MCP 服务器
├── main.py                # FastAPI 入口
└── requirements.txt       # Python 依赖
```

## 技术栈

- **后端**: FastAPI, SQLite, Python 3.10+
- **前端**: React 18, TypeScript, Tailwind CSS, D3.js
- **协议**: MCP (Model Context Protocol)
- **数据库**: SQLite（支持 workspace 隔离）

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

[MIT License](LICENSE)

---

<div align="center">

**让 AI Agent 拥有可发现、可学习、可执行的 Skill**

</div>
