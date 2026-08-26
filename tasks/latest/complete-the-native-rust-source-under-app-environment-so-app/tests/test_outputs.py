from __future__ import annotations

import itertools
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
ENV = APP / "environment"
BINARY = APP / "bin" / "forest-audit"
DEFAULT_MODEL = APP / "data" / "demo.forest"
DEFAULT_AUDIT = APP / "data" / "demo.audit"
DEFAULT_OUTPUT = APP / "output" / "certificates.json"


def fnv1a(data: bytes) -> str:
    value = 14695981039346656037
    for byte in data:
        value ^= byte
        value = (value * 1099511628211) & ((1 << 64) - 1)
    return f"{value:016x}"


def useful_lines(text: str) -> list[tuple[int, str]]:
    return [
        (number, line)
        for number, line in enumerate(text.splitlines(), 1)
        if line and not line.startswith("#")
    ]


def parse_model_reference(text: str) -> dict:
    features: dict[str, dict] = {}
    trees: dict[str, dict] = {}
    nodes: dict[tuple[str, str], dict] = {}
    bias = None
    for _, line in useful_lines(text)[1:]:
        fields = line.split("|")
        if fields[0] == "BIAS":
            bias = int(fields[1])
        elif fields[0] == "FEATURE":
            features[fields[1]] = {
                "min": int(fields[2]),
                "max": int(fields[3]),
                "cost": int(fields[4]),
            }
        elif fields[0] == "TREE":
            trees[fields[1]] = {"weight": int(fields[2]), "root": fields[3]}
        elif fields[0] == "NODE":
            nodes[(fields[1], fields[2])] = {
                "feature": fields[3],
                "threshold": int(fields[4]),
                "left": fields[5],
                "right": fields[6],
            }
    assert bias is not None
    return {"bias": bias, "features": features, "trees": trees, "nodes": nodes}


def canonical_model(model: dict) -> str:
    parts = [f"BIAS|{model['bias']}\n"]
    for feature in sorted(model["features"]):
        item = model["features"][feature]
        parts.append(f"FEATURE|{feature}|{item['min']}|{item['max']}|{item['cost']}\n")
    for tree in sorted(model["trees"]):
        item = model["trees"][tree]
        parts.append(f"TREE|{tree}|{item['weight']}|{item['root']}\n")
    for tree, node in sorted(model["nodes"]):
        item = model["nodes"][(tree, node)]
        parts.append(
            f"NODE|{tree}|{node}|{item['feature']}|{item['threshold']}|"
            f"{item['left']}|{item['right']}\n"
        )
    return "".join(parts)


def evaluate_reference(model: dict, values: dict[str, int]) -> dict:
    score = model["bias"]
    votes = []
    for tree in sorted(model["trees"]):
        tree_spec = model["trees"][tree]
        node_id = tree_spec["root"]
        while True:
            node = model["nodes"][(tree, node_id)]
            child = node["left"] if values[node["feature"]] <= node["threshold"] else node["right"]
            if child.startswith("L:"):
                leaf = int(child[2:])
                break
            node_id = child[2:]
        vote = tree_spec["weight"] * leaf
        score += vote
        votes.append({"tree": tree, "leaf": leaf, "vote": vote})
    return {"score": score, "prediction": "POS" if score > 0 else "NEG", "votes": votes}


def parse_audit_reference(text: str, model: dict) -> list[dict]:
    checks = []
    session = None
    point: dict[str, int] = {}
    locked: set[str] = set()
    budget = 0
    stack: list[tuple[dict[str, int], set[str], int]] = []
    for _, line in useful_lines(text)[1:]:
        fields = line.split("|")
        kind = fields[0]
        if kind == "SESSION":
            session = fields[1]
            point = {}
            locked = set()
            budget = 0
            stack = []
        elif kind == "POINT":
            point = {name: int(value) for name, value in (part.split("=") for part in fields[1].split(","))}
        elif kind == "PUSH":
            stack.append((dict(point), set(locked), budget))
        elif kind == "POP":
            point, locked, budget = stack.pop()
        elif kind == "SET":
            point[fields[1]] = int(fields[2])
        elif kind == "LOCK":
            locked.add(fields[1])
        elif kind == "UNLOCK":
            locked.discard(fields[1])
        elif kind == "BUDGET":
            budget = int(fields[1])
        elif kind == "CHECK":
            checks.append(
                {
                    "session": session,
                    "check": fields[1],
                    "budget": budget,
                    "point": dict(point),
                    "locked": set(locked),
                }
            )
        elif kind == "END":
            session = None
    return checks


def reference_report(model_text: str, audit_text: str) -> bytes:
    model = parse_model_reference(model_text)
    model_hash = fnv1a(canonical_model(model).encode())
    checks = []
    state_lines = [f"MODEL|{model_hash}\n"]
    feature_ids = sorted(model["features"])
    domains = [range(model["features"][feature]["min"], model["features"][feature]["max"] + 1) for feature in feature_ids]
    for state in parse_audit_reference(audit_text, model):
        base = evaluate_reference(model, state["point"])
        best = None
        for raw_values in itertools.product(*domains):
            values = dict(zip(feature_ids, raw_values, strict=True))
            if any(values[feature] != state["point"][feature] for feature in state["locked"]):
                continue
            cost = sum(
                model["features"][feature]["cost"] * abs(values[feature] - state["point"][feature])
                for feature in feature_ids
            )
            if cost > state["budget"]:
                continue
            evaluation = evaluate_reference(model, values)
            if evaluation["prediction"] == base["prediction"]:
                continue
            changed = sum(values[feature] != state["point"][feature] for feature in feature_ids)
            key = (cost, changed, tuple(values[feature] for feature in feature_ids))
            if best is None or key < best[0]:
                best = (key, values, evaluation)
        point_rows = [{"feature": feature, "value": state["point"][feature]} for feature in feature_ids]
        if best is None:
            result = {"kind": "certified"}
            kind = "certified"
        else:
            key, values, evaluation = best
            result = {
                "kind": "counterexample",
                "cost": key[0],
                "changed": key[1],
                "values": [{"feature": feature, "value": values[feature]} for feature in feature_ids],
                "prediction": evaluation["prediction"],
                "score": evaluation["score"],
                "votes": evaluation["votes"],
            }
            kind = "counterexample"
        check_row = {
            "session": state["session"],
            "check": state["check"],
            "budget": state["budget"],
            "point": point_rows,
            "locked": sorted(state["locked"]),
            "prediction": base["prediction"],
            "score": base["score"],
            "result": result,
        }
        checks.append(check_row)
        locked_csv = ",".join(sorted(state["locked"]))
        point_csv = ",".join(f"{feature}={state['point'][feature]}" for feature in feature_ids)
        state_lines.append(
            f"CHECK|{state['session']}|{state['check']}|{state['budget']}|"
            f"{base['prediction']}|{base['score']}|{locked_csv}|{point_csv}|{kind}\n"
        )
        if best is not None:
            key, values, evaluation = best
            values_csv = ",".join(f"{feature}={values[feature]}" for feature in feature_ids)
            votes_csv = ",".join(
                f"{vote['tree']}={vote['leaf']}:{vote['vote']}" for vote in evaluation["votes"]
            )
            state_lines.append(
                f"COUNTER|{key[0]}|{key[1]}|{evaluation['prediction']}|{evaluation['score']}|"
                f"{values_csv}|{votes_csv}\n"
            )
    report = {
        "schema": 1,
        "model_hash": model_hash,
        "checks": checks,
        "state_hash": fnv1a("".join(state_lines).encode()),
    }
    return json.dumps(report, separators=(",", ":")).encode() + b"\n"


def run_explicit(tmp_path: Path, model_text: str, audit_text: str, old: bytes | None = None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    model = tmp_path / "model.forest"
    audit = tmp_path / "audit.txt"
    output = tmp_path / "nested" / "report.json"
    model.write_text(model_text)
    audit.write_text(audit_text)
    if old is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(old)
    result = subprocess.run(
        [str(BINARY), str(model), str(audit), str(output)],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    return result, output


@pytest.fixture(scope="session", autouse=True)
def rebuild_binary() -> None:
    """Rebuild and install the native Rust command so stale executables cannot satisfy the verifier."""
    shutil.rmtree(APP / "target", ignore_errors=True)
    BINARY.unlink(missing_ok=True)
    result = subprocess.run(
        ["cargo", "build", "--release", "--locked", "--offline"],
        cwd=ENV,
        env={**os.environ, "CARGO_TARGET_DIR": str(APP / "target")},
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    built = APP / "target" / "release" / "forest-audit"
    BINARY.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(built, BINARY)
    BINARY.chmod(0o755)
    assert BINARY.read_bytes()[:4] == b"\x7fELF"


BASE_MODEL = """MODEL|1
BIAS|-1
FEATURE|A|0|3|2
FEATURE|B|-2|2|1
FEATURE|C|0|2|3
TREE|TA|3|N0
TREE|TB|2|N0
TREE|TC|4|N0
NODE|TA|N0|A|1|L:-1|N:N1
NODE|TA|N1|B|0|L:1|L:-1
NODE|TB|N0|B|-1|L:-1|L:1
NODE|TC|N0|C|0|L:-1|L:1
"""


def audit_for(point: str, budget: int = 5, extra: str = "", check: str = "C0") -> str:
    return f"AUDIT|1\nSESSION|S0\nPOINT|{point}\nBUDGET|{budget}\n{extra}CHECK|{check}\nEND\n"


def test_default_invocation_matches_reference() -> None:
    """The no-argument command must write the bundled certificate to the documented public path."""
    DEFAULT_OUTPUT.unlink(missing_ok=True)
    result = subprocess.run([str(BINARY)], text=True, capture_output=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert DEFAULT_OUTPUT.read_bytes() == reference_report(DEFAULT_MODEL.read_text(), DEFAULT_AUDIT.read_text())


def test_nested_scopes_restore_point_locks_and_budget(tmp_path: Path) -> None:
    """Nested POP operations must restore the complete saved audit state rather than only feature values."""
    audit = """AUDIT|1
SESSION|S0
POINT|A=1,B=0,C=0
BUDGET|6
CHECK|C0
PUSH
SET|C|1
LOCK|A
BUDGET|2
CHECK|C1
PUSH
SET|B|-1
UNLOCK|A
BUDGET|1
CHECK|C2
POP
CHECK|C3
POP
CHECK|C4
END
"""
    result, output = run_explicit(tmp_path, BASE_MODEL, audit)
    assert result.returncode == 0, result.stderr
    assert output.read_bytes() == reference_report(BASE_MODEL, audit)
    parsed = json.loads(output.read_text())
    assert parsed["checks"][1]["point"] == parsed["checks"][3]["point"]
    assert parsed["checks"][1]["locked"] == parsed["checks"][3]["locked"]
    assert parsed["checks"][0]["point"] == parsed["checks"][4]["point"]


def test_feature_locks_change_the_exact_counterexample(tmp_path: Path) -> None:
    """Locked coordinates must remain fixed even when changing one would yield a cheaper class flip."""
    unlocked = audit_for("A=1,B=0,C=0", 5)
    locked = audit_for("A=1,B=0,C=0", 5, "LOCK|C\n")
    r1, o1 = run_explicit(tmp_path / "u", BASE_MODEL, unlocked)
    r2, o2 = run_explicit(tmp_path / "l", BASE_MODEL, locked)
    assert r1.returncode == r2.returncode == 0
    assert o1.read_bytes() == reference_report(BASE_MODEL, unlocked)
    assert o2.read_bytes() == reference_report(BASE_MODEL, locked)
    assert json.loads(o1.read_text())["checks"][0]["result"] != json.loads(o2.read_text())["checks"][0]["result"]


def test_weighted_global_search_beats_feature_count_greedy(tmp_path: Path) -> None:
    """The selected witness must minimize weighted distance before minimizing the number of changed features."""
    model = """MODEL|1
BIAS|1
FEATURE|A|0|1|7
FEATURE|B|0|1|2
FEATURE|C|0|1|2
TREE|TA|4|N0
TREE|TB|2|N0
TREE|TC|2|N0
NODE|TA|N0|A|0|L:-1|L:1
NODE|TB|N0|B|0|L:-1|L:1
NODE|TC|N0|C|0|L:-1|L:1
"""
    audit = audit_for("A=0,B=0,C=0", 8)
    result, output = run_explicit(tmp_path, model, audit)
    assert result.returncode == 0, result.stderr
    assert output.read_bytes() == reference_report(model, audit)
    witness = json.loads(output.read_text())["checks"][0]["result"]
    assert witness["cost"] == 4
    assert witness["changed"] == 2


def test_changed_count_and_value_vector_break_equal_cost_ties(tmp_path: Path) -> None:
    """Equal-cost witnesses must prefer fewer changed features and then the lexicographically smaller value vector."""
    model = """MODEL|1
BIAS|-1
FEATURE|A|0|2|2
FEATURE|B|0|2|1
TREE|T0|2|N0
TREE|T1|2|N0
NODE|T0|N0|A|0|L:-1|L:1
NODE|T1|N0|B|0|L:-1|L:1
"""
    audit = audit_for("A=0,B=0", 4)
    result, output = run_explicit(tmp_path, model, audit)
    assert result.returncode == 0
    assert output.read_bytes() == reference_report(model, audit)


def test_zero_score_is_negative_and_thresholds_are_inclusive(tmp_path: Path) -> None:
    """A threshold equality must follow the left branch and a zero forest score must predict NEG."""
    model = """MODEL|1
BIAS|2
FEATURE|A|-1|1|1
TREE|T0|2|N0
NODE|T0|N0|A|0|L:-1|L:1
"""
    audit = audit_for("A=0", 1)
    result, output = run_explicit(tmp_path, model, audit)
    assert result.returncode == 0
    report = json.loads(output.read_text())
    assert report["checks"][0]["score"] == 0
    assert report["checks"][0]["prediction"] == "NEG"
    assert output.read_bytes() == reference_report(model, audit)


def test_model_record_order_does_not_change_report_bytes(tmp_path: Path) -> None:
    """Equivalent declaration orderings must produce the same canonical model hash and report bytes."""
    lines = BASE_MODEL.strip().splitlines()
    reordered = "\n".join([lines[0], lines[7], lines[2], lines[10], lines[1], lines[4], lines[6], lines[3], lines[9], lines[5], lines[8], lines[11]]) + "\n"
    audit = audit_for("A=1,B=0,C=0", 5)
    r1, o1 = run_explicit(tmp_path / "a", BASE_MODEL, audit)
    r2, o2 = run_explicit(tmp_path / "b", reordered, audit)
    assert r1.returncode == r2.returncode == 0
    assert o1.read_bytes() == o2.read_bytes()


@pytest.mark.parametrize(
    ("model", "token"),
    [
        ("MODEL|1\nBIAS|0\nFEATURE|bad|0|1|1\nFEATURE|A|00|1|1\n", "E_MODEL_IDENTIFIER:3"),
        ("MODEL|1\nBIAS|0\nFEATURE|A|0|1|1\nFEATURE|A|0|1|1\n", "E_MODEL_DUPLICATE:4"),
        ("MODEL|1\nBIAS|0\nFEATURE|A|2|1|1\n", "E_MODEL_RANGE:3"),
        ("MODEL|1\nBIAS|0\nFEATURE|A|0|1|1\nTREE|T0|1|N0\nNODE|T0|N0|B|0|L:-1|L:1\n", "E_MODEL_REFERENCE:5"),
    ],
    ids=["identifier-precedes-number", "duplicate", "range", "reference"],
)
def test_model_validation_categories_and_priority(tmp_path: Path, model: str, token: str) -> None:
    """Model validation must use the public category priority and physical line for its diagnostic."""
    audit = audit_for("A=0", 0)
    result, output = run_explicit(tmp_path, model, audit, b"old")
    assert result.returncode == 2
    assert result.stderr.strip() == f"forest-audit: {token}"
    assert output.read_bytes() == b"old"


@pytest.mark.parametrize(
    ("model", "token"),
    [
        (
            "MODEL|1\nBIAS|0\nFEATURE|A|0|1|1\nTREE|T0|1|N0\nNODE|T0|N0|A|0|N:N0|L:1\n",
            "E_MODEL_TREE:4",
        ),
        (
            "MODEL|1\nBIAS|0\nFEATURE|A|0|1|1\nTREE|T0|1|N0\nNODE|T0|N0|A|0|L:-1|L:1\nNODE|T0|N1|A|0|L:-1|L:1\n",
            "E_MODEL_TREE:6",
        ),
    ],
    ids=["cycle", "unreachable"],
)
def test_tree_topology_validation(tmp_path: Path, model: str, token: str) -> None:
    """Cycles and unreachable declared nodes must be rejected as tree-topology failures."""
    result, output = run_explicit(tmp_path, model, audit_for("A=0"), b"keep")
    assert result.returncode == 2
    assert result.stderr.strip() == f"forest-audit: {token}"
    assert output.read_bytes() == b"keep"


@pytest.mark.parametrize(
    ("audit", "token"),
    [
        ("AUDIT|1\nSESSION|S0\nPOINT|A=0,B=0,C=0\nPOP\nEND\n", "E_AUDIT_STATE:4"),
        ("AUDIT|1\nSESSION|S0\nPOINT|A=0,B=0,C=0\nPUSH\nEND\n", "E_AUDIT_STATE:5"),
        ("AUDIT|1\nSESSION|S0\nPOINT|A=0,B=0,C=0\nCHECK|C0\nCHECK|C0\nEND\n", "E_AUDIT_DUPLICATE:5"),
        ("AUDIT|1\nSESSION|S0\nPOINT|A=0,B=0,C=0\nSET|NOPE|0\nBUDGET|+1\nEND\n", "E_AUDIT_NUMBER:5"),
    ],
    ids=["pop-empty", "open-scope", "duplicate-check", "number-precedes-reference"],
)
def test_audit_state_and_validation_priority(tmp_path: Path, audit: str, token: str) -> None:
    """Audit diagnostics must cover scope errors, duplicate checks, and cross-category priority."""
    result, output = run_explicit(tmp_path, BASE_MODEL, audit, b"old")
    assert result.returncode == 2
    assert result.stderr.strip() == f"forest-audit: {token}"
    assert output.read_bytes() == b"old"


def test_budget_boundary_changes_certification(tmp_path: Path) -> None:
    """A witness whose cost equals the budget must be accepted while one unit less remains certified."""
    low = audit_for("A=1,B=0,C=0", 2)
    exact = audit_for("A=1,B=0,C=0", 3)
    r1, o1 = run_explicit(tmp_path / "low", BASE_MODEL, low)
    r2, o2 = run_explicit(tmp_path / "exact", BASE_MODEL, exact)
    assert r1.returncode == r2.returncode == 0
    assert json.loads(o1.read_text())["checks"][0]["result"]["kind"] == "certified"
    assert json.loads(o2.read_text())["checks"][0]["result"]["kind"] == "counterexample"


def generated_case(seed: int, features: int = 4, trees: int = 6) -> tuple[str, str]:
    model_lines = ["MODEL|1", f"BIAS|{(seed % 5) - 2}"]
    for index in range(features):
        model_lines.append(f"FEATURE|F{index}|-1|1|{1 + ((seed + index) % 3)}")
    for index in range(trees):
        feature = f"F{(seed * 3 + index) % features}"
        weight = 1 + ((seed + index * 2) % 5)
        model_lines.append(f"TREE|T{index}|{weight}|N0")
        model_lines.append(f"NODE|T{index}|N0|{feature}|0|L:-1|L:1")
    point = ",".join(f"F{index}={(seed + index) % 3 - 1}" for index in reversed(range(features)))
    audit = (
        "AUDIT|1\nSESSION|S0\n"
        f"POINT|{point}\nBUDGET|{3 + seed % 5}\nCHECK|C0\n"
        "PUSH\nLOCK|F0\nSET|F1|0\nCHECK|C1\nPOP\nCHECK|C2\nEND\n"
    )
    return "\n".join(model_lines) + "\n", audit


@pytest.mark.parametrize("seed", [3, 11, 29, 47])
def test_generated_forests_match_independent_reference(tmp_path: Path, seed: int) -> None:
    """Fresh generated forests and audit states must match the independent exhaustive certifier."""
    model, audit = generated_case(seed)
    result, output = run_explicit(tmp_path, model, audit)
    assert result.returncode == 0, result.stderr
    assert output.read_bytes() == reference_report(model, audit)


def test_larger_bounded_domain_remains_exact(tmp_path: Path) -> None:
    """An eight-feature domain with several checks must remain exact without relying on bundled fixtures."""
    model, audit = generated_case(19, features=8, trees=12)
    audit = audit.replace("CHECK|C2", "BUDGET|8\nCHECK|C2")
    result, output = run_explicit(tmp_path, model, audit)
    assert result.returncode == 0, result.stderr
    assert output.read_bytes() == reference_report(model, audit)


def test_usage_and_missing_inputs_preserve_existing_output(tmp_path: Path) -> None:
    """Usage and read failures must return their exact tokens without changing an existing destination."""
    output = tmp_path / "report.json"
    output.write_bytes(b"old")
    usage = subprocess.run([str(BINARY), "relative", "x", str(output)], text=True, capture_output=True, check=False)
    assert usage.returncode == 64
    assert usage.stderr.strip() == "forest-audit: E_USAGE"
    assert output.read_bytes() == b"old"
    missing = subprocess.run(
        [str(BINARY), str(tmp_path / "missing"), str(DEFAULT_AUDIT), str(output)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert missing.returncode == 3
    assert missing.stderr.strip() == "forest-audit: E_IO"
    assert output.read_bytes() == b"old"


def test_publication_creates_parents_sets_mode_and_replaces_symlink(tmp_path: Path) -> None:
    """Successful publication must create parents, set mode 0644, and replace rather than follow a destination symlink."""
    model = tmp_path / "model"
    audit = tmp_path / "audit"
    model.write_text(BASE_MODEL)
    audit_text = audit_for("A=1,B=0,C=0", 5)
    audit.write_text(audit_text)
    target = tmp_path / "target"
    target.write_bytes(b"do-not-touch")
    output = tmp_path / "one" / "two" / "report.json"
    output.parent.mkdir(parents=True)
    output.symlink_to(target)
    result = subprocess.run([str(BINARY), str(model), str(audit), str(output)], text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    assert target.read_bytes() == b"do-not-touch"
    assert output.is_file() and not output.is_symlink()
    assert stat.S_IMODE(output.stat().st_mode) == 0o644
    assert output.read_bytes() == reference_report(BASE_MODEL, audit_text)


def test_publication_failure_cleans_temporary_files(tmp_path: Path) -> None:
    """A failed rename must leave the destination object intact and remove same-directory temporary files."""
    model = tmp_path / "model"
    audit = tmp_path / "audit"
    model.write_text(BASE_MODEL)
    audit.write_text(audit_for("A=1,B=0,C=0", 5))
    output = tmp_path / "dest"
    output.mkdir()
    marker = output / "keep"
    marker.write_bytes(b"keep")
    before = sorted(path.name for path in tmp_path.iterdir())
    result = subprocess.run([str(BINARY), str(model), str(audit), str(output)], text=True, capture_output=True, check=False)
    assert result.returncode == 3
    assert result.stderr.strip() == "forest-audit: E_PUBLISH"
    assert marker.read_bytes() == b"keep"
    assert sorted(path.name for path in tmp_path.iterdir()) == before


def test_repeated_success_is_byte_identical_and_leaves_no_temp_files(tmp_path: Path) -> None:
    """Repeated successful runs must be byte-identical and leave no publication scratch files."""
    model, audit = generated_case(7)
    result, output = run_explicit(tmp_path, model, audit)
    assert result.returncode == 0
    first = output.read_bytes()
    second = subprocess.run(
        [str(BINARY), str(tmp_path / "model.forest"), str(tmp_path / "audit.txt"), str(output)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert second.returncode == 0, second.stderr
    assert output.read_bytes() == first
    assert {path.name for path in output.parent.iterdir()} == {output.name}
