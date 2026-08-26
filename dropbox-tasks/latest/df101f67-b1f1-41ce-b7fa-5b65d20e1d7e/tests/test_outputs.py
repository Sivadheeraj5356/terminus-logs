from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import model_for_tests


ROOT = Path("/")
APP = Path("/app")
PUBLIC_OUT = ROOT / "var/lib/harborlane/out"
PLAN_COLUMNS = model_for_tests.PLAN_COLUMNS


def _read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _build_binary(tmp_path: Path) -> Path:
    source = APP / "Main.hs"
    assert source.is_file(), "missing /app/Main.hs"
    text = source.read_text(encoding="utf-8")
    forbidden = ["System.Process", "System.Cmd", "createProcess", "callCommand", "readProcess", "system "]
    for token in forbidden:
        assert token not in text
    hardcoded_markers = [
        "seg-no-",
        "seg-ea-",
        "seg-so-",
        "seg-we-",
        "seg-de-",
        "seg-re-",
        "seg-qu-",
        "seg-lo-",
        "seg-ga-",
    ]
    for token in hardcoded_markers:
        assert token not in text, f"planner appears to hard-code public segment ids: {token}"
    out = tmp_path / "harborlane-planner"
    build_dir = tmp_path / "ghc"
    build_dir.mkdir()
    subprocess.run(
        ["ghc", "-O2", "-v0", "-outputdir", str(build_dir), "-o", str(out), str(source)],
        cwd=APP,
        check=True,
    )
    assert out.is_file()
    assert os.access(out, os.X_OK)
    return out


def _run_planner(binary: Path, root: Path, out_dir: Path) -> tuple[Path, Path]:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    subprocess.run(
        [str(binary), "--root", str(root), "--out-dir", str(out_dir)],
        cwd=APP,
        check=True,
    )
    return out_dir / "plan.tsv", out_dir / "Plan.hs"


def _read_plan(plan_path: Path) -> tuple[list[str] | None, list[dict[str, str]]]:
    assert plan_path.exists(), f"missing {plan_path}"
    with plan_path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return reader.fieldnames, list(reader)


def _read_haskell_payload(plan_hs: Path) -> tuple[list[tuple[str, str, str, str, str]], dict[str, str]]:
    assert plan_hs.exists(), f"missing {plan_hs}"
    harness = """
import Data.List (intercalate)
import Plan (affinityCounts, planDigest, planRows, priorityBands, streamTierCounts, thresholdBuckets, tierCounts)
import Text.Printf (printf)

render :: (String, Int, Double, Int, String) -> String
render (sid, enabled, threshold, priority, tier) =
  sid ++ "\\t" ++ show enabled ++ "\\t" ++ printf "%.2f" threshold ++ "\\t" ++ show priority ++ "\\t" ++ tier

renderTier :: (String, Int) -> String
renderTier (tier, count) = tier ++ ":" ++ show count

renderCell :: ((String, String), Int) -> String
renderCell ((tier, stream), count) = tier ++ ":" ++ stream ++ ":" ++ show count

renderBucket :: (String, Int) -> String
renderBucket (bucket, count) = bucket ++ ":" ++ show count

renderBand :: (Int, Int, Int, Int, Int, Int, Int, Int) -> String
renderBand (band, edge, bulk, defer, ingest, ledger, cache, repair) =
  show band ++ ":" ++ show edge ++ ":" ++ show bulk ++ ":" ++ show defer ++ ":" ++
  show ingest ++ ":" ++ show ledger ++ ":" ++ show cache ++ ":" ++ show repair

main :: IO ()
main = do
  mapM_ putStrLn (map render planRows)
  putStrLn ("DIGEST\\t" ++ planDigest)
  putStrLn ("TIERS\\t" ++ intercalate "," (map renderTier tierCounts))
  putStrLn ("CELLS\\t" ++ intercalate "," (map renderCell streamTierCounts))
  putStrLn ("BUCKETS\\t" ++ intercalate "," (map renderBucket thresholdBuckets))
  putStrLn ("AFFINITY\\t" ++ intercalate "," (map renderTier affinityCounts))
  putStrLn ("BANDS\\t" ++ intercalate "," (map renderBand priorityBands))
"""
    harness_path = plan_hs.parent / "ReadPlanRows.hs"
    harness_path.write_text(harness, encoding="utf-8")
    try:
        proc = subprocess.run(
            ["runghc", f"-i{plan_hs.parent}", str(harness_path)],
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        harness_path.unlink(missing_ok=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    rows: list[tuple[str, str, str, str, str]] = []
    meta: dict[str, str] = {}
    for line_no, line in enumerate(proc.stdout.splitlines(), 1):
        if line.startswith(("DIGEST\t", "TIERS\t", "CELLS\t", "BUCKETS\t", "AFFINITY\t", "BANDS\t")):
            key, value = line.split("\t", 1)
            meta[key] = value
            continue
        parts = line.split("\t")
        assert len(parts) == 5, f"bad Plan.hs row {line_no}: {line!r}"
        rows.append((parts[0], parts[1], parts[2], parts[3], parts[4]))
    return rows, meta


def _parse_summary(value: str, width: int) -> dict[Any, int]:
    out: dict[Any, int] = {}
    if not value:
        return out
    for chunk in value.split(","):
        parts = chunk.split(":")
        assert len(parts) == width, f"bad summary chunk: {chunk!r}"
        key: Any = tuple(parts[:-1]) if width > 2 else parts[0]
        out[key] = int(parts[-1])
    return out


def _parse_bands(value: str) -> dict[int, tuple[int, int, int, int, int, int, int]]:
    out: dict[int, tuple[int, int, int, int, int, int, int]] = {}
    if not value:
        return out
    for chunk in value.split(","):
        parts = chunk.split(":")
        assert len(parts) == 8, f"bad priority band chunk: {chunk!r}"
        band = int(parts[0])
        out[band] = tuple(int(part) for part in parts[1:])  # type: ignore[assignment]
    return out


def _assert_artifacts(root: Path, plan_path: Path, plan_hs: Path) -> dict[str, Any]:
    header, rows = _read_plan(plan_path)
    hs_rows, hs_meta = _read_haskell_payload(plan_hs)
    segments = _read_tsv(root / "var/lib/harborlane/data/segments.tsv")
    segment_map = {row["segment_id"]: row for row in segments}
    assert header == PLAN_COLUMNS
    assert [row["segment_id"] for row in rows] == [row["segment_id"] for row in segments]
    assert [row[0] for row in hs_rows] == [row["segment_id"] for row in segments]
    assert len(rows) == len(segments)
    for row, hs in zip(rows, hs_rows, strict=True):
        assert hs == (
            row["segment_id"],
            row["enabled"],
            row["threshold_param"],
            row["priority"],
            row["routing_tier"],
        )
        assert row["enabled"] in {"0", "1"}
        assert row["routing_tier"] in {"EDGE", "BULK", "DEFER", "OFF"}
        if row["enabled"] == "0":
            assert row["threshold_param"] == "0.00"
            assert row["priority"] == "0"
            assert row["routing_tier"] == "OFF"
        else:
            assert 0.50 <= float(row["threshold_param"]) <= 2.00

    active = [row for row in rows if row["enabled"] == "1"]
    active_by_priority = sorted(active, key=lambda row: int(row["priority"]))
    assert len(active) == model_for_tests.N_ACTIVE
    assert sorted(int(row["priority"]) for row in active) == list(range(1, model_for_tests.N_ACTIVE + 1))
    assert hs_meta["DIGEST"] == hashlib.sha256(plan_path.read_bytes()).hexdigest()
    assert _parse_summary(hs_meta["TIERS"], 2) == {
        tier: sum(1 for row in active if row["routing_tier"] == tier)
        for tier in model_for_tests.TIER_RANGES
    }
    assert _parse_summary(hs_meta["CELLS"], 3) == {
        (tier, stream): sum(
            1
            for row in active
            if row["routing_tier"] == tier
            and segment_map[row["segment_id"]]["stream_class"] == stream
        )
        for tier in model_for_tests.TIER_RANGES
        for stream in model_for_tests.STREAM_RANGES
    }
    assert _parse_summary(hs_meta["BUCKETS"], 2) == {
        bucket: sum(
            1
            for row in active
            if model_for_tests._threshold_bucket(float(row["threshold_param"])) == bucket
        )
        for bucket in model_for_tests.THRESHOLD_BUCKET_RANGES
    }
    assert _parse_summary(hs_meta["AFFINITY"], 2) == {
        tier: sum(
            1
            for row in active
            if row["routing_tier"] == tier
            and segment_map[row["segment_id"]]["affinity"] == tier
        )
        for tier in model_for_tests.TIER_RANGES
    }
    assert _parse_bands(hs_meta["BANDS"]) == {
        band_no: (
            sum(1 for row in band if row["routing_tier"] == "EDGE"),
            sum(1 for row in band if row["routing_tier"] == "BULK"),
            sum(1 for row in band if row["routing_tier"] == "DEFER"),
            sum(1 for row in band if segment_map[row["segment_id"]]["stream_class"] == "ingest"),
            sum(1 for row in band if segment_map[row["segment_id"]]["stream_class"] == "ledger"),
            sum(1 for row in band if segment_map[row["segment_id"]]["stream_class"] == "cache"),
            sum(1 for row in band if segment_map[row["segment_id"]]["stream_class"] == "repair"),
        )
        for band_no, band in enumerate(
            (
                active_by_priority[start : start + model_for_tests.PRIORITY_BAND_SIZE]
                for start in range(0, len(active_by_priority), model_for_tests.PRIORITY_BAND_SIZE)
            ),
            1,
        )
    }

    result = model_for_tests.evaluate(root, plan_path)
    assert result.get("hard_ok") is True, json.dumps(result, sort_keys=True)
    assert result.get("passes_gate") is True, json.dumps(result, sort_keys=True)
    for key, threshold in model_for_tests.GATES.items():
        assert result[key] >= threshold, f"{key}={result[key]:.6f} below {threshold:.6f}"
    return result


def _variant_root(tmp_path: Path, salt: int) -> Path:
    root = tmp_path / f"variant-{salt}"
    data = root / "var/lib/harborlane/data"
    leases_dir = root / "var/cache/harborlane/state"
    policy_dir = root / "etc/harborlane"
    scripts_dir = root / "opt/harborlane/scripts"
    data.mkdir(parents=True)
    leases_dir.mkdir(parents=True)
    policy_dir.mkdir(parents=True)
    scripts_dir.mkdir(parents=True)
    shutil.copy2(ROOT / "etc/harborlane/policy.tsv", policy_dir / "policy.tsv")
    shutil.copy2(ROOT / "opt/harborlane/scripts/model.py", scripts_dir / "model.py")

    original = _read_tsv(ROOT / "var/lib/harborlane/data/segments.tsv")
    rename: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(original):
        new_id = f"v{salt:02d}-{row['segment_id']}"
        rename[row["segment_id"]] = new_id
        value_shift = ((idx * 37 + salt * 19) % 11) - 5
        replay_shift = ((idx * 17 + salt * 13) % 9) - 4
        work_shift = ((idx * 23 + salt * 11) % 9) - 4
        drift_shift = ((idx * 29 + salt * 5) % 9) - 4
        risk_shift = (((idx * 31 + salt * 7) % 9) - 4) * 0.006
        threshold_shift = (((idx * 7 + salt * 3) % 7) - 3) * 0.006
        noise_shift = (((idx * 5 + salt * 17) % 5) - 2) * 0.001
        out = dict(row)
        out["segment_id"] = new_id
        out["value"] = str(max(35, int(row["value"]) + value_shift))
        out["replay"] = str(max(40, int(row["replay"]) + replay_shift))
        out["work"] = str(max(45, int(row["work"]) + work_shift))
        out["drift"] = str(max(30, int(row["drift"]) + drift_shift))
        out["risk"] = f"{min(0.990, max(0.120, float(row['risk']) + risk_shift)):.3f}"
        out["threshold"] = f"{min(0.540, max(0.290, float(row['threshold']) + threshold_shift)):.2f}"
        out["noise"] = f"{min(0.026, max(0.005, float(row['noise']) + noise_shift)):.3f}"
        rows.append(out)
    rows.sort(key=lambda row: hashlib.sha256(f"{salt}|{row['segment_id']}".encode()).hexdigest())
    _write_tsv(data / "segments.tsv", list(original[0]), rows)

    replay = []
    for row in _read_tsv(ROOT / "var/lib/harborlane/data/replay.tsv"):
        out = dict(row)
        out["segment_id"] = rename[row["segment_id"]]
        heat = min(1.0, max(0.0, float(row["heat"]) + (((salt + len(row["event_id"])) % 7) - 3) * 0.0015))
        pressure = min(1.0, max(0.0, float(row["pressure"]) + (((salt * 2 + len(row["segment_id"])) % 7) - 3) * 0.0015))
        out["heat"] = f"{heat:.3f}"
        out["pressure"] = f"{pressure:.3f}"
        replay.append(out)
    _write_tsv(data / "replay.tsv", list(replay[0]), replay)

    conflicts = []
    for row in _read_tsv(ROOT / "var/lib/harborlane/data/conflicts.tsv"):
        conflicts.append(
            {
                "left_segment": rename[row["left_segment"]],
                "right_segment": rename[row["right_segment"]],
            }
        )
    _write_tsv(data / "conflicts.tsv", ["left_segment", "right_segment"], conflicts)

    lease_rows = []
    for row in _read_tsv(ROOT / "var/cache/harborlane/state/leases.tsv"):
        out = dict(row)
        out["segment_id"] = rename[row["segment_id"]]
        lease_rows.append(out)
    _write_tsv(leases_dir / "leases.tsv", list(lease_rows[0]), lease_rows)
    _write_manifest(root)
    return root


def _write_manifest(root: Path) -> None:
    rels = [
        "/var/lib/harborlane/data/segments.tsv",
        "/var/lib/harborlane/data/conflicts.tsv",
        "/var/lib/harborlane/data/replay.tsv",
        "/var/cache/harborlane/state/leases.tsv",
        "/etc/harborlane/policy.tsv",
    ]
    lines = []
    for rel in rels:
        digest = hashlib.sha256((root / rel.lstrip("/")).read_bytes()).hexdigest()
        lines.append(f"{digest}  {rel}")
    manifest = root / "var/lib/harborlane/data/MANIFEST.sha256"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_public_root_is_solved_and_schema_is_canonical(tmp_path: Path) -> None:
    binary = _build_binary(tmp_path)
    plan_path, plan_hs = _run_planner(binary, ROOT, PUBLIC_OUT)
    _assert_artifacts(ROOT, plan_path, plan_hs)


def test_generated_compatibility_matrix(tmp_path: Path) -> None:
    binary = _build_binary(tmp_path)
    scores: list[float] = []
    plan_digests: set[str] = set()
    active_shapes: set[tuple[str, ...]] = set()
    salts = [1, 4, 7, 10, 13, 16]
    for salt in salts:
        root = _variant_root(tmp_path, salt)
        out_dir = tmp_path / f"out-{salt}"
        plan_path, plan_hs = _run_planner(binary, root, out_dir)
        result = _assert_artifacts(root, plan_path, plan_hs)
        scores.append(result["total_score"])
        rows = _read_plan(plan_path)[1]
        active = [row for row in rows if row["enabled"] == "1"]
        plan_digests.add(hashlib.sha256(plan_path.read_bytes()).hexdigest())
        active_shapes.add(tuple(sorted(row["segment_id"][4:] for row in active)))
        assert all(row["segment_id"].startswith(f"v{salt:02d}-") for row in rows)
    assert min(scores) >= model_for_tests.GATES["total_score"]
    assert len(plan_digests) == len(salts)
    assert len(active_shapes) >= 3


def test_visible_bait_generator_still_fails_gate(tmp_path: Path) -> None:
    bait = tmp_path / "bait-plan.tsv"
    subprocess.run(
        ["python", "/opt/harborlane/scripts/baseline.py", "--out", str(bait)],
        check=True,
    )
    result = model_for_tests.evaluate(ROOT, bait)
    assert result.get("hard_ok") is True, json.dumps(result, sort_keys=True)
    assert result.get("passes_gate") is False
    assert result["risk_score"] < model_for_tests.GATES["risk_score"]


def test_repeated_runs_are_stable_and_inputs_stay_intact(tmp_path: Path) -> None:
    binary = _build_binary(tmp_path)
    root = _variant_root(tmp_path, 4)
    ok, bad = model_for_tests.verify_manifest(root)
    assert ok, f"input manifest mismatch: {bad}"
    first_plan, first_hs = _run_planner(binary, root, tmp_path / "first")
    first = first_plan.read_bytes(), first_hs.read_bytes()
    second_plan, second_hs = _run_planner(binary, root, tmp_path / "second")
    second = second_plan.read_bytes(), second_hs.read_bytes()
    assert first == second
    ok, bad = model_for_tests.verify_manifest(root)
    assert ok, f"input manifest mismatch after planning: {bad}"
