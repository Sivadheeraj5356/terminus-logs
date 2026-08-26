"""Behavioral verifier for ingress holdback replay."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import uuid
from pathlib import Path

APP_TASK = Path("/app/task_file")
BIN = Path("/app/bin/replay_tool")
OUT = Path("/app/output")
EXPECTED_SUMMARY = {
    "applied_events": 13,
    "duplicate_events": 1,
    "rejected_events": 7,
    "buffers_total": 3,
    "total_filled": 33,
    "total_holdback": 0,
    "total_dispatched": 24,
}


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    cmd = [str(BIN), str(APP_TASK)] if not args else [str(BIN), *args]
    return subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=300)


def _quiet(cp: subprocess.CompletedProcess[str]) -> None:
    assert cp.stdout == ""
    assert cp.stderr == ""


def _run_ok() -> None:
    cp = _run()
    _quiet(cp)
    assert cp.returncode == 0


def _json() -> dict:
    return json.loads((OUT / "result.json").read_text(encoding="utf-8"))


def _csv(name: str) -> list[dict[str, str]]:
    with (OUT / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _snapshot(tmp_path: Path) -> Path:
    snap = tmp_path / "task_file_snapshot"
    shutil.copytree(APP_TASK, snap)
    return snap


def _restore(snapshot: Path) -> None:
    if APP_TASK.exists():
        shutil.rmtree(APP_TASK, ignore_errors=True)
    shutil.copytree(snapshot, APP_TASK)


def test_binary_is_native_elf() -> None:
    """Verify binary is native elf."""
    assert BIN.read_bytes()[:4] == b"\x7fELF"


def test_seed_summary_and_cell_balances() -> None:
    """Verify seed summary and buffer balances."""
    _run_ok()
    data = _json()
    rows = {r["buffer_id"]: r for r in data["buffers"]}
    assert rows["BUF_A"] == {
        "available": 71,
        "buffer_id": "BUF_A",
        "capacity": 100,
        "dispatched": 8,
        "filled": 29,
        "holdback": 0,
        "status": "OPEN",
    }
    assert rows["BUF_B"]["filled"] == 4
    assert rows["BUF_B"]["dispatched"] == 16
    assert rows["BUF_B"]["status"] == "OPEN"
    assert rows["BUF_C"]["available"] == 40
    assert data["summary"] == EXPECTED_SUMMARY


def test_reject_reason_strings() -> None:
    """Verify reject reason strings on seed fixtures."""
    _run_ok()
    rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
    assert rejects["i4"] == "BUFFER_PAUSED"
    assert rejects["ob1"] == "OVER_CAPACITY"
    assert rejects["ir1"] == "INSUFFICIENT_HOLDBACK"
    assert rejects["unk"] == "UNKNOWN_BUFFER"
    assert rejects["bq"] == "BAD_QTY"
    assert rejects["ba"] == "BAD_LANE"


def test_audit_and_reject_csv_headers() -> None:
    """Verify audit.csv and rejects.csv use the documented column order."""
    _run_ok()
    with (OUT / "audit.csv").open(encoding="utf-8") as f:
        assert next(csv.reader(f)) == [
            "event_id",
            "timestamp",
            "buffer_id",
            "lane_id",
            "applied_qty",
        ]
    with (OUT / "rejects.csv").open(encoding="utf-8") as f:
        assert next(csv.reader(f)) == ["event_id", "timestamp", "buffer_id", "reason"]


def test_nothing_to_release_when_filled_zero(tmp_path: Path) -> None:
    """Verify RELEASE on empty filled rejects NOTHING_TO_RELEASE."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "NR1", "capacity": 20, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_nr1.jsonl").write_text(
            '{"event_id":"ntr1","timestamp":9800,"op":"RELEASE","buffer_id":"NR1","lane_id":"L1","qty":"3"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
        assert rejects["ntr1"] == "NOTHING_TO_RELEASE"
    finally:
        _restore(snap)


def test_result_json_exact_python_formatting() -> None:
    """Verify result json exact python formatting."""
    _run_ok()
    text = (OUT / "result.json").read_text(encoding="utf-8")
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"


def test_audit_applied_qty_matches_seed_chain() -> None:
    """Verify audit applied qty matches seed chain."""
    _run_ok()
    audit = {r["event_id"]: r for r in _csv("audit.csv")}
    assert audit["h1"]["applied_qty"] == "10"
    assert audit["d1"]["applied_qty"] == "8"
    assert audit["c1"]["applied_qty"] == "2"
    assert audit["r1"]["applied_qty"] == "3"
    assert audit["p1"]["applied_qty"] == "0"


def test_binary_exits_nonzero_wrong_cli_arity() -> None:
    """Verify binary exits nonzero on wrong cli arity."""
    cp = subprocess.run([str(BIN)], check=False, capture_output=True, text=True, timeout=300)
    _quiet(cp)
    assert cp.returncode != 0
    cp2 = subprocess.run(
        [str(BIN), str(APP_TASK), "/extra"],
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    _quiet(cp2)
    assert cp2.returncode != 0


def test_binary_exits_nonzero_missing_events_directory(tmp_path: Path) -> None:
    """Verify binary exits nonzero when events directory is missing."""
    snap = _snapshot(tmp_path)
    try:
        shutil.rmtree(OUT, ignore_errors=True)
        shutil.rmtree(APP_TASK / "events")
        cp = _run()
        _quiet(cp)
        assert cp.returncode != 0
        assert not OUT.exists()
    finally:
        _restore(snap)


def test_fatal_duplicate_buffer_preserves_output_tree(tmp_path: Path) -> None:
    """Verify fatal duplicate buffer id preserves output tree."""
    snap = _snapshot(tmp_path)
    try:
        _run_ok()
        before = {p.relative_to(OUT).as_posix() for p in OUT.rglob("*") if p.is_file()}
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append(dict(buffers[0]))
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        cp2 = _run()
        _quiet(cp2)
        assert cp2.returncode != 0
        after = {p.relative_to(OUT).as_posix() for p in OUT.rglob("*") if p.is_file()}
        assert after == before
    finally:
        _restore(snap)


def test_dispatch_consumes_holdback_before_filled(tmp_path: Path) -> None:
    """Verify DISPATCH spends holdback before filled."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "HB1", "capacity": 50, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_hb1.jsonl").write_text(
            '{"event_id":"x1","timestamp":9000,"op":"INGEST","buffer_id":"HB1","lane_id":"L1","qty":"20"}\n'
            '{"event_id":"x2","timestamp":9001,"op":"HOLDBACK","buffer_id":"HB1","lane_id":"L1","qty":"12"}\n'
            '{"event_id":"x3","timestamp":9002,"op":"DISPATCH","buffer_id":"HB1","lane_id":"L1","qty":"15"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["HB1"]["holdback"] == 0
        assert rows["HB1"]["filled"] == 5
        assert rows["HB1"]["dispatched"] == 15
        assert rows["HB1"]["available"] == 45
    finally:
        _restore(snap)


def test_buffer_paused_blocks_ingest_not_release(tmp_path: Path) -> None:
    """Verify HOLD status blocks INGEST but RELEASE still applies."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "PH1", "capacity": 30, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_ph1.jsonl").write_text(
            '{"event_id":"pi1","timestamp":9100,"op":"INGEST","buffer_id":"PH1","lane_id":"L1","qty":"10"}\n'
            '{"event_id":"pi2","timestamp":9101,"op":"PAUSE","buffer_id":"PH1","lane_id":"-","qty":"0"}\n'
            '{"event_id":"pi3","timestamp":9102,"op":"INGEST","buffer_id":"PH1","lane_id":"L1","qty":"1"}\n'
            '{"event_id":"pi4","timestamp":9103,"op":"RELEASE","buffer_id":"PH1","lane_id":"L1","qty":"4"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
        assert rejects["pi3"] == "BUFFER_PAUSED"
        audit = {r["event_id"]: r for r in _csv("audit.csv")}
        assert audit["pi4"]["applied_qty"] == "4"
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["PH1"]["status"] == "HOLD"
        assert rows["PH1"]["filled"] == 6
    finally:
        _restore(snap)


def test_holdback_all_or_nothing(tmp_path: Path) -> None:
    """Verify HOLDBACK rejects INSUFFICIENT_FILLED without partial move."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "HF1", "capacity": 20, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_hf1.jsonl").write_text(
            '{"event_id":"hf1","timestamp":9200,"op":"INGEST","buffer_id":"HF1","lane_id":"L1","qty":"5"}\n'
            '{"event_id":"hf2","timestamp":9201,"op":"HOLDBACK","buffer_id":"HF1","lane_id":"L1","qty":"8"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
        assert rejects["hf2"] == "INSUFFICIENT_FILLED"
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["HF1"]["filled"] == 5
        assert rows["HF1"]["holdback"] == 0
    finally:
        _restore(snap)


def test_transfer_moves_holdback_between_buffers(tmp_path: Path) -> None:
    """Verify TRANSFER moves holdback from source to peer buffer."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.extend(
            [
                {"buffer_id": "TS1", "capacity": 40, "status": "OPEN"},
                {"buffer_id": "TD1", "capacity": 40, "status": "OPEN"},
            ]
        )
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_tr1.jsonl").write_text(
            '{"event_id":"tr1","timestamp":9300,"op":"INGEST","buffer_id":"TS1","lane_id":"L1","qty":"15"}\n'
            '{"event_id":"tr2","timestamp":9301,"op":"HOLDBACK","buffer_id":"TS1","lane_id":"L1","qty":"10"}\n'
            '{"event_id":"tr3","timestamp":9302,"op":"TRANSFER","buffer_id":"TS1","peer_buffer_id":"TD1","lane_id":"L1","qty":"6"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["TS1"]["holdback"] == 4
        assert rows["TD1"]["holdback"] == 6
    finally:
        _restore(snap)


def test_bad_control_on_pause_with_lane(tmp_path: Path) -> None:
    """Verify PAUSE with real lane_id rejects BAD_CONTROL."""
    snap = _snapshot(tmp_path)
    try:
        (APP_TASK / "events" / "zz_bc1.jsonl").write_text(
            '{"event_id":"bc1","timestamp":9400,"op":"PAUSE","buffer_id":"BUF_A","lane_id":"L1","qty":"0"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
        assert rejects["bc1"] == "BAD_CONTROL"
    finally:
        _restore(snap)


def test_pause_empty_lane_rejects_bad_control(tmp_path: Path) -> None:
    """Verify PAUSE with empty lane_id rejects BAD_CONTROL, not BAD_LANE."""
    snap = _snapshot(tmp_path)
    try:
        (APP_TASK / "events" / "zz_el1.jsonl").write_text(
            '{"event_id":"el1","timestamp":9450,"op":"PAUSE","buffer_id":"BUF_A","lane_id":"","qty":"0"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
        assert rejects["el1"] == "BAD_CONTROL"
    finally:
        _restore(snap)


def test_holdback_moves_from_filled(tmp_path: Path) -> None:
    """Verify HOLDBACK subtracts qty from filled and adds to holdback."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "HM1", "capacity": 30, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_hm1.jsonl").write_text(
            '{"event_id":"hm1","timestamp":9470,"op":"INGEST","buffer_id":"HM1","lane_id":"L1","qty":"10"}\n'
            '{"event_id":"hm2","timestamp":9471,"op":"HOLDBACK","buffer_id":"HM1","lane_id":"L1","qty":"4"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["HM1"]["filled"] == 6
        assert rows["HM1"]["holdback"] == 4
        assert rows["HM1"]["available"] == 20
    finally:
        _restore(snap)


def test_unknown_event_property_is_fatal(tmp_path: Path) -> None:
    """Verify unknown JSON properties on events are a silent fatal exit."""
    snap = _snapshot(tmp_path)
    try:
        _run_ok()
        before = {p.relative_to(OUT).as_posix() for p in OUT.rglob("*") if p.is_file()}
        (APP_TASK / "events" / "zz_unkp.jsonl").write_text(
            '{"event_id":"uxp1","timestamp":9480,"op":"INGEST","buffer_id":"BUF_A","lane_id":"L1","qty":"1","extra_field":"x"}\n',
            encoding="utf-8",
        )
        cp = _run()
        _quiet(cp)
        assert cp.returncode != 0
        after = {p.relative_to(OUT).as_posix() for p in OUT.rglob("*") if p.is_file()}
        assert after == before
    finally:
        _restore(snap)


def test_rejection_does_not_mark_event_id_seen(tmp_path: Path) -> None:
    """Verify rejected event_id may succeed on a later line."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "RK1", "capacity": 25, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_rk1.jsonl").write_text(
            '{"event_id":"rid1","timestamp":9500,"op":"DISPATCH","buffer_id":"RK1","lane_id":"L1","qty":"5"}\n'
            '{"event_id":"rid2","timestamp":9501,"op":"INGEST","buffer_id":"RK1","lane_id":"L1","qty":"5"}\n'
            '{"event_id":"rid1","timestamp":9502,"op":"DISPATCH","buffer_id":"RK1","lane_id":"L1","qty":"3"}\n',
            encoding="utf-8",
        )
        _run_ok()
        audit = {r["event_id"]: r for r in _csv("audit.csv")}
        assert audit["rid1"]["applied_qty"] == "3"
    finally:
        _restore(snap)


def test_crlf_jsonl_line_endings(tmp_path: Path) -> None:
    """Verify CRLF jsonl lines normalize and replay."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "CR1", "capacity": 10, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_cr1.jsonl").write_bytes(
            b'{"event_id":"cr1","timestamp":9600,"op":"INGEST","buffer_id":"CR1","lane_id":"L1","qty":"3"}\r\n'
        )
        _run_ok()
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["CR1"]["filled"] == 3
    finally:
        _restore(snap)


def test_empty_peer_buffer_id_on_non_transfer_applies(tmp_path: Path) -> None:
    """Empty-string peer_buffer_id on non-TRANSFER is treated as unset and must apply."""
    task = tmp_path / "empty_peer"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "B1", "capacity": 50, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"ep1","timestamp":1,"op":"INGEST","buffer_id":"B1","lane_id":"L1","qty":"7","peer_buffer_id":""}\n',
        encoding="utf-8",
    )
    subprocess.run([str(BIN), str(task)], check=True, capture_output=True, text=True)
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["B1"]["filled"] == 7
    assert [r for r in _csv("rejects.csv") if r["event_id"] == "ep1"] == []


def test_compound_spend_with_peer_buffer_id_is_bad_control(tmp_path: Path) -> None:
    """Verify peer_buffer_id on non-TRANSFER op rejects BAD_CONTROL."""
    snap = _snapshot(tmp_path)
    try:
        (APP_TASK / "events" / "zz_pb1.jsonl").write_text(
            '{"event_id":"pb1","timestamp":9700,"op":"INGEST","buffer_id":"BUF_A","peer_buffer_id":"BUF_B","lane_id":"L1","qty":"1"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
        assert rejects["pb1"] == "BAD_CONTROL"
    finally:
        _restore(snap)


def test_buffers_sorted_in_result_json() -> None:
    """Verify buffers array is sorted ascending by buffer_id."""
    _run_ok()
    ids = [r["buffer_id"] for r in _json()["buffers"]]
    assert ids == sorted(ids)


def test_binary_does_not_modify_task_file() -> None:
    """Verify binary does not modify task_file tree."""
    before = {
        p.relative_to(APP_TASK).as_posix(): p.read_bytes()
        for p in APP_TASK.rglob("*")
        if p.is_file()
    }
    _run_ok()
    after = {
        p.relative_to(APP_TASK).as_posix(): p.read_bytes()
        for p in APP_TASK.rglob("*")
        if p.is_file()
    }
    assert before == after


def test_task_file_schema_present() -> None:
    """Verify schema.md ships under task_file."""
    assert (APP_TASK / "schema.md").is_file()


def test_replay_contract_docs_present() -> None:
    """Supplementary contract docs are present for solver reference."""
    assert Path("/app/docs/holdback_buffer_replay_contract.md").is_file()


def test_uppercase_jsonl_extension_ignored(tmp_path: Path) -> None:
    """Uppercase .JSONL files are not discovered."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "UP1", "capacity": 10, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_UP1.JSONL").write_text(
            '{"event_id":"up1","timestamp":9801,"op":"INGEST","buffer_id":"UP1","lane_id":"L1","qty":"4"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["UP1"]["filled"] == 0
    finally:
        _restore(snap)


def test_commit_partial_when_holdback_less_than_qty(tmp_path: Path) -> None:
    """COMMIT applied_qty caps at current holdback."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "CP1", "capacity": 30, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_cp1.jsonl").write_text(
            '{"event_id":"cp1","timestamp":9810,"op":"INGEST","buffer_id":"CP1","lane_id":"L1","qty":"12"}\n'
            '{"event_id":"cp2","timestamp":9811,"op":"HOLDBACK","buffer_id":"CP1","lane_id":"L1","qty":"5"}\n'
            '{"event_id":"cp3","timestamp":9812,"op":"COMMIT","buffer_id":"CP1","lane_id":"L1","qty":"9"}\n',
            encoding="utf-8",
        )
        _run_ok()
        audit = {r["event_id"]: r for r in _csv("audit.csv")}
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert audit["cp3"]["applied_qty"] == "5"
        assert rows["CP1"]["holdback"] == 0
        assert rows["CP1"]["filled"] == 12
    finally:
        _restore(snap)


def test_second_pause_on_hold_is_bad_control(tmp_path: Path) -> None:
    """Second PAUSE on an already HOLD buffer rejects BAD_CONTROL."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "SP1", "capacity": 20, "status": "HOLD"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_sp1.jsonl").write_text(
            '{"event_id":"sp1","timestamp":9820,"op":"PAUSE","buffer_id":"SP1","lane_id":"-","qty":"0"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
        assert rejects["sp1"] == "BAD_CONTROL"
    finally:
        _restore(snap)


def test_unpause_on_open_is_bad_control(tmp_path: Path) -> None:
    """UNPAUSE on an OPEN buffer rejects BAD_CONTROL."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "UO1", "capacity": 20, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_uo1.jsonl").write_text(
            '{"event_id":"uo1","timestamp":9830,"op":"UNPAUSE","buffer_id":"UO1","lane_id":"-","qty":"0"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
        assert rejects["uo1"] == "BAD_CONTROL"
    finally:
        _restore(snap)


def test_commit_on_hold_buffer_applies(tmp_path: Path) -> None:
    """COMMIT still applies after the buffer is paused."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "CH1", "capacity": 25, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_ch1.jsonl").write_text(
            '{"event_id":"ch1","timestamp":9840,"op":"INGEST","buffer_id":"CH1","lane_id":"L1","qty":"8"}\n'
            '{"event_id":"ch2","timestamp":9841,"op":"HOLDBACK","buffer_id":"CH1","lane_id":"L1","qty":"3"}\n'
            '{"event_id":"ch3","timestamp":9842,"op":"PAUSE","buffer_id":"CH1","lane_id":"-","qty":"0"}\n'
            '{"event_id":"ch4","timestamp":9843,"op":"COMMIT","buffer_id":"CH1","lane_id":"L1","qty":"2"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["CH1"]["status"] == "HOLD"
        assert rows["CH1"]["holdback"] == 1
        assert rows["CH1"]["filled"] == 7
    finally:
        _restore(snap)


def test_nested_subdirectory_jsonl_discovered(tmp_path: Path) -> None:
    """Nested events/**/*.jsonl files are replayed."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "NS1", "capacity": 15, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        nested = APP_TASK / "events" / "nested" / "deep"
        nested.mkdir(parents=True)
        (nested / "ns1.jsonl").write_text(
            '{"event_id":"ns1","timestamp":9850,"op":"INGEST","buffer_id":"NS1","lane_id":"L1","qty":"6"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["NS1"]["filled"] == 6
    finally:
        _restore(snap)


def test_bad_lane_on_ingest_with_dash_lane(tmp_path: Path) -> None:
    """INGEST with lane_id '-' rejects BAD_LANE."""
    snap = _snapshot(tmp_path)
    try:
        (APP_TASK / "events" / "zz_dl1.jsonl").write_text(
            '{"event_id":"dl1","timestamp":9860,"op":"INGEST","buffer_id":"BUF_A","lane_id":"-","qty":"1"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
        assert rejects["dl1"] == "BAD_LANE"
    finally:
        _restore(snap)


def test_holdback_on_empty_lane_rejects_when_other_lane_has_filled(tmp_path: Path) -> None:
    """HOLDBACK on a lane with insufficient filled rejects even when another lane has filled units."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "HLN", "capacity": 50, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_hln.jsonl").write_text(
            '{"event_id":"hln1","timestamp":9870,"op":"INGEST","buffer_id":"HLN","lane_id":"A","qty":"5"}\n'
            '{"event_id":"hln2","timestamp":9871,"op":"INGEST","buffer_id":"HLN","lane_id":"B","qty":"12"}\n'
            '{"event_id":"hln3","timestamp":9872,"op":"HOLDBACK","buffer_id":"HLN","lane_id":"A","qty":"8"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
        assert rejects["hln3"] == "INSUFFICIENT_FILLED"
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["HLN"]["filled"] == 17
        assert rows["HLN"]["holdback"] == 0
    finally:
        _restore(snap)


def test_commit_on_empty_lane_rejects_when_other_lane_has_holdback(tmp_path: Path) -> None:
    """COMMIT on a lane with zero holdback rejects even when another lane still has holdback."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "CLN", "capacity": 40, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_cln.jsonl").write_text(
            '{"event_id":"cln1","timestamp":9880,"op":"INGEST","buffer_id":"CLN","lane_id":"X","qty":"10"}\n'
            '{"event_id":"cln2","timestamp":9881,"op":"HOLDBACK","buffer_id":"CLN","lane_id":"X","qty":"6"}\n'
            '{"event_id":"cln3","timestamp":9882,"op":"COMMIT","buffer_id":"CLN","lane_id":"Y","qty":"3"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
        assert rejects["cln3"] == "INSUFFICIENT_HOLDBACK"
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["CLN"]["holdback"] == 6
    finally:
        _restore(snap)


def test_release_on_empty_lane_rejects_when_other_lane_has_filled(tmp_path: Path) -> None:
    """RELEASE on a lane with zero filled rejects even when another lane still has filled units."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "RLN", "capacity": 30, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_rln.jsonl").write_text(
            '{"event_id":"rln1","timestamp":9890,"op":"INGEST","buffer_id":"RLN","lane_id":"P","qty":"7"}\n'
            '{"event_id":"rln2","timestamp":9891,"op":"RELEASE","buffer_id":"RLN","lane_id":"Q","qty":"2"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
        assert rejects["rln2"] == "NOTHING_TO_RELEASE"
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["RLN"]["filled"] == 7
    finally:
        _restore(snap)


def test_transfer_insufficient_uses_lane_slice_not_buffer_total(tmp_path: Path) -> None:
    """TRANSFER INSUFFICIENT_HOLDBACK when lane slice is too small despite higher buffer holdback."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.extend(
            [
                {"buffer_id": "TLS", "capacity": 50, "status": "OPEN"},
                {"buffer_id": "TLD", "capacity": 50, "status": "OPEN"},
            ]
        )
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_tls.jsonl").write_text(
            '{"event_id":"tls1","timestamp":9900,"op":"INGEST","buffer_id":"TLS","lane_id":"BIG","qty":"15"}\n'
            '{"event_id":"tls2","timestamp":9901,"op":"HOLDBACK","buffer_id":"TLS","lane_id":"BIG","qty":"10"}\n'
            '{"event_id":"tls3","timestamp":9902,"op":"INGEST","buffer_id":"TLS","lane_id":"SMALL","qty":"8"}\n'
            '{"event_id":"tls4","timestamp":9903,"op":"HOLDBACK","buffer_id":"TLS","lane_id":"SMALL","qty":"3"}\n'
            '{"event_id":"tls5","timestamp":9904,"op":"TRANSFER","buffer_id":"TLS","peer_buffer_id":"TLD","lane_id":"SMALL","qty":"5"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
        assert rejects["tls5"] == "INSUFFICIENT_HOLDBACK"
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["TLS"]["holdback"] == 13
        assert rows["TLD"]["holdback"] == 0
    finally:
        _restore(snap)


def test_dispatch_debits_holdback_lanes_in_lex_order(tmp_path: Path) -> None:
    """DISPATCH spends holdback lane slices in ascending lane_id order before filled."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "LEX", "capacity": 60, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_lex.jsonl").write_text(
            '{"event_id":"lex1","timestamp":9910,"op":"INGEST","buffer_id":"LEX","lane_id":"B","qty":"10"}\n'
            '{"event_id":"lex2","timestamp":9911,"op":"INGEST","buffer_id":"LEX","lane_id":"A","qty":"10"}\n'
            '{"event_id":"lex3","timestamp":9912,"op":"HOLDBACK","buffer_id":"LEX","lane_id":"B","qty":"5"}\n'
            '{"event_id":"lex4","timestamp":9913,"op":"HOLDBACK","buffer_id":"LEX","lane_id":"A","qty":"5"}\n'
            '{"event_id":"lex5","timestamp":9914,"op":"DISPATCH","buffer_id":"LEX","lane_id":"A","qty":"7"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["LEX"]["holdback"] == 3
        assert rows["LEX"]["filled"] == 10
        assert rows["LEX"]["dispatched"] == 7
    finally:
        _restore(snap)


def test_transfer_blocked_when_peer_is_hold(tmp_path: Path) -> None:
    """TRANSFER rejects BUFFER_PAUSED when the peer buffer is HOLD."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.extend(
            [
                {"buffer_id": "THS", "capacity": 30, "status": "OPEN"},
                {"buffer_id": "THD", "capacity": 30, "status": "HOLD"},
            ]
        )
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_tht.jsonl").write_text(
            '{"event_id":"tht1","timestamp":9920,"op":"INGEST","buffer_id":"THS","lane_id":"L1","qty":"8"}\n'
            '{"event_id":"tht2","timestamp":9921,"op":"HOLDBACK","buffer_id":"THS","lane_id":"L1","qty":"4"}\n'
            '{"event_id":"tht3","timestamp":9922,"op":"TRANSFER","buffer_id":"THS","peer_buffer_id":"THD","lane_id":"L1","qty":"2"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
        assert rejects["tht3"] == "BUFFER_PAUSED"
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["THS"]["holdback"] == 4
        assert rows["THD"]["holdback"] == 0
    finally:
        _restore(snap)


def test_transfer_blocked_when_source_is_hold(tmp_path: Path) -> None:
    """TRANSFER rejects BUFFER_PAUSED when the source buffer is HOLD."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.extend(
            [
                {"buffer_id": "THS2", "capacity": 30, "status": "OPEN"},
                {"buffer_id": "THD2", "capacity": 30, "status": "OPEN"},
            ]
        )
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_ths2.jsonl").write_text(
            '{"event_id":"ths2a","timestamp":9925,"op":"INGEST","buffer_id":"THS2","lane_id":"L1","qty":"6"}\n'
            '{"event_id":"ths2b","timestamp":9926,"op":"HOLDBACK","buffer_id":"THS2","lane_id":"L1","qty":"3"}\n'
            '{"event_id":"ths2c","timestamp":9927,"op":"PAUSE","buffer_id":"THS2","lane_id":"-","qty":"0"}\n'
            '{"event_id":"ths2d","timestamp":9928,"op":"TRANSFER","buffer_id":"THS2","peer_buffer_id":"THD2","lane_id":"L1","qty":"2"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
        assert rejects["ths2d"] == "BUFFER_PAUSED"
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["THS2"]["holdback"] == 3
        assert rows["THD2"]["holdback"] == 0
    finally:
        _restore(snap)


def test_binary_exits_nonzero_no_jsonl_shards(tmp_path: Path) -> None:
    """Verify fatal exit when events/ has no lowercase .jsonl files."""
    snap = _snapshot(tmp_path)
    try:
        shutil.rmtree(APP_TASK / "events")
        events = APP_TASK / "events"
        events.mkdir()
        (events / "dummy.txt").write_text("not jsonl\n", encoding="utf-8")
        cp = _run()
        _quiet(cp)
        assert cp.returncode != 0
    finally:
        _restore(snap)


def test_tiebreak_order_at_equal_timestamp(tmp_path: Path) -> None:
    """Equal timestamps replay in events-relative path order before line number."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "TBK", "capacity": 40, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "aa_tbk.jsonl").write_text(
            '{"event_id":"tbk1","timestamp":10000,"op":"HOLDBACK","buffer_id":"TBK","lane_id":"L1","qty":"5"}\n',
            encoding="utf-8",
        )
        (APP_TASK / "events" / "zz_tbk.jsonl").write_text(
            '{"event_id":"tbk2","timestamp":10000,"op":"INGEST","buffer_id":"TBK","lane_id":"L1","qty":"5"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["TBK"]["filled"] == 5
        assert rows["TBK"]["holdback"] == 0
        rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
        assert rejects["tbk1"] == "INSUFFICIENT_FILLED"
    finally:
        _restore(snap)


def test_skip_whitespace_and_non_object_lines(tmp_path: Path) -> None:
    """Whitespace-only and non-object JSON lines are skipped without fatal exit."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "SKP", "capacity": 25, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_skp.jsonl").write_text(
            "\n"
            "   \n"
            "[1,2,3]\n"
            '"hello"\n'
            "42\n"
            '{"event_id":"skp1","timestamp":10010,"op":"INGEST","buffer_id":"SKP","lane_id":"L1","qty":"4"}\n'
            "\t\n"
            '{"event_id":"skp2","timestamp":10011,"op":"HOLDBACK","buffer_id":"SKP","lane_id":"L1","qty":"2"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["SKP"]["filled"] == 2
        assert rows["SKP"]["holdback"] == 2
    finally:
        _restore(snap)


def test_dispatch_over_capacity_insufficient_total(tmp_path: Path) -> None:
    """DISPATCH rejects OVER_CAPACITY when holdback plus filled is less than qty."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "DOC", "capacity": 50, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_doc.jsonl").write_text(
            '{"event_id":"doc1","timestamp":10020,"op":"INGEST","buffer_id":"DOC","lane_id":"L1","qty":"3"}\n'
            '{"event_id":"doc2","timestamp":10021,"op":"HOLDBACK","buffer_id":"DOC","lane_id":"L1","qty":"2"}\n'
            '{"event_id":"doc3","timestamp":10022,"op":"DISPATCH","buffer_id":"DOC","lane_id":"L1","qty":"10"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
        assert rejects["doc3"] == "OVER_CAPACITY"
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["DOC"]["filled"] == 1
        assert rows["DOC"]["holdback"] == 2
        assert rows["DOC"]["dispatched"] == 0
    finally:
        _restore(snap)


def test_cr_only_jsonl_line_endings(tmp_path: Path) -> None:
    """Bare CR line separators are normalized before parsing."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "CR2", "capacity": 20, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_cr2.jsonl").write_bytes(
            b'{"event_id":"cro1","timestamp":10030,"op":"INGEST","buffer_id":"CR2","lane_id":"L1","qty":"4"}\r'
            b'{"event_id":"cro2","timestamp":10031,"op":"INGEST","buffer_id":"CR2","lane_id":"L1","qty":"5"}'
        )
        cp = _run(str(APP_TASK))
        _quiet(cp)
        assert cp.returncode == 0
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["CR2"]["filled"] == 9
        audit_ids = {r["event_id"] for r in _csv("audit.csv")}
        assert {"cro1", "cro2"} <= audit_ids
    finally:
        _restore(snap)


def test_unknown_buffer_property_is_fatal(tmp_path: Path) -> None:
    """Unknown keys on buffer config objects are fatal and preserve /app/output."""
    snap = _snapshot(tmp_path)
    try:
        _run_ok()
        before = {
            p.relative_to(OUT).as_posix(): p.read_bytes()
            for p in OUT.rglob("*")
            if p.is_file()
        }
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append(
            {"buffer_id": "UK1", "capacity": 20, "status": "OPEN", "warehouse": "east"}
        )
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        cp = _run()
        _quiet(cp)
        assert cp.returncode != 0
        after = {
            p.relative_to(OUT).as_posix(): p.read_bytes()
            for p in OUT.rglob("*")
            if p.is_file()
        }
        assert after == before
    finally:
        _restore(snap)


def test_bad_control_precedes_unknown_buffer(tmp_path: Path) -> None:
    """PAUSE with wrong lane on unknown buffer rejects BAD_CONTROL before UNKNOWN_BUFFER."""
    snap = _snapshot(tmp_path)
    try:
        (APP_TASK / "events" / "zz_uc1.jsonl").write_text(
            '{"event_id":"uc1","timestamp":10040,"op":"PAUSE","buffer_id":"NO_SUCH","lane_id":"L1","qty":"0"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
        assert rejects["uc1"] == "BAD_CONTROL"
    finally:
        _restore(snap)


def test_duplicate_event_id_retry_with_bad_qty_is_duplicate_not_reject(tmp_path: Path) -> None:
    """Duplicate detection runs before BAD_QTY evaluation."""
    snap = _snapshot(tmp_path)
    try:
        (APP_TASK / "events" / "zz_dup2.jsonl").write_text(
            '{"event_id":"dupq","timestamp":10050,"op":"INGEST","buffer_id":"BUF_A","lane_id":"L1","qty":"2"}\n'
            '{"event_id":"dupq","timestamp":10051,"op":"INGEST","buffer_id":"BUF_A","lane_id":"L1","qty":"01"}\n',
            encoding="utf-8",
        )
        _run_ok()
        data = _json()
        assert data["summary"]["duplicate_events"] == 2
        rejects = [r for r in _csv("rejects.csv") if r["event_id"] == "dupq"]
        assert len(rejects) == 0
    finally:
        _restore(snap)


def test_output_directory_is_recreated_removes_stale_files(tmp_path: Path) -> None:
    """Success deletes and recreates /app/output removing stale files."""
    snap = _snapshot(tmp_path)
    try:
        OUT.mkdir(parents=True, exist_ok=True)
        stale = OUT / "stale.txt"
        stale.write_text("keep", encoding="utf-8")
        _run_ok()
        assert not stale.exists()
        assert (OUT / "result.json").is_file()
    finally:
        _restore(snap)


def test_output_nested_stale_subdir_removed(tmp_path: Path) -> None:
    """Success removes nested stale directories under /app/output."""
    snap = _snapshot(tmp_path)
    try:
        nested = OUT / "old" / "nested"
        nested.mkdir(parents=True, exist_ok=True)
        (nested / "stale.txt").write_text("keep", encoding="utf-8")
        _run_ok()
        assert not (OUT / "old").exists()
        assert (OUT / "result.json").is_file()
    finally:
        _restore(snap)


def test_release_partial_audit_magnitude(tmp_path: Path) -> None:
    """RELEASE applied_qty equals units moved, capped by lane filled slice."""
    snap = _snapshot(tmp_path)
    try:
        path = APP_TASK / "config" / "buffers.json"
        buffers = json.loads(path.read_text(encoding="utf-8"))
        buffers.append({"buffer_id": "RP1", "capacity": 30, "status": "OPEN"})
        path.write_text(json.dumps(buffers, indent=2) + "\n", encoding="utf-8")
        (APP_TASK / "events" / "zz_rp1.jsonl").write_text(
            '{"event_id":"rp1","timestamp":10060,"op":"INGEST","buffer_id":"RP1","lane_id":"L1","qty":"6"}\n'
            '{"event_id":"rp2","timestamp":10061,"op":"RELEASE","buffer_id":"RP1","lane_id":"L1","qty":"10"}\n',
            encoding="utf-8",
        )
        _run_ok()
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["RP1"]["filled"] == 0
        audit = {r["event_id"]: int(r["applied_qty"]) for r in _csv("audit.csv")}
        assert audit["rp2"] == 6
    finally:
        _restore(snap)


def test_replay_tool_src_is_modular_rust_cargo_project() -> None:
    """Shipped modular Rust Cargo project agents must complete."""
    root = Path("/app/replay_tool_src")
    assert (root / "Cargo.toml").is_file()
    assert (root / "src" / "main.rs").is_file()
    src_files = sorted(p.name for p in (root / "src").glob("*.rs"))
    assert len(src_files) >= 5, f"expected multiple Rust modules, got {src_files}"
    assert "main.rs" in src_files
    main_text = (root / "src" / "main.rs").read_text(encoding="utf-8")
    mod_count = sum(1 for line in main_text.splitlines() if line.strip().startswith("mod "))
    assert mod_count >= 4, f"main.rs should declare multiple modules, saw {mod_count}"
    assert "replay_tool" in (root / "Cargo.toml").read_text(encoding="utf-8")


def test_pause_unpause_signed_zero_accepted(tmp_path: Path) -> None:
    """PAUSE with +0 and UNPAUSE with -0 are valid control qty values."""
    task = tmp_path / "sz_ctrl"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "SZ", "capacity": 100, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"sz1","timestamp":10100,"op":"PAUSE","buffer_id":"SZ","lane_id":"-","qty":"+0"}\n'
        '{"event_id":"sz2","timestamp":10101,"op":"UNPAUSE","buffer_id":"SZ","lane_id":"-","qty":"-0"}\n',
        encoding="utf-8",
    )
    cp = _run(str(task))
    assert cp.returncode == 0
    _quiet(cp)
    audit = {r["event_id"] for r in _csv("audit.csv")}
    assert audit == {"sz1", "sz2"}


def test_compound_duplicate_no_reject_row(tmp_path: Path) -> None:
    """Successful duplicate increments summary only — no reject.csv row."""
    task = tmp_path / "dup_only"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "D1", "capacity": 50, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"dup","timestamp":10110,"op":"INGEST","buffer_id":"D1","lane_id":"L1","qty":"3"}\n'
        '{"event_id":"dup","timestamp":10111,"op":"INGEST","buffer_id":"D1","lane_id":"L1","qty":"3"}\n',
        encoding="utf-8",
    )
    cp = _run(str(task))
    assert cp.returncode == 0
    _quiet(cp)
    data = _json()
    assert data["summary"]["duplicate_events"] == 1
    assert data["summary"]["applied_events"] == 1
    with (OUT / "rejects.csv").open(newline="", encoding="utf-8") as f:
        assert [r for r in csv.DictReader(f) if r["event_id"] == "dup"] == []


def _run_task_root(task: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(BIN), str(task)], capture_output=True, text=True, timeout=300
    )


def _run_ok_task(task: Path) -> None:
    cp = _run_task_root(task)
    _quiet(cp)
    assert cp.returncode == 0


def test_fatal_only_uppercase_jsonl_extensions(tmp_path: Path) -> None:
    """events/ with only uppercase .JSONL files is fatal — no selectable lowercase .jsonl."""
    task = tmp_path / "upper_only"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "U1", "capacity": 50, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "ONLY.JSONL").write_text(
        '{"event_id":"x1","timestamp":1,"op":"INGEST","buffer_id":"U1","lane_id":"L1","qty":"5"}\n',
        encoding="utf-8",
    )
    cp = _run_task_root(task)
    _quiet(cp)
    assert cp.returncode != 0


def test_compound_uppercase_poison_preserves_seed_summary(tmp_path: Path) -> None:
    """Ignored .JSONL poison must not change seed summary or buffer balances."""
    snap = _snapshot(tmp_path)
    try:
        (APP_TASK / "events" / "POISON.JSONL").write_text(
            '{"event_id":"poison","timestamp":1,"op":"INGEST","buffer_id":"BUF_B","lane_id":"L1","qty":"99999"}\n',
            encoding="utf-8",
        )
        _run_ok()
        assert _json()["summary"] == EXPECTED_SUMMARY
        rows = {r["buffer_id"]: r for r in _json()["buffers"]}
        assert rows["BUF_B"]["filled"] == 4
    finally:
        _restore(snap)


def test_compound_insufficient_filled_reject_same_id_ingest_applies(tmp_path: Path) -> None:
    """INSUFFICIENT_FILLED reject does not reserve event_id; a later row with the same id may apply."""
    task = tmp_path / "if_reuse"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "I1", "capacity": 50, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "chain.jsonl").write_text(
        '{"event_id":"e1","timestamp":10200,"op":"INGEST","buffer_id":"I1","lane_id":"L1","qty":"5"}\n'
        '{"event_id":"shared","timestamp":10201,"op":"HOLDBACK","buffer_id":"I1","lane_id":"L1","qty":"10"}\n'
        '{"event_id":"shared","timestamp":10202,"op":"INGEST","buffer_id":"I1","lane_id":"L1","qty":"3"}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
    assert rejects["shared"] == "INSUFFICIENT_FILLED"
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["I1"]["filled"] == 8
    assert _json()["summary"]["duplicate_events"] == 0


def test_compound_over_capacity_reject_same_id_ingest_applies(tmp_path: Path) -> None:
    """OVER_CAPACITY reject does not reserve event_id; a later row with the same id may apply."""
    task = tmp_path / "oc_reuse"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "O1", "capacity": 10, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "chain.jsonl").write_text(
        '{"event_id":"fail","timestamp":10210,"op":"INGEST","buffer_id":"O1","lane_id":"L1","qty":"12"}\n'
        '{"event_id":"fail","timestamp":10211,"op":"INGEST","buffer_id":"O1","lane_id":"L1","qty":"3"}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
    assert rejects["fail"] == "OVER_CAPACITY"
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["O1"]["filled"] == 3
    assert _json()["summary"]["duplicate_events"] == 0


def test_compound_nested_uppercase_ignored_with_dispatch_lex_order(tmp_path: Path) -> None:
    """Nested .JSONL poison is ignored while DISPATCH debits holdback lanes in lex order."""
    task = tmp_path / "nest_lex"
    (task / "config").mkdir(parents=True)
    (task / "events" / "nested").mkdir(parents=True)
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "NX", "capacity": 60, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "nested" / "IGNORE.JSONL").write_text(
        '{"event_id":"bad","timestamp":1,"op":"INGEST","buffer_id":"NX","lane_id":"L1","qty":"99"}\n',
        encoding="utf-8",
    )
    (task / "events" / "chain.jsonl").write_text(
        '{"event_id":"n1","timestamp":10220,"op":"INGEST","buffer_id":"NX","lane_id":"B","qty":"10"}\n'
        '{"event_id":"n2","timestamp":10221,"op":"INGEST","buffer_id":"NX","lane_id":"A","qty":"10"}\n'
        '{"event_id":"n3","timestamp":10222,"op":"HOLDBACK","buffer_id":"NX","lane_id":"B","qty":"5"}\n'
        '{"event_id":"n4","timestamp":10223,"op":"HOLDBACK","buffer_id":"NX","lane_id":"A","qty":"5"}\n'
        '{"event_id":"n5","timestamp":10224,"op":"DISPATCH","buffer_id":"NX","lane_id":"A","qty":"7"}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["NX"]["holdback"] == 3
    assert rows["NX"]["filled"] == 10
    assert rows["NX"]["dispatched"] == 7


def test_compound_triple_reject_apply_duplicate_chain(tmp_path: Path) -> None:
    """Reject, apply, then duplicate on the same event_id follows full duplicate semantics."""
    task = tmp_path / "rad_chain"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "R1", "capacity": 20, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "chain.jsonl").write_text(
        '{"event_id":"setup","timestamp":10230,"op":"INGEST","buffer_id":"R1","lane_id":"L1","qty":"15"}\n'
        '{"event_id":"fail","timestamp":10231,"op":"INGEST","buffer_id":"R1","lane_id":"L1","qty":"10"}\n'
        '{"event_id":"fail","timestamp":10232,"op":"INGEST","buffer_id":"R1","lane_id":"L1","qty":"3"}\n'
        '{"event_id":"fail","timestamp":10233,"op":"INGEST","buffer_id":"R1","lane_id":"L1","qty":"1"}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rejects = [r for r in _csv("rejects.csv") if r["event_id"] == "fail"]
    assert len(rejects) == 1
    assert rejects[0]["reason"] == "OVER_CAPACITY"
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["R1"]["filled"] == 18
    assert _json()["summary"]["duplicate_events"] == 1
    assert [r for r in _csv("rejects.csv") if r.get("reason") == "DUPLICATE_EVENT"] == []


def test_qty_scientific_notation_is_bad_qty(tmp_path: Path) -> None:
    """Scientific-notation qty strings reject BAD_QTY without fatal exit."""
    task = tmp_path / "sci_qty"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "S1", "capacity": 100, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"sq1","timestamp":10300,"op":"INGEST","buffer_id":"S1","lane_id":"L1","qty":"1e3"}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
    assert rejects["sq1"] == "BAD_QTY"


def test_qty_leading_zero_is_bad_qty(tmp_path: Path) -> None:
    """Leading-zero qty strings reject BAD_QTY without fatal exit."""
    task = tmp_path / "lz_qty"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "Z1", "capacity": 100, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"lq1","timestamp":10310,"op":"INGEST","buffer_id":"Z1","lane_id":"L1","qty":"05"}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
    assert rejects["lq1"] == "BAD_QTY"


def test_compound_same_timestamp_intra_file_line_order(tmp_path: Path) -> None:
    """Equal timestamps in one shard replay in ascending physical line order."""
    task = tmp_path / "line_tie"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "T1", "capacity": 100, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"lt1","timestamp":10320,"op":"INGEST","buffer_id":"T1","lane_id":"L1","qty":"10"}\n'
        '{"event_id":"lt2","timestamp":10320,"op":"HOLDBACK","buffer_id":"T1","lane_id":"L1","qty":"10"}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["T1"]["filled"] == 0
    assert rows["T1"]["holdback"] == 10
    audit = [r["event_id"] for r in _csv("audit.csv")]
    assert audit.index("lt1") < audit.index("lt2")


def test_compound_path_tiebreak_different_fill_outcome(tmp_path: Path) -> None:
    """Path tie-break at equal timestamp changes which INGEST applies when capacity is tight."""
    task = tmp_path / "path_out"
    (task / "config").mkdir(parents=True)
    (task / "events" / "z").mkdir(parents=True)
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "P1", "capacity": 70, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "a.jsonl").write_text(
        '{"event_id":"big","timestamp":10330,"op":"INGEST","buffer_id":"P1","lane_id":"L1","qty":"50"}\n',
        encoding="utf-8",
    )
    (task / "events" / "z" / "late.jsonl").write_text(
        '{"event_id":"small","timestamp":10330,"op":"INGEST","buffer_id":"P1","lane_id":"L1","qty":"30"}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["P1"]["filled"] == 50
    rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
    assert rejects["small"] == "OVER_CAPACITY"


def test_compound_duplicate_unpause_no_state_change(tmp_path: Path) -> None:
    """Duplicate UNPAUSE after success does not reapply buffer status."""
    task = tmp_path / "dup_unpause"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "U1", "capacity": 50, "status": "HOLD"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"u1","timestamp":10340,"op":"UNPAUSE","buffer_id":"U1","lane_id":"-","qty":"0"}\n'
        '{"event_id":"u1","timestamp":10341,"op":"UNPAUSE","buffer_id":"U1","lane_id":"-","qty":"0"}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["U1"]["status"] == "OPEN"
    assert _json()["summary"]["duplicate_events"] == 1
    assert [r for r in _csv("rejects.csv") if r["event_id"] == "u1"] == []


def test_compound_bad_lane_reject_same_id_ingest_applies(tmp_path: Path) -> None:
    """BAD_LANE reject does not reserve event_id; a later row with the same id may apply."""
    task = tmp_path / "bl_reuse"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "B1", "capacity": 100, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "chain.jsonl").write_text(
        '{"event_id":"reuse","timestamp":10350,"op":"INGEST","buffer_id":"B1","lane_id":"-","qty":"6"}\n'
        '{"event_id":"reuse","timestamp":10351,"op":"INGEST","buffer_id":"B1","lane_id":"L1","qty":"6"}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
    assert rejects["reuse"] == "BAD_LANE"
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["B1"]["filled"] == 6
    assert _json()["summary"]["duplicate_events"] == 0


def test_fatal_malformed_json_preserves_output(tmp_path: Path) -> None:
    """Malformed JSONL is fatal and preserves existing /app/output bytes."""
    snap = _snapshot(tmp_path)
    try:
        (APP_TASK / "events" / "zz_bad.jsonl").write_text("{not json\n", encoding="utf-8")
        OUT.mkdir(parents=True, exist_ok=True)
        marker = OUT / "keep.txt"
        marker.write_text("stay", encoding="utf-8")
        cp = _run()
        assert cp.returncode != 0
        _quiet(cp)
        assert marker.read_text(encoding="utf-8") == "stay"
    finally:
        _restore(snap)


def test_ingest_at_exact_available_boundary_succeeds(tmp_path: Path) -> None:
    """INGEST that exactly fills remaining available capacity succeeds."""
    task = tmp_path / "ingest_exact"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "E1", "capacity": 50, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"e1","timestamp":10360,"op":"INGEST","buffer_id":"E1","lane_id":"L1","qty":"30"}\n'
        '{"event_id":"e2","timestamp":10361,"op":"HOLDBACK","buffer_id":"E1","lane_id":"L1","qty":"10"}\n'
        '{"event_id":"e3","timestamp":10362,"op":"INGEST","buffer_id":"E1","lane_id":"L2","qty":"20"}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["E1"]["filled"] == 40
    assert rows["E1"]["holdback"] == 10
    assert rows["E1"]["available"] == 0


def test_compound_same_timestamp_line_order_not_event_id(tmp_path: Path) -> None:
    """Same timestamp in one shard orders by physical line, not lexicographic event_id."""
    task = tmp_path / "eid_trap"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "E2", "capacity": 80, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"z_last","timestamp":10370,"op":"INGEST","buffer_id":"E2","lane_id":"L1","qty":"50"}\n'
        '{"event_id":"a_first","timestamp":10370,"op":"INGEST","buffer_id":"E2","lane_id":"L1","qty":"40"}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
    assert rejects["a_first"] == "OVER_CAPACITY"
    assert _json()["buffers"][0]["filled"] == 50


def test_compound_transfer_insufficient_holdback_beats_over_capacity(tmp_path: Path) -> None:
    """When TRANSFER triggers lane INSUFFICIENT_HOLDBACK and peer OVER_CAPACITY, INSUFFICIENT_HOLDBACK wins."""
    task = tmp_path / "xfer_prec"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps(
            [
                {"buffer_id": "SRC", "capacity": 100, "status": "OPEN"},
                {"buffer_id": "DST", "capacity": 20, "status": "OPEN"},
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (task / "events" / "chain.jsonl").write_text(
        '{"event_id":"s1","timestamp":10400,"op":"INGEST","buffer_id":"SRC","lane_id":"L1","qty":"4","peer_buffer_id":""}\n'
        '{"event_id":"s2","timestamp":10401,"op":"HOLDBACK","buffer_id":"SRC","lane_id":"L1","qty":"4","peer_buffer_id":""}\n'
        '{"event_id":"s3","timestamp":10402,"op":"INGEST","buffer_id":"DST","lane_id":"L1","qty":"19","peer_buffer_id":""}\n'
        '{"event_id":"s4","timestamp":10403,"op":"TRANSFER","buffer_id":"SRC","lane_id":"L1","qty":"6","peer_buffer_id":"DST"}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
    assert rejects["s4"] == "INSUFFICIENT_HOLDBACK"
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["SRC"]["holdback"] == 4
    assert rows["DST"]["filled"] == 19


def test_compound_transfer_reject_no_mutation_both_buffers(tmp_path: Path) -> None:
    """Rejected TRANSFER leaves both source and destination buffer ledgers unchanged."""
    task = tmp_path / "xfer_nomut"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps(
            [
                {"buffer_id": "SRC", "capacity": 50, "status": "OPEN"},
                {"buffer_id": "DST", "capacity": 50, "status": "OPEN"},
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (task / "events" / "chain.jsonl").write_text(
        '{"event_id":"m1","timestamp":10410,"op":"INGEST","buffer_id":"SRC","lane_id":"A","qty":"8","peer_buffer_id":""}\n'
        '{"event_id":"m2","timestamp":10411,"op":"HOLDBACK","buffer_id":"SRC","lane_id":"A","qty":"8","peer_buffer_id":""}\n'
        '{"event_id":"m3","timestamp":10412,"op":"INGEST","buffer_id":"DST","lane_id":"A","qty":"48","peer_buffer_id":""}\n'
        '{"event_id":"m4","timestamp":10413,"op":"TRANSFER","buffer_id":"SRC","lane_id":"A","qty":"5","peer_buffer_id":"DST"}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
    assert rejects["m4"] == "OVER_CAPACITY"
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["SRC"]["holdback"] == 8
    assert rows["DST"]["filled"] == 48


def test_compound_commit_partial_lane_holdback(tmp_path: Path) -> None:
    """COMMIT moves min(requested qty, lane holdback) into that lane's filled slice."""
    task = tmp_path / "commit_partial"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "B1", "capacity": 100, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "chain.jsonl").write_text(
        '{"event_id":"c1","timestamp":10420,"op":"INGEST","buffer_id":"B1","lane_id":"L1","qty":"20","peer_buffer_id":""}\n'
        '{"event_id":"c2","timestamp":10421,"op":"HOLDBACK","buffer_id":"B1","lane_id":"L1","qty":"20","peer_buffer_id":""}\n'
        '{"event_id":"c3","timestamp":10422,"op":"COMMIT","buffer_id":"B1","lane_id":"L1","qty":"12","peer_buffer_id":""}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["B1"]["holdback"] == 8
    assert rows["B1"]["filled"] == 12
    audit = {r["event_id"]: int(r["applied_qty"]) for r in _csv("audit.csv")}
    assert audit["c3"] == 12


def test_compound_unpause_signed_zero_minus0(tmp_path: Path) -> None:
    """UNPAUSE accepts -0 as signed-zero control qty."""
    task = tmp_path / "unpause_m0"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "H1", "capacity": 40, "status": "HOLD"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "chain.jsonl").write_text(
        '{"event_id":"u1","timestamp":10430,"op":"UNPAUSE","buffer_id":"H1","lane_id":"-","qty":"-0","peer_buffer_id":""}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    assert _json()["buffers"][0]["status"] == "OPEN"
    audit = {r["event_id"]: int(r["applied_qty"]) for r in _csv("audit.csv")}
    assert audit["u1"] == 0


def test_compound_dispatch_holdback_lex_then_filled(tmp_path: Path) -> None:
    """DISPATCH debits holdback lanes in lex order before touching filled lanes."""
    task = tmp_path / "dispatch_lex"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "D1", "capacity": 100, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "chain.jsonl").write_text(
        '{"event_id":"d1","timestamp":10440,"op":"INGEST","buffer_id":"D1","lane_id":"Z","qty":"6","peer_buffer_id":""}\n'
        '{"event_id":"d2","timestamp":10441,"op":"INGEST","buffer_id":"D1","lane_id":"A","qty":"6","peer_buffer_id":""}\n'
        '{"event_id":"d3","timestamp":10442,"op":"HOLDBACK","buffer_id":"D1","lane_id":"Z","qty":"4","peer_buffer_id":""}\n'
        '{"event_id":"d4","timestamp":10443,"op":"HOLDBACK","buffer_id":"D1","lane_id":"A","qty":"2","peer_buffer_id":""}\n'
        '{"event_id":"d5","timestamp":10444,"op":"DISPATCH","buffer_id":"D1","lane_id":"A","qty":"8","peer_buffer_id":""}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["D1"]["holdback"] == 0
    assert rows["D1"]["filled"] == 4
    assert rows["D1"]["dispatched"] == 8


def test_compound_event_id_duplicate_is_case_sensitive(tmp_path: Path) -> None:
    """event_id matching is case-sensitive; evt and EVT are distinct ids."""
    task = tmp_path / "case_id"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "B1", "capacity": 50, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"evt","timestamp":10450,"op":"INGEST","buffer_id":"B1","lane_id":"L1","qty":"5","peer_buffer_id":""}\n'
        '{"event_id":"EVT","timestamp":10451,"op":"INGEST","buffer_id":"B1","lane_id":"L2","qty":"3","peer_buffer_id":""}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["B1"]["filled"] == 8
    assert _json()["summary"]["duplicate_events"] == 0
    assert _json()["summary"]["applied_events"] == 2


def test_compound_success_then_duplicate_same_id_skips_reject(tmp_path: Path) -> None:
    """After successful apply, duplicate same event_id skips rejects.csv entirely."""
    task = tmp_path / "dup_skip"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "B1", "capacity": 50, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"same","timestamp":10460,"op":"INGEST","buffer_id":"B1","lane_id":"L1","qty":"4","peer_buffer_id":""}\n'
        '{"event_id":"same","timestamp":10461,"op":"HOLDBACK","buffer_id":"B1","lane_id":"L1","qty":"2","peer_buffer_id":""}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    assert _json()["summary"]["duplicate_events"] == 1
    assert _json()["summary"]["rejected_events"] == 0
    assert [r for r in _csv("rejects.csv") if r["event_id"] == "same"] == []


def test_compound_commit_on_hold_buffer_still_applies(tmp_path: Path) -> None:
    """COMMIT applies after PAUSE because BUFFER_PAUSED blocks INGEST/DISPATCH only."""
    task = tmp_path / "commit_hold"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "H1", "capacity": 40, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"h1","timestamp":10470,"op":"INGEST","buffer_id":"H1","lane_id":"L1","qty":"10","peer_buffer_id":""}\n'
        '{"event_id":"h2","timestamp":10471,"op":"HOLDBACK","buffer_id":"H1","lane_id":"L1","qty":"6","peer_buffer_id":""}\n'
        '{"event_id":"h3","timestamp":10472,"op":"PAUSE","buffer_id":"H1","lane_id":"-","qty":"0","peer_buffer_id":""}\n'
        '{"event_id":"h4","timestamp":10473,"op":"COMMIT","buffer_id":"H1","lane_id":"L1","qty":"4","peer_buffer_id":""}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["H1"]["status"] == "HOLD"
    assert rows["H1"]["holdback"] == 2
    assert rows["H1"]["filled"] == 8
    assert "h4" in {r["event_id"] for r in _csv("audit.csv")}


def test_compound_reject_then_success_same_event_id(tmp_path: Path) -> None:
    """Rejected OVER_CAPACITY does not consume event_id; later line with same id can apply."""
    task = tmp_path / "rej_retry"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "B1", "capacity": 10, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"retry","timestamp":10480,"op":"INGEST","buffer_id":"B1","lane_id":"L1","qty":"12","peer_buffer_id":""}\n'
        '{"event_id":"retry","timestamp":10481,"op":"INGEST","buffer_id":"B1","lane_id":"L1","qty":"6","peer_buffer_id":""}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rejects = [r for r in _csv("rejects.csv") if r["event_id"] == "retry"]
    assert len(rejects) == 1
    assert rejects[0]["reason"] == "OVER_CAPACITY"
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["B1"]["filled"] == 6
    assert _json()["summary"]["applied_events"] == 1


def test_dynamic_transfer_unknown_peer_rejects_unknown_buffer(tmp_path: Path) -> None:
    """Runtime-random ids: TRANSFER with absent peer_buffer_id rejects UNKNOWN_BUFFER."""
    uid = uuid.uuid4().hex[:8]
    src = f"S_{uid}"
    ghost = f"G_{uid}"
    event_id = f"T_{uid}"
    task = tmp_path / f"dyn_peer_{uid}"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": src, "capacity": 100, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "flow.jsonl").write_text(
        f'{{"event_id":"i1","timestamp":1,"op":"INGEST","buffer_id":"{src}","lane_id":"L1","qty":"20","peer_buffer_id":""}}\n'
        f'{{"event_id":"h1","timestamp":2,"op":"HOLDBACK","buffer_id":"{src}","lane_id":"L1","qty":"12","peer_buffer_id":""}}\n'
        f'{{"event_id":"{event_id}","timestamp":3,"op":"TRANSFER","buffer_id":"{src}","peer_buffer_id":"{ghost}","lane_id":"L1","qty":"5"}}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
    assert rejects[event_id] == "UNKNOWN_BUFFER"
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows[src]["holdback"] == 12


def test_compound_holdback_debits_event_lane_filled_slice(tmp_path: Path) -> None:
    """HOLDBACK moves qty from the event lane filled slice into that lane holdback slice."""
    task = tmp_path / "holdback_lane_slice"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "B1", "capacity": 100, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"f1","timestamp":1,"op":"INGEST","buffer_id":"B1","lane_id":"A","qty":"10","peer_buffer_id":""}\n'
        '{"event_id":"f2","timestamp":2,"op":"INGEST","buffer_id":"B1","lane_id":"B","qty":"8","peer_buffer_id":""}\n'
        '{"event_id":"h1","timestamp":3,"op":"HOLDBACK","buffer_id":"B1","lane_id":"A","qty":"6","peer_buffer_id":""}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["B1"]["filled"] == 12
    assert rows["B1"]["holdback"] == 6


def test_compound_three_lane_dispatch_holdback_lex_order(tmp_path: Path) -> None:
    """DISPATCH debits holdback lanes in ascending lane_id order before filled lanes."""
    task = tmp_path / "dispatch_lex3"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "D1", "capacity": 100, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"i1","timestamp":1,"op":"INGEST","buffer_id":"D1","lane_id":"M","qty":"5","peer_buffer_id":""}\n'
        '{"event_id":"i2","timestamp":2,"op":"INGEST","buffer_id":"D1","lane_id":"A","qty":"4","peer_buffer_id":""}\n'
        '{"event_id":"i3","timestamp":3,"op":"INGEST","buffer_id":"D1","lane_id":"Z","qty":"3","peer_buffer_id":""}\n'
        '{"event_id":"h1","timestamp":4,"op":"HOLDBACK","buffer_id":"D1","lane_id":"M","qty":"5","peer_buffer_id":""}\n'
        '{"event_id":"h2","timestamp":5,"op":"HOLDBACK","buffer_id":"D1","lane_id":"A","qty":"4","peer_buffer_id":""}\n'
        '{"event_id":"h3","timestamp":6,"op":"HOLDBACK","buffer_id":"D1","lane_id":"Z","qty":"2","peer_buffer_id":""}\n'
        '{"event_id":"d1","timestamp":7,"op":"DISPATCH","buffer_id":"D1","lane_id":"M","qty":"8","peer_buffer_id":""}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["D1"]["holdback"] == 3
    assert rows["D1"]["filled"] == 1
    assert rows["D1"]["dispatched"] == 8


def test_compound_transfer_insufficient_holdback_before_over_capacity(tmp_path: Path) -> None:
    """INSUFFICIENT_HOLDBACK on TRANSFER wins before destination OVER_CAPACITY."""
    task = tmp_path / "xfer_prec"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps(
            [
                {"buffer_id": "SRC", "capacity": 100, "status": "OPEN"},
                {"buffer_id": "DST", "capacity": 12, "status": "OPEN"},
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"s1","timestamp":1,"op":"INGEST","buffer_id":"SRC","lane_id":"L1","qty":"20","peer_buffer_id":""}\n'
        '{"event_id":"s2","timestamp":2,"op":"HOLDBACK","buffer_id":"SRC","lane_id":"L1","qty":"3","peer_buffer_id":""}\n'
        '{"event_id":"d1","timestamp":3,"op":"INGEST","buffer_id":"DST","lane_id":"L1","qty":"10","peer_buffer_id":""}\n'
        '{"event_id":"x1","timestamp":4,"op":"TRANSFER","buffer_id":"SRC","peer_buffer_id":"DST","lane_id":"L1","qty":"8"}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
    assert rejects["x1"] == "INSUFFICIENT_HOLDBACK"
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["SRC"]["holdback"] == 3
    assert rows["DST"]["filled"] == 10


def test_compound_duplicate_before_reject_bad_qty(tmp_path: Path) -> None:
    """Already-applied event_id skips soft reject and counts duplicate_events only."""
    task = tmp_path / "dup_bad_qty"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "B1", "capacity": 20, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"same","timestamp":1,"op":"INGEST","buffer_id":"B1","lane_id":"L1","qty":"5","peer_buffer_id":""}\n'
        '{"event_id":"same","timestamp":2,"op":"INGEST","buffer_id":"B1","lane_id":"L1","qty":"01","peer_buffer_id":""}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    assert _json()["summary"]["duplicate_events"] == 1
    assert [r for r in _csv("rejects.csv") if r["event_id"] == "same"] == []
    assert _json()["buffers"][0]["filled"] == 5


def test_dynamic_transfer_credits_peer_holdback_not_filled(tmp_path: Path) -> None:
    """Runtime-random ids: successful TRANSFER credits peer holdback slice, not filled."""
    uid = uuid.uuid4().hex[:8]
    src = f"S_{uid}"
    dst = f"D_{uid}"
    task = tmp_path / f"dyn_xfer_{uid}"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps(
            [
                {"buffer_id": src, "capacity": 100, "status": "OPEN"},
                {"buffer_id": dst, "capacity": 100, "status": "OPEN"},
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (task / "events" / "flow.jsonl").write_text(
        f'{{"event_id":"a","timestamp":1,"op":"INGEST","buffer_id":"{src}","lane_id":"L1","qty":"15","peer_buffer_id":""}}\n'
        f'{{"event_id":"b","timestamp":2,"op":"HOLDBACK","buffer_id":"{src}","lane_id":"L1","qty":"9","peer_buffer_id":""}}\n'
        f'{{"event_id":"c","timestamp":3,"op":"TRANSFER","buffer_id":"{src}","peer_buffer_id":"{dst}","lane_id":"L1","qty":"7"}}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows[src]["holdback"] == 2
    assert rows[dst]["holdback"] == 7
    assert rows[dst]["filled"] == 0


def test_compound_holdback_rejects_lane_slice_not_buffer_total(tmp_path: Path) -> None:
    """HOLDBACK rejects INSUFFICIENT_FILLED when the event lane slice is too small even if buffer filled suffices."""
    task = tmp_path / "hb_lane_reject"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "B1", "capacity": 100, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"a1","timestamp":1,"op":"INGEST","buffer_id":"B1","lane_id":"A","qty":"2","peer_buffer_id":""}\n'
        '{"event_id":"b1","timestamp":2,"op":"INGEST","buffer_id":"B1","lane_id":"B","qty":"20","peer_buffer_id":""}\n'
        '{"event_id":"h1","timestamp":3,"op":"HOLDBACK","buffer_id":"B1","lane_id":"A","qty":"5","peer_buffer_id":""}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
    assert rejects["h1"] == "INSUFFICIENT_FILLED"
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["B1"]["filled"] == 22
    assert rows["B1"]["holdback"] == 0


def test_compound_release_rejects_lane_slice_not_buffer_total(tmp_path: Path) -> None:
    """RELEASE rejects NOTHING_TO_RELEASE when the event lane slice is empty even if buffer filled is positive."""
    task = tmp_path / "rel_lane_reject"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "B1", "capacity": 100, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"a1","timestamp":1,"op":"INGEST","buffer_id":"B1","lane_id":"A","qty":"15","peer_buffer_id":""}\n'
        '{"event_id":"r1","timestamp":2,"op":"RELEASE","buffer_id":"B1","lane_id":"B","qty":"3","peer_buffer_id":""}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
    assert rejects["r1"] == "NOTHING_TO_RELEASE"
    assert _json()["buffers"][0]["filled"] == 15


def test_compound_commit_rejects_lane_holdback_not_buffer_total(tmp_path: Path) -> None:
    """COMMIT rejects INSUFFICIENT_HOLDBACK when the event lane holdback slice is zero even if buffer holdback is positive."""
    task = tmp_path / "cm_lane_reject"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "B1", "capacity": 100, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"a1","timestamp":1,"op":"INGEST","buffer_id":"B1","lane_id":"B","qty":"10","peer_buffer_id":""}\n'
        '{"event_id":"h1","timestamp":2,"op":"HOLDBACK","buffer_id":"B1","lane_id":"B","qty":"6","peer_buffer_id":""}\n'
        '{"event_id":"c1","timestamp":3,"op":"COMMIT","buffer_id":"B1","lane_id":"A","qty":"2","peer_buffer_id":""}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rejects = {r["event_id"]: r["reason"] for r in _csv("rejects.csv")}
    assert rejects["c1"] == "INSUFFICIENT_HOLDBACK"
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["B1"]["holdback"] == 6
    assert rows["B1"]["filled"] == 4


def test_compound_dispatch_filled_debits_ascending_after_holdback(tmp_path: Path) -> None:
    """After holdback is exhausted, DISPATCH debits remaining qty from filled lanes in ascending lane_id order."""
    task = tmp_path / "disp_filled_lex"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": "B1", "capacity": 100, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "only.jsonl").write_text(
        '{"event_id":"i1","timestamp":1,"op":"INGEST","buffer_id":"B1","lane_id":"Z","qty":"6","peer_buffer_id":""}\n'
        '{"event_id":"i2","timestamp":2,"op":"INGEST","buffer_id":"B1","lane_id":"A","qty":"4","peer_buffer_id":""}\n'
        '{"event_id":"d1","timestamp":3,"op":"DISPATCH","buffer_id":"B1","lane_id":"Z","qty":"5","peer_buffer_id":""}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows["B1"]["filled"] == 5
    assert rows["B1"]["dispatched"] == 5


def test_dynamic_dispatch_holdback_then_filled_lex_order(tmp_path: Path) -> None:
    """Runtime-random ids: DISPATCH spends holdback lanes ascending then filled lanes ascending."""
    uid = uuid.uuid4().hex[:8]
    buf = f"B_{uid}"
    task = tmp_path / f"dyn_lex_{uid}"
    (task / "config").mkdir(parents=True)
    (task / "events").mkdir()
    (task / "config" / "buffers.json").write_text(
        json.dumps([{"buffer_id": buf, "capacity": 200, "status": "OPEN"}]) + "\n",
        encoding="utf-8",
    )
    (task / "events" / "flow.jsonl").write_text(
        f'{{"event_id":"i1","timestamp":1,"op":"INGEST","buffer_id":"{buf}","lane_id":"M","qty":"5","peer_buffer_id":""}}\n'
        f'{{"event_id":"i2","timestamp":2,"op":"INGEST","buffer_id":"{buf}","lane_id":"A","qty":"7","peer_buffer_id":""}}\n'
        f'{{"event_id":"h1","timestamp":3,"op":"HOLDBACK","buffer_id":"{buf}","lane_id":"M","qty":"5","peer_buffer_id":""}}\n'
        f'{{"event_id":"h2","timestamp":4,"op":"HOLDBACK","buffer_id":"{buf}","lane_id":"A","qty":"3","peer_buffer_id":""}}\n'
        f'{{"event_id":"d1","timestamp":5,"op":"DISPATCH","buffer_id":"{buf}","lane_id":"M","qty":"9","peer_buffer_id":""}}\n',
        encoding="utf-8",
    )
    _run_ok_task(task)
    rows = {r["buffer_id"]: r for r in _json()["buffers"]}
    assert rows[buf]["holdback"] == 0
    assert rows[buf]["filled"] == 3
    assert rows[buf]["dispatched"] == 9
