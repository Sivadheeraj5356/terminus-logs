import hashlib
import re
import subprocess
import tempfile
from pathlib import Path


CLI = Path("/opt/linkseal/bin/linkseal")
SRC = Path("/opt/linkseal/src/main.rs")
PUBLIC = Path("/opt/linkseal/public")
PUBLIC_OUT = Path("/opt/linkseal/public.lock")
TOKEN = re.compile(r"^[a-z0-9._-]+$")
SEGMENT = re.compile(r"^seg_(\d+).*\.pkg$")
EXEC_EVENT = re.compile(r"\bexecve(?:at)?\(")


def version(text):
    parts = text.split(".")
    if len(parts) != 3 or any(not part or not part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def version_text(value):
    return ".".join(str(part) for part in value)


def version_code(value):
    return value[0] * 1_000_000 + value[1] * 1_000 + value[2]


def parse_requirement(text):
    condition = None
    atom = text
    if "?" in text:
        raw, atom = text.split("?", 1)
        wanted = not raw.startswith("!")
        flag = raw if wanted else raw[1:]
        if not TOKEN.fullmatch(flag):
            return None
        condition = (flag, wanted)
    if "#" not in atom or ".." not in atom or "@" not in atom:
        return None
    cap_abi, bounds = atom.split("#", 1)
    cap, abi_text = cap_abi.rsplit("@", 1)
    lo_text, hi_text = bounds.split("..", 1)
    if not TOKEN.fullmatch(cap):
        return None
    if abi_text == "*":
        abi = None
    elif abi_text.isdigit():
        abi = int(abi_text)
    else:
        return None
    lo = None if lo_text == "*" else version(lo_text)
    hi = None if hi_text == "*" else version(hi_text)
    if (lo_text != "*" and lo is None) or (hi_text != "*" and hi is None):
        return None
    if lo is not None and hi is not None and lo > hi:
        return None
    return {"condition": condition, "cap": cap, "abi": abi, "lo": lo, "hi": hi}


def parse_provide(text):
    if "@" not in text:
        return None
    cap, abi = text.rsplit("@", 1)
    if not TOKEN.fullmatch(cap) or not abi.isdigit():
        return None
    return cap, int(abi)


def parse_conflict(text):
    if "@" in text:
        cap, abi = text.rsplit("@", 1)
        if not TOKEN.fullmatch(cap) or (abi != "*" and not abi.isdigit()):
            return None
        return ("cap", cap, None if abi == "*" else int(abi))
    if not TOKEN.fullmatch(text):
        return None
    return ("name", text)


def parse_list(text, parser):
    if text == "-":
        return []
    result = []
    for item in text.split(","):
        if not item:
            return None
        parsed = parser(item)
        if parsed is None:
            return None
        result.append(parsed)
    return result


def parse_release(text, segment, line, filename):
    fields = [field.strip() for field in text.split("|")]
    if len(fields) != 11 or not TOKEN.fullmatch(fields[0]):
        return None
    ver = version(fields[1])
    if ver is None:
        return None
    if fields[2] == "*":
        targets = ["*"]
    else:
        targets = fields[2].split(",")
        if not targets or any(not TOKEN.fullmatch(item) for item in targets):
            return None
    provides = parse_list(fields[3], parse_provide)
    requires = parse_list(fields[4], parse_requirement)
    conflicts = parse_list(fields[5], parse_conflict)
    if not provides or requires is None or conflicts is None:
        return None
    try:
        toolchain, source, image, risk = map(int, fields[6:10])
    except ValueError:
        return None
    if min(toolchain, source, image, risk) < 0 or fields[10] not in {"yes", "no"}:
        return None
    return {
        "name": fields[0],
        "version": ver,
        "targets": targets,
        "provides": provides,
        "requires": requires,
        "conflicts": conflicts,
        "toolchain": toolchain,
        "source": source,
        "image": image,
        "risk": risk,
        "cached": fields[10] == "yes",
        "segment": segment,
        "line": line,
        "file": filename,
    }


def active_lines(path):
    for line_number, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if line and not line.startswith("#"):
            yield line_number, line


def load_case(case_dir):
    policy_values = {}
    for _, line in active_lines(case_dir / "policy.cfg"):
        key, value = line.split("=", 1)
        policy_values[key.strip()] = value.strip()
    flags = set() if policy_values["flags"] == "-" else set(policy_values["flags"].split(","))
    policy = {
        "target": policy_values["target"],
        "flags": flags,
        "toolchain_max": int(policy_values["toolchain_max"]),
        "source_budget": int(policy_values["source_budget"]),
        "image_budget": int(policy_values["image_budget"]),
        "risk_budget": int(policy_values["risk_budget"]),
    }
    roots = []
    for _, line in active_lines(case_dir / "roots.req"):
        req = parse_requirement(line)
        assert req is not None and req["condition"] is None
        roots.append(req)

    kept = {}
    registry = case_dir / "registry"
    for path in sorted(registry.iterdir(), key=lambda item: item.name):
        match = SEGMENT.fullmatch(path.name)
        if not path.is_file() or not match:
            continue
        segment = int(match.group(1))
        for line_number, line in active_lines(path):
            row = parse_release(line, segment, line_number, path.name)
            if row is None:
                continue
            key = row["name"], row["version"]
            old = kept.get(key)
            if (
                old is None
                or row["segment"] > old["segment"]
                or (row["segment"] == old["segment"] and row["line"] > old["line"])
                or (
                    row["segment"] == old["segment"]
                    and row["line"] == old["line"]
                    and row["file"] < old["file"]
                )
            ):
                kept[key] = row

    groups = {}
    for row in kept.values():
        if (
            row["toolchain"] <= policy["toolchain_max"]
            and ("*" in row["targets"] or policy["target"] in row["targets"])
        ):
            groups.setdefault(row["name"], []).append(row)
    for rows in groups.values():
        rows.sort(key=lambda row: row["version"])
    return policy, roots, [groups[name] for name in sorted(groups)]


def requirement_active(req, flags):
    if req["condition"] is None:
        return True
    flag, wanted = req["condition"]
    return (flag in flags) == wanted


def requirement_satisfied(req, selected):
    for row in selected:
        if req["lo"] is not None and row["version"] < req["lo"]:
            continue
        if req["hi"] is not None and row["version"] > req["hi"]:
            continue
        for cap, abi in row["provides"]:
            if cap == req["cap"] and (req["abi"] is None or abi == req["abi"]):
                return True
    return False


def plan_metrics(selected):
    ordered = sorted(selected, key=lambda row: row["name"])
    return {
        "rows": ordered,
        "count": len(ordered),
        "freshness": sum(version_code(row["version"]) for row in ordered),
        "source": sum(0 if row["cached"] else row["source"] for row in ordered),
        "image": sum(row["image"] for row in ordered),
        "risk": sum(row["risk"] for row in ordered),
        "signature": ",".join(f'{row["name"]}@{version_text(row["version"])}' for row in ordered),
    }


def feasible(selected, policy, roots):
    metrics = plan_metrics(selected)
    if (
        metrics["source"] > policy["source_budget"]
        or metrics["image"] > policy["image_budget"]
        or metrics["risk"] > policy["risk_budget"]
    ):
        return False
    abi_by_cap = {}
    for row in selected:
        for cap, abi in row["provides"]:
            if cap in abi_by_cap and abi_by_cap[cap] != abi:
                return False
            abi_by_cap[cap] = abi
    if any(not requirement_satisfied(req, selected) for req in roots):
        return False
    for row in selected:
        for req in row["requires"]:
            if requirement_active(req, policy["flags"]) and not requirement_satisfied(req, selected):
                return False
    for index, row in enumerate(selected):
        for conflict in row["conflicts"]:
            for other_index, other in enumerate(selected):
                if index == other_index:
                    continue
                if conflict[0] == "name" and other["name"] == conflict[1]:
                    return False
                if conflict[0] == "cap":
                    if any(
                        cap == conflict[1] and (conflict[2] is None or abi == conflict[2])
                        for cap, abi in other["provides"]
                    ):
                        return False
    return True


def score(metrics):
    return (
        metrics["count"],
        -metrics["freshness"],
        metrics["source"],
        metrics["image"],
        metrics["risk"],
        metrics["signature"],
    )


def solve_case(case_dir):
    policy, roots, groups = load_case(case_dir)
    best = None

    def requirement_key(req):
        return req["cap"], req["abi"], req["lo"], req["hi"]

    requirements = {requirement_key(req): req for req in roots}
    release_needs = {}
    for rows in groups:
        for row in rows:
            active = {
                requirement_key(req)
                for req in row["requires"]
                if requirement_active(req, policy["flags"])
            }
            release_needs[id(row)] = active
            for req in row["requires"]:
                if requirement_active(req, policy["flags"]):
                    requirements[requirement_key(req)] = req

    release_satisfies = {}
    for rows in groups:
        for row in rows:
            release_satisfies[id(row)] = {
                key for key, req in requirements.items() if requirement_satisfied(req, [row])
            }

    future = [set() for _ in range(len(groups) + 1)]
    for index in range(len(groups) - 1, -1, -1):
        future[index] = set(future[index + 1])
        for row in groups[index]:
            future[index].update(release_satisfies[id(row)])

    def visit(index, selected, source, image, risk, needed, satisfied):
        nonlocal best
        if (
            source > policy["source_budget"]
            or image > policy["image_budget"]
            or risk > policy["risk_budget"]
        ):
            return
        if not needed.issubset(satisfied | future[index]):
            return
        if best is not None and len(selected) > best["count"]:
            return
        if index == len(groups):
            if feasible(selected, policy, roots):
                metrics = plan_metrics(selected)
                if best is None or score(metrics) < score(best):
                    best = metrics
            return
        visit(index + 1, selected, source, image, risk, needed, satisfied)
        for row in groups[index]:
            visit(
                index + 1,
                selected + [row],
                source + (0 if row["cached"] else row["source"]),
                image + row["image"],
                risk + row["risk"],
                needed | release_needs[id(row)],
                satisfied | release_satisfies[id(row)],
            )

    visit(0, [], 0, 0, 0, {requirement_key(req) for req in roots}, set())
    if best is None:
        return "UNSAT\n"
    lines = [
        f'TOTAL|{best["count"]}|{best["freshness"]}|{best["source"]}|{best["image"]}|{best["risk"]}'
    ]
    lines.extend(
        f'LOCK|{row["name"]}|{version_text(row["version"])}|{row["segment"]}|{row["line"]}|{"yes" if row["cached"] else "no"}'
        for row in best["rows"]
    )
    return "\n".join(lines) + "\n"


def tree_hash(root):
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def run_cli(case_dir, output_path):
    before = tree_hash(case_dir)
    expected = solve_case(case_dir)
    with tempfile.TemporaryDirectory(prefix="linkseal-exec-trace-") as trace_dir:
        trace_path = Path(trace_dir) / "exec.trace"
        proc = subprocess.run(
            [
                "strace",
                "-f",
                "-qq",
                "-e",
                "trace=execve,execveat",
                "-o",
                str(trace_path),
                str(CLI),
                "--input",
                str(case_dir),
                "--output",
                str(output_path),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
        )
        exec_events = [
            line for line in trace_path.read_text().splitlines() if EXEC_EVENT.search(line)
        ]
    assert len(exec_events) == 1, (
        "resolver launched a helper process: " + " | ".join(exec_events)
    )
    assert f'execve("{CLI}"' in exec_events[0], exec_events[0]
    assert proc.returncode == 0, proc.stderr
    assert output_path.exists(), "required output was not created"
    actual = output_path.read_text()
    assert actual == expected
    assert actual.endswith("\n")
    assert tree_hash(case_dir) == before
    return actual


def write_case(parent, name, roots, segments, **overrides):
    case_dir = Path(parent) / name
    registry = case_dir / "registry"
    registry.mkdir(parents=True)
    policy = {
        "target": "x86_64-linux",
        "flags": "-",
        "toolchain_max": 185,
        "source_budget": 100,
        "image_budget": 300,
        "risk_budget": 100,
    }
    policy.update(overrides)
    (case_dir / "policy.cfg").write_text(
        "\n".join(
            [
                f'target={policy["target"]}',
                f'flags={policy["flags"]}',
                f'toolchain_max={policy["toolchain_max"]}',
                f'source_budget={policy["source_budget"]}',
                f'image_budget={policy["image_budget"]}',
                f'risk_budget={policy["risk_budget"]}',
            ]
        )
        + "\n"
    )
    (case_dir / "roots.req").write_text("\n".join(roots) + ("\n" if roots else ""))
    for filename, lines in segments.items():
        (registry / filename).write_text("\n".join(lines) + "\n")
    return case_dir


def row(name, ver, provides, requires="-", conflicts="-", target="*", toolchain=170,
        source=0, image=1, risk=1, cached="yes"):
    return (
        f"{name}|{ver}|{target}|{provides}|{requires}|{conflicts}|"
        f"{toolchain}|{source}|{image}|{risk}|{cached}"
    )


def hard_case(parent, name, flags):
    rows = [
        row("frontd", "3.2.0", "front@2", "core@2#2.0.0..*,net@2#2.0.0..*,secure?proof@1#*..*",
            target="arm64-linux", source=1, image=3, risk=1, cached="no"),
        row("frontd", "3.1.0", "front@2", "core@2#2.0.0..*,net@2#2.0.0..*,secure?proof@1#*..*",
            target="riscv64-linux", toolchain=180, source=3, image=8, risk=1, cached="no"),
        row("frontd", "3.0.0", "front@2", "core@2#2.0.0..*,net@2#2.0.0..*,secure?proof@1#*..*",
            target="riscv64-linux", image=13, risk=5),
        row("workerd", "4.2.0", "worker@2", "core@2#2.0.0..*,codec@2#2.0.0..*,!thin?render@2#*..*",
            target="riscv64-linux", toolchain=190, source=1, image=3, risk=1, cached="no"),
        row("workerd", "4.1.0", "worker@2", "core@2#2.0.0..*,codec@2#2.0.0..*,!thin?render@2#*..*",
            target="riscv64-linux", toolchain=180, source=2, image=8, risk=1, cached="no"),
        row("workerd", "4.0.0", "worker@2", "core@2#2.0.0..*,codec@2#2.0.0..*,!thin?render@2#*..*",
            target="riscv64-linux", image=13, risk=5),
        row("auditd", "2.1.0", "audit@2", "core@2#2.0.0..*,store@2#2.0.0..*,secure?proof@1#*..*",
            target="riscv64-linux", toolchain=180, source=2, image=8, risk=1, cached="no"),
        row("auditd", "2.0.0", "audit@2", "core@2#2.0.0..*,store@2#2.0.0..*,secure?proof@1#*..*",
            target="riscv64-linux", image=13, risk=5),
        row("mesh", "2.3.0", "core@2,net@2,codec@2", target="riscv64-linux",
            toolchain=180, source=5, image=14, risk=2, cached="no"),
        row("mesh", "2.1.0", "core@2,net@2,codec@2", target="riscv64-linux",
            image=22, risk=8),
        row("renderx", "2.2.0", "render@2", target="riscv64-linux",
            toolchain=180, source=3, image=7, risk=1, cached="no"),
        row("renderx", "2.0.0", "render@2", target="riscv64-linux", image=12, risk=5),
        row("storex", "2.1.0", "store@2", target="riscv64-linux",
            toolchain=180, source=2, image=7, risk=1, cached="no"),
        row("storex", "2.0.0", "store@2", target="riscv64-linux", image=12, risk=5),
        row("proofx", "1.2.0", "proof@1", target="riscv64-linux",
            toolchain=180, source=3, image=6, risk=1, cached="no"),
        row("proofx", "1.0.0", "proof@1", target="riscv64-linux", image=10, risk=4),
    ]
    return write_case(
        parent,
        name,
        ["front@*#*..*", "worker@*#*..*", "audit@*#*..*"],
        {"seg_004_riscv.pkg": rows},
        target="riscv64-linux",
        flags=flags,
        toolchain_max=180,
        source_budget=10,
        image_budget=76,
        risk_budget=22,
    )


def profile_case(parent, name):
    if name == "basic_range":
        return write_case(parent, name, ["api@*#1.2.0..2.0.0"], {"seg_001_a.pkg": [
            row("apid", "1.1.0", "api@1"),
            row("apid", "1.7.0", "api@1"),
            row("apid", "2.1.0", "api@1"),
        ]})
    if name == "target_toolchain":
        return write_case(parent, name, ["engine@*#*..*"], {"seg_002_t.pkg": [
            row("engined", "3.0.0", "engine@1", target="arm64-linux"),
            row("engined", "2.0.0", "engine@1", target="x86_64-linux", toolchain=186),
            row("engined", "1.9.0", "engine@1", target="*", toolchain=185),
        ]})
    if name == "count_priority":
        return write_case(parent, name, ["alpha@*#*..*", "beta@*#*..*"], {"seg_001_c.pkg": [
            row("bundle", "1.0.0", "alpha@1,beta@1", source=5, cached="no"),
            row("alphaonly", "9.0.0", "alpha@1"),
            row("betaonly", "9.0.0", "beta@1"),
        ]})
    if name in {"flag_positive", "flag_negative"}:
        flags = "fips" if name == "flag_positive" else "-"
        return write_case(parent, name, ["app@*#*..*"], {"seg_001_f.pkg": [
            row("appd", "1.0.0", "app@1", "fips?guard@1#*..*,!fips?shim@1#*..*"),
            row("guardd", "1.0.0", "guard@1"),
            row("shimd", "1.0.0", "shim@1"),
        ]}, flags=flags)
    if name == "duplicate_segments":
        return write_case(parent, name, ["api@*#*..*"], {
            "seg_001_old.pkg": [row("apid", "1.0.0", "api@1", image=30, risk=9)],
            "seg_009_patch.pkg": [
                "# retained row is selected by physical position",
                row("apid", "1.0.0", "api@1", image=9, risk=4),
                "",
                row("apid", "1.0.0", "api@1", image=2, risk=1),
            ],
            "seg_010_invalid.pkg": ["apid|1.0|*|api@1|-|-|170|0|1|1|yes"],
        })
    if name == "duplicate_filename":
        return write_case(parent, name, ["api@*#*..*"], {
            "seg_007_a.pkg": [row("apid", "1.0.0", "api@1", image=2)],
            "seg_007_b.pkg": [row("apid", "1.0.0", "api@1", image=20)],
        })
    if name == "abi_unused":
        return write_case(parent, name, ["main@*#*..*"], {"seg_003_abi.pkg": [
            row("maind", "2.0.0", "main@1,shared@1", "dep@1#*..*"),
            row("maind", "1.0.0", "main@1", "dep@1#*..*"),
            row("depd", "1.0.0", "dep@1,shared@2"),
        ]})
    if name in {"name_conflict", "cap_conflict"}:
        conflict = "libd" if name == "name_conflict" else "lib@*"
        return write_case(parent, name, ["app@*#*..*"], {"seg_002_x.pkg": [
            row("appd", "2.0.0", "app@1", "lib@1#*..*", conflict),
            row("appd", "1.0.0", "app@1", "lib@1#*..*"),
            row("libd", "1.0.0", "lib@1"),
        ]})
    if name == "cached_budget":
        return write_case(parent, name, ["a@*#*..*", "b@*#*..*"], {"seg_001_k.pkg": [
            row("ad", "2.0.0", "a@1", source=999, image=3, risk=1, cached="yes"),
            row("ad", "1.0.0", "a@1", source=1, image=3, risk=1, cached="no"),
            row("bd", "1.0.0", "b@1", source=3, image=3, risk=1, cached="no"),
        ]}, source_budget=3)
    if name == "multi_budget":
        lines = []
        for package, cap, latest_source in [
            ("ad", "a", 3), ("bd", "b", 2), ("cd", "c", 2), ("dd", "d", 1)
        ]:
            lines.append(row(package, "2.0.0", f"{cap}@1", source=latest_source,
                             image=3, risk=1, cached="no"))
            lines.append(row(package, "1.0.0", f"{cap}@1", image=7, risk=5))
        return write_case(
            parent,
            name,
            [f"{cap}@*#*..*" for cap in "abcd"],
            {"seg_005_budget.pkg": lines},
            source_budget=5,
            image_budget=20,
            risk_budget=12,
        )
    if name in {"tie_source", "tie_image", "tie_risk", "tie_signature"}:
        first = {"source": 5, "image": 5, "risk": 5}
        second = {"source": 5, "image": 5, "risk": 5}
        if name == "tie_source":
            second["source"] = 2
        elif name == "tie_image":
            second["image"] = 2
        elif name == "tie_risk":
            second["risk"] = 2
        return write_case(parent, name, ["root@*#*..*"], {"seg_001_tie.pkg": [
            row("alpha", "1.0.0", "root@1", cached="no", **first),
            row("zeta", "1.0.0", "root@1", cached="no", **second),
        ]})
    if name == "range_boundary":
        return write_case(parent, name, ["api@2#1.2.0..1.4.0"], {"seg_001_b.pkg": [
            row("apid", "1.2.0", "api@2"),
            row("apid", "1.4.0", "api@2"),
            row("apid", "1.5.0", "api@2"),
        ]})
    if name == "scale_matrix":
        roots = []
        lines = []
        for index in range(20):
            package = f"node{index:02d}"
            capability = f"unit{index:02d}"
            roots.append(f"{capability}@*#*..*")
            lines.append(row(package, "1.0.0", f"{capability}@1", image=2, risk=1))
            if index == 0:
                lines.append(row(package, "2.9.999", f"{capability}@1", source=6,
                                 image=14, risk=7, cached="no"))
            else:
                lines.append(row(package, f"2.0.{index}", f"{capability}@1", source=1,
                                 image=4, risk=2, cached="no"))
        return write_case(
            parent,
            name,
            roots,
            {"seg_020_scale.pkg": lines},
            source_budget=6,
            image_budget=52,
            risk_budget=26,
        )
    if name == "hard_closure":
        return hard_case(parent, name, "secure")
    if name == "hard_thin":
        return hard_case(parent, name, "secure,thin")
    if name == "unsat":
        return write_case(parent, name, ["missing@1#*..*"], {"seg_001_u.pkg": [
            row("otherd", "1.0.0", "other@1"),
        ]})
    raise AssertionError(name)


def test_runtime_native_artifact_contract():
    for binary in ["bash", "rustc", "tmux", "asciinema", "readelf", "file", "strace"]:
        proc = subprocess.run(["/bin/sh", "-lc", f"command -v {binary}"], text=True,
                              stdout=subprocess.PIPE)
        assert proc.returncode == 0, f"{binary} is missing"
    assert SRC.is_file(), "Rust source is missing"
    assert CLI.is_file(), "resolver executable is missing"
    assert CLI.read_bytes()[:4] == b"\x7fELF", "resolver is not an ELF binary"


def test_public_registry_exact_and_input_integrity():
    expected = solve_case(PUBLIC)
    assert expected != "UNSAT\n"
    assert expected.count("\n") >= 8
    actual = run_cli(PUBLIC, PUBLIC_OUT)
    assert actual == expected
    assert "|3|" in next(line for line in actual.splitlines() if line.startswith("LOCK|gatewayd|"))


def test_hidden_basic_compatibility_gradient():
    with tempfile.TemporaryDirectory() as tmp:
        for name in ["basic_range", "target_toolchain", "count_priority", "range_boundary"]:
            case_dir = profile_case(tmp, name)
            run_cli(case_dir, Path(tmp) / f"{name}.lock")


def test_hidden_conditional_and_duplicate_matrix():
    with tempfile.TemporaryDirectory() as tmp:
        for name in ["flag_positive", "flag_negative", "duplicate_segments", "duplicate_filename"]:
            case_dir = profile_case(tmp, name)
            actual = run_cli(case_dir, Path(tmp) / f"{name}.lock")
            if name == "duplicate_segments":
                assert "LOCK|apid|1.0.0|9|4|yes" in actual
            if name == "duplicate_filename":
                assert "LOCK|apid|1.0.0|7|1|yes" in actual


def test_hidden_abi_and_asymmetric_conflict_matrix():
    with tempfile.TemporaryDirectory() as tmp:
        for name in ["abi_unused", "name_conflict", "cap_conflict"]:
            case_dir = profile_case(tmp, name)
            run_cli(case_dir, Path(tmp) / f"{name}.lock")


def test_hidden_budget_coupling_and_cached_accounting():
    with tempfile.TemporaryDirectory() as tmp:
        for name in ["cached_budget", "multi_budget"]:
            case_dir = profile_case(tmp, name)
            actual = run_cli(case_dir, Path(tmp) / f"{name}.lock")
            if name == "multi_budget":
                assert "LOCK|ad|1.0.0" in actual
                for package in ["bd", "cd", "dd"]:
                    assert f"LOCK|{package}|2.0.0" in actual


def test_hidden_complete_plan_tiebreak_matrix():
    with tempfile.TemporaryDirectory() as tmp:
        expected_names = {
            "tie_source": "zeta",
            "tie_image": "zeta",
            "tie_risk": "zeta",
            "tie_signature": "alpha",
        }
        for name, selected in expected_names.items():
            case_dir = profile_case(tmp, name)
            actual = run_cli(case_dir, Path(tmp) / f"{name}.lock")
            assert f"LOCK|{selected}|1.0.0" in actual


def test_hidden_hard_closure_flag_and_scale_variants():
    with tempfile.TemporaryDirectory() as tmp:
        full = profile_case(tmp, "hard_closure")
        thin = profile_case(tmp, "hard_thin")
        scale = profile_case(tmp, "scale_matrix")
        full_text = run_cli(full, Path(tmp) / "hard.lock")
        thin_text = run_cli(thin, Path(tmp) / "thin.lock")
        scale_text = run_cli(scale, Path(tmp) / "scale.lock")
        assert full_text != thin_text
        assert full_text.count("\n") >= 8
        assert "LOCK|mesh|2.1.0" in full_text
        assert scale_text.startswith("TOTAL|20|26000099|6|52|26\n")
        assert "LOCK|node00|1.0.0" in scale_text
        for index in range(14, 20):
            assert f"LOCK|node{index:02d}|2.0.{index}" in scale_text


def test_unsat_and_custom_nested_output():
    with tempfile.TemporaryDirectory() as tmp:
        unsat = profile_case(tmp, "unsat")
        assert run_cli(unsat, Path(tmp) / "unsat.lock") == "UNSAT\n"
        normal = profile_case(tmp, "basic_range")
        nested = Path(tmp) / "nested" / "locks" / "plan.lock"
        run_cli(normal, nested)
        assert nested.is_file()
