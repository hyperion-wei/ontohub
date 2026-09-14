from __future__ import annotations
from typing import Any

from ontohub.core.store import ObjectStore
from ontohub.core.schema_store import SchemaStore
from ontohub.core.audit import AuditLogger
from ontohub.dynamic_functions import DynamicFunctionRegistry


class BusinessTools:
    """业务工具 — 从本体的 Action 和 Function 自动生成 MCP Tool。"""

    def __init__(
        self,
        store: ObjectStore,
        schema_store: SchemaStore,
        functions: DynamicFunctionRegistry,
        audit: AuditLogger,
    ):
        self._store = store
        self._schema_store = schema_store
        self._functions = functions
        self._audit = audit

    def get_tool_definitions(self) -> list[dict]:
        """从当前本体的 Action 和 Function 生成工具定义。"""
        tools = []

        # Function tools
        for fn in self._functions.list_functions():
            properties = {}
            required = []
            for pname, pdef in fn.get("params", {}).items():
                prop = {"type": _yaml_type_to_json(pdef.get("type", "string"))}
                if pdef.get("description"):
                    prop["description"] = pdef["description"]
                if pdef.get("values"):
                    prop["enum"] = pdef["values"]
                properties[pname] = prop
                if pdef.get("required"):
                    required.append(pname)

            tools.append({
                "name": f"function:{fn['name']}",
                "description": fn.get("description", f"Call function {fn['name']}"),
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            })

        # Action tools
        for act in self._schema_store.list_actions():
            properties = {}
            required = []
            for pname, pdef in act.get("params", {}).items():
                prop = {"type": _yaml_type_to_json(pdef.get("type", "string"))}
                if pdef.get("description"):
                    prop["description"] = pdef["description"]
                if pdef.get("values"):
                    prop["enum"] = pdef["values"]
                properties[pname] = prop
                if pdef.get("required"):
                    required.append(pname)

            # Action 需要 confirmed 参数
            properties["confirmed"] = {
                "type": "boolean",
                "description": "Set true after user has seen and approved the preview",
                "default": False,
            }

            tools.append({
                "name": f"action:{act['name']}",
                "description": f"[Action] {act.get('description', act['name'])}",
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            })

        return tools

    def call(self, tool_name: str, arguments: dict, user_id: str = "system") -> Any:
        if tool_name.startswith("function:"):
            return self._call_function(tool_name[9:], arguments, user_id)
        elif tool_name.startswith("action:"):
            return self._call_action(tool_name[7:], arguments, user_id)
        raise KeyError(f"Unknown business tool: {tool_name}")

    def _call_function(self, fn_name: str, params: dict, user_id: str) -> Any:
        try:
            result = self._functions.call(fn_name, params)
            self._audit.log(user_id, "function", None, None,
                           {"function": fn_name, "params": params},
                           {"status": "success"})
            return result
        except KeyError as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"Function execution failed: {e}"}

    def _call_action(self, act_name: str, params: dict, user_id: str) -> Any:
        action = self._schema_store.get_action(act_name)
        if not action:
            return {"error": f"Unknown action: {act_name}"}

        confirmed = params.pop("confirmed", False)
        requires_confirmation = action.get("requires_confirmation", False)

        if requires_confirmation and not confirmed:
            # Return preview
            changes = []
            if action.get("creates"):
                changes.append({"type": "create", "object_type": action["target_type"], "data": params})
            else:
                edits = action.get("edits", {})
                for field, param_key in edits.items():
                    changes.append({"field": field, "to": params.get(param_key)})
            return {
                "status": "pending_confirmation",
                "action": act_name,
                "changes": changes,
                "requires_confirmation": True,
                "message": "Please review the changes and call again with confirmed=true",
            }

        # Execute
        try:
            if action.get("creates"):
                target_type = action["target_type"]
                pk = self._schema_store.get_primary_key(target_type)
                data = dict(params)
                if pk not in data:
                    import uuid
                    data[pk] = f"{target_type[:3].upper()}-{uuid.uuid4().hex[:6].upper()}"
                result = self._store.create(target_type, data[pk], data)
            else:
                target_type = action["target_type"]
                # Find target ID from params
                target_id = None
                for key in params:
                    if key.endswith("Id") or key.endswith("_id") or key == "id":
                        target_id = params[key]
                        break
                if not target_id:
                    return {"error": "Cannot determine target object ID from params"}
                changes = {}
                edits = action.get("edits", {})
                for field, param_key in edits.items():
                    changes[field] = params.get(param_key)
                result = self._store.update(target_type, target_id, changes)

            self._audit.log(user_id, "action", None, None,
                           {"action": act_name, "params": params, "confirmed": confirmed},
                           {"status": "executed"})
            return {"status": "executed", "action": act_name, "result": result}
        except Exception as e:
            return {"error": f"Action execution failed: {e}"}


def _yaml_type_to_json(yaml_type: str) -> str:
    mapping = {
        "string": "string",
        "int": "integer",
        "integer": "integer",
        "float": "number",
        "number": "number",
        "bool": "boolean",
        "boolean": "boolean",
        "list": "array",
        "array": "array",
        "object": "object",
        "dict": "object",
        "enum": "string",
        "datetime": "string",
    }
    return mapping.get(yaml_type, "string")
