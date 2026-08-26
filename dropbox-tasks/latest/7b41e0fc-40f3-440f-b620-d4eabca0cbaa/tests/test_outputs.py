"""Verifier for btrfs-send-fork v3 — matrix pass, cache, journal, sidecar blob."""

import json
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

APP = Path("/app")

ENV = APP / "environment"
REPORT = APP / "output" / "bw_emit.json"
WITNESS = APP / "output" / "stream_sidecar.bin"
LANES = APP / "data" / "lanes"
RELOAD = APP / "data" / "reload"
VAR = APP / "var"
CACHE = VAR / "lane_cache"
JOURNAL = VAR / "journal_tail.json"
CHECKPOINT = VAR / "checkpoint.json"
WRAP = VAR / "wrap.gen"
LANE_IDS = ENV / "docs" / "lane_ids.txt"

BOOTSTRAP_JOURNAL = {"journal_seq": 7, "receiver_tail": ""}
BOOTSTRAP_CHECKPOINT = {"lanes_witnessed": 0, "last_lane_id": ""}
BOOTSTRAP_WRAP = "1"

FNV_OFFSET = 2166136261
FNV_PRIME = 16777619


def _fnv1a32(text: str) -> int:
    h = FNV_OFFSET
    for b in text.encode():
        h ^= b
        h = (h * FNV_PRIME) & 0xFFFFFFFF
    return h


def _fnv_hex(text: str) -> str:
    return f"{_fnv1a32(text):08x}"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _load_lanes() -> list[dict]:
    return [_load_json(p) for p in sorted(LANES.glob("*.json"))]


def _load_reload() -> list[dict]:
    return [_load_json(p) for p in sorted(RELOAD.glob("*.json"))]


def _build_graph(edges: list[list[str]]) -> dict[str, str]:
    return {a: b for a, b in edges}


def _apply_a1(journal: dict, lane: dict) -> str:
    chunk = lane["receiver_chain"][-1]
    interrupted = lane["interrupted"]
    retry = lane["retry_overwrite"]
    idx = max(len(lane["receiver_chain"]) - 2, 0)
    interrupted_anchor = lane["receiver_chain"][idx]
    if interrupted:
        journal["receiver_tail"] = interrupted_anchor
    elif retry:
        journal["receiver_tail"] = chunk
    else:
        journal["receiver_tail"] = chunk
    return journal["receiver_tail"]


def _apply_g3(lane: dict) -> str:
    graph = _build_graph(lane["metadata_edges"])
    source_tail = lane["source_chain"][-1]
    candidates = lane["candidate_parents"]
    expect = graph.get(source_tail)
    if expect and expect in candidates:
        return expect
    return candidates[0] if candidates else ""


def _row_for_lane(lane: dict, journal: dict, cache: dict[tuple[str, int], dict]) -> dict:
    key = (lane["lane_id"], lane["wrap_epoch"])
    if key in cache:
        return cache[key]
    source_tail = lane["source_chain"][-1]
    receiver_tail = _apply_a1(journal, lane)
    parent_pick = _apply_g3(lane)
    stamp = _fnv_hex(f"{source_tail}|{receiver_tail}|{parent_pick}")
    if source_tail == receiver_tail == parent_pick:
        band = 0
    else:
        band = (int(stamp[:4], 16) % 900) + 100
    aligned = source_tail == receiver_tail == parent_pick
    imp = bool(lane["content_match"])
    replay = imp and aligned
    sync = "steady" if band == 0 and replay else "drift"
    tag = _fnv1a32(lane["lane_id"])
    tag ^= lane["wrap_epoch"]
    tag = (tag * FNV_PRIME) & 0xFFFFFFFF
    for link in lane["source_chain"]:
        tag ^= _fnv1a32(link)
        tag = (tag * FNV_PRIME) & 0xFFFFFFFF
    tag ^= 0xA5A55A5A if lane["interrupted"] else 0x5A5AA5A5
    tag ^= 0x0F0FF0F0 if lane["retry_overwrite"] else 0xF0F00F0F
    row = {
        "lane_id": lane["lane_id"],
        "chain_stamp": stamp,
        "parent_pick": parent_pick,
        "rc_band": band,
        "sync_label": sync,
        "stream_tag": tag & 0xFFFFFFFF,
    }
    cache[key] = row
    return row


def _bw_seed_var() -> None:
    VAR.mkdir(parents=True, exist_ok=True)
    JOURNAL.write_text(json.dumps(BOOTSTRAP_JOURNAL) + "\n")
    CHECKPOINT.write_text(json.dumps(BOOTSTRAP_CHECKPOINT) + "\n")
    WRAP.write_text(BOOTSTRAP_WRAP + "\n")
    if CACHE.exists():
        shutil.rmtree(CACHE)
    CACHE.mkdir(parents=True, exist_ok=True)


def _bw_contract_matrix() -> dict:
    journal = dict(BOOTSTRAP_JOURNAL)
    wrap_epoch = int(BOOTSTRAP_WRAP)
    cache: dict[tuple[str, int], dict] = {}
    rows_by_id: dict[str, dict] = {}
    lanes = _load_lanes()
    for lane in lanes:
        wrap_epoch = max(wrap_epoch, lane["wrap_epoch"])
        row = _row_for_lane(lane, journal, cache)
        rows_by_id[lane["lane_id"]] = row
    for seed in _load_reload():
        base = next(lane for lane in lanes if lane["lane_id"] == seed["lane_id"])
        merged = json.loads(json.dumps(base))
        for k, v in seed.items():
            if k != "lane_id":
                merged[k] = v
        wrap_epoch = max(wrap_epoch, merged["wrap_epoch"])
        row = _row_for_lane(merged, journal, cache)
        rows_by_id[merged["lane_id"]] = row
    rows = sorted(rows_by_id.values(), key=lambda r: r["lane_id"])
    stamps = [r["chain_stamp"] for r in rows]
    bands = [r["rc_band"] for r in rows]
    journal["journal_seq"] = journal["journal_seq"] + len(rows)
    fold = (journal["journal_seq"] ^ wrap_epoch) & 0xFFFFFFFF
    for stamp in stamps:
        fold = (fold + int(stamp, 16)) & 0xFFFFFFFF
        fold = ((fold << 5) | (fold >> 27)) & 0xFFFFFFFF
    summary_sync = "steady" if all(r["sync_label"] == "steady" for r in rows) else "drift"
    return {
        "rows": rows,
        "summary": {
            "rows_total": len(rows),
            "span_band": max(bands) - min(bands) if bands else 0,
            "lineage_digest": f"{fold:08x}",
            "sync_label": summary_sync,
            "journal_seq": journal["journal_seq"],
            "wrap_epoch": wrap_epoch,
        },
    }


def _bw_fold_hex(stamps: list[str], journal_seq: int, wrap_epoch: int) -> str:
    fold = (journal_seq ^ wrap_epoch) & 0xFFFFFFFF
    for stamp in stamps:
        fold = (fold + int(stamp, 16)) & 0xFFFFFFFF
        fold = ((fold << 5) | (fold >> 27)) & 0xFFFFFFFF
    return f"{fold:08x}"


def _le32(value: int) -> bytes:
    value &= 0xFFFFFFFF
    return bytes((value >> (8 * i)) & 0xFF for i in range(4))


def _bw_pack_sidecar(rows: list[dict]) -> bytes:
    out = bytearray(b"SWTB")
    out.extend(_le32(len(rows)))
    for row in rows:
        out.extend(row["lane_id"].encode() + b"\x00")
        out.extend(_le32(row["stream_tag"]))
        out.extend(_le32(row["rc_band"]))
        out.extend(_le32(int(row["chain_stamp"], 16)))
    return bytes(out)


def _bw_rebuild_cli() -> None:
    subprocess.run(
        ["cargo", "build", "--release", "--locked"],
        cwd="/app/environment",
        check=True,
        capture_output=True,
        text=True,
    )
    shutil.copy2(APP / "target" / "release" / "m6_ctl", APP / "bin" / "m6_ctl")


def _bw_exec_matrix() -> dict:
    for path in (REPORT, WITNESS):
        if path.exists():
            path.unlink()
    _bw_seed_var()
    subprocess.run([str(APP / "bin" / "m6_ctl"), "matrix-all"], check=True)
    return _load_json(REPORT)


@contextmanager
def _bw_reset_var() -> Iterator[None]:
    backup = APP / "var" / ".bootstrap_backup"
    _bw_seed_var()
    if backup.exists():
        shutil.rmtree(backup)
    shutil.copytree(VAR, backup)
    try:
        yield
    finally:
        if CACHE.exists():
            shutil.rmtree(CACHE)
        for item in VAR.iterdir():
            if item.is_file():
                item.unlink()
        for item in backup.iterdir():
            if item.is_file():
                shutil.copy2(item, VAR / item.name)


def _bw_lane_ids() -> list[str]:
    return [
        line.strip()
        for line in LANE_IDS.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def test_bw_s01_lane_bundle():
    """Matrix report includes exactly the bundled lane ids."""
    report = _bw_exec_matrix()
    ids = {row["lane_id"] for row in report["rows"]}
    assert ids == set(_bw_lane_ids())
    assert len(report["rows"]) == len(_bw_lane_ids())


def test_bw_s02_row_formulas():
    """Each row matches formulas in fc0_contract.md."""
    report = _bw_exec_matrix()
    expected = _bw_contract_matrix()
    assert report["rows"] == expected["rows"]


def test_bw_s03_summary_fold():
    """Summary fold, journal increment, and wrap epoch match contract."""
    report = _bw_exec_matrix()
    expected = _bw_contract_matrix()
    assert report["summary"] == expected["summary"]


def test_bw_s04_digest_order():
    """Digest fold walks rows in ascending lane_id order, not reverse or pass order."""
    report = _bw_exec_matrix()
    rows = report["rows"]
    stamps = [row["chain_stamp"] for row in rows]
    assert rows == sorted(rows, key=lambda r: r["lane_id"])
    expected_digest = _bw_fold_hex(
        stamps,
        report["summary"]["journal_seq"],
        report["summary"]["wrap_epoch"],
    )
    assert report["summary"]["lineage_digest"] == expected_digest
    reverse_stamps = list(reversed(stamps))
    if len(stamps) > 1 and reverse_stamps != stamps:
        assert report["summary"]["lineage_digest"] != _bw_fold_hex(
            reverse_stamps,
            report["summary"]["journal_seq"],
            report["summary"]["wrap_epoch"],
        )


def test_bw_s05_bootstrap_repeat():
    """Two matrix-all runs from the same bootstrap var state produce identical witnesses."""
    with _bw_reset_var():
        first = _bw_exec_matrix()
    with _bw_reset_var():
        second = _bw_exec_matrix()
    assert first == second


def test_bw_s06_sidecar_blob():
    """stream_sidecar.bin encodes the sorted row set from the report."""
    report = _bw_exec_matrix()
    blob = WITNESS.read_bytes()
    assert blob[:4] == b"SWTB"
    assert blob == _bw_pack_sidecar(report["rows"])


def test_bw_s07_reload_overlay():
    """Reload overlays applied after base passes replace rows at higher wrap_epoch."""
    report = _bw_exec_matrix()
    expected = _bw_contract_matrix()
    alpha = next(r for r in report["rows"] if r["lane_id"] == "lane_alpha")
    exp_alpha = next(r for r in expected["rows"] if r["lane_id"] == "lane_alpha")
    assert alpha == exp_alpha
    assert report["summary"]["wrap_epoch"] >= 2


def test_bw_s08_memo_epoch_miss():
    """Stale lane-id sidecars must not satisfy reload rows at a higher wrap_epoch."""
    _bw_rebuild_cli()
    _bw_seed_var()
    expected = _bw_contract_matrix()
    seed = next(s for s in _load_reload() if "wrap_epoch" in s)
    lane_id = seed["lane_id"]
    exp_row = next(r for r in expected["rows"] if r["lane_id"] == lane_id)
    stale = dict(exp_row)
    stale["chain_stamp"] = "00000000"
    stale["parent_pick"] = exp_row["parent_pick"][::-1]
    stale["rc_band"] = 777
    stale["sync_label"] = "drift"
    stale["stream_tag"] = 0
    (CACHE / f"{lane_id}.json").write_text(json.dumps(stale) + "\n")
    for path in (REPORT, WITNESS):
        if path.exists():
            path.unlink()
    subprocess.run([str(APP / "bin" / "m6_ctl"), "matrix-all"], check=True)
    report = _load_json(REPORT)
    row = next(r for r in report["rows"] if r["lane_id"] == lane_id)
    assert row == exp_row


def test_bw_s09_dual_flag_anchor():
    """Lanes with both interruption and retry flags follow contract anchor ordering."""
    report = _bw_exec_matrix()
    expected = _bw_contract_matrix()
    dual_flag_lanes = {
        lane["lane_id"]
        for lane in _load_lanes()
        if lane["interrupted"] and lane["retry_overwrite"]
    }
    assert dual_flag_lanes
    for lane_id in dual_flag_lanes:
        row = next(r for r in report["rows"] if r["lane_id"] == lane_id)
        exp_row = next(r for r in expected["rows"] if r["lane_id"] == lane_id)
        assert row == exp_row


def test_bw_s10_drift_band():
    """Rows marked drift with forked ancestry must expose nonzero rc_band."""
    report = _bw_exec_matrix()
    expected = _bw_contract_matrix()
    for row, exp in zip(report["rows"], expected["rows"]):
        if exp["sync_label"] == "drift" and exp["rc_band"] > 0:
            assert row["sync_label"] == "drift"
            assert row["rc_band"] > 0


def test_bw_s11_journal_seq():
    """Journal sequence matches summary after matrix-all."""
    with _bw_reset_var():
        before = _load_json(JOURNAL)
        report = _bw_exec_matrix()
        after = _load_json(JOURNAL)
        assert after["journal_seq"] == report["summary"]["journal_seq"]
        assert after["journal_seq"] > before["journal_seq"]


def test_bw_s12_checkpoint_tail():
    """Checkpoint lanes_witnessed tracks emitted row count."""
    with _bw_reset_var():
        _bw_exec_matrix()
        ckpt = _load_json(CHECKPOINT)
        report = _load_json(REPORT)
        assert ckpt["lanes_witnessed"] == report["summary"]["rows_total"]
        sorted_rows = sorted(report["rows"], key=lambda row: row["lane_id"])
        trailing = sorted_rows[len(sorted_rows) - 1]
        assert ckpt["last_lane_id"] == trailing["lane_id"]


def test_bw_s13_rebuild_stable():
    """Verifier rebuild path must produce the same digest as a clean matrix run."""
    _bw_rebuild_cli()
    first = _bw_exec_matrix()
    _bw_rebuild_cli()
    second = _bw_exec_matrix()
    assert first["summary"]["lineage_digest"] == second["summary"]["lineage_digest"]
    assert first == second
