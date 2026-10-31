from __future__ import annotations

import copy
from typing import Any, Dict, List


def make_patch(source: Dict[str, Any], target: Dict[str, Any], path_prefix: str = "") -> List[Dict[str, Any]]:
    """
    Computes an RFC 6902 JSON Patch delta between source and target dictionaries (CTL-AUD-02).
    Supported operations: add, replace, remove.
    """
    patch: List[Dict[str, Any]] = []

    # Check for removed or replaced keys
    for key, src_val in source.items():
        curr_path = f"{path_prefix}/{key}"
        if key not in target:
            patch.append({"op": "remove", "path": curr_path})
        elif isinstance(src_val, dict) and isinstance(target[key], dict):
            # Recurse nested objects
            sub_patch = make_patch(src_val, target[key], curr_path)
            patch.extend(sub_patch)
        elif src_val != target[key]:
            patch.append({"op": "replace", "path": curr_path, "value": target[key]})

    # Check for added keys
    for key, tgt_val in target.items():
        if key not in source:
            curr_path = f"{path_prefix}/{key}"
            patch.append({"op": "add", "path": curr_path, "value": tgt_val})

    return patch


def apply_patch(doc: Dict[str, Any], patch: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Applies a list of RFC 6902 patch operations to a document."""
    res = copy.deepcopy(doc)
    for op in patch:
        parts = [p for p in op["path"].split("/") if p]
        if not parts:
            continue

        target_obj = res
        for p in parts[:-1]:
            if p not in target_obj or not isinstance(target_obj[p], dict):
                target_obj[p] = {}
            target_obj = target_obj[p]

        last_key = parts[-1]
        action = op.get("op")
        if action in {"add", "replace"}:
            target_obj[last_key] = op.get("value")
        elif action == "remove":
            target_obj.pop(last_key, None)

    return res
