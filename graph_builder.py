from __future__ import annotations
from ontohub.core.store import ObjectStore
from ontohub.core.schema_store import SchemaStore


def build_graph(store: ObjectStore, schema_store: SchemaStore) -> dict:
    """构建前端可视化所需的节点+边图数据。"""
    nodes = []
    edges = []
    node_ids = set()

    types = schema_store.list_types()

    for type_def in types:
        type_name = type_def["name"]
        pk = _find_pk(type_def)
        objects = store.all_objects(type_name)

        for obj in objects:
            obj_id = obj.get(pk, "unknown")
            node_key = f"{type_name}:{obj_id}"
            if node_key in node_ids:
                continue
            node_ids.add(node_key)

            # 找一个适合当 label 的字段
            label = (obj.get("name") or obj.get("label") or
                     obj.get("title") or obj.get("keyValue") or obj_id)

            nodes.append({
                "id": node_key,
                "label": str(label),
                "type": type_name,
                "properties": obj,
            })

        # 构建边
        for link_name, link_def in type_def.get("links", {}).items():
            target_type = link_def.get("target", "")
            fk_field = link_def.get("foreign_key", "")
            target_type_def = schema_store.get_type(target_type)
            if not target_type_def:
                continue
            target_pk = _find_pk(target_type_def)

            for obj in objects:
                fk_value = obj.get(fk_field)
                if fk_value is None:
                    continue
                source_key = f"{type_name}:{obj.get(pk, 'unknown')}"

                # 支持单值和列表外键
                fk_values = fk_value if isinstance(fk_value, list) else [fk_value]
                for fv in fk_values:
                    target_key = f"{target_type}:{fv}"
                    edges.append({
                        "source": source_key,
                        "target": target_key,
                        "label": link_name,
                        "properties": {},
                    })

    return {
        "nodes": nodes,
        "edges": edges,
        "nodeCount": len(nodes),
        "edgeCount": len(edges),
    }


def _find_pk(type_def: dict) -> str:
    for prop_name, prop_def in type_def.get("properties", {}).items():
        if prop_def.get("primary_key"):
            return prop_name
    return "id"
