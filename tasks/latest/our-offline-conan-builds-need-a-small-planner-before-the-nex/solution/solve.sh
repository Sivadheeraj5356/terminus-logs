#!/bin/bash
set -euo pipefail

mkdir -p /app/bin
cat > /app/bin/conanplan <<'PY'
#!/usr/bin/env python3
import json
import sys
from pathlib import Path

FILES = {"root": "profile-requests.json", "repo": "recipe-index.json", "lock": "conan-lock.json", "cache": "package-cache.json"}

def vkey(v):
    return tuple(int(x) for x in v.split("."))

def sat(version, constraint):
    val = vkey(version)
    for part in constraint.split(","):
        part = part.strip()
        if not part:
            continue
        if part.startswith(">="):
            if val < vkey(part[2:]): return False
        elif part.startswith("<="):
            if val > vkey(part[2:]): return False
        elif part.startswith(">"):
            if val <= vkey(part[1:]): return False
        elif part.startswith("<"):
            if val >= vkey(part[1:]): return False
        elif part.startswith("="):
            if val != vkey(part[1:]): return False
        else:
            raise SystemExit(f"bad constraint {constraint}")
    return True

def load_case(path):
    base = Path(path)
    return {k: json.loads((base / f).read_text()) for k, f in FILES.items()}

def repo_map(case):
    return {p["name"]: p for p in case["repo"]["packages"]}

def find_version(repo, name, version):
    for ver in repo.get(name, {}).get("versions", []):
        if ver["version"] == version:
            return ver
    return None

def future_direct(case):
    cons, feats = {}, {}
    for stage in case["root"]["stages"]:
        for req in stage["requests"]:
            cons.setdefault(req["target"], []).append(req["constraint"])
            feats.setdefault(req["target"], set()).update(req.get("features", []))
    return cons, feats

def reusable(case, name, version, toolchain, features):
    fs = sorted(set(features))
    repo = repo_map(case)
    ver = find_version(repo, name, version)
    if not ver:
        return False
    hashes = {a["hash"] for a in ver.get("artifacts", []) if a.get("toolchain") == toolchain and sorted(a.get("features", [])) == fs}
    if not hashes:
        return False
    return any(
        ent.get("name") == name and ent.get("version") == version and ent.get("toolchain") == toolchain and
        sorted(ent.get("features", [])) == fs and ent.get("hash") in hashes
        for ent in case["cache"].get("entries", [])
    )

def dep_count(ver, projected):
    deps = list(ver.get("dependencies", []))
    for feat in projected:
        deps.extend(ver.get("feature_dependencies", {}).get(feat, []))
    return len(deps)

def choose(case, name, constraints, features):
    repo = repo_map(case)
    toolchain = case["root"]["toolchain"]
    fcons, ffeats = future_direct(case)
    all_cons = list(constraints.get(name, [])) + fcons.get(name, [])
    best = []
    for ver in repo.get(name, {}).get("versions", []):
        projected = set(ver.get("default_features", [])) | set(features.get(name, set())) | ffeats.get(name, set())
        if toolchain not in ver.get("toolchains", []):
            continue
        if not all(sat(ver["version"], c) for c in all_cons):
            continue
        if not projected <= set(ver.get("supported_features", [])):
            continue
        best.append((1 if reusable(case, name, ver["version"], toolchain, projected) else 0, -dep_count(ver, projected), vkey(ver["version"]), name, ver["version"], ver))
    if not best:
        return None
    best.sort(reverse=True)
    return best[0][-1]

def solve_case(case):
    repo = repo_map(case)
    selected, features, constraints = {}, {}, {}
    conflicts_total = 0
    for ent in case["lock"].get("locked", []):
        name = ent["name"]
        version = ent["version"]
        selected[name] = version
        ver = find_version(repo, name, version)
        features[name] = set(ent.get("features", []))
        if ver:
            features[name].update(ver.get("default_features", []))
    stages_out = []
    for stage in case["root"]["stages"]:
        before = {k: (selected.get(k), tuple(sorted(features.get(k, set())))) for k in set(selected) | set(features)}
        queue = list(stage.get("requests", []))
        stage_conflicts, changed, seen_expansions = set(), set(), set()
        while queue:
            req = queue.pop(0)
            name = req["target"]
            constraints.setdefault(name, []).append(req["constraint"])
            old = set(features.get(name, set()))
            features.setdefault(name, set()).update(req.get("features", []))
            if features[name] != old:
                changed.add(name)
            if name in selected:
                ver = find_version(repo, name, selected[name])
                if not ver or not all(sat(selected[name], c) for c in constraints.get(name, [])):
                    stage_conflicts.add((name, "locked-version"))
                    continue
                features[name].update(ver.get("default_features", []))
                if not features[name] <= set(ver.get("supported_features", [])):
                    stage_conflicts.add((name, "unsupported-feature"))
                    continue
            else:
                ver = choose(case, name, constraints, features)
                if not ver:
                    stage_conflicts.add((name, "no-candidate"))
                    continue
                selected[name] = ver["version"]
                features[name].update(ver.get("default_features", []))
                changed.add(name)
            ver = find_version(repo, name, selected[name])
            exp_key = (name, selected[name], tuple(sorted(features[name])))
            if exp_key in seen_expansions:
                continue
            seen_expansions.add(exp_key)
            queue.extend(ver.get("dependencies", []))
            for feat in sorted(features[name]):
                queue.extend(ver.get("feature_dependencies", {}).get(feat, []))
        action_names = []
        for name in sorted(set(selected) | changed):
            now = (selected.get(name), tuple(sorted(features.get(name, set()))))
            if now != before.get(name) and name in selected and not any(c[0] == name for c in stage_conflicts):
                action_names.append(name)
        selected_arr = [{"name": n, "version": selected[n], "features": sorted(features[n])} for n in action_names]
        reused, built = [], []
        for ent in selected_arr:
            (reused if reusable(case, ent["name"], ent["version"], case["root"]["toolchain"], ent["features"]) else built).append(ent)
        conflicts = [{"name": n, "reason": r} for n, r in sorted(stage_conflicts)]
        conflicts_total += len(conflicts)
        stages_out.append({"id": stage["id"], "selected": selected_arr, "reused": reused, "built": built, "conflicts": conflicts})
    final_lock = [{"name": n, "version": selected[n], "features": sorted(features[n])} for n in sorted(selected)]
    return {"stages": stages_out, "final_lock": final_lock, "summary": {
        "selected": sum(len(s["selected"]) for s in stages_out),
        "reused": sum(len(s["reused"]) for s in stages_out),
        "built": sum(len(s["built"]) for s in stages_out),
        "conflicts": conflicts_total,
    }}

def main():
    if len(sys.argv) != 3:
        print("usage: planner INPUT_DIR OUTPUT_JSON", file=sys.stderr)
        return 2
    case = load_case(sys.argv[1])
    out = solve_case(case)
    path = Path(sys.argv[2])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, separators=(",", ":")))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
PY
chmod +x /app/bin/conanplan
