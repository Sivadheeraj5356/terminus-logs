import json
import subprocess
from pathlib import Path

DATA = Path("/app/environment/data/cell_bin")
HEADER = "observation_id,peptide,retention_time,confidence"


def _call(tmp_path, root=DATA, holdout=None, coverage=None, check=True):
    tmp_path.mkdir(parents=True, exist_ok=True)
    out = tmp_path / DATA.name
    holdout_args = [] if holdout is None else ["--holdout", holdout]
    coverage_args = [] if coverage is None else ["--coverage", str(coverage)]
    proc = subprocess.run(
        [
            "/app/environment/tools/ra_run",
            "--emit-attestation",
            str(out),
            "--input-root",
            str(root),
            *holdout_args,
            *coverage_args,
        ],
        cwd="/app",
        capture_output=True,
        timeout=120,
    )
    if check:
        assert proc.returncode == 0, proc.stderr.decode()
        return json.loads(out.read_text()), out
    return proc, out


def _records(root=DATA):
    rows = []
    for path in root.rglob("*.cell"):
        lines = path.read_text().strip().splitlines()
        run = lines[1].split("=", 1)[1]
        rows.extend((run, line.split(",")) for line in lines[3:])
    return rows


def _write(root, groups):
    root.mkdir(parents=True, exist_ok=True)
    for name, run, rows in groups:
        body = ["CELL/3", f"run_id={run}", HEADER]
        body.extend(",".join(row) for row in rows)
        (root / name).write_text("\n".join(body) + "\n")


def _semantic(doc):
    return {key: value for key, value in doc.items() if key not in {"sources", "seal"}}


def _replay(doc, run):
    return next(item for item in doc["replays"] if item["holdout_run"] == run)


def _seal_digest(doc):
    body = json.loads(json.dumps(doc))
    body.pop("seal", None)
    encoded = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()
    proc = subprocess.run(
        ("sha256sum",),
        input=encoded,
        check=True,
        capture_output=True,
        timeout=30,
    )
    return proc.stdout.decode().split()[0]


def _ceil(value):
    whole = int(value)
    return whole if value == whole else whole + 1


def test_rt_a1_guard(tmp_path):
    """The public command emits typed JSON and rejects errors atomically."""
    subprocess.run(
        [
            "/app/environment/tools/ra_run",
            "--emit-attestation",
            "/app/output/attestation_pack.json",
        ],
        cwd="/app",
        check=True,
        timeout=120,
    )
    doc, out = _call(tmp_path / DATA.name)
    assert set(doc) == {
        "schema_version",
        "coverage_target",
        "sources",
        "observations",
        "runs",
        "model",
        "replays",
        "lineage",
        "seal",
    }
    assert doc["schema_version"] == "retention-attestation/3"
    original = out.read_bytes()
    bad = tmp_path / HEADER.split(",")[0]
    run, row = _records()[0]
    _write(bad, [("x.cell", run, [row])])
    unknown = DATA.name
    for extra in (
        ["--input-root", str(bad)],
        ["--input-root", str(DATA), "--coverage", "1"],
        ["--input-root", str(DATA), "--holdout", unknown],
        ["unknown"],
    ):
        proc = subprocess.run(
            ["/app/environment/tools/ra_run", "--emit-attestation", str(out), *extra],
            cwd="/app",
            capture_output=True,
            timeout=120,
        )
        assert proc.returncode != 0
        assert out.read_bytes() == original


def test_rt_b1_layout(tmp_path):
    """Permutation, renaming, and shard boundaries preserve semantic analysis."""
    baseline, _ = _call(tmp_path / "base")
    rows = list(reversed(_records()))
    groups = []
    for index, run in enumerate(sorted({run for run, _ in rows})):
        selected = [row for row_run, row in rows if row_run == run]
        midpoint = max(1, len(selected) // 2)
        groups.append((f"z{index}_right.cell", run, list(reversed(selected[midpoint:]))))
        groups.append((f"a{index}_left.cell", run, list(reversed(selected[:midpoint]))))
    changed_root = tmp_path / DATA.name
    _write(changed_root, groups)
    transformed, _ = _call(tmp_path / "changed", changed_root)
    assert _semantic(transformed) == _semantic(baseline)
    assert transformed["sources"] != baseline["sources"]


def test_rt_c1_keys(tmp_path):
    """Exact duplicate identities collapse while conflicting identities reject."""
    baseline, _ = _call(tmp_path / "base")
    root = tmp_path / DATA.name
    rows = _records()
    by_run = {}
    for run, row in rows:
        if run not in by_run:
            by_run[run] = []
        by_run[run].append(row)
    groups = [(f"{run}.cell", run, values) for run, values in by_run.items()]
    groups.append(("repeat.cell", rows[0][0], [rows[0][1]]))
    _write(root, groups)
    duplicate, out = _call(root, root)
    assert _semantic(duplicate) == _semantic(baseline)
    before = out.read_bytes()
    conflict = list(rows[0][1])
    conflict[2] = str(float(conflict[2]) + 1.0)
    _write(root, [("conflict.cell", rows[0][0], [conflict])])
    proc = subprocess.run(
        [
            "/app/environment/tools/ra_run",
            "--emit-attestation",
            str(out),
            "--input-root",
            str(root),
        ],
        cwd="/app",
        capture_output=True,
        timeout=120,
    )
    assert proc.returncode != 0
    assert out.read_bytes() == before


def test_rt_d1_affine(tmp_path):
    """Independent positive affine run transforms preserve model and replay semantics."""
    baseline, _ = _call(tmp_path / "base")
    groups = []
    for index, run in enumerate(sorted({item[0] for item in _records()})):
        scale = index + 2
        offset = 101 * (index + 1)
        rows = []
        for row_run, row in _records():
            if row_run == run:
                changed = list(row)
                changed[2] = str(scale * float(changed[2]) + offset)
                rows.append(changed)
        groups.append((f"{run}.cell", run, rows))
    root = tmp_path / "affine"
    _write(root, groups)
    transformed, _ = _call(root, root)
    assert _semantic(transformed) == _semantic(baseline)


def test_rt_e1_isolation(tmp_path):
    """Every default held-out record equals a separately generated held-out record."""
    default, _ = _call(tmp_path / "default")
    observations = default["observations"]
    views = {
        item["holdout_run"]: item for item in default["lineage"]["selected_views"]
    }
    for run in reversed([item["run_id"] for item in default["runs"]]):
        expected_ids = sorted(
            row["observation_id"] for row in observations if row["run_id"] != run
        )
        assert views[run]["observation_ids"] == expected_ids
        replay = _replay(default, run)
        assert run not in replay["training_runs"]
        for center in replay["model"]["centers"]:
            assert center["support"] == sum(
                row["peptide"] == center["peptide"]
                and row["run_id"] in replay["training_runs"]
                for row in observations
            )
        isolated, _ = _call(tmp_path / f"one-{run}", holdout=run)
        assert isolated["replays"] == [replay]
        assert isolated["model"] == isolated["replays"][0]["model"]


def test_rt_f1_sequence(tmp_path):
    """Generating held-out attestations in either order has no cross-call contamination."""
    default, _ = _call(tmp_path / "default")
    runs = [item["run_id"] for item in default["runs"]]
    forward = {}
    reverse = {}
    for run in runs:
        forward[run] = _call(tmp_path / run, holdout=run)[0]["replays"][0]
    for run in reversed(runs):
        reverse[run] = _call(tmp_path / run, holdout=run)[0]["replays"][0]
    assert forward == reverse


def test_rt_g1_locality(tmp_path):
    """A confidence-only perturbation changes only its observation provenance."""
    baseline, _ = _call(tmp_path / "base")
    root = tmp_path / "local"
    groups = []
    changed_id = "a01"
    for run in sorted({item[0] for item in _records()}):
        values = []
        for row_run, row in _records():
            if row_run == run:
                item = list(row)
                if item[0] == changed_id:
                    item[3] = "0.71"
                values.append(item)
        groups.append((f"{run}.cell", run, values))
    _write(root, groups)
    changed, _ = _call(tmp_path / "changed", root)
    before_rows = {row["observation_id"]: row for row in baseline["observations"]}
    after_rows = {row["observation_id"]: row for row in changed["observations"]}
    assert {key for key in before_rows if before_rows[key] != after_rows[key]} == {changed_id}
    for section in ("runs", "model", "replays", "lineage"):
        assert changed[section] == baseline[section]


def test_rt_h1_levels(tmp_path):
    """Coverage counts match residual rows and higher targets do not lower thresholds."""
    low, _ = _call(tmp_path / "low", coverage=0.55)
    high, _ = _call(tmp_path / "high", coverage=0.9)
    assert [item["holdout_run"] for item in low["replays"]] == [
        item["holdout_run"] for item in high["replays"]
    ]
    for left, right in zip(low["replays"], high["replays"]):
        for item, target in ((left, 0.55), (right, 0.9)):
            assert item["covered"] == sum(row["covered"] for row in item["residuals"])
            assert item["total"] == len(item["residuals"]) > 0
            assert all(
                row["covered"] == (row["residual"] <= item["threshold"])
                for row in item["residuals"]
            )
            training_count = sum(
                1 for row in low["observations"] if row["run_id"] in item["training_runs"]
            )
            expected_rank = min(
                training_count,
                max(1, _ceil((training_count + 1) * target)),
            )
            assert item["quantile_rank"] == expected_rank
        assert right["threshold"] >= left["threshold"]
        assert right["quantile_rank"] >= left["quantile_rank"]


def test_rt_i1_binding(tmp_path):
    """The closure digest covers every sorted semantic top-level section."""
    doc, _ = _call(tmp_path / "seal")
    assert doc["seal"] == {"algorithm": "sha256", "digest": _seal_digest(doc)}
    for section in (
        "schema_version",
        "coverage_target",
        "sources",
        "observations",
        "runs",
        "model",
        "replays",
        "lineage",
    ):
        changed = json.loads(json.dumps(doc))
        if isinstance(changed[section], list):
            changed[section] = list(reversed(changed[section])) + [
                json.loads(json.dumps(changed[section][0]))
            ]
        elif isinstance(changed[section], dict):
            nested_key = next(
                key for key, value in changed[section].items() if isinstance(value, list)
            )
            changed[section][nested_key].append(
                json.loads(json.dumps(changed[section][nested_key][0]))
            )
        elif isinstance(changed[section], str):
            changed[section] += doc["schema_version"]
        else:
            changed[section] += 0.001
        assert _seal_digest(changed) != doc["seal"]["digest"]


def test_rt_j1_cycle(tmp_path):
    """Regenerating A after a distinct valid B reproduces A byte for byte."""
    root_b = tmp_path / HEADER.split(",")[1]
    groups = []
    for run in sorted({item[0] for item in _records()}):
        rows = [list(row) for row_run, row in _records() if row_run == run]
        for row in rows:
            row[2] = str(float(row[2]) * 3 + 7)
        groups.append((f"{run}.cell", run, rows))
    _write(root_b, groups)
    output_dir = tmp_path / DATA.name
    first, out = _call(output_dir)
    bytes_a = out.read_bytes()
    second, _ = _call(output_dir, root_b)
    assert second != first
    third, _ = _call(output_dir)
    assert third == first
    assert out.read_bytes() == bytes_a


def test_rt_k1_extension(tmp_path):
    """Adding a run adds one replay and extends every prior training membership."""
    baseline, _ = _call(tmp_path / "base")
    root = tmp_path / DATA.name
    groups = []
    for run in sorted({item[0] for item in _records()}):
        groups.append((f"{run}.cell", run, [row for row_run, row in _records() if row_run == run]))
    new_run = "".join(sorted({item[0] for item in _records()}))
    peptides = sorted({item[1][1] for item in _records()})
    new_rows = [
        [f"{new_run}{index}", peptide, str((index + 1) * 4), "0.9"]
        for index, peptide in enumerate(peptides)
    ]
    groups.append((f"{new_run}.cell", new_run, new_rows))
    _write(root, groups)
    extended, _ = _call(tmp_path / new_run, root)
    old_runs = {item["run_id"] for item in baseline["runs"]}
    assert {item["holdout_run"] for item in extended["replays"]} == old_runs | {new_run}
    for run in old_runs:
        assert new_run in _replay(extended, run)["training_runs"]
    assert set(_replay(extended, new_run)["training_runs"]) == old_runs
