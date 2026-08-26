import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class Instance:
    ref: str
    parent_ref: str
    name: str
    version_range: str
    required_features: Tuple[str, ...]
    is_root: bool
    allow_keg_only: bool


def parse_version(raw: str) -> Tuple[Tuple[int, ...], str]:
    if "-" in raw:
        main, prerelease = raw.split("-", 1)
    else:
        main, prerelease = raw, ""
    return tuple(int(piece) for piece in main.split(".")), prerelease


def compare_version(left: str, right: str) -> int:
    lv, lp = parse_version(left)
    rv, rp = parse_version(right)
    width = max(len(lv), len(rv))
    lv = lv + (0,) * (width - len(lv))
    rv = rv + (0,) * (width - len(rv))
    if lv < rv:
        return -1
    if lv > rv:
        return 1
    if lp == rp:
        return 0
    if lp == "":
        return 1
    if rp == "":
        return -1
    return -1 if lp < rp else 1


def split_comparator(raw: str) -> Tuple[str, str]:
    for op in (">=", "<=", ">", "<", "="):
        if raw.startswith(op):
            return op, raw[len(op) :]
    raise ValueError(raw)


def compare_op(result: int, op: str) -> bool:
    return {
        ">=": result >= 0,
        "<=": result <= 0,
        ">": result > 0,
        "<": result < 0,
        "=": result == 0,
    }[op]


def matches_range(version: str, version_range: str) -> bool:
    lower, upper = version_range.split()
    low_op, low_ver = split_comparator(lower)
    high_op, high_ver = split_comparator(upper)
    return compare_op(compare_version(version, low_ver), low_op) and compare_op(compare_version(version, high_ver), high_op)


def dedupe_sorted(values: List[str]) -> List[str]:
    return sorted(dict.fromkeys(values))


def load_inputs(catalog_root: Path, request_path: Path):
    request = json.loads(request_path.read_text())
    request["root_formulae"] = [
        {
            **root,
            "required_features": dedupe_sorted(root["required_features"]),
        }
        for root in request["root_formulae"]
    ]
    catalog = json.loads((catalog_root / "formula_catalog.json").read_text())
    policies = {
        row["platform"]: row for row in json.loads((catalog_root / "platform_policy.json").read_text())["platforms"]
    }
    mirrors = set(json.loads((catalog_root / "mirror_inventory.json").read_text())["mirrored_digests"])
    formulas: Dict[str, List[dict]] = {}
    for record in catalog["formulas"]:
        versions = [{**row, "name": record["name"]} for row in record["versions"]]
        versions.sort(key=lambda row: (parse_version(row["version"])[0], parse_version(row["version"])[1] == "", parse_version(row["version"])[1], -row["revision"]), reverse=True)
        versions.sort(key=lambda row: row["revision"])
        versions.sort(key=lambda row: parse_version(row["version"]), reverse=True)
        formulas[record["name"]] = versions
    return request, formulas, policies, mirrors


def bottle_map(version: dict) -> Dict[str, dict]:
    return {row["platform"]: row for row in version["bottles"]}


def local_reasons(instance: Instance, version: dict, request: dict, policies: Dict[str, dict]) -> List[str]:
    reasons: List[str] = []
    if not matches_range(version["version"], instance.version_range):
        reasons.append("version_out_of_range")
    if version["prerelease"] and not request["allow_prerelease"]:
        reasons.append("prerelease_blocked")
    if instance.is_root and not instance.allow_keg_only and version["keg_only"]:
        reasons.append("keg_only_blocked")
    if reasons:
        return reasons

    bottles = bottle_map(version)
    missing = False
    runtime_conflict = False
    relocation_conflict = False
    codesign_missing = False
    for platform in request["target_platforms"]:
        bottle = bottles.get(platform)
        if bottle is None:
            missing = True
            continue
        policy = policies[platform]
        if compare_version(bottle["runtime_floor"], policy["minimum_runtime"]) > 0:
            runtime_conflict = True
        if request["relocation_policy"] == "strict" and not bottle["relocatable"]:
            relocation_conflict = True
        if policy["require_codesigned"] and not bottle["codesigned"]:
            codesign_missing = True
    if missing:
        reasons.append("platform_unavailable")
    if runtime_conflict:
        reasons.append("runtime_floor_conflict")
    if relocation_conflict:
        reasons.append("relocation_conflict")
    if codesign_missing:
        reasons.append("codesign_missing")
    return reasons


def make_children(instance: Instance, version: dict) -> List[Instance]:
    features = set(instance.required_features)
    children: List[Instance] = []
    for edge in version["dependencies"]:
        if all(feature in features for feature in edge["requires_features"]):
            children.append(
                Instance(
                    ref=f"{instance.ref}->{edge['name']}",
                    parent_ref=instance.ref,
                    name=edge["name"],
                    version_range=edge["version_range"],
                    required_features=tuple(),
                    is_root=False,
                    allow_keg_only=True,
                )
            )
    return children


def identity_list(selected_formulae: List[dict]) -> List[str]:
    values = []
    for row in selected_formulae:
        for bottle in row["bottles"]:
            values.append(f"formula/{row['name']}/{row['version']}/{bottle['platform']}@{bottle['digest']}")
    return sorted(values)


def render(selected: Dict[str, dict], instances: List[Instance], request: dict, formulas: Dict[str, List[dict]], policies: Dict[str, dict], mirrors: set):
    selected_formulae = []
    root_selections = []
    for root in request["root_formulae"]:
        root_selections.append({"name": root["name"], "selected_version": selected[root["name"]]["version"]})

    rows = {}
    new_digest_count = 0
    new_bytes = 0
    rebuild_sum = 0
    seen_new = set()
    for name in sorted(selected):
        version = selected[name]
        is_root = any(root["name"] == name for root in request["root_formulae"])
        active_features = []
        if is_root:
            active_features = next(root["required_features"] for root in request["root_formulae"] if root["name"] == name)
        dependencies = [
            {
                "name": edge["name"],
                "version_range": edge["version_range"],
                "requires_features": list(edge["requires_features"]),
            }
            for edge in version["dependencies"]
            if all(feature in active_features for feature in edge["requires_features"])
        ]
        bottles = []
        for platform in request["target_platforms"]:
            bottle = bottle_map(version).get(platform)
            if bottle is None:
                raise ValueError("missing bottle")
            cached = bottle["digest"] in mirrors
            bottles.append(
                {
                    "platform": platform,
                    "digest": bottle["digest"],
                    "cached": cached,
                    "bytes": bottle["bytes"],
                    "rebuild": bottle["rebuild"],
                    "relocatable": bottle["relocatable"],
                    "codesigned": bottle["codesigned"],
                    "runtime_floor": bottle["runtime_floor"],
                }
            )
            user = f"{name}@{platform}"
            row = rows.get(bottle["digest"])
            if row is None:
                rows[bottle["digest"]] = {
                    "formula_name": name,
                    "platform": platform,
                    "digest": bottle["digest"],
                    "bytes": bottle["bytes"],
                    "cached": cached,
                    "used_by_formulae": [user],
                }
            else:
                row["used_by_formulae"].append(user)
                if user < f"{row['formula_name']}@{row['platform']}":
                    row["formula_name"] = name
                    row["platform"] = platform
            if not cached and bottle["digest"] not in seen_new:
                seen_new.add(bottle["digest"])
                new_digest_count += 1
                new_bytes += bottle["bytes"]
            rebuild_sum += bottle["rebuild"]
        selected_formulae.append(
            {
                "name": name,
                "version": version["version"],
                "revision": version["revision"],
                "active_features": active_features,
                "root_requested": is_root,
                "dependencies": dependencies,
                "bottles": bottles,
            }
        )

    plan = {
        "request_id": request["request_id"],
        "relocation_policy": request["relocation_policy"],
        "target_platforms": request["target_platforms"],
        "root_selections": root_selections,
        "selected_formulae": selected_formulae,
        "unique_new_digest_count": new_digest_count,
        "total_new_bytes": new_bytes,
        "total_rebuild_sum": rebuild_sum,
    }

    selected_versions = [{"name": name, "version": selected[name]["version"]} for name in sorted(selected)]
    report = {
        "request_id": request["request_id"],
        "selected_versions": selected_versions,
        "instances": [],
    }
    for inst in instances:
        candidates = []
        for version in formulas[inst.name]:
            reasons = local_reasons(inst, version, request, policies)
            if reasons:
                status = "rejected_gate"
            elif selected[inst.name]["version"] == version["version"] and selected[inst.name]["revision"] == version["revision"]:
                status = "selected"
            else:
                status = "eligible_not_chosen"
            candidates.append(
                {
                    "version": version["version"],
                    "revision": version["revision"],
                    "status": status,
                    "reasons": reasons,
                }
            )
        report["instances"].append(
            {
                "instance_ref": inst.ref,
                "parent_instance_ref": inst.parent_ref,
                "name": inst.name,
                "version_range": inst.version_range,
                "required_features": list(inst.required_features),
                "candidate_versions": candidates,
            }
        )

    row_list = list(rows.values())
    for row in row_list:
        row["used_by_formulae"].sort()
    row_list.sort(key=lambda row: (0 if not row["cached"] else 1, row["formula_name"], row["platform"], row["digest"]))
    fetch_lines = ["step\taction\tdigest\tformula_name\tplatform\tbytes\tcached\tused_by_formulae"]
    for idx, row in enumerate(row_list, start=1):
        fetch_lines.append(
            "\t".join(
                [
                    str(idx),
                    "fetch" if not row["cached"] else "reuse_mirrored",
                    row["digest"],
                    row["formula_name"],
                    row["platform"],
                    str(row["bytes"]),
                    "true" if row["cached"] else "false",
                    ",".join(row["used_by_formulae"]),
                ]
            )
        )
    fetch_text = "\n".join(fetch_lines) + "\n"
    return plan, report, fetch_text


def compare_solution(left, right, request):
    lp, _, _ = left
    rp, _, _ = right
    left_key = [
        lp["unique_new_digest_count"],
        lp["total_new_bytes"],
        lp["total_rebuild_sum"],
    ]
    right_key = [
        rp["unique_new_digest_count"],
        rp["total_new_bytes"],
        rp["total_rebuild_sum"],
    ]
    if left_key != right_key:
        return -1 if left_key < right_key else 1
    for root in request["root_formulae"]:
        lv = next(row["selected_version"] for row in lp["root_selections"] if row["name"] == root["name"])
        rv = next(row["selected_version"] for row in rp["root_selections"] if row["name"] == root["name"])
        cmp = compare_version(lv, rv)
        if cmp != 0:
            return -cmp
    left_ids = identity_list(lp["selected_formulae"])
    right_ids = identity_list(rp["selected_formulae"])
    return -1 if left_ids < right_ids else (1 if left_ids > right_ids else 0)


def search_best(request, formulas, policies, mirrors):
    best = None
    root_instances = [
        Instance(
            ref=f"root.{root['name']}",
            parent_ref="NONE",
            name=root["name"],
            version_range=root["version_range"],
            required_features=tuple(root["required_features"]),
            is_root=True,
            allow_keg_only=root["allow_keg_only"],
        )
        for root in request["root_formulae"]
    ]

    def recurse(pending: List[Instance], selected: Dict[str, dict], instances: List[Instance]):
        nonlocal best
        if not pending:
            rendered = render(selected, instances, request, formulas, policies, mirrors)
            plan = rendered[0]
            if plan["unique_new_digest_count"] > request["max_new_digests"] or plan["total_new_bytes"] > request["max_new_bytes"]:
                return
            if best is None or compare_solution(rendered, best, request) < 0:
                best = rendered
            return

        inst = pending[0]
        rest = pending[1:]
        next_instances = instances + [inst]
        if inst.name in selected:
            if not local_reasons(inst, selected[inst.name], request, policies):
                recurse(make_children(inst, selected[inst.name]) + rest, selected, next_instances)
            return

        for version in formulas[inst.name]:
            if local_reasons(inst, version, request, policies):
                continue
            next_selected = dict(selected)
            next_selected[inst.name] = version
            recurse(make_children(inst, version) + rest, next_selected, next_instances)

    recurse(root_instances, {}, [])
    return best


def build_reference(catalog_root: Path, request_path: Path):
    request, formulas, policies, mirrors = load_inputs(catalog_root, request_path)
    best = search_best(request, formulas, policies, mirrors)
    if best is None:
        raise RuntimeError("no feasible plan")
    plan, report, fetch_text = best
    return {
        "promotion_plan.json": json.dumps(plan, separators=(",", ":")) + "\n",
        "candidate_report.json": json.dumps(report, separators=(",", ":")) + "\n",
        "mirror_fetch.tsv": fetch_text,
    }
