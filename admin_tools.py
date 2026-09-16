from __future__ import annotations
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from ontohub.core.store import ObjectStore
from ontohub.core.schema_store import SchemaStore
from ontohub.core.audit import AuditLogger
from ontohub.dynamic_functions import DynamicFunctionRegistry, SandboxError
from ontohub.graph_builder import build_graph
from ontohub.tool_governance import ToolGovernance


# YAML 本体模板路径（创建 workspace 时 template=yaml 使用）
_DEFAULT_CONFIG_DIR = os.environ.get(
    "ONTOHUB_CONFIG",
    os.path.join(os.path.dirname(__file__), "config"),
)
_DEFAULT_ONTOLOGY_YAML = os.path.join(_DEFAULT_CONFIG_DIR, "skill_ontology.yaml")


class AdminTools:
    """本体管理工具集 — 15 个 Admin Tool 的实现。"""

    def __init__(
        self,
        store: ObjectStore,
        schema_store: SchemaStore,
        functions: DynamicFunctionRegistry,
        governance: ToolGovernance,
        audit: AuditLogger,
    ):
        self._store = store
        self._schema_store = schema_store
        self._functions = functions
        self._governance = governance
        self._audit = audit

    # ── 工具定义（MCP Tool Schema） ──────────────────────────────────────

    def get_tool_definitions(self) -> list[dict]:
        return [
            {
                "name": "ontology_create_workspace",
                "description": "创建新的工作空间（可选择空白或从模板初始化）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "工作空间名称"},
                        "description": {"type": "string", "description": "工作空间描述"},
                        "template": {
                            "type": "string",
                            "enum": ["empty", "default", "yaml"],
                            "description": "初始化模板：empty=空白（默认），default=复制 default workspace 的 types/functions/actions，yaml=从 config/skill_ontology.yaml 导入官方本体模板",
                            "default": "empty",
                        },
                    },
                    "required": ["name"],
                },
            },
            {
                "name": "ontology_delete_workspace",
                "description": "删除工作空间及其所有数据",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "工作空间名称"},
                    },
                    "required": ["name"],
                },
            },
            {
                "name": "ontology_list_workspaces",
                "description": "列出所有工作空间",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "ontology_switch_workspace",
                "description": "切换当前工作空间",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "工作空间名称"},
                    },
                    "required": ["name"],
                },
            },
            {
                "name": "ontology_get_current_workspace",
                "description": "获取当前工作空间信息",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "ontology_create_type",
                "description": "创建新的对象类型（定义属性、主键、关系）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "类型名称"},
                        "description": {"type": "string", "description": "类型描述"},
                        "properties": {"type": "object", "description": "属性定义 {字段名: {type, required, primary_key, description}}"},
                        "links": {"type": "object", "description": "关系定义 {关系名: {target, foreign_key}}"},
                    },
                    "required": ["name", "properties"],
                },
            },
            {
                "name": "ontology_update_type",
                "description": "修改对象类型（加字段、改关系）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "properties": {"type": "object"},
                        "links": {"type": "object"},
                    },
                    "required": ["name"],
                },
            },
            {
                "name": "ontology_delete_type",
                "description": "删除对象类型及其所有实例",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                    },
                    "required": ["name"],
                },
            },
            {
                "name": "ontology_create_instance",
                "description": "创建本体实例",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_type": {"type": "string"},
                        "data": {"type": "object", "description": "实例数据（必须包含主键字段）"},
                    },
                    "required": ["object_type", "data"],
                },
            },
            {
                "name": "ontology_update_instance",
                "description": "修改本体实例",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_type": {"type": "string"},
                        "object_id": {"type": "string"},
                        "changes": {"type": "object"},
                    },
                    "required": ["object_type", "object_id", "changes"],
                },
            },
            {
                "name": "ontology_delete_instance",
                "description": "删除本体实例",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_type": {"type": "string"},
                        "object_id": {"type": "string"},
                    },
                    "required": ["object_type", "object_id"],
                },
            },
            {
                "name": "ontology_get_instance",
                "description": "查询单个实例",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_type": {"type": "string"},
                        "object_id": {"type": "string"},
                    },
                    "required": ["object_type", "object_id"],
                },
            },
            {
                "name": "ontology_query_instances",
                "description": "条件查询实例列表",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_type": {"type": "string"},
                        "filters": {"type": "object", "description": "过滤条件 {字段: 值}"},
                        "properties": {"type": "array", "items": {"type": "string"}, "description": "只返回指定字段"},
                        "limit": {"type": "integer", "description": "返回条数限制"},
                    },
                    "required": ["object_type"],
                },
            },
            {
                "name": "ontology_traverse",
                "description": "关系遍历查询",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "object_type": {"type": "string"},
                        "object_id": {"type": "string"},
                        "link_name": {"type": "string"},
                        "properties": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["object_type", "object_id", "link_name"],
                },
            },
            {
                "name": "ontology_register_function",
                "description": "注册新 Function（上传 Python 代码，动态加载）",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Function 名称"},
                        "code": {"type": "string", "description": "Python 函数体代码（接收 params 参数，返回结果）"},
                        "description": {"type": "string"},
                        "params": {"type": "object", "description": "参数签名 {参数名: {type, required, description}}"},
                        "returns": {"type": "string", "description": "返回值描述"},
                    },
                    "required": ["name", "code"],
                },
            },
            {
                "name": "ontology_unregister_function",
                "description": "注销 Function",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                    },
                    "required": ["name"],
                },
            },
            {
                "name": "ontology_list_functions",
                "description": "列出所有已注册的 Function",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "ontology_get_schema",
                "description": "获取本体完整定义（类型、关系、函数、操作）",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "ontology_list_types",
                "description": "列出所有对象类型",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "ontology_get_graph",
                "description": "获取图数据（节点+边，供前端可视化）",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "ontology_assign_tools",
                "description": "给角色分配工具权限",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string"},
                        "tools": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["role", "tools"],
                },
            },
            {
                "name": "ontology_revoke_tools",
                "description": "撤销角色的工具权限",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string"},
                        "tools": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["role", "tools"],
                },
            },
            {
                "name": "ontology_list_roles",
                "description": "列出所有角色及其工具权限",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    # ── 工具调用路由 ─────────────────────────────────────────────────────

    def call(self, tool_name: str, arguments: dict, user_id: str = "system") -> Any:
        handlers = {
            "ontology_create_workspace": self._create_workspace,
            "ontology_delete_workspace": self._delete_workspace,
            "ontology_list_workspaces": self._list_workspaces,
            "ontology_switch_workspace": self._switch_workspace,
            "ontology_get_current_workspace": self._get_current_workspace,
            "ontology_create_type": self._create_type,
            "ontology_update_type": self._update_type,
            "ontology_delete_type": self._delete_type,
            "ontology_create_instance": self._create_instance,
            "ontology_update_instance": self._update_instance,
            "ontology_delete_instance": self._delete_instance,
            "ontology_get_instance": self._get_instance,
            "ontology_query_instances": self._query_instances,
            "ontology_traverse": self._traverse,
            "ontology_register_function": self._register_function,
            "ontology_unregister_function": self._unregister_function,
            "ontology_list_functions": self._list_functions,
            "ontology_get_schema": self._get_schema,
            "ontology_list_types": self._list_types,
            "ontology_get_graph": self._get_graph,
            "ontology_assign_tools": self._assign_tools,
            "ontology_revoke_tools": self._revoke_tools,
            "ontology_list_roles": self._list_roles,
        }
        handler = handlers.get(tool_name)
        if not handler:
            raise KeyError(f"Unknown admin tool: {tool_name}")
        return handler(arguments)

    # ── Workspace 管理 ───────────────────────────────────────────────────

    def _create_workspace(self, args: dict) -> dict:
        name = args["name"]
        description = args.get("description", "")
        template = (args.get("template") or "empty").strip().lower()
        if template not in ("empty", "default", "yaml"):
            return {"error": f"Invalid template '{template}'. Must be one of: empty, default, yaml"}

        result = self._schema_store.create_workspace(name, description)
        if "error" in result:
            return result

        self._audit.log("system", "create_workspace", name)

        # 应用模板
        applied = self._apply_workspace_template(name, template)

        # 同步在新 workspace 内创建 Workspace 实例（代表自身），
        # 以便 Skill.belongsToWorkspace 等关系能被 traverse。
        self._ensure_workspace_instance(name, description)

        result["template"] = template
        result["applied"] = applied
        return result

    def _apply_workspace_template(self, ws_name: str, template: str) -> dict:
        """为新建的 workspace 应用模板，返回应用统计。"""
        stats = {"types": 0, "functions": 0, "actions": 0}
        if template == "empty":
            return stats

        if template == "default":
            copy_result = self._schema_store.copy_workspace_schema("default", ws_name)
            if "error" in copy_result:
                stats["error"] = copy_result["error"]
                return stats
            stats["types"] = copy_result.get("types", 0)
            stats["functions"] = copy_result.get("functions", 0)
            stats["actions"] = copy_result.get("actions", 0)
            return stats

        # template == "yaml"
        yaml_path = _DEFAULT_ONTOLOGY_YAML
        if not os.path.exists(yaml_path):
            stats["error"] = f"YAML template not found: {yaml_path}"
            return stats
        original_ws = self._schema_store.get_workspace()
        try:
            self._schema_store.set_workspace(ws_name)
            counts = self._schema_store.import_from_yaml(yaml_path)
            stats["types"] = counts.get("types", 0)
            stats["functions"] = counts.get("functions", 0)
            stats["actions"] = counts.get("actions", 0)
        finally:
            self._schema_store.set_workspace(original_ws)
        return stats

    def _ensure_workspace_instance(self, ws_name: str, description: str = "") -> None:
        """确保指定 workspace 内存在一个同名的 Workspace 实例。

        仅当目标 workspace 本体定义了 Workspace 类型时才写入（empty 模板的 workspace
        没有 Workspace 类型，也就不会创建实例）。失败不报错（不影响 workspace 创建）。
        """
        original_schema_ws = self._schema_store.get_workspace()
        original_store_ws = self._store.get_workspace()
        try:
            # 先切换到目标 workspace 检查类型是否存在
            self._schema_store.set_workspace(ws_name)
            if not self._schema_store.get_type("Workspace"):
                return
            pk = self._schema_store.get_primary_key("Workspace")

            self._store.set_workspace(ws_name)
            if self._store.get("Workspace", ws_name) is None:
                self._store.create("Workspace", ws_name, {
                    pk: ws_name,
                    "name": ws_name,
                    "description": description,
                    "status": "active",
                    "createdAt": datetime.now(timezone.utc).isoformat(),
                })
        except Exception:
            pass
        finally:
            self._schema_store.set_workspace(original_schema_ws)
            self._store.set_workspace(original_store_ws)

    def _delete_workspace(self, args: dict) -> dict:
        name = args["name"]
        result = self._schema_store.delete_workspace(name)
        if "error" not in result:
            self._audit.log("system", "delete_workspace", name)
        return result

    def _list_workspaces(self, args: dict) -> dict:
        workspaces = self._schema_store.list_workspaces()
        current = self._schema_store.get_workspace()
        return {
            "workspaces": workspaces,
            "current": current,
            "count": len(workspaces),
        }

    def _switch_workspace(self, args: dict) -> dict:
        name = args["name"]
        # 验证 workspace 存在
        info = self._schema_store.get_workspace_info(name)
        if not info:
            return {"error": f"Workspace '{name}' not found"}
        # 切换 schema_store 和 store 的 workspace
        self._schema_store.set_workspace(name)
        self._store.set_workspace(name)
        self._audit.log("system", "switch_workspace", name)
        return {"status": "switched", "workspace": name}

    def _get_current_workspace(self, args: dict) -> dict:
        current = self._schema_store.get_workspace()
        info = self._schema_store.get_workspace_info(current)
        return {
            "workspace": current,
            "info": info,
        }

    # ── Type 管理 ────────────────────────────────────────────────────────

    def _create_type(self, args: dict) -> dict:
        name = args["name"]
        existing = self._schema_store.get_type(name)
        if existing:
            return {"error": f"Type '{name}' already exists"}
        self._schema_store.save_type(
            name=name,
            description=args.get("description", ""),
            properties=args.get("properties", {}),
            links=args.get("links", {}),
        )
        self._audit.log("system", "create_type", name)
        return {"status": "created", "name": name}

    def _update_type(self, args: dict) -> dict:
        name = args["name"]
        existing = self._schema_store.get_type(name)
        if not existing:
            return {"error": f"Type '{name}' not found"}
        self._schema_store.save_type(
            name=name,
            description=args.get("description", existing["description"]),
            properties=args.get("properties", existing["properties"]),
            links=args.get("links", existing["links"]),
        )
        return {"status": "updated", "name": name}

    def _delete_type(self, args: dict) -> dict:
        name = args["name"]
        # 删除所有实例
        objects = self._store.all_objects(name)
        for obj in objects:
            pk = self._schema_store.get_primary_key(name)
            self._store.delete(name, obj.get(pk, ""))
        # 删除类型定义
        removed = self._schema_store.delete_type(name)
        return {"status": "deleted" if removed else "not_found", "name": name, "instances_deleted": len(objects)}

    # ── Instance CRUD ────────────────────────────────────────────────────

    def _create_instance(self, args: dict) -> dict:
        object_type = args["object_type"]
        data = args["data"]
        pk = self._schema_store.get_primary_key(object_type)
        object_id = data.get(pk)
        if not object_id:
            return {"error": f"Missing primary key '{pk}' in data"}
        result = self._store.create(object_type, object_id, data)
        self._audit.log("system", "create_instance", object_type, object_id, data)
        return {"status": "created", "object_type": object_type, "object_id": object_id, "data": result}

    def _update_instance(self, args: dict) -> dict:
        object_type = args["object_type"]
        object_id = args["object_id"]
        changes = args["changes"]
        result = self._store.update(object_type, object_id, changes)
        self._audit.log("system", "update_instance", object_type, object_id, changes)
        return {"status": "updated", "data": result}

    def _delete_instance(self, args: dict) -> dict:
        object_type = args["object_type"]
        object_id = args["object_id"]
        removed = self._store.delete(object_type, object_id)
        self._audit.log("system", "delete_instance", object_type, object_id)
        return {"status": "deleted" if removed else "not_found"}

    def _get_instance(self, args: dict) -> dict:
        obj = self._store.get(args["object_type"], args["object_id"])
        if not obj:
            return {"error": f"{args['object_type']}:{args['object_id']} not found"}
        return obj

    def _query_instances(self, args: dict) -> list[dict]:
        object_type = args["object_type"]
        filters = args.get("filters")
        properties = args.get("properties")
        limit = args.get("limit")
        results = self._store.query(object_type, filters, properties)
        if limit:
            results = results[:limit]
        return results

    def _traverse(self, args: dict) -> list[dict]:
        object_type = args["object_type"]
        object_id = args["object_id"]
        link_name = args["link_name"]
        properties = args.get("properties")

        type_def = self._schema_store.get_type(object_type)
        if not type_def:
            return [{"error": f"Type '{object_type}' not found"}]
        link_def = type_def.get("links", {}).get(link_name)
        if not link_def:
            return [{"error": f"No link '{link_name}' on {object_type}"}]

        # 反向遍历（一→多）：foreign_key 在 target 类型上，用当前实例的主键值去查
        if link_def.get("reverse"):
            source = self._store.get(object_type, object_id)
            if source is None:
                return []
            source_pk = self._schema_store.get_primary_key(object_type)
            pk_value = source.get(source_pk)
            if pk_value is None:
                return []
            fk_field = link_def.get("foreign_key", "")
            return self._store.query(link_def["target"], {fk_field: pk_value}, properties)

        # 正向遍历（多→一）：foreign_key 在当前类型上
        target_pk = self._schema_store.get_primary_key(link_def["target"])
        return self._store.traverse(object_type, object_id, link_name, link_def, target_pk, properties)

    # ── Function 注册 ────────────────────────────────────────────────────

    def _register_function(self, args: dict) -> dict:
        try:
            result = self._functions.register(
                name=args["name"],
                code=args["code"],
                description=args.get("description", ""),
                params=args.get("params"),
                returns=args.get("returns", ""),
            )
            self._audit.log("system", "register_function", args["name"])
            return result
        except SandboxError as e:
            return {"error": str(e)}

    def _unregister_function(self, args: dict) -> dict:
        removed = self._functions.unregister(args["name"])
        return {"status": "unregistered" if removed else "not_found", "name": args["name"]}

    def _list_functions(self, args: dict) -> list[dict]:
        return self._functions.list_functions()

    # ── Schema 查询 ──────────────────────────────────────────────────────

    def _get_schema(self, args: dict) -> dict:
        types = self._schema_store.list_types()
        functions = self._schema_store.list_functions()
        actions = self._schema_store.list_actions()
        return {
            "object_types": {t["name"]: t for t in types},
            "functions": {f["name"]: {k: v for k, v in f.items() if k != "code"} for f in functions},
            "actions": {a["name"]: a for a in actions},
            "typeCount": len(types),
            "functionCount": len(functions),
            "actionCount": len(actions),
        }

    def _list_types(self, args: dict) -> list[dict]:
        types = self._schema_store.list_types()
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "propertyCount": len(t.get("properties", {})),
                "linkCount": len(t.get("links", {})),
                "instanceCount": self._store.count(t["name"], None),
            }
            for t in types
        ]

    def _get_graph(self, args: dict) -> dict:
        return build_graph(self._store, self._schema_store)

    # ── 角色权限管理 ─────────────────────────────────────────────────────

    def _assign_tools(self, args: dict) -> dict:
        role = args["role"]
        tools = args["tools"]
        self._governance.assign_tools(role, tools)
        return {"status": "assigned", "role": role, "tools": self._governance.get_allowed_tools(role)}

    def _revoke_tools(self, args: dict) -> dict:
        role = args["role"]
        tools = args["tools"]
        self._governance.revoke_tools(role, tools)
        return {"status": "revoked", "role": role, "tools": self._governance.get_allowed_tools(role)}

    def _list_roles(self, args: dict) -> dict:
        return self._governance.list_roles()
