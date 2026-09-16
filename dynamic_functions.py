from __future__ import annotations
import json as _json
import re
import signal
import threading
import urllib.request as _urllib_request
from typing import Any, Callable

from ontohub.core.store import ObjectStore
from ontohub.core.schema_store import SchemaStore


# 禁止的模块和内置函数
_BLOCKED_IMPORTS = {
    "os", "sys", "subprocess", "shutil", "pathlib",
    "socket", "requests", "urllib", "http",
    "importlib", "ctypes", "signal", "multiprocessing",
}
_BLOCKED_BUILTINS = {
    "open", "exec", "eval", "__import__", "compile",
    "globals", "locals", "vars", "dir",
    "getattr", "setattr", "delattr",
    "breakpoint", "exit", "quit",
}


class SandboxError(Exception):
    pass


def _check_code_safety(code: str) -> list[str]:
    """静态检查代码安全性，返回违规列表。"""
    violations = []

    # 检查 import 语句
    for match in re.finditer(r'^\s*(?:from|import)\s+(\w+)', code, re.MULTILINE):
        module = match.group(1)
        if module in _BLOCKED_IMPORTS:
            violations.append(f"Blocked import: {module}")

    # 检查危险函数调用
    for func_name in _BLOCKED_BUILTINS:
        if re.search(rf'\b{func_name}\s*\(', code):
            violations.append(f"Blocked builtin: {func_name}()")

    # 检查 dunder 属性访问
    if re.search(r'\b__\w+__\b', code):
        violations.append("Blocked dunder attribute access")

    return violations


class DynamicFunctionRegistry:
    """动态 Function 注册引擎 — 编译、沙箱执行、注册/注销。"""

    def __init__(self, store: ObjectStore, schema_store: SchemaStore):
        self._store = store
        self._schema_store = schema_store
        self._fns: dict[str, Callable] = {}
        self._fn_meta: dict[str, dict] = {}

    def load_from_db(self) -> int:
        """从 SQLite 加载所有 workspace 的已注册 Function。"""
        original_ws = self._schema_store.get_workspace()
        total = 0
        try:
            for ws in self._schema_store.list_workspaces():
                self._schema_store.set_workspace(ws["name"])
                functions = self._schema_store.list_functions()
                for fn in functions:
                    if fn.get("code"):
                        try:
                            self._compile_and_register(
                                name=fn["name"],
                                code=fn["code"],
                                description=fn.get("description", ""),
                                params=fn.get("params", {}),
                                returns=fn.get("returns", ""),
                            )
                            total += 1
                        except Exception:
                            pass  # 跳过编译失败的
        finally:
            self._schema_store.set_workspace(original_ws)
        return total

    def register(self, name: str, code: str, description: str = "",
                 params: dict | None = None, returns: str = "") -> dict:
        """注册新 Function：安全检查 → 编译 → 保存到 DB → 注册到内存。"""
        # 安全检查
        violations = _check_code_safety(code)
        if violations:
            raise SandboxError(f"Code safety check failed: {violations}")

        # 编译并注册
        self._compile_and_register(name, code, description, params or {}, returns)

        # 保存到 DB
        self._schema_store.save_function(
            name=name,
            description=description,
            params=params or {},
            returns=returns,
            code=code,
        )

        return {
            "status": "registered",
            "name": name,
            "params": params or {},
        }

    def unregister(self, name: str) -> bool:
        """注销 Function。"""
        removed = self._fns.pop(name, None) is not None
        self._fn_meta.pop(name, None)
        self._schema_store.delete_function(name)
        return removed

    def call(self, name: str, params: dict) -> Any:
        """调用已注册的 Function。"""
        if name not in self._fns:
            raise KeyError(f"Unknown function: {name}")
        return self._fns[name](params)

    def has(self, name: str) -> bool:
        return name in self._fns

    def list_functions(self) -> list[dict]:
        return [
            {"name": name, **meta}
            for name, meta in self._fn_meta.items()
        ]

    def _compile_and_register(self, name: str, code: str,
                               description: str, params: dict, returns: str) -> None:
        """编译代码并注册为可调用函数。"""
        # 构建安全的全局命名空间
        safe_builtins = {
            "len": len, "str": str, "int": int, "float": float,
            "bool": bool, "list": list, "dict": dict, "set": set,
            "tuple": tuple, "range": range, "enumerate": enumerate,
            "zip": zip, "map": map, "filter": filter, "sorted": sorted,
            "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
            "isinstance": isinstance, "type": type, "print": print,
            "repr": repr, "format": format,
            "True": True, "False": False, "None": None,
        }

        namespace: dict[str, Any] = {
            "__builtins__": safe_builtins,
            "store": self._store,
            "schema_store": self._schema_store,
            "http_request": _urllib_request,
            "json": _json,
        }

        # 包装代码为函数
        wrapped_code = f"def {name}(params):\n"
        for line in code.strip().split("\n"):
            wrapped_code += f"    {line}\n"

        exec(wrapped_code, namespace)

        fn = namespace.get(name)
        if not callable(fn):
            raise SandboxError(f"Code did not produce a callable function '{name}'")

        self._fns[name] = fn
        self._fn_meta[name] = {
            "description": description,
            "params": params,
            "returns": returns,
        }
