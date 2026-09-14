from __future__ import annotations
import fnmatch


# 默认角色-工具映射
DEFAULT_ROLES: dict[str, dict] = {
    "admin": {
        "tools": ["*"],  # 所有工具
        "description": "管理员，拥有全部工具权限",
    },
    "operator": {
        "tools": [
            "ontology_get_instance",
            "ontology_query_instances",
            "ontology_traverse",
            "ontology_get_schema",
            "ontology_list_types",
            "ontology_get_graph",
            "ontology_list_functions",
            "function:*",
            "action:*",
        ],
        "description": "操作员，可查询数据和调用业务函数/操作",
    },
    "viewer": {
        "tools": [
            "ontology_get_instance",
            "ontology_query_instances",
            "ontology_get_schema",
            "ontology_list_types",
            "ontology_get_graph",
        ],
        "description": "观察者，只能查询本体结构和实例数据",
    },
}


class ToolGovernance:
    """Tool 级别权限控制。"""

    def __init__(self):
        self._roles: dict[str, dict] = dict(DEFAULT_ROLES)

    def can_use_tool(self, role: str, tool_name: str) -> bool:
        role_def = self._roles.get(role, {})
        allowed = role_def.get("tools", [])
        for pattern in allowed:
            if pattern == "*":
                return True
            if fnmatch.fnmatch(tool_name, pattern):
                return True
        return False

    def get_allowed_tools(self, role: str) -> list[str]:
        return self._roles.get(role, {}).get("tools", [])

    def filter_tools(self, role: str, all_tools: list[dict]) -> list[dict]:
        return [t for t in all_tools if self.can_use_tool(role, t.get("name", ""))]

    def assign_tools(self, role: str, tools: list[str]) -> None:
        if role not in self._roles:
            self._roles[role] = {"tools": [], "description": ""}
        current = set(self._roles[role].get("tools", []))
        current.update(tools)
        self._roles[role]["tools"] = sorted(current)

    def revoke_tools(self, role: str, tools: list[str]) -> None:
        if role not in self._roles:
            return
        current = set(self._roles[role].get("tools", []))
        current -= set(tools)
        self._roles[role]["tools"] = sorted(current)

    def create_role(self, role: str, tools: list[str], description: str = "") -> None:
        self._roles[role] = {"tools": tools, "description": description}

    def delete_role(self, role: str) -> bool:
        if role == "admin":
            return False  # 不能删除 admin
        return self._roles.pop(role, None) is not None

    def list_roles(self) -> dict[str, dict]:
        return dict(self._roles)
