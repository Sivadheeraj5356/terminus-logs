"""Domain checks for the desk rollout fairness scorecard export."""

import hashlib
import json
import subprocess
from pathlib import Path

APP = Path("/app")
ENV = APP / "environment"
OUT = APP / "output"
SCORE = OUT / "blk_k9.json"
TRACE = OUT / "trace_w8.jsonl"
CATALOG = ENV / "fixtures" / "k9" / "w8_catalog.json"
TOMB = ENV / "fixtures" / "k9" / "a8_tomb.jsonl"
PAIRS = ENV / "fixtures" / "k9" / "pair_w3.json"
SCHEMA = ENV / "schemas" / "blk_k9.schema.json"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_catalog() -> dict:
    return _load_json(CATALOG)


def _load_tomb_ids() -> list[str]:
    lines = TOMB.read_text(encoding="utf-8").strip().split("\n")
    return [json.loads(line)["block_id"] for line in lines if line.strip()]


def _load_pairs() -> list[dict]:
    return _load_json(PAIRS)["pairs"]


def _ratio_label(ratio: float) -> str:
    return f"{ratio:.4f}"


def _ref_op_a(rows: list[dict], floor: int) -> dict:
    eligible = [row for row in rows if row["total"] >= floor]
    hits = sum(row["hits"] for row in eligible)
    total = sum(row["total"] for row in eligible)
    ratio = hits / total if total else 0.0
    under = sum(1 for row in rows if row["total"] < floor)
    return {"eligible": eligible, "ratio": ratio, "under_tally": under}


def _ref_reconcile(left: dict, right: dict, anchor: dict) -> dict:
    if anchor["left_rank"] < anchor["right_rank"]:
        return left
    if anchor["right_rank"] < anchor["left_rank"]:
        return right
    return left if left["weight"] >= right["weight"] else right


def _ref_step_b(fresh: list[dict], tomb_ids: list[str], prior: list[dict]) -> list[dict]:
    tomb = set(tomb_ids)
    seen: set[str] = set()
    out: list[dict] = []
    for block in fresh:
        if block["block_id"] in tomb or block["block_id"] in seen:
            continue
        seen.add(block["block_id"])
        out.append(block)
    for block in prior:
        if block["block_id"] in tomb or block["block_id"] in seen:
            continue
        seen.add(block["block_id"])
        out.append(block)
    return out


def _block_hash(block_id: str, lane: str, ratio: str) -> str:
    return _sha256_hex(f"block|{block_id}|{lane}|{ratio}".encode())


def _cover_digest(coverage: list[dict]) -> str:
    lines = sorted(f"{row['lane']}:{row['ratio']}" for row in coverage if row["eligible"])
    return _sha256_hex("\n".join(lines).encode())


def _merge_digest(winners: list[str]) -> str:
    return _sha256_hex("\n".join(winners).encode())


def _block_digest(blocks: list[dict]) -> str:
    lines = sorted(f"{b['block_id']}:{b['block_hash']}" for b in blocks)
    return _sha256_hex("\n".join(lines).encode())


def _parity_fp(cover_hex: str, merge_hex: str, block_hex: str) -> str:
    out = subprocess.check_output(
        [
            "python3",
            str(ENV / "hold" / "ref_hold.py"),
            "parity_fp",
            cover_hex,
            merge_hex,
            block_hex,
        ],
        text=True,
    )
    return out.strip()


def _ref_scorecard() -> tuple[dict, list[dict]]:
    catalog = _load_catalog()
    floor = int(catalog["floor_min"])
    ratio_min = float(catalog["ratio_min"])
    under_total = 0
    final_coverage: list[dict] = []
    trace: list[dict] = []

    for rot in catalog["rotations"]:
        if rot["staging"]:
            continue
        slice_ref = _ref_op_a(rot["rows"], floor)
        if slice_ref["ratio"] < ratio_min:
            under_total += 1
        final_coverage = []
        for row in rot["rows"]:
            eligible = row["total"] >= floor
            row_ratio = row["hits"] / row["total"] if eligible and row["total"] else 0.0
            final_coverage.append(
                {
                    "lane": row["lane"],
                    "ratio": _ratio_label(row_ratio),
                    "eligible": eligible,
                }
            )
        for row in final_coverage:
            trace.append({"event": "cover", "lane": row["lane"], "detail": row["ratio"]})

    fresh_blocks = []
    for idx, row in enumerate([r for r in final_coverage if r["eligible"]], start=1):
        block_id = f"blk_new_{idx}"
        fresh_blocks.append(
            {
                "block_id": block_id,
                "block_hash": _block_hash(block_id, row["lane"], row["ratio"]),
                "lane": row["lane"],
            }
        )

    prior = [
        {"block_id": "blk_a1", "block_hash": _block_hash("blk_a1", "L1", _ratio_label(0.5)), "lane": "L1"},
        {"block_id": "blk_a2", "block_hash": _block_hash("blk_a2", "L2", _ratio_label(0.5)), "lane": "L2"},
    ]
    blocks = _ref_step_b(fresh_blocks, _load_tomb_ids(), prior)

    for tomb_id in _load_tomb_ids():
        trace.append({"event": "reopen", "lane": "", "detail": f"invalidate|{tomb_id}"})

    winners = [_ref_reconcile(p["left"], p["right"], p["anchor"])["token"] for p in _load_pairs()]
    cover_hex = _cover_digest(final_coverage)
    merge_hex = _merge_digest(winners)
    block_hex = _block_digest(blocks)

    scorecard = {
        "schema_version": "1.0",
        "catalog_label": catalog["catalog_label"],
        "cover_digest": cover_hex,
        "merge_digest": merge_hex,
        "block_digest": block_hex,
        "parity_fp": _parity_fp(cover_hex, merge_hex, block_hex),
        "under_tally": under_total,
        "blocks": blocks,
        "coverage": final_coverage,
    }
    return scorecard, trace


def _run_k9() -> tuple[dict, list[dict]]:
    subprocess.check_call(["/app/environment/tools/k9ctl", "score"], cwd="/app")
    scorecard = _load_json(SCORE)
    trace = [json.loads(line) for line in TRACE.read_text(encoding="utf-8").splitlines() if line.strip()]
    return scorecard, trace


def _assert_schema(scorecard: dict) -> None:
    schema = _load_json(SCHEMA)
    required = set(schema["required"])
    assert required.issubset(scorecard.keys())
    assert scorecard["schema_version"] == "1.0"
    for field in ("cover_digest", "merge_digest", "block_digest", "parity_fp"):
        val = scorecard[field]
        assert isinstance(val, str) and len(val) == 64 and val == val.lower()


def test_f9_r1_k4_w3():
    """Rotation catalog replay exposes undercoverage after correct floor ordering."""
    ref, _trace = _ref_scorecard()
    got, _ = _run_k9()
    assert got["under_tally"] == ref["under_tally"] == 0


def test_f9_r2_m7_q1():
    """Held-out rotation parity digests match pin_norm."""
    ref, _trace = _ref_scorecard()
    got, _ = _run_k9()
    assert got["cover_digest"] == ref["cover_digest"]
    assert got["merge_digest"] == ref["merge_digest"]
    assert got["parity_fp"] == ref["parity_fp"]


def test_f9_r3_p2_z8():
    """Prior ruling tomb entries invalidate stale blocks before rescoring."""
    ref, _trace = _ref_scorecard()
    got, _ = _run_k9()
    tomb = set(_load_tomb_ids())
    for block in got["blocks"]:
        assert block["block_id"] not in tomb
    assert got["block_digest"] == ref["block_digest"]


def test_f9_m1_cover_q6():
    """Coverage tallies respect min-sample floor before ratio."""
    ref, _trace = _ref_scorecard()
    got, _ = _run_k9()
    catalog = _load_catalog()
    floor = int(catalog["floor_min"])
    for row in got["coverage"]:
        if row["eligible"]:
            assert float(row["ratio"]) >= 0.0
        ref_row = next(r for r in ref["coverage"] if r["lane"] == row["lane"])
        assert row == ref_row
    final_rot = [r for r in catalog["rotations"] if not r["staging"]][-1]
    expected_ineligible = [row["lane"] for row in final_rot["rows"] if row["total"] < floor]
    for lane in expected_ineligible:
        assert any(r["lane"] == lane and not r["eligible"] for r in got["coverage"])


def test_f9_m2_trace_w8():
    """Trace rows document invalidation events per pin_norm."""
    ref, ref_trace = _ref_scorecard()
    got, got_trace = _run_k9()
    reopen_got = [e for e in got_trace if e["event"] == "reopen"]
    reopen_ref = [e for e in ref_trace if e["event"] == "reopen"]
    assert reopen_got == reopen_ref
    cover_got = sorted(e["lane"] for e in got_trace if e["event"] == "cover")
    cover_ref = sorted(e["lane"] for e in ref_trace if e["event"] == "cover")
    assert cover_got == cover_ref


def test_f9_m3_merge_z3():
    """Contested pairs merge by audit-anchor precedence."""
    ref, _trace = _ref_scorecard()
    got, _ = _run_k9()
    assert got["merge_digest"] == ref["merge_digest"]


def test_f9_p1_stable_r5():
    """Sequential k9ctl score reruns keep trace fingerprints stable."""
    got1, trace1 = _run_k9()
    got2, trace2 = _run_k9()
    assert got1["block_digest"] == got2["block_digest"]
    assert got1["parity_fp"] == got2["parity_fp"]
    assert trace1 == trace2


def test_f9_p2_parity_t1():
    """Metamorphic parity across rotations in w8_catalog.json."""
    ref, _trace = _ref_scorecard()
    got, _ = _run_k9()
    catalog = _load_catalog()
    non_staging = [r for r in catalog["rotations"] if not r["staging"]]
    assert len(non_staging) >= 2
    assert got["catalog_label"] == catalog["catalog_label"]
    assert got["under_tally"] == 0
    assert got["cover_digest"] == ref["cover_digest"]
    _assert_schema(got)
