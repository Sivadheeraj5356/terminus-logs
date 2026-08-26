#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path


PROFILE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
MODULE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
LAYOUT_DIRS = ["bin", "cache", "config", "logs", "scripts", "scripts/addons", "startup"]
EXPORTS = {
    "BLENDER_USER_CONFIG": "config",
    "BLENDER_USER_SCRIPTS": "scripts",
    "BLENDER_USER_DATA": "",
    "BLENDER_USER_CACHE": "cache",
}
ZERO_HASH = "0" * 64
GENERATION_LEDGER = "generation_ledger.jsonl"
GENERATION_STATE = "generation_state.json"
GENERATION_PENDING = ".generation.pending.json"


class UsageError(Exception):
    pass


def fail(message):
    print(message, file=sys.stderr)
    return 1


def safe_profile(name):
    if not name or not PROFILE_RE.match(name) or name in {".", ".."} or "/" in name or "\\" in name:
        raise UsageError(f"invalid profile: {name}")


def safe_module(name):
    if not name or not MODULE_RE.match(name):
        raise UsageError(f"invalid addon module: {name}")


def safe_file_path(path):
    p = Path(path)
    if p.is_absolute() or ".." in p.parts or path in {"", ".", ".."} or "\\" in path:
        raise UsageError(f"unsafe addon file path: {path}")
    return p


def load_manifest(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as exc:
        raise UsageError(f"failed to read manifest {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise UsageError(f"manifest {path} must be a JSON object")
    validate_manifest_schema(data, path)
    return data


def validate_manifest_schema(data, path):
    for key in ["blender_version", "python_expr"]:
        if not isinstance(data.get(key), str):
            raise UsageError(f"manifest {path} field {key} must be a string")
    env = data.get("env")
    if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
        raise UsageError(f"manifest {path} field env must be an object of string values")
    if not isinstance(data.get("profile_settings"), dict):
        raise UsageError(f"manifest {path} field profile_settings must be an object")
    addons = data.get("addons", [])
    if addons is None:
        addons = []
    if not isinstance(addons, list):
        raise UsageError("manifest addons must be an array")
    seen_ids = set()
    seen_modules = set()
    for addon in addons:
        if not isinstance(addon, dict):
            raise UsageError("addon rows must be objects")
        addon_id = addon.get("id")
        module = addon.get("module")
        if not isinstance(addon_id, str):
            raise UsageError("addon id must be a string")
        if not isinstance(module, str):
            raise UsageError("addon module must be a string")
        if addon_id in seen_ids:
            raise UsageError(f"duplicate addon id: {addon_id}")
        if module in seen_modules:
            raise UsageError(f"duplicate addon module: {module}")
        seen_ids.add(addon_id)
        seen_modules.add(module)
    for addon in addons:
        addon_id = addon["id"]
        module = addon["module"]
        safe_module(module)
        if not isinstance(addon.get("version"), str):
            raise UsageError(f"addon {addon_id} version must be a string")
        if not isinstance(addon.get("enabled"), bool):
            raise UsageError(f"addon {addon_id} enabled must be a boolean")
        if not isinstance(addon.get("preferences"), dict):
            raise UsageError(f"addon {addon_id} preferences must be an object")
        for list_key in ["load_after", "load_before", "conflicts"]:
            values = addon.get(list_key, [])
            if values is None:
                values = []
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                raise UsageError(f"addon {addon_id} {list_key} must be an array of module names")
            for item in values:
                safe_module(item)
        requires = addon.get("requires", [])
        if requires is None:
            requires = []
        if not isinstance(requires, list):
            raise UsageError(f"addon {addon_id} requires must be an array")
        for item in requires:
            if not isinstance(item, dict):
                raise UsageError(f"addon {addon_id} requires rows must be objects")
            dep_module = item.get("module")
            min_version = item.get("min_version", "0")
            if not isinstance(dep_module, str):
                raise UsageError(f"addon {addon_id} dependency module must be a string")
            safe_module(dep_module)
            if not isinstance(min_version, str):
                raise UsageError(f"addon {addon_id} dependency min_version must be a string")
            parse_version(min_version)
        files = addon.get("files", {})
        if not isinstance(files, dict):
            raise UsageError(f"addon {addon_id} files must be an object")
        for rel, content in files.items():
            if not isinstance(rel, str):
                raise UsageError(f"addon {addon_id} file path must be a string")
            safe_file_path(rel)
            if not isinstance(content, str):
                raise UsageError(f"addon {addon_id} file {rel} content must be a string")


def validate_out_path(out_path):
    if out_path.exists() and out_path.is_dir():
        raise UsageError(f"invalid output path: {out_path}")
    parent = out_path.parent
    if parent and parent.exists() and not parent.is_dir():
        raise UsageError(f"invalid output path: {out_path}")


def ensure_out_parent(out_path):
    validate_out_path(out_path)
    parent = out_path.parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)


def write_json_atomic(path, payload):
    ensure_out_parent(path)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(tmp, path)
    except OSError as exc:
        raise UsageError(f"failed to write output {path}: {exc}") from exc


def abs_str(path):
    return str(path.resolve())


def manifest_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stable_json_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def generation_paths(profile_root):
    config = profile_root / "config"
    return config / GENERATION_LEDGER, config / GENERATION_STATE, config / GENERATION_PENDING


def generation_record_hash(record):
    unsigned = {key: value for key, value in record.items() if key != "record_hash"}
    return hashlib.sha256(canonical_json(unsigned).encode("utf-8")).hexdigest()


def current_lineage_hashes(profile_root):
    return {
        "managed_files_sha256": maybe_file_sha256(profile_root / "config" / "managed_files.json"),
        "profile_audit_sha256": maybe_file_sha256(profile_root / "config" / "profile_audit.json"),
    }


def parse_generation_ledger(path):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines:
            raise ValueError("empty ledger")
        records = [json.loads(line) for line in lines]
    except Exception as exc:
        raise UsageError(f"invalid generation ledger {path}: {exc}") from exc
    if not all(isinstance(record, dict) for record in records):
        raise UsageError(f"invalid generation ledger {path}: records must be objects")
    return records


def validate_generation_records(records, profile):
    previous = ZERO_HASH
    for index, record in enumerate(records, start=1):
        required = {
            "generation",
            "profile",
            "manifest_sha256",
            "managed_files_sha256",
            "profile_audit_sha256",
            "previous_hash",
            "record_hash",
        }
        if set(record) != required or record.get("generation") != index or record.get("profile") != profile:
            raise UsageError("invalid generation ledger metadata or order")
        if record.get("previous_hash") != previous or record.get("record_hash") != generation_record_hash(record):
            raise UsageError("invalid generation ledger hash chain")
        for key in ["manifest_sha256", "managed_files_sha256", "profile_audit_sha256", "previous_hash", "record_hash"]:
            value = record.get(key)
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise UsageError("invalid generation ledger digest")
        previous = record["record_hash"]


def expected_generation_state(profile, record):
    return {
        "generated_by": "blendprofile",
        "profile": profile,
        "generation": record["generation"],
        "head_hash": record["record_hash"],
        "manifest_sha256": record["manifest_sha256"],
        "managed_files_sha256": record["managed_files_sha256"],
        "profile_audit_sha256": record["profile_audit_sha256"],
    }


def load_generation_lineage(profile_root, profile):
    ledger_path, state_path, pending_path = generation_paths(profile_root)
    if not ledger_path.exists() and not state_path.exists():
        return []
    if not ledger_path.is_file() or not state_path.is_file():
        raise UsageError("generation lineage is incomplete")
    records = parse_generation_ledger(ledger_path)
    validate_generation_records(records, profile)
    state = read_json(state_path, None)
    if state != expected_generation_state(profile, records[-1]):
        raise UsageError("generation state does not match ledger head")
    if pending_path.exists():
        pending = read_json(pending_path, None)
        hashes = current_lineage_hashes(profile_root)
        expected_pending = {
            "generated_by": "blendprofile",
            "profile": profile,
            "base_generation": state["generation"],
            "base_hash": state["head_hash"],
            "manifest_sha256": state["manifest_sha256"],
            **hashes,
        }
        if pending != expected_pending:
            raise UsageError("generation recovery marker conflicts with committed profile")
        pending_path.unlink()
    return records


def write_generation_lineage(profile_root, profile, manifest_sha, records):
    ledger_path, state_path, _ = generation_paths(profile_root)
    hashes = current_lineage_hashes(profile_root)
    if not all(hashes.values()):
        raise UsageError("generation lineage requires managed index and profile audit")
    if records:
        head = records[-1]
        if head["manifest_sha256"] == manifest_sha and all(head[key] == value for key, value in hashes.items()):
            return head
    record = {
        "generation": len(records) + 1,
        "profile": profile,
        "manifest_sha256": manifest_sha,
        **hashes,
        "previous_hash": records[-1]["record_hash"] if records else ZERO_HASH,
    }
    record["record_hash"] = generation_record_hash(record)
    updated = [*records, record]
    ledger_text = "".join(canonical_json(row) + "\n" for row in updated)
    ledger_tmp = ledger_path.with_name(ledger_path.name + ".tmp")
    try:
        ledger_tmp.write_text(ledger_text, encoding="utf-8")
        os.replace(ledger_tmp, ledger_path)
    except OSError as exc:
        raise UsageError(f"failed to write generation ledger {ledger_path}: {exc}") from exc
    write_json_atomic(state_path, expected_generation_state(profile, record))
    return record


def addon_content_sha(files):
    digest = hashlib.sha256()
    for name, content in sorted((files or {}).items()):
        digest.update(str(name).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(content).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def maybe_file_sha256(path):
    path = Path(path)
    if not path.exists() or path.is_symlink() or not path.is_file():
        return None
    return file_sha256(path)


def parse_version(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d+(?:\.\d+)*", value):
        raise UsageError(f"invalid version: {value}")
    return tuple(int(part) for part in value.split("."))


def version_gte(actual, minimum):
    left = list(parse_version(actual))
    right = list(parse_version(minimum))
    width = max(len(left), len(right))
    left.extend([0] * (width - len(left)))
    right.extend([0] * (width - len(right)))
    return tuple(left) >= tuple(right)


def requires_rows(addon):
    rows = []
    for item in addon.get("requires") or []:
        rows.append({"module": item["module"], "min_version": item.get("min_version", "0")})
    return sorted(rows, key=lambda row: (row["module"], row["min_version"]))


def addon_graph_fields(addon):
    return {
        "requires": requires_rows(addon),
        "load_after": sorted(addon.get("load_after") or []),
        "load_before": sorted(addon.get("load_before") or []),
        "conflicts": sorted(addon.get("conflicts") or []),
    }


def resolve_addon_graph(addons):
    by_module = {addon["module"]: addon for addon in addons}
    enabled = {addon["module"] for addon in addons if bool(addon.get("enabled", False))}
    edges = set()
    for addon in addons:
        module = addon["module"]
        if module not in enabled:
            continue
        for conflict in addon.get("conflicts") or []:
            if conflict in enabled:
                raise UsageError(f"addon conflict: {module} conflicts with {conflict}")
        for dep in requires_rows(addon):
            dep_module = dep["module"]
            if dep_module not in by_module or dep_module not in enabled:
                raise UsageError(f"addon dependency missing or disabled: {module} requires {dep_module}")
            actual = by_module[dep_module].get("version", "")
            minimum = dep["min_version"]
            if not version_gte(actual, minimum):
                raise UsageError(f"addon dependency version: {module} requires {dep_module} >= {minimum}")
            edges.add((dep_module, module))
        for dep_module in addon.get("load_after") or []:
            if dep_module not in enabled:
                raise UsageError(f"addon load_after missing or disabled: {module} after {dep_module}")
            edges.add((dep_module, module))
        for target in addon.get("load_before") or []:
            if target not in enabled:
                raise UsageError(f"addon load_before missing or disabled: {module} before {target}")
            edges.add((module, target))
    children = {module: set() for module in enabled}
    indegree = {module: 0 for module in enabled}
    for before, after in sorted(edges):
        if before == after:
            raise UsageError(f"addon dependency cycle: {before}")
        children[before].add(after)
        indegree[after] += 1
    ready = sorted(module for module, degree in indegree.items() if degree == 0)
    order = []
    while ready:
        module = ready.pop(0)
        order.append(module)
        for child in sorted(children[module]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort()
    if len(order) != len(enabled):
        raise UsageError("addon dependency cycle")
    return {
        "enabled_modules": sorted(enabled),
        "addon_load_order": order,
        "dependency_edges": [f"{before}->{after}" for before, after in sorted(edges)],
    }


def addon_disk_content_sha(addon_dir, files):
    digest = hashlib.sha256()
    for name in sorted((files or {}).keys()):
        target = addon_dir / safe_file_path(name)
        if not target.exists() or not target.is_file():
            return None
        digest.update(str(name).encode("utf-8"))
        digest.update(b"\0")
        digest.update(target.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def profile_paths(root, profile):
    profile_root = root / profile
    return profile_root, profile_root / "bin" / f"blender-{profile}", profile_root / "startup" / "bootstrap.py"


def managed_file_count(manifest):
    addons = manifest.get("addons") or []
    return 4 + len(addons) + sum(len(addon.get("files") or {}) for addon in addons)


def managed_file_specs(profile_root, profile, manifest):
    wrapper = profile_root / "bin" / f"blender-{profile}"
    specs = [
        (wrapper, "wrapper"),
        (profile_root / "startup" / "bootstrap.py", "bootstrap"),
        (profile_root / "config" / "enabled_addons.json", "enabled_metadata"),
        (profile_root / "config" / "addons.lock.json", "addon_lock"),
    ]
    for addon in sorted(manifest.get("addons") or [], key=lambda row: row["module"]):
        addon_dir = profile_root / "scripts" / "addons" / addon["module"]
        specs.append((addon_dir / "addon_manifest.json", "addon_manifest"))
        for rel in sorted((addon.get("files") or {}).keys()):
            specs.append((addon_dir / safe_file_path(rel), "addon_file"))
    return specs


def write_managed_index(profile_root, profile, manifest, manifest_sha):
    rows = []
    for path, kind in managed_file_specs(profile_root, profile, manifest):
        if not path.exists() or path.is_symlink() or not path.is_file():
            raise UsageError(f"managed file missing before index write: {path}")
        rows.append(
            {
                "path": path.relative_to(profile_root).as_posix(),
                "kind": kind,
                "sha256": file_sha256(path),
            }
        )
    rows.sort(key=lambda row: row["path"])
    payload = {
        "generated_by": "blendprofile",
        "profile": profile,
        "manifest_sha256": manifest_sha,
        "file_count": len(rows),
        "files": rows,
    }
    write_json_atomic(profile_root / "config" / "managed_files.json", payload)


def profile_audit_payload(profile_root, profile, manifest, manifest_sha):
    _, wrapper, bootstrap = profile_paths(profile_root.parent, profile)
    graph = resolve_addon_graph(manifest.get("addons") or [])
    enabled_path = profile_root / "config" / "enabled_addons.json"
    lock_path = profile_root / "config" / "addons.lock.json"
    managed_path = profile_root / "config" / "managed_files.json"
    addon_manifest_hashes = {}
    addon_content_hashes = {}
    for addon in sorted(manifest.get("addons") or [], key=lambda row: row["module"]):
        module = addon["module"]
        addon_dir = profile_root / "scripts" / "addons" / module
        addon_manifest_hashes[module] = maybe_file_sha256(addon_dir / "addon_manifest.json")
        addon_content_hashes[module] = addon_disk_content_sha(addon_dir, addon.get("files") or {})
    return {
        "generated_by": "blendprofile",
        "profile": profile,
        "manifest_sha256": manifest_sha,
        "wrapper_sha256": maybe_file_sha256(wrapper),
        "bootstrap_sha256": maybe_file_sha256(bootstrap),
        "enabled_addons_sha256": maybe_file_sha256(enabled_path),
        "addons_lock_sha256": maybe_file_sha256(lock_path),
        "managed_files_sha256": maybe_file_sha256(managed_path),
        "addon_manifest_sha256": addon_manifest_hashes,
        "addon_content_sha256": addon_content_hashes,
        "addon_load_order": graph["addon_load_order"],
        "dependency_edges": graph["dependency_edges"],
    }


def write_profile_audit(profile_root, profile, manifest, manifest_sha):
    write_json_atomic(profile_root / "config" / "profile_audit.json", profile_audit_payload(profile_root, profile, manifest, manifest_sha))


def preflight_managed_file_drift(profile_root):
    index_path = profile_root / "config" / "managed_files.json"
    if not index_path.exists():
        return
    payload = read_json(index_path, None)
    if not isinstance(payload, dict) or not isinstance(payload.get("files"), list):
        raise UsageError(f"managed file index is invalid: {index_path}")
    for row in payload["files"]:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str) or not isinstance(row.get("sha256"), str):
            raise UsageError(f"managed file index is invalid: {index_path}")
        rel = row["path"]
        safe_file_path(rel)
        target = profile_root / rel
        if not target.exists() or target.is_symlink() or not target.is_file() or file_sha256(target) != row["sha256"]:
            raise UsageError(f"managed file changed: {rel}")


def create_report(manifest, root, profile, dry_run, manifest_sha, generation=0, generation_hash=ZERO_HASH):
    profile_root, wrapper, bootstrap = profile_paths(root, profile)
    addons = sorted(manifest.get("addons") or [], key=lambda row: row["module"])
    graph = resolve_addon_graph(addons)
    lock_path = profile_root / "config" / "addons.lock.json"
    managed_path = profile_root / "config" / "managed_files.json"
    audit_path = profile_root / "config" / "profile_audit.json"
    ledger_path, state_path, _ = generation_paths(profile_root)
    return {
        "generated_by": "blendprofile",
        "profile": profile,
        "profile_root": abs_str(profile_root),
        "directories": sorted(abs_str(profile_root / rel) for rel in LAYOUT_DIRS),
        "wrapper_path": abs_str(wrapper),
        "bootstrap_path": abs_str(bootstrap),
        "blender_version": manifest.get("blender_version", ""),
        "manifest_sha256": manifest_sha,
        "dry_run": dry_run,
        "addon_count": len(addons),
        "addon_file_count": sum(len(row.get("files") or {}) for row in addons),
        "enabled_addons": sorted(row["module"] for row in addons if bool(row.get("enabled", False))),
        "addon_load_order": graph["addon_load_order"],
        "dependency_edges": graph["dependency_edges"],
        "addon_manifests": sorted(abs_str(profile_root / "scripts" / "addons" / row["module"] / "addon_manifest.json") for row in addons),
        "addon_lock_path": abs_str(lock_path),
        "managed_files_path": abs_str(managed_path),
        "profile_audit_path": abs_str(audit_path),
        "generation_ledger_path": abs_str(ledger_path),
        "generation_state_path": abs_str(state_path),
        "generation": generation,
        "generation_hash": generation_hash,
        "managed_file_count": managed_file_count(manifest),
    }


def write_wrapper(path, profile_root):
    text = "\n".join(
        [
            "#!/bin/sh",
            f"export BLENDER_USER_CONFIG={profile_root / 'config'}",
            f"export BLENDER_USER_SCRIPTS={profile_root / 'scripts'}",
            f"export BLENDER_USER_DATA={profile_root}",
            f"export BLENDER_USER_CACHE={profile_root / 'cache'}",
            'exec blender "$@"',
            "",
        ]
    )
    path.write_text(text, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def write_bootstrap(path, profile, manifest, manifest_sha):
    text = (
        f'PROFILE_NAME = "{profile}"\n'
        f'BLENDER_VERSION = "{manifest.get("blender_version", "")}"\n'
        f"PYTHON_EXPR = {json.dumps(manifest.get('python_expr', ''))}\n"
        f"PROFILE_ENV = {json.dumps(manifest.get('env', {}), sort_keys=True)}\n"
        f"PROFILE_SETTINGS = {json.dumps(manifest.get('profile_settings', {}), sort_keys=True)}\n"
        f'MANIFEST_SHA256 = "{manifest_sha}"\n'
    )
    path.write_text(text, encoding="utf-8")


def expected_bootstrap_lines(profile, manifest, manifest_sha):
    return {
        "PROFILE_NAME": f'PROFILE_NAME = "{profile}"',
        "BLENDER_VERSION": f'BLENDER_VERSION = "{manifest.get("blender_version", "")}"',
        "PYTHON_EXPR": f"PYTHON_EXPR = {json.dumps(manifest.get('python_expr', ''))}",
        "PROFILE_ENV": f"PROFILE_ENV = {json.dumps(manifest.get('env', {}), sort_keys=True)}",
        "PROFILE_SETTINGS": f"PROFILE_SETTINGS = {json.dumps(manifest.get('profile_settings', {}), sort_keys=True)}",
        "MANIFEST_SHA256": f'MANIFEST_SHA256 = "{manifest_sha}"',
    }


def lock_row(addon):
    files = addon.get("files") or {}
    return {
        "id": addon["id"],
        "module": addon["module"],
        "version": addon.get("version", ""),
        "enabled": bool(addon.get("enabled", False)),
        "file_count": len(files),
        "content_sha256": addon_content_sha(files),
        "preferences_sha256": stable_json_sha(addon.get("preferences", {})),
    }


def preflight_addon_targets(profile_root, addons):
    addon_root = profile_root / "scripts" / "addons"
    for addon in addons:
        addon_dir = addon_root / addon["module"]
        if addon_dir.exists() and not addon_dir.is_dir():
            raise UsageError(f"failed to install addon {addon['module']}: addon path is not a directory")


def install_addons(profile_root, profile, addons, manifest_sha):
    addon_root = profile_root / "scripts" / "addons"
    graph = resolve_addon_graph(addons)
    declared_modules = {addon["module"] for addon in addons}
    addon_root.mkdir(parents=True, exist_ok=True)
    for child in addon_root.iterdir():
        if child.name not in declared_modules:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    installed = []
    enabled_rows = []
    for addon in sorted(addons, key=lambda row: row["module"]):
        addon_dir = addon_root / addon["module"]
        if addon_dir.exists() and not addon_dir.is_dir():
            raise UsageError(f"failed to install addon {addon['module']}: addon path is not a directory")
        if addon_dir.exists():
            shutil.rmtree(addon_dir)
        addon_dir.mkdir(parents=True, exist_ok=True)
        for rel, content in sorted((addon.get("files") or {}).items()):
            target = addon_dir / safe_file_path(rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(content), encoding="utf-8")
        meta = {
            "id": addon["id"],
            "module": addon["module"],
            "version": addon.get("version", ""),
            "enabled": bool(addon.get("enabled", False)),
            "preferences": addon.get("preferences", {}),
            "install_path": abs_str(addon_dir),
            "files": sorted((addon.get("files") or {}).keys()),
            **addon_graph_fields(addon),
        }
        write_json_atomic(addon_dir / "addon_manifest.json", meta)
        installed.append(meta)
        if meta["enabled"]:
            enabled_rows.append(meta)
    enabled_payload = {
        "generated_by": "blendprofile",
        "profile": profile,
        "enabled_modules": sorted(row["module"] for row in enabled_rows),
        "addon_load_order": graph["addon_load_order"],
        "dependency_edges": graph["dependency_edges"],
        "addons": sorted(enabled_rows, key=lambda row: row["module"]),
    }
    write_json_atomic(profile_root / "config" / "enabled_addons.json", enabled_payload)
    lock_payload = {
        "generated_by": "blendprofile",
        "profile": profile,
        "manifest_sha256": manifest_sha,
        "addon_count": len(addons),
        "addon_file_count": sum(len(row.get("files") or {}) for row in addons),
        "addon_load_order": graph["addon_load_order"],
        "dependency_edges": graph["dependency_edges"],
        "addons": [lock_row(row) for row in sorted(addons, key=lambda row: row["module"])],
    }
    write_json_atomic(profile_root / "config" / "addons.lock.json", lock_payload)
    return installed


def command_create(args):
    safe_profile(args.profile)
    manifest = load_manifest(args.manifest)
    manifest_sha = manifest_sha256(args.manifest)
    root = Path(args.root)
    out = Path(args.out)
    if root.exists() and not root.is_dir():
        raise UsageError(f"root path is not a directory: {root}")
    validate_out_path(out)
    report = create_report(manifest, root, args.profile, args.dry_run, manifest_sha)
    if args.dry_run:
        write_json_atomic(out, report)
        return 0
    profile_root, wrapper, bootstrap = profile_paths(root, args.profile)
    if profile_root.is_symlink() or (profile_root.exists() and not profile_root.is_dir()):
        raise UsageError(f"invalid profile root: {profile_root}")
    records = load_generation_lineage(profile_root, args.profile)
    preflight_managed_file_drift(profile_root)
    preflight_addon_targets(profile_root, manifest.get("addons") or [])
    for rel in LAYOUT_DIRS:
        (profile_root / rel).mkdir(parents=True, exist_ok=True)
    write_wrapper(wrapper, profile_root)
    write_bootstrap(bootstrap, args.profile, manifest, manifest_sha)
    install_addons(profile_root, args.profile, manifest.get("addons") or [], manifest_sha)
    write_managed_index(profile_root, args.profile, manifest, manifest_sha)
    write_profile_audit(profile_root, args.profile, manifest, manifest_sha)
    head = write_generation_lineage(profile_root, args.profile, manifest_sha, records)
    report = create_report(
        manifest,
        root,
        args.profile,
        False,
        manifest_sha,
        head["generation"],
        head["record_hash"],
    )
    write_json_atomic(out, report)
    return 0


def read_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def inspect_managed_index(profile_root, profile, manifest, manifest_sha):
    index_path = profile_root / "config" / "managed_files.json"
    if not index_path.exists():
        return ["__missing_index__"], 0
    payload = read_json(index_path, None)
    mismatches = []
    if not isinstance(payload, dict):
        return ["__metadata__"], 0
    rows = payload.get("files")
    if payload.get("generated_by") != "blendprofile" or payload.get("profile") != profile or payload.get("manifest_sha256") != manifest_sha:
        mismatches.append("__metadata__")
    if not isinstance(rows, list):
        mismatches.append("__metadata__")
        return sorted(set(mismatches)), 0
    expected_specs = managed_file_specs(profile_root, profile, manifest)
    expected_by_path = {path.relative_to(profile_root).as_posix(): kind for path, kind in expected_specs}
    expected_paths = sorted(expected_by_path)
    actual_paths = []
    rows_by_path = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            mismatches.append("__metadata__")
            continue
        rel = row["path"]
        try:
            safe_file_path(rel)
        except UsageError:
            mismatches.append("__metadata__")
            continue
        actual_paths.append(rel)
        rows_by_path[rel] = row
    if actual_paths != sorted(actual_paths):
        mismatches.append("__order__")
    if sorted(actual_paths) != expected_paths or payload.get("file_count") != len(expected_paths):
        mismatches.append("__paths__")
    for rel in expected_paths:
        row = rows_by_path.get(rel)
        if not row:
            continue
        target = profile_root / rel
        if row.get("kind") != expected_by_path[rel]:
            mismatches.append(rel)
            continue
        if not isinstance(row.get("sha256"), str):
            mismatches.append(rel)
            continue
        if not target.exists() or target.is_symlink() or not target.is_file() or file_sha256(target) != row["sha256"]:
            mismatches.append(rel)
    return sorted(set(mismatches)), len(expected_paths)


def inspect_profile_audit(profile_root, profile, manifest, manifest_sha):
    audit_path = profile_root / "config" / "profile_audit.json"
    if not audit_path.exists():
        return ["__missing_audit__"]
    payload = read_json(audit_path, None)
    if not isinstance(payload, dict):
        return ["__metadata__"]
    expected = profile_audit_payload(profile_root, profile, manifest, manifest_sha)
    mismatches = []
    if (
        payload.get("generated_by") != "blendprofile"
        or payload.get("profile") != profile
        or payload.get("manifest_sha256") != manifest_sha
    ):
        mismatches.append("__metadata__")
    checks = [
        ("wrapper_sha256", "__wrapper__"),
        ("bootstrap_sha256", "__bootstrap__"),
        ("enabled_addons_sha256", "__enabled__"),
        ("addons_lock_sha256", "__lock__"),
        ("managed_files_sha256", "__managed__"),
    ]
    for key, sentinel in checks:
        if payload.get(key) != expected.get(key):
            mismatches.append(sentinel)
    if payload.get("addon_load_order") != expected["addon_load_order"] or payload.get("dependency_edges") != expected["dependency_edges"]:
        mismatches.append("__graph__")
    actual_manifest_hashes = payload.get("addon_manifest_sha256")
    actual_content_hashes = payload.get("addon_content_sha256")
    if not isinstance(actual_manifest_hashes, dict) or not isinstance(actual_content_hashes, dict):
        mismatches.append("__metadata__")
    else:
        for module, expected_hash in expected["addon_manifest_sha256"].items():
            if actual_manifest_hashes.get(module) != expected_hash:
                mismatches.append(f"{module}:addon_manifest")
        for module, expected_hash in expected["addon_content_sha256"].items():
            if actual_content_hashes.get(module) != expected_hash:
                mismatches.append(f"{module}:addon_files")
    return sorted(set(mismatches))


def inspect_generation_lineage(profile_root, profile, manifest_sha):
    ledger_path, state_path, pending_path = generation_paths(profile_root)
    mismatches = []
    records = []
    if not ledger_path.exists():
        mismatches.append("__missing_ledger__")
    elif not ledger_path.is_file():
        mismatches.append("__metadata__")
    else:
        try:
            records = parse_generation_ledger(ledger_path)
        except UsageError:
            mismatches.append("__metadata__")
    if records:
        previous = ZERO_HASH
        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict) or record.get("generation") != index or record.get("profile") != profile:
                mismatches.append("__order__")
                continue
            if record.get("previous_hash") != previous or record.get("record_hash") != generation_record_hash(record):
                mismatches.append("__chain__")
            previous = record.get("record_hash") if isinstance(record.get("record_hash"), str) else ZERO_HASH
    if not state_path.exists():
        mismatches.append("__missing_state__")
        state = None
    elif not state_path.is_file():
        mismatches.append("__metadata__")
        state = None
    else:
        state = read_json(state_path, None)
        if not isinstance(state, dict):
            mismatches.append("__metadata__")
            state = None
    head = records[-1] if records and isinstance(records[-1], dict) else None
    if state is not None and head is not None:
        if state != expected_generation_state(profile, head):
            mismatches.append("__head__")
        if head.get("manifest_sha256") != manifest_sha:
            mismatches.append("__manifest__")
        hashes = current_lineage_hashes(profile_root)
        if head.get("managed_files_sha256") != hashes["managed_files_sha256"]:
            mismatches.append("__managed__")
        if head.get("profile_audit_sha256") != hashes["profile_audit_sha256"]:
            mismatches.append("__audit__")
    if pending_path.exists():
        mismatches.append("__pending__")
    return sorted(set(mismatches))


def command_validate(args):
    safe_profile(args.profile)
    manifest = load_manifest(args.manifest)
    manifest_sha = manifest_sha256(args.manifest)
    root = Path(args.root)
    out = Path(args.out)
    validate_out_path(out)
    profile_root, wrapper, bootstrap = profile_paths(root, args.profile)
    lock_path = profile_root / "config" / "addons.lock.json"
    managed_path = profile_root / "config" / "managed_files.json"
    audit_path = profile_root / "config" / "profile_audit.json"
    ledger_path, state_path, _ = generation_paths(profile_root)
    graph = resolve_addon_graph(manifest.get("addons") or [])
    checked = [profile_root / rel for rel in LAYOUT_DIRS] + [
        wrapper,
        bootstrap,
        profile_root / "config" / "enabled_addons.json",
        lock_path,
        managed_path,
        audit_path,
        ledger_path,
        state_path,
    ]
    for addon in sorted(manifest.get("addons") or [], key=lambda row: row["module"]):
        addon_dir = profile_root / "scripts" / "addons" / addon["module"]
        checked.append(addon_dir / "addon_manifest.json")
        for rel in sorted((addon.get("files") or {}).keys()):
            checked.append(addon_dir / safe_file_path(rel))
    missing = sorted(abs_str(path) for path in checked if not path.exists())
    mismatched = []
    if wrapper.exists():
        text = wrapper.read_text(encoding="utf-8")
        for key, rel in EXPORTS.items():
            expected = profile_root if rel == "" else profile_root / rel
            if f"{key}={expected}" not in text:
                mismatched.append(key)
    else:
        mismatched.extend(sorted(EXPORTS))
    enabled_payload = read_json(profile_root / "config" / "enabled_addons.json", {})
    enabled_modules = enabled_payload.get("enabled_modules", [])
    if not isinstance(enabled_modules, list):
        enabled_modules = []
    issues = []
    issues.extend(f"missing:{path}" for path in missing)
    issues.extend(f"export:{name}" for name in sorted(mismatched))
    declared_modules = {addon["module"] for addon in manifest.get("addons") or []}
    addon_root = profile_root / "scripts" / "addons"
    unexpected_addons = []
    if addon_root.exists() and addon_root.is_dir():
        unexpected_addons = sorted(child.name for child in addon_root.iterdir() if child.is_dir() and child.name not in declared_modules)
    issues.extend(f"unexpected:{name}" for name in unexpected_addons)
    unexpected_addon_files = []
    unsafe_addon_paths = []
    for addon in sorted(manifest.get("addons") or [], key=lambda row: row["module"]):
        addon_dir = addon_root / addon["module"]
        if not addon_dir.exists() or not addon_dir.is_dir():
            continue
        expected_files = {"addon_manifest.json"}
        expected_files.update(Path(name).as_posix() for name in (addon.get("files") or {}).keys())
        module_unsafe = set()
        for rel in sorted((addon.get("files") or {}).keys()):
            posix_rel = Path(rel).as_posix()
            declared_path = addon_dir / safe_file_path(rel)
            if declared_path.exists() or declared_path.is_symlink():
                if declared_path.is_symlink() or not declared_path.is_file():
                    module_unsafe.add(f"{addon['module']}:{posix_rel}")
        for path in sorted(addon_dir.rglob("*")):
            rel = path.relative_to(addon_dir).as_posix()
            if path.is_symlink():
                module_unsafe.add(f"{addon['module']}:{rel}")
            if not path.is_file():
                continue
            if rel not in expected_files:
                unexpected_addon_files.append(f"{addon['module']}:{rel}")
        unsafe_addon_paths.extend(module_unsafe)
    unexpected_addon_files = sorted(unexpected_addon_files)
    issues.extend(f"unexpected_file:{name}" for name in unexpected_addon_files)
    unsafe_addon_paths = sorted(set(unsafe_addon_paths))
    issues.extend(f"unsafe:{name}" for name in unsafe_addon_paths)
    bootstrap_issues = []
    if bootstrap.exists():
        boot_lines = set(bootstrap.read_text(encoding="utf-8").splitlines())
        for key, expected in expected_bootstrap_lines(args.profile, manifest, manifest_sha).items():
            if expected not in boot_lines:
                bootstrap_issues.append(f"bootstrap:{key}")
    enabled_issues = []
    expected_enabled_addons = []
    for addon in sorted((row for row in manifest.get("addons") or [] if bool(row.get("enabled", False))), key=lambda row: row["module"]):
        addon_dir = profile_root / "scripts" / "addons" / addon["module"]
        expected_enabled_addons.append(
            {
                "id": addon["id"],
                "module": addon["module"],
                "version": addon.get("version", ""),
                "enabled": True,
                "preferences": addon.get("preferences", {}),
                "install_path": abs_str(addon_dir),
                "files": sorted((addon.get("files") or {}).keys()),
                **addon_graph_fields(addon),
            }
        )
    expected_enabled_modules = sorted(row["module"] for row in expected_enabled_addons)
    if enabled_payload:
        if enabled_payload.get("generated_by") != "blendprofile":
            enabled_issues.append("enabled:generated_by")
        if enabled_payload.get("profile") != args.profile:
            enabled_issues.append("enabled:profile")
        if enabled_payload.get("enabled_modules") != expected_enabled_modules:
            enabled_issues.append("enabled:enabled_modules")
        actual_enabled_addons = enabled_payload.get("addons")
        if actual_enabled_addons != expected_enabled_addons:
            enabled_issues.append("enabled:addons")
    dependency_mismatches = []
    if enabled_payload:
        if enabled_payload.get("addon_load_order") != graph["addon_load_order"]:
            dependency_mismatches.append("__enabled_order__")
        if enabled_payload.get("dependency_edges") != graph["dependency_edges"]:
            dependency_mismatches.append("__enabled_edges__")
    managed_mismatches, managed_file_total = inspect_managed_index(profile_root, args.profile, manifest, manifest_sha)
    metadata_issues = []
    lock_mismatches = []
    lock_payload = read_json(lock_path, {}) if lock_path.exists() else {}
    lock_addons = lock_payload.get("addons", []) if isinstance(lock_payload, dict) else []
    if not isinstance(lock_addons, list):
        lock_addons = []
    lock_rows = {row.get("module"): row for row in lock_addons if isinstance(row, dict)}
    expected_lock_rows = [lock_row(row) for row in sorted(manifest.get("addons") or [], key=lambda row: row["module"])]
    if lock_path.exists():
        if lock_payload.get("generated_by") != "blendprofile":
            lock_mismatches.append("__generated_by__")
        if lock_payload.get("profile") != args.profile:
            lock_mismatches.append("__profile__")
        if lock_payload.get("manifest_sha256") != manifest_sha:
            lock_mismatches.append("__manifest__")
        if lock_payload.get("addon_count") != len(manifest.get("addons") or []):
            lock_mismatches.append("__count__")
        if lock_payload.get("addon_file_count") != sum(len(row.get("files") or {}) for row in manifest.get("addons") or []):
            lock_mismatches.append("__file_count__")
        if [row.get("module") if isinstance(row, dict) else None for row in lock_addons] != [row["module"] for row in expected_lock_rows]:
            lock_mismatches.append("__order__")
        if lock_payload.get("addon_load_order") != graph["addon_load_order"]:
            dependency_mismatches.append("__lock_order__")
        if lock_payload.get("dependency_edges") != graph["dependency_edges"]:
            dependency_mismatches.append("__lock_edges__")
    audit_mismatches = inspect_profile_audit(profile_root, args.profile, manifest, manifest_sha)
    lineage_mismatches = inspect_generation_lineage(profile_root, args.profile, manifest_sha)
    for addon in sorted(manifest.get("addons") or [], key=lambda row: row["module"]):
        addon_dir = profile_root / "scripts" / "addons" / addon["module"]
        meta_path = addon_dir / "addon_manifest.json"
        if not meta_path.exists():
            continue
        meta = read_json(meta_path, {})
        expected = {
            "id": addon["id"],
            "module": addon["module"],
            "version": addon.get("version", ""),
            "enabled": bool(addon.get("enabled", False)),
            "preferences": addon.get("preferences", {}),
            "install_path": abs_str(addon_dir),
            "files": sorted((addon.get("files") or {}).keys()),
            **addon_graph_fields(addon),
        }
        for key, value in expected.items():
            if meta.get(key) != value:
                metadata_issues.append(f"metadata:{addon['module']}:{key}")
        expected_lock = lock_row(addon)
        actual_lock = lock_rows.get(addon["module"])
        disk_sha = addon_disk_content_sha(addon_dir, addon.get("files") or {})
        if actual_lock != expected_lock or disk_sha != expected_lock["content_sha256"]:
            lock_mismatches.append(addon["module"])
    lock_mismatches = sorted(set(lock_mismatches))
    dependency_mismatches = sorted(set(dependency_mismatches))
    managed_mismatches = sorted(set(managed_mismatches))
    issues.extend(f"lock:{name}" for name in lock_mismatches)
    issues.extend(f"dependency:{name}" for name in dependency_mismatches)
    issues.extend(f"managed:{name}" for name in managed_mismatches)
    issues.extend(f"audit:{name}" for name in audit_mismatches)
    issues.extend(f"lineage:{name}" for name in lineage_mismatches)
    issues.extend(bootstrap_issues)
    issues.extend(enabled_issues)
    payload = {
        "generated_by": "blendprofile",
        "profile": args.profile,
        "profile_root": abs_str(profile_root),
        "ok": not missing and not unexpected_addons and not unexpected_addon_files and not unsafe_addon_paths and not mismatched and not bootstrap_issues and not enabled_issues and not metadata_issues and not lock_mismatches and not dependency_mismatches and not managed_mismatches and not audit_mismatches and not lineage_mismatches,
        "missing_paths": missing,
        "unexpected_addons": unexpected_addons,
        "unexpected_addon_files": unexpected_addon_files,
        "unsafe_addon_paths": unsafe_addon_paths,
        "mismatched_exports": sorted(mismatched),
        "lock_mismatches": lock_mismatches,
        "dependency_mismatches": dependency_mismatches,
        "managed_mismatches": managed_mismatches,
        "audit_mismatches": audit_mismatches,
        "lineage_mismatches": lineage_mismatches,
        "enabled_modules": sorted(enabled_modules),
        "addon_load_order": graph["addon_load_order"],
        "dependency_edges": graph["dependency_edges"],
        "managed_file_count": managed_file_total,
        "addon_count": len(manifest.get("addons") or []),
        "issues": sorted(issues + metadata_issues),
        "checked_paths": sorted(abs_str(path) for path in checked),
    }
    write_json_atomic(out, payload)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="blendprofile")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["create", "validate"]:
        cmd = sub.add_parser(name)
        cmd.add_argument("--manifest", required=True)
        cmd.add_argument("--root", required=True)
        cmd.add_argument("--profile", required=True)
        cmd.add_argument("--out", required=True)
        if name == "create":
            cmd.add_argument("--dry-run", action="store_true")
    return parser


def main():
    try:
        args = build_parser().parse_args()
        if args.command == "create":
            return command_create(args)
        if args.command == "validate":
            return command_validate(args)
    except UsageError as exc:
        return fail(str(exc))
    return fail("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
