"""Shared reference helpers for Iris provenance verifiers."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections import deque
from pathlib import Path
from typing import Any

WORKSPACE = "/workspace"
CLI = "/workspace/iris-provenance/bin/iris-prov"
DEFAULT_PATHS = "/workspace/config/paths.json"


def load_json(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def read_text(path: str | Path) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def output_path(name: str) -> str:
    return os.path.join(WORKSPACE, "output", name)


def strip_incompatible(version: str) -> str:
    if version.endswith("+incompatible"):
        return version[: -len("+incompatible")]
    return version


def strip_checksum(checksum: str, *, single_peel: bool = True) -> str:
    if single_peel:
        for prefix in ("h1:", "sha256:"):
            if checksum.startswith(prefix):
                return checksum[len(prefix) :]
        return checksum
    out = checksum
    while True:
        changed = False
        for prefix in ("h1:", "sha256:"):
            if out.startswith(prefix):
                out = out[len(prefix) :]
                changed = True
                break
        if not changed:
            break
    return out


def load_cutover_register(paths: dict) -> dict:
    register_path = paths.get("cutover_register")
    assert register_path, "paths.cutover_register is required"
    return load_json(register_path)


def export_root(export_doc: dict) -> tuple[str, str]:
    meta = export_doc.get("export_meta", {})
    if "root_module" not in meta or "root_version" not in meta:
        raise ValueError("export_meta missing root keys")
    return meta["root_module"], strip_incompatible(meta["root_version"])


def is_queued(path: str, version: str, queue: list) -> bool:
    norm = strip_incompatible(version)
    for item in queue:
        if item["module_path"] == path and strip_incompatible(item["version"]) == norm:
            return True
    return False


def is_scaffold(req: dict, *, truthy_only: bool) -> bool:
    keys = ("indirect", "toolchain", "development", "test")
    if truthy_only:
        return any(req.get(k) for k in keys)
    return any(k in req for k in keys)


def resolve_replace(
    child_path: str,
    child_version: str,
    replaces: list,
    *,
    first_wins: bool = True,
) -> tuple[str, str, str, dict | None]:
    norm_child = strip_incompatible(child_version)
    rules = replaces if first_wins else list(reversed(replaces))
    for rule in rules:
        old_v = strip_incompatible(rule["old_version"])
        if rule["old_path"] == child_path and old_v == norm_child:
            return (
                rule["new_path"],
                strip_incompatible(rule["new_version"]),
                "replace",
                rule,
            )
    return child_path, norm_child, "require", None


def lookup_unit(module_index: dict, path: str, version: str) -> dict | None:
    entry = module_index.get(path)
    if not entry:
        return None
    versions = entry.get("versions", {})
    want = strip_incompatible(version)
    for key, block in versions.items():
        for unit in block.get("units") or []:
            if unit.get("path") != path:
                continue
            unit_ver = strip_incompatible(unit.get("version", key))
            if unit_ver == want or strip_incompatible(key) == want:
                return {"go_version": block.get("go_version", ""), "unit": unit}
    return None


def _sorted_rows(rows: list[dict], keys: tuple[str, ...]) -> list[dict]:
    return sorted(rows, key=lambda row: tuple(row[k] for k in keys))


def assert_graph_equivalent(actual: dict, expected: dict) -> None:
    """Compare normalized graphs with sorted array order required by the binding."""
    assert actual == expected


def expected_normalized_graph(
    export_path: str | None = None,
    paths_path: str | None = None,
) -> dict:
    paths = load_json(paths_path or DEFAULT_PATHS)
    register = load_cutover_register(paths)
    first_wins = register.get("replace_match_policy") == "list_scan_alpha"
    single_peel = register.get("checksum_peel_mode") == "single_affix"
    truthy_scaffold = register.get("scaffold_gate") == "truthy_flags"
    post_rewrite = register.get("queue_timing") == "post_rewrite"

    export_path = export_path or paths["proxy_export"]
    export_doc = load_json(export_path)
    root_module, root_version = export_root(export_doc)
    retract_queue = export_doc.get("retract_queue", [])
    exclude_queue = export_doc.get("exclude_queue", [])
    module_index = export_doc["module_index"]

    modules_out: list[dict] = []
    edges_out: list[dict] = []
    replaces_out: list[dict] = []
    replace_seen: set[tuple[str, str, str, str]] = set()
    visited: set[tuple[str, str]] = set()
    queue: deque[tuple[str, str]] = deque([(root_module, root_version)])

    while queue:
        path, version = queue.popleft()
        key = (path, version)
        if key in visited:
            continue
        if is_queued(path, version, retract_queue) or is_queued(path, version, exclude_queue):
            continue
        found = lookup_unit(module_index, path, version)
        if found is None:
            continue
        visited.add(key)
        unit = found["unit"]
        modules_out.append(
            {
                "module_path": path,
                "version": version,
                "checksum_sha256": strip_checksum(
                    unit.get("checksum", ""), single_peel=single_peel
                ),
                "go_version": found["go_version"],
                "is_root": path == root_module and version == root_version,
            }
        )
        unit_replaces = unit.get("replaces", [])
        for req in unit.get("requires", []):
            if is_scaffold(req, truthy_only=truthy_scaffold):
                continue
            req_path = req["path"]
            req_version = strip_incompatible(req["version"])
            if not post_rewrite:
                if is_queued(req_path, req_version, retract_queue):
                    continue
                if is_queued(req_path, req_version, exclude_queue):
                    continue
            child_path, child_version, edge_kind, matched = resolve_replace(
                req_path, req_version, unit_replaces, first_wins=first_wins
            )
            if post_rewrite:
                if is_queued(child_path, child_version, retract_queue):
                    continue
                if is_queued(child_path, child_version, exclude_queue):
                    continue
            if matched is not None:
                rule_key = (
                    path,
                    version,
                    matched["old_path"],
                    strip_incompatible(matched["old_version"]),
                )
                if rule_key not in replace_seen:
                    replace_seen.add(rule_key)
                    replaces_out.append(
                        {
                            "scope_path": path,
                            "scope_version": version,
                            "old_path": matched["old_path"],
                            "old_version": strip_incompatible(matched["old_version"]),
                            "new_path": matched["new_path"],
                            "new_version": strip_incompatible(matched["new_version"]),
                        }
                    )
            edges_out.append(
                {
                    "parent_path": path,
                    "parent_version": version,
                    "child_path": child_path,
                    "child_version": child_version,
                    "edge_kind": edge_kind,
                }
            )
            queue.append((child_path, child_version))

    modules_out = _sorted_rows(modules_out, ("module_path", "version"))
    edges_out = _sorted_rows(
        edges_out,
        ("parent_path", "parent_version", "child_path", "child_version", "edge_kind"),
    )
    replaces_out = _sorted_rows(
        replaces_out,
        ("scope_path", "scope_version", "old_path", "old_version"),
    )
    return {
        "schema_version": paths["schema_version"],
        "root_module": root_module,
        "root_version": root_version,
        "modules": modules_out,
        "edges": edges_out,
        "replace_rules": replaces_out,
    }


def canonical_digest_lines(graph: dict) -> list[str]:
    lines: list[str] = []
    for row in graph["modules"]:
        lines.append(
            json.dumps(
                {
                    "kind": "module",
                    "module_path": row["module_path"],
                    "version": row["version"],
                    "checksum_sha256": row["checksum_sha256"],
                    "go_version": row["go_version"],
                    "is_root": row["is_root"],
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    for row in graph["edges"]:
        lines.append(
            json.dumps(
                {
                    "kind": "edge",
                    "parent_path": row["parent_path"],
                    "parent_version": row["parent_version"],
                    "child_path": row["child_path"],
                    "child_version": row["child_version"],
                    "edge_kind": row["edge_kind"],
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    for row in graph["replace_rules"]:
        lines.append(
            json.dumps(
                {
                    "kind": "replace",
                    "scope_path": row["scope_path"],
                    "scope_version": row["scope_version"],
                    "old_path": row["old_path"],
                    "old_version": row["old_version"],
                    "new_path": row["new_path"],
                    "new_version": row["new_version"],
                },
                separators=(",", ":"),
                sort_keys=True,
            )
        )
    lines.sort()
    return lines


def expected_digest_sha256(graph: dict | None = None) -> str:
    graph = graph or expected_normalized_graph()
    body = "\n".join(canonical_digest_lines(graph)) + "\n"
    return hashlib.sha256(body.encode()).hexdigest()


def write_same_path_replace_probe_export(path: str) -> None:
    """Verifier probe: replace keeps module path, bumps version, edge_kind=replace."""
    doc = {
        "export_meta": {
            "proxy_id": "probe-same-path-replace",
            "format_rev": "proxy-nested-7",
            "root_module": "github.com/probe/svc",
            "root_version": "v1.0.0",
        },
        "retract_queue": [],
        "exclude_queue": [],
        "module_index": {
            "github.com/probe/svc": {
                "selected_version": "v1.0.0",
                "versions": {
                    "v1.0.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/svc",
                                "version": "v1.0.0",
                                "checksum": "h1:" + ("11" * 32),
                                "requires": [
                                    {
                                        "path": "github.com/probe/libx",
                                        "version": "v0.3.0",
                                    }
                                ],
                                "replaces": [
                                    {
                                        "old_path": "github.com/probe/libx",
                                        "old_version": "v0.3.0",
                                        "new_path": "github.com/probe/libx",
                                        "new_version": "v0.4.0",
                                    },
                                    {
                                        "old_path": "github.com/probe/unused",
                                        "old_version": "v9.0.0",
                                        "new_path": "github.com/probe/unused",
                                        "new_version": "v9.1.0",
                                    },
                                ],
                            }
                        ],
                    }
                },
            },
            "github.com/probe/libx": {
                "selected_version": "v0.4.0",
                "versions": {
                    "v0.3.0": {
                        "go_version": "1.21.0",
                        "units": [
                            {
                                "path": "github.com/probe/libx",
                                "version": "v0.3.0",
                                "checksum": "h1:" + ("22" * 32),
                                "requires": [],
                                "replaces": [],
                            }
                        ],
                    },
                    "v0.4.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/libx",
                                "version": "v0.4.0",
                                "checksum": "h1:" + ("33" * 32),
                                "requires": [],
                                "replaces": [],
                            }
                        ],
                    },
                },
            },
            "github.com/probe/unused": {
                "selected_version": "v9.1.0",
                "versions": {
                    "v9.1.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/unused",
                                "version": "v9.1.0",
                                "checksum": "h1:" + ("44" * 32),
                                "requires": [],
                                "replaces": [],
                            }
                        ],
                    }
                },
            },
        },
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=2)
        handle.write("\n")


def write_exclude_toolchain_probe_export(path: str) -> None:
    """Verifier probe: exclude_queue + toolchain requires must not enter the graph."""
    doc = {
        "export_meta": {
            "proxy_id": "probe-exclude-toolchain",
            "format_rev": "proxy-nested-7",
            "root_module": "github.com/probe/core",
            "root_version": "v1.0.0",
        },
        "retract_queue": [],
        "exclude_queue": [
            {
                "module_path": "github.com/probe/banned",
                "version": "v0.1.0",
            }
        ],
        "module_index": {
            "github.com/probe/core": {
                "selected_version": "v1.0.0",
                "versions": {
                    "v1.0.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/core/cmd",
                                "version": "v1.0.0",
                                "checksum": "h1:" + ("ee" * 32),
                                "requires": [],
                                "replaces": [],
                            },
                            {
                                "path": "github.com/probe/core",
                                "version": "v1.0.0",
                                "checksum": "h1:" + ("55" * 32),
                                "requires": [
                                    {
                                        "path": "github.com/probe/lib",
                                        "version": "v1.0.0",
                                    },
                                    {
                                        "path": "github.com/probe/banned",
                                        "version": "v0.1.0",
                                    },
                                    {
                                        "path": "github.com/probe/tooldep",
                                        "version": "v0.2.0",
                                        "toolchain": True,
                                    },
                                    {
                                        "path": "github.com/probe/metrics",
                                        "version": "v0.3.0",
                                        "toolchain": False,
                                        "development": False,
                                        "indirect": False,
                                    },
                                ],
                                "replaces": [],
                            },
                        ],
                    }
                },
            },
            "github.com/probe/metrics": {
                "selected_version": "v0.3.0",
                "versions": {
                    "v0.3.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/metrics",
                                "version": "v0.3.0",
                                "checksum": "h1:" + ("99" * 32),
                                "requires": [],
                                "replaces": [],
                            }
                        ],
                    }
                },
            },
            "github.com/probe/lib": {
                "selected_version": "v1.0.0",
                "versions": {
                    "v1.0.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/lib",
                                "version": "v1.0.0",
                                "checksum": "sha256:" + ("66" * 32),
                                "published_sum": "sha256:" + ("aa" * 32),
                                "requires": [],
                                "replaces": [],
                            }
                        ],
                    }
                },
            },
            "github.com/probe/banned": {
                "selected_version": "v0.1.0",
                "versions": {
                    "v0.1.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/banned",
                                "version": "v0.1.0",
                                "checksum": "h1:" + ("77" * 32),
                                "requires": [],
                                "replaces": [],
                            }
                        ],
                    }
                },
            },
            "github.com/probe/tooldep": {
                "selected_version": "v0.2.0",
                "versions": {
                    "v0.2.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/tooldep",
                                "version": "v0.2.0",
                                "checksum": "h1:" + ("88" * 32),
                                "requires": [],
                                "replaces": [],
                            }
                        ],
                    }
                },
            },
        },
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=2)
        handle.write("\n")


def write_retract_replace_probe_export(path: str) -> None:
    """Verifier probe: retracted require target replaced by a valid module."""
    doc = {
        "export_meta": {
            "proxy_id": "probe-retract-replace",
            "format_rev": "proxy-nested-7",
            "root_module": "github.com/probe/app",
            "root_version": "v1.0.0",
        },
        "retract_queue": [
            {
                "module_path": "github.com/probe/broken-dep",
                "version": "v0.1.0",
            }
        ],
        "module_index": {
            "github.com/probe/app": {
                "selected_version": "v1.0.0",
                "versions": {
                    "v1.0.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/app",
                                "version": "v1.0.0",
                                "checksum": "h1:" + ("aa" * 32),
                                "requires": [
                                    {
                                        "path": "github.com/probe/broken-dep",
                                        "version": "v0.1.0",
                                    }
                                ],
                                "replaces": [
                                    {
                                        "old_path": "github.com/probe/broken-dep",
                                        "old_version": "v0.1.0",
                                        "new_path": "github.com/probe/fixed-dep",
                                        "new_version": "v2.0.0",
                                    }
                                ],
                            }
                        ],
                    }
                },
            },
            "github.com/probe/broken-dep": {
                "selected_version": "v0.1.0",
                "versions": {
                    "v0.1.0": {
                        "go_version": "1.21.0",
                        "units": [
                            {
                                "path": "github.com/probe/broken-dep",
                                "version": "v0.1.0",
                                "checksum": "h1:" + ("bb" * 32),
                                "requires": [],
                                "replaces": [],
                            }
                        ],
                    }
                },
            },
            "github.com/probe/fixed-dep": {
                "selected_version": "v2.0.0",
                "versions": {
                    "v2.0.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/fixed-dep",
                                "version": "v2.0.0",
                                "checksum": "h1:" + ("cc" * 32),
                                "requires": [],
                                "replaces": [],
                            }
                        ],
                    }
                },
            },
        },
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=2)
        handle.write("\n")


def write_m1_probe_export(path: str) -> None:
    doc = {
        "export_meta": {
            "proxy_id": "probe-west",
            "format_rev": "proxy-nested-7",
            "root_module": "github.com/probe/widget",
            "root_version": "v2.0.0",
        },
        "retract_queue": [
            {
                "module_path": "github.com/probe/legacy",
                "version": "v0.9.0",
            }
        ],
        "module_index": {
            "github.com/probe/widget": {
                "selected_version": "v2.0.0",
                "versions": {
                    "v2.0.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/widget",
                                "version": "v2.0.0",
                                "checksum": "h1:" + ("ab" * 32),
                                "requires": [
                                    {
                                        "path": "github.com/probe/lib",
                                        "version": "v1.1.0",
                                    },
                                    {
                                        "path": "github.com/probe/legacy",
                                        "version": "v0.9.0",
                                    },
                                    {
                                        "path": "github.com/probe/metrics",
                                        "version": "v3.0.0",
                                        "indirect": True,
                                    },
                                ],
                                "replaces": [],
                            }
                        ],
                    }
                },
            },
            "github.com/probe/lib": {
                "selected_version": "v1.1.0",
                "versions": {
                    "v1.1.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/lib",
                                "version": "v1.1.0",
                                "checksum": "sha256:" + ("cd" * 32),
                                "requires": [],
                                "replaces": [],
                            }
                        ],
                    }
                },
            },
            "github.com/probe/legacy": {
                "selected_version": "v0.9.0",
                "versions": {
                    "v0.9.0": {
                        "go_version": "1.21.0",
                        "units": [
                            {
                                "path": "github.com/probe/legacy",
                                "version": "v0.9.0",
                                "checksum": "h1:" + ("ef" * 32),
                                "requires": [
                                    {
                                        "path": "github.com/probe/shim",
                                        "version": "v0.1.0",
                                    }
                                ],
                                "replaces": [],
                            }
                        ],
                    }
                },
            },
            "github.com/probe/shim": {
                "selected_version": "v0.1.0",
                "versions": {
                    "v0.1.0": {
                        "go_version": "1.21.0",
                        "units": [
                            {
                                "path": "github.com/probe/shim",
                                "version": "v0.1.0",
                                "checksum": "h1:" + ("11" * 32),
                                "requires": [],
                                "replaces": [],
                            }
                        ],
                    }
                },
            },
            "github.com/probe/metrics": {
                "selected_version": "v3.0.0",
                "versions": {
                    "v3.0.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/metrics",
                                "version": "v3.0.0",
                                "checksum": "h1:" + ("22" * 32),
                                "requires": [],
                                "replaces": [],
                            }
                        ],
                    }
                },
            },
            "github.com/probe/orphan": {
                "selected_version": "v8.0.0",
                "versions": {
                    "v8.0.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/orphan",
                                "version": "v8.0.0",
                                "checksum": "h1:" + ("33" * 32),
                                "requires": [],
                                "replaces": [],
                            }
                        ],
                    }
                },
            },
        },
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=2)
        handle.write("\n")


def write_first_wins_replace_probe_export(path: str) -> None:
    """Verifier probe: two replaces match one require; the first listed row wins."""
    doc = {
        "export_meta": {
            "proxy_id": "probe-first-wins",
            "format_rev": "proxy-nested-7",
            "root_module": "github.com/probe/app",
            "root_version": "v1.0.0",
        },
        "retract_queue": [],
        "exclude_queue": [],
        "module_index": {
            "github.com/probe/app": {
                "selected_version": "v1.0.0",
                "versions": {
                    "v1.0.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/app",
                                "version": "v1.0.0",
                                "checksum": "h1:" + ("a1" * 32),
                                "requires": [
                                    {
                                        "path": "github.com/probe/dep",
                                        "version": "v0.1.0",
                                    }
                                ],
                                "replaces": [
                                    {
                                        "old_path": "github.com/probe/dep",
                                        "old_version": "v0.1.0",
                                        "new_path": "github.com/probe/dep",
                                        "new_version": "v0.5.0",
                                    },
                                    {
                                        "old_path": "github.com/probe/dep",
                                        "old_version": "v0.1.0",
                                        "new_path": "github.com/probe/dep",
                                        "new_version": "v0.9.0",
                                    },
                                ],
                            }
                        ],
                    }
                },
            },
            "github.com/probe/dep": {
                "selected_version": "v0.5.0",
                "versions": {
                    "v0.5.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/dep",
                                "version": "v0.5.0",
                                "checksum": "h1:" + ("b2" * 32),
                                "requires": [],
                                "replaces": [],
                            }
                        ],
                    },
                    "v0.9.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/dep",
                                "version": "v0.9.0",
                                "checksum": "h1:" + ("c3" * 32),
                                "requires": [],
                                "replaces": [],
                            }
                        ],
                    },
                },
            },
        },
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=2)
        handle.write("\n")


def write_double_prefix_checksum_probe_export(path: str) -> None:
    """Verifier probe: only the single leading checksum prefix is stripped."""
    doc = {
        "export_meta": {
            "proxy_id": "probe-double-prefix",
            "format_rev": "proxy-nested-7",
            "root_module": "github.com/probe/svc",
            "root_version": "v1.0.0",
        },
        "retract_queue": [],
        "exclude_queue": [],
        "module_index": {
            "github.com/probe/svc": {
                "selected_version": "v1.0.0",
                "versions": {
                    "v1.0.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/svc",
                                "version": "v1.0.0",
                                "checksum": "h1:" + ("d4" * 32),
                                "requires": [
                                    {
                                        "path": "github.com/probe/leaf",
                                        "version": "v0.2.0",
                                    }
                                ],
                                "replaces": [],
                            }
                        ],
                    }
                },
            },
            "github.com/probe/leaf": {
                "selected_version": "v0.2.0",
                "versions": {
                    "v0.2.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/leaf",
                                "version": "v0.2.0",
                                "checksum": "h1:sha256:" + ("cc" * 32),
                                "requires": [],
                                "replaces": [],
                            }
                        ],
                    }
                },
            },
        },
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=2)
        handle.write("\n")


def write_test_flag_probe_export(path: str) -> None:
    """Verifier probe: test-flagged requires skip; explicit test false still walks."""
    doc = {
        "export_meta": {
            "proxy_id": "probe-test-flag",
            "format_rev": "proxy-nested-7",
            "root_module": "github.com/probe/core",
            "root_version": "v1.0.0",
        },
        "retract_queue": [],
        "exclude_queue": [],
        "module_index": {
            "github.com/probe/core": {
                "selected_version": "v1.0.0",
                "versions": {
                    "v1.0.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/core",
                                "version": "v1.0.0",
                                "checksum": "h1:" + ("e5" * 32),
                                "requires": [
                                    {
                                        "path": "github.com/probe/keep",
                                        "version": "v0.1.0",
                                        "test": False,
                                    },
                                    {
                                        "path": "github.com/probe/skip",
                                        "version": "v0.2.0",
                                        "test": True,
                                    },
                                ],
                                "replaces": [],
                            }
                        ],
                    }
                },
            },
            "github.com/probe/keep": {
                "selected_version": "v0.1.0",
                "versions": {
                    "v0.1.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/keep",
                                "version": "v0.1.0",
                                "checksum": "h1:" + ("f6" * 32),
                                "requires": [],
                                "replaces": [],
                            }
                        ],
                    }
                },
            },
            "github.com/probe/skip": {
                "selected_version": "v0.2.0",
                "versions": {
                    "v0.2.0": {
                        "go_version": "1.22.0",
                        "units": [
                            {
                                "path": "github.com/probe/skip",
                                "version": "v0.2.0",
                                "checksum": "h1:" + ("07" * 32),
                                "requires": [],
                                "replaces": [],
                            }
                        ],
                    }
                },
            },
        },
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=2)
        handle.write("\n")


def write_isolated_paths(
    base_dir: str,
    *,
    schema_version: str | None = None,
    proxy_export: str | None = None,
    cutover_register: str | None = None,
) -> str:
    """Write a paths.json under base_dir with isolated sqlite/digest/checksum paths."""
    os.makedirs(base_dir, exist_ok=True)
    base = load_json(DEFAULT_PATHS)
    doc: dict[str, Any] = dict(base)
    if schema_version is not None:
        doc["schema_version"] = schema_version
    if proxy_export is not None:
        doc["proxy_export"] = proxy_export
    if cutover_register is not None:
        doc["cutover_register"] = cutover_register
    doc["sqlite_path"] = os.path.join(base_dir, "module-provenance.sqlite3")
    doc["digest_path"] = os.path.join(base_dir, "dependency-digest.txt")
    doc["checksum_path"] = os.path.join(base_dir, "digest-checksum.sha256")
    # Keep smoke decoys pointing at the default workspace DB, not the isolated path.
    doc["database_path"] = "/workspace/state/module-provenance.sqlite3"
    doc["phinx_sqlite_name"] = "/workspace/state/module-provenance"
    path = os.path.join(base_dir, "paths.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, indent=2)
        handle.write("\n")
    return path


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [CLI, *args],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        timeout=180,
    )


def assert_two_space_json(path: str | Path) -> None:
    text = Path(path).read_text(encoding="utf-8")
    assert text.endswith("\n"), f"{path} must end with newline"
    doc = json.loads(text)
    canonical = json.dumps(doc, indent=2) + "\n"
    assert text == canonical, f"{path} must use two-space JSON"
