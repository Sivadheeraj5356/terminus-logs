"""Independent reference for helmvals chart coalesce contracts."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


def parse_yaml(data: str) -> dict[str, Any]:
    lines = data.replace("\r\n", "\n").split("\n")
    root: dict[str, Any] = {}
    stack: list[dict[str, Any]] = [root]
    list_stack: list[list[Any]] = []

    def current_map() -> dict[str, Any]:
        return stack[-1]

    for i, raw in enumerate(lines):
        line = raw.rstrip(" \t")
        if not line or line.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2:
            raise ValueError(f"line {i+1}: bad indent")
        while len(stack) > 1 and indent <= (len(stack) - 1) * 2 - 1:
            stack.pop()
            if list_stack and len(list_stack) >= len(stack):
                list_stack.pop()
        trim = line.strip()
        if trim.startswith("- "):
            if not list_stack:
                raise ValueError(f"line {i+1}: list outside list")
            rest = trim[2:].strip()
            if ":" not in rest:
                list_stack[-1].append(_scalar(rest))
                continue
            key, val = rest.split(":", 1)
            item: dict[str, Any] = {}
            item[key.strip()] = _scalar(val.strip())
            list_stack[-1].append(item)
            stack.append(item)
            continue
        key, val = trim.split(":", 1)
        key = key.strip()
        val = val.strip()
        if not val:
            nxt_indent = indent + 2
            if i + 1 < len(lines) and lines[i + 1].startswith(" " * nxt_indent + "-"):
                lst: list[Any] = []
                current_map()[key] = lst
                list_stack.append(lst)
            else:
                child: dict[str, Any] = {}
                current_map()[key] = child
                stack.append(child)
            continue
        current_map()[key] = _scalar(val)
    return root


def _scalar(s: str) -> Any:
    if s == "true":
        return True
    if s == "false":
        return False
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1]
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    return s


def deep_merge(dst: dict[str, Any], src: dict[str, Any]) -> dict[str, Any]:
    for k, v in src.items():
        if k in dst and isinstance(dst[k], dict) and isinstance(v, dict):
            deep_merge(dst[k], v)
        else:
            dst[k] = json.loads(json.dumps(v))
    return dst


def clone_map(m: dict[str, Any] | None) -> dict[str, Any]:
    if not m:
        return {}
    return json.loads(json.dumps(m))


def get_path(m: dict[str, Any], path: str) -> Any:
    cur: Any = m
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def is_truthy(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v not in ("", "false", "0")
    return True


def subtree(m: dict[str, Any], key: str) -> dict[str, Any]:
    v = m.get(key)
    return v if isinstance(v, dict) else {}


def split_set_key(key: str) -> list[str]:
    parts: list[str] = []
    cur: list[str] = []
    i = 0
    while i < len(key):
        if key[i] == "\\" and i + 1 < len(key) and key[i + 1] == ".":
            cur.append(".")
            i += 2
            continue
        if key[i] == ".":
            parts.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(key[i])
        i += 1
    parts.append("".join(cur))
    return parts


def set_path(m: dict[str, Any], path: list[str], value: Any) -> None:
    cur = m
    for part in path[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    if path:
        cur[path[-1]] = value


def load_chart(chart_dir: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    meta = parse_yaml((chart_dir / "Chart.yaml").read_text(encoding="utf-8"))
    defaults: dict[str, Any] = {}
    values_path = chart_dir / "values.yaml"
    if values_path.is_file():
        defaults = parse_yaml(values_path.read_text(encoding="utf-8"))
    deps_raw = meta.get("dependencies") or []
    deps: list[dict[str, Any]] = []
    if isinstance(deps_raw, list):
        for item in deps_raw:
            if isinstance(item, dict):
                deps.append(item)
    return meta, defaults, deps


def manifest_id(dep: dict[str, Any]) -> str:
    return str(dep.get("alias") or dep["name"])


def canonical_json_bytes(obj: Any) -> str:
    if isinstance(obj, dict):
        return "{" + ",".join(
            json.dumps(k) + ":" + canonical_json_bytes(obj[k]) for k in sorted(obj)
        ) + "}"
    if isinstance(obj, list):
        return "[" + ",".join(canonical_json_bytes(x) for x in obj) + "]"
    return json.dumps(obj)


def reference_manifest_hash(manifest: dict[str, Any]) -> str:
    payload = {k: v for k, v in manifest.items() if k != "manifest_hash"}
    data = canonical_json_bytes(payload).encode()
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sort_map(m: dict[str, Any]) -> dict[str, Any]:
    return {k: sort_map(v) if isinstance(v, dict) else v for k, v in sorted(m.items())}


def reference_resolve(
    chart_dir: Path,
    values_files: list[Path] | None = None,
    set_args: list[str] | None = None,
) -> dict[str, Any]:
    values_layers = []
    for vf in values_files or []:
        values_layers.append(parse_yaml(vf.read_text(encoding="utf-8")))
    set_pairs = []
    for arg in set_args or []:
        eq = arg.index("=")
        path = split_set_key(arg[:eq])
        val = _scalar(arg[eq + 1 :])
        set_pairs.append((path, val))

    state = _ResolveState(chart_dir)
    state.run(values_layers, set_pairs)
    active = sorted(state.active)
    values = {cid: sort_map(state.values[cid]) for cid in active}
    trail = sorted(
        state.trail,
        key=lambda r: (r["chart"], r["path"], r["ordinal"]),
    )
    manifest = {
        "active_charts": active,
        "values": values,
        "precedence_trail": trail,
    }
    manifest["manifest_hash"] = reference_manifest_hash(manifest)
    return manifest


class _ResolveState:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.values: dict[str, dict[str, Any]] = {}
        self.active: list[str] = []
        self.trail: list[dict[str, Any]] = []
        self.ordinal = 0
        self.known: set[str] = set()
        meta, _, deps = load_chart(root_dir)
        self._register(meta, root_dir)

    def _register(self, meta: dict[str, Any], chart_dir: Path) -> None:
        self.known.add(str(meta["name"]))
        _, _, deps = load_chart(chart_dir)
        for dep in deps:
            self.known.add(manifest_id(dep))
            sub = chart_dir / "charts" / dep["name"]
            sub_meta, _, _ = load_chart(sub)
            self._register(sub_meta, sub)

    def run(self, values_layers: list[dict[str, Any]], set_pairs: list[tuple[list[str], Any]]) -> None:
        meta, _, _ = load_chart(self.root_dir)
        self._resolve_chart(self.root_dir, str(meta["name"]), None, True, values_layers, set_pairs)

    def _resolve_chart(
        self,
        chart_dir: Path,
        chart_id: str,
        parent_vals: dict[str, Any] | None,
        is_root: bool,
        values_layers: list[dict[str, Any]],
        set_pairs: list[tuple[list[str], Any]],
    ) -> None:
        _, defaults, deps = load_chart(chart_dir)
        vals = clone_map(self.values.get(chart_id))
        vals = self._apply(vals, defaults, chart_id, "defaults")
        self._propagate_global(defaults.get("global"))

        if parent_vals is not None:
            sub = subtree(parent_vals, chart_id)
            vals = self._apply(vals, sub, chart_id, "parent")
            if isinstance(sub.get("global"), dict):
                self._propagate_global(sub["global"])

        for layer in values_layers:
            scope = layer if is_root else subtree(layer, chart_id)
            vals = self._apply(vals, scope, chart_id, "values")
            if isinstance(scope.get("global"), dict):
                self._propagate_global(scope["global"])

        self.values[chart_id] = vals
        if chart_id not in self.active:
            self.active.append(chart_id)
        condition_base = clone_map(vals)

        for path, value in set_pairs:
            target, rest = self._set_target(path, chart_id)
            if target != chart_id:
                continue
            patch: dict[str, Any] = {}
            set_path(patch, rest, value)
            vals = self._apply(vals, patch, chart_id, "set")
            self.values[chart_id] = vals

        for dep in sorted(deps, key=lambda d: manifest_id(d)):
            cond = dep.get("condition")
            if cond and not is_truthy(get_path(condition_base, str(cond))):
                continue
            sub_dir = chart_dir / "charts" / dep["name"]
            sub_meta, _, _ = load_chart(sub_dir)
            self._resolve_chart(
                sub_dir,
                manifest_id(dep),
                condition_base,
                False,
                values_layers,
                set_pairs,
            )

    def _apply(self, dst: dict[str, Any], src: dict[str, Any], chart_id: str, layer: str) -> dict[str, Any]:
        before = clone_map(dst)
        out = deep_merge(clone_map(dst), src)
        flat_before = _flatten(before)
        flat_after = _flatten(out)
        for path in sorted(flat_after):
            val = flat_after[path]
            if path not in flat_before or flat_before[path] != val:
                self.ordinal += 1
                self.trail.append(
                    {"chart": chart_id, "path": path, "value": val, "layer": layer, "ordinal": self.ordinal}
                )
        return out

    def _propagate_global(self, g: Any) -> None:
        if not isinstance(g, dict) or not g:
            return
        for cid in self.known:
            if cid not in self.values:
                self.values[cid] = {}
            cur = self.values[cid].get("global")
            if not isinstance(cur, dict):
                cur = {}
            self.values[cid]["global"] = deep_merge(clone_map(cur), g)

    def _set_target(self, path: list[str], self_id: str) -> tuple[str, list[str]]:
        if len(path) > 1 and path[0] in self.known:
            return path[0], path[1:]
        return self_id, path


def _flatten(m: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in m.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.update(_flatten(v, path))
        else:
            out[path] = v
    return out
