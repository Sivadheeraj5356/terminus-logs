#!/usr/bin/env python3
"""Memory Vault campaign scoring and save-journal playthrough checks."""

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path("/app/environment")
OUT = Path("/app/output")
CASES = ROOT / "cases"
GDB = ROOT / "traces" / "watch-chambers.log"
VG = ROOT / "traces" / "scrub-chambers.txt"
BATCH = "/app/environment/campaign/play.sh"
TRANS = OUT / "transcripts"
EPOCH = OUT / "state" / "hazard.epoch"
JOURNAL = OUT / "state" / "replay.journal"
MANIFEST = OUT / "batch.manifest.json"

# Held-out SHA256 digests of canonicalized oracle transcripts for c01–c06.
# Generated once from a valid oracle run; never derived from agent output at runtime.
BASELINE_DIGESTS = {
    "c01": "5afac1100a70aaadcb1416d7a23bdfa66c372b1d97bf5ed1a56ef1bd7eaf0723",
    "c02": "44d0ca299966adcef1c7a5c5505511405bf9d43d416784ff56612efb0534a5cf",
    "c03": "bbfdc9a63a4930a3894f59eba16321f1bfa0b3a55d15d4e6cc536128de297a5a",
    "c04": "3863d6496e2a17548c6d87bd77755c7d42d7d98b343acdde1a4700edd2c1fe5d",
    "c05": "320f2ce6c29dbc736d46e2f379fbafea1aca9fae128b34445b04b5377c6d1014",
    "c06": "bf74044873b5ea38e92452f9ef391b83c1711c1c1b6550139ef54be2c7ea8928",
}

_SCORE_BONUS = {"WIN": 25, "PARTIAL": 5, "LOSE": -20}
_REQUIRED_FIELDS = {
    "case_id",
    "status",
    "score",
    "moves",
    "visited",
    "inventory",
    "violations",
    "trace_hash",
    "generation",
    "path_summary",
}


def _sha16(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _filtered(path: Path):
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        t = line.strip()
        if t and not t.startswith("#"):
            out.append(t)
    return out


def _moves_fp(lines):
    return _sha16("\n".join(lines).encode())


def _generation() -> str:
    return _sha16(GDB.read_bytes() + b"\n" + VG.read_bytes())


def _canon_digest(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _clear_out() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)


def _run(*extra: str):
    return subprocess.run(["bash", BATCH, *extra], text=True, capture_output=True)


def _run_ok(*extra: str):
    proc = _run(*extra)
    assert proc.returncode == 0, proc.stderr
    return proc


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _case_ids():
    return sorted(p.stem for p in CASES.glob("*.moves"))


def _assert_transcript_contract(got: dict, case_id: str, generation: str) -> None:
    """Validate observable transcript invariants without replaying moves."""
    assert set(got.keys()) >= _REQUIRED_FIELDS
    assert got["case_id"] == case_id
    assert got["generation"] == generation
    assert got["status"] in ("WIN", "LOSE", "PARTIAL")
    assert isinstance(got["score"], int)
    assert isinstance(got["moves"], int) and got["moves"] >= 0
    assert isinstance(got["visited"], list) and got["visited"]
    assert got["visited"][0] == "atrium"
    assert isinstance(got["inventory"], list)
    assert got["inventory"] == sorted(got["inventory"])
    assert isinstance(got["violations"], list)
    assert isinstance(got["trace_hash"], str)
    assert re.fullmatch(r"[0-9a-f]{16}", got["trace_hash"])
    ps = got["path_summary"]
    assert isinstance(ps, dict)
    assert ps["start"] == got["visited"][0]
    assert ps["end"] == got["visited"][-1]
    assert ps["unique_rooms"] == len(set(got["visited"]))
    bonus = _SCORE_BONUS[got["status"]]
    expect_score = 100 - got["moves"] * 2 - len(got["violations"]) * 17 + bonus
    assert got["score"] == expect_score


def _assert_manifest_consistent(man: dict, generation: str, case_ids=None) -> None:
    """Validate each manifest row against its published transcript."""
    if case_ids is None:
        case_ids = _case_ids()
    assert man["generation"] == generation
    assert man["hazard_epoch"] == generation
    rows = man["cases"]
    assert [c["case_id"] for c in rows] == case_ids
    for row in rows:
        cid = row["case_id"]
        got = _load_json(TRANS / f"{cid}.json")
        _assert_transcript_contract(got, cid, generation)
        assert row["case_id"] == got["case_id"]
        assert row["generation"] == got["generation"] == generation
        assert row["status"] == got["status"]
        assert row["score"] == got["score"]
        assert row["moves_fp"] == _moves_fp(_filtered(CASES / f"{cid}.moves"))


def _assert_baseline_digests(case_ids=None) -> None:
    if case_ids is None:
        case_ids = [cid for cid in _case_ids() if cid in BASELINE_DIGESTS]
    for cid in case_ids:
        got = _load_json(TRANS / f"{cid}.json")
        assert _canon_digest(got) == BASELINE_DIGESTS[cid]


def test_clean_batch_fingerprints_and_generation():
    """Clean batch publishes matching transcripts, epoch, journal GEN, and manifest fingerprints."""
    _clear_out()
    _run_ok()
    gen = _generation()
    assert EPOCH.read_text(encoding="utf-8").strip() == gen
    assert JOURNAL.read_text(encoding="utf-8").splitlines()[0] == f"GEN|{gen}"
    man = _load_json(MANIFEST)
    _assert_manifest_consistent(man, gen)
    _assert_baseline_digests()


def test_interrupted_run_recovers_to_clean_result():
    """A --stop-after interrupt then a normal run converges to a clean batch."""
    _clear_out()
    _run_ok()
    clean_man = MANIFEST.read_text(encoding="utf-8")
    clean_c01 = (TRANS / "c01.json").read_text(encoding="utf-8")
    clean_digests = {
        cid: _canon_digest(_load_json(TRANS / f"{cid}.json")) for cid in _case_ids()
    }
    _clear_out()
    _run("--stop-after", "4")
    _run_ok()
    assert MANIFEST.read_text(encoding="utf-8") == clean_man
    assert (TRANS / "c01.json").read_text(encoding="utf-8") == clean_c01
    for cid, digest in clean_digests.items():
        assert _canon_digest(_load_json(TRANS / f"{cid}.json")) == digest


def test_interrupt_during_finalize_does_not_duplicate_exit():
    """Recovery after stopping mid-case must not duplicate EXIT penalties or EVT lines."""
    _clear_out()
    _run("--stop-after", "8")
    _run_ok()
    text = JOURNAL.read_text(encoding="utf-8")
    exits = [ln for ln in text.splitlines() if "|EXIT" in ln and ln.startswith("EVT|")]
    by_case = {}
    for ln in exits:
        cid = ln.split("|")[1]
        by_case[cid] = by_case.get(cid, 0) + 1
    assert by_case
    assert all(v == 1 for v in by_case.values())
    gen = _generation()
    _assert_transcript_contract(_load_json(TRANS / "c01.json"), "c01", gen)
    assert _canon_digest(_load_json(TRANS / "c01.json")) == BASELINE_DIGESTS["c01"]


def test_single_case_invalidation_on_moves_edit():
    """Editing one .moves file regenerates only that case fingerprint/result."""
    _clear_out()
    _run_ok()
    target = sorted(CASES.glob("*.moves"))[1]
    cid = target.stem
    before_canon = {
        x: json.dumps(_load_json(TRANS / f"{x}.json"), sort_keys=True, separators=(",", ":"))
        for x in _case_ids()
    }
    before_fp = _moves_fp(_filtered(target))
    original = target.read_text(encoding="utf-8")
    try:
        target.write_text(original + "\n# marker\nDROP torch\n", encoding="utf-8")
        _run_ok()
        gen = _generation()
        after = {x: _load_json(TRANS / f"{x}.json") for x in _case_ids()}
        for other in _case_ids():
            if other == cid:
                assert (
                    json.dumps(after[other], sort_keys=True, separators=(",", ":"))
                    != before_canon[other]
                )
                _assert_transcript_contract(after[other], other, gen)
            else:
                assert (
                    json.dumps(after[other], sort_keys=True, separators=(",", ":"))
                    == before_canon[other]
                )
        man = _load_json(MANIFEST)
        row = next(c for c in man["cases"] if c["case_id"] == cid)
        new_fp = _moves_fp(_filtered(target))
        assert new_fp != before_fp
        assert row["moves_fp"] == new_fp
        assert row["status"] == after[cid]["status"]
        assert row["score"] == after[cid]["score"]
    finally:
        target.write_text(original, encoding="utf-8")
        _clear_out()
        _run_ok()


def test_trace_change_invalidates_every_case_generation():
    """Mutating Valgrind input changes generation and rewrites all transcripts."""
    _clear_out()
    _run_ok()
    old_gen = EPOCH.read_text(encoding="utf-8").strip()
    old_hashes = {cid: _load_json(TRANS / f"{cid}.json")["trace_hash"] for cid in _case_ids()}
    old_digests = {cid: _canon_digest(_load_json(TRANS / f"{cid}.json")) for cid in _case_ids()}
    original = VG.read_text(encoding="utf-8")
    try:
        VG.write_text(original + "\nnote room=mirror requires=scrub\n", encoding="utf-8")
        _run_ok()
        new_gen = _generation()
        assert new_gen != old_gen
        assert EPOCH.read_text(encoding="utf-8").strip() == new_gen
        man = _load_json(MANIFEST)
        _assert_manifest_consistent(man, new_gen)
        for cid in _case_ids():
            got = _load_json(TRANS / f"{cid}.json")
            assert got["generation"] == new_gen
            assert _canon_digest(got) != old_digests[cid]
            assert got["trace_hash"] != old_hashes[cid] or got["violations"] != []
    finally:
        VG.write_text(original, encoding="utf-8")
        _clear_out()
        _run_ok()


def test_poisoned_transcript_epoch_manifest_are_not_authoritative():
    """Poisoned published artifacts must be regenerated from live inputs."""
    _clear_out()
    _run_ok()
    gen = _generation()
    poison = {"case_id": "c01", "status": "WIN", "score": 999, "generation": "deadbeefdeadbeef"}
    (TRANS / "c01.json").write_text(json.dumps(poison) + "\n", encoding="utf-8")
    EPOCH.write_text("deadbeefdeadbeef\n", encoding="utf-8")
    MANIFEST.write_text(json.dumps({"generation": "deadbeefdeadbeef", "cases": []}) + "\n", encoding="utf-8")
    _run_ok()
    assert EPOCH.read_text(encoding="utf-8").strip() == gen
    assert _canon_digest(_load_json(TRANS / "c01.json")) == BASELINE_DIGESTS["c01"]
    man = _load_json(MANIFEST)
    assert man["generation"] == gen
    assert len(man["cases"]) == len(_case_ids())
    _assert_manifest_consistent(man, gen)
    _assert_baseline_digests()


def test_truncated_journal_tail_recovers():
    """A truncated final journal line is discarded and the batch recovers cleanly."""
    _clear_out()
    _run("--stop-after", "5")
    raw = JOURNAL.read_bytes()
    JOURNAL.write_bytes(raw + b"START|c99|abcd|")
    _run_ok()
    gen = _generation()
    assert _load_json(MANIFEST)["generation"] == gen
    assert _canon_digest(_load_json(TRANS / "c01.json")) == BASELINE_DIGESTS["c01"]
    assert all(not ln.startswith("START|c99|") for ln in JOURNAL.read_text(encoding="utf-8").splitlines())
    _assert_manifest_consistent(_load_json(MANIFEST), gen)
    _assert_baseline_digests()


def test_mid_journal_corruption_preserves_manifest():
    """Corruption in the middle of committed history fails and leaves the last manifest untouched."""
    _clear_out()
    _run_ok()
    saved = MANIFEST.read_text(encoding="utf-8")
    lines = JOURNAL.read_text(encoding="utf-8").splitlines()
    idx = next(i for i, ln in enumerate(lines) if ln.startswith("COMMIT|"))
    lines.insert(idx + 1, "NOTAVALID|record")
    JOURNAL.write_text("\n".join(lines) + "\n", encoding="utf-8")
    proc = _run()
    assert proc.returncode != 0
    assert MANIFEST.read_text(encoding="utf-8") == saved


def test_deleted_case_transcript_removed_from_manifest():
    """Removing a case file drops its transcript and manifest row."""
    _clear_out()
    extra = CASES / "zdrop.moves"
    extra.write_text("MOVE buffer\nEXIT\n", encoding="utf-8")
    try:
        _run_ok()
        assert (TRANS / "zdrop.json").exists()
        assert any(c["case_id"] == "zdrop" for c in _load_json(MANIFEST)["cases"])
        extra.unlink()
        _run_ok()
        leftover = list(TRANS.glob("zdrop.json"))
        assert len(leftover) == 0
        assert all(c["case_id"] != "zdrop" for c in _load_json(MANIFEST)["cases"])
        assert [c["case_id"] for c in _load_json(MANIFEST)["cases"]] == _case_ids()
        gen = _generation()
        _assert_manifest_consistent(_load_json(MANIFEST), gen)
        _assert_baseline_digests()
    finally:
        if extra.exists():
            extra.unlink()


def test_cross_case_state_isolation_clean_and_recovery():
    """Inventory/violations remain isolated across cases in clean and recovery runs."""
    _clear_out()
    _run("--stop-after", "6")
    _run_ok()
    ids = _case_ids()
    gen = _generation()
    a = _load_json(TRANS / f"{ids[0]}.json")
    b = _load_json(TRANS / f"{ids[1]}.json")
    _assert_transcript_contract(a, ids[0], gen)
    _assert_transcript_contract(b, ids[1], gen)
    if ids[0] in BASELINE_DIGESTS:
        assert _canon_digest(a) == BASELINE_DIGESTS[ids[0]]
    if ids[1] in BASELINE_DIGESTS:
        assert _canon_digest(b) == BASELINE_DIGESTS[ids[1]]
    assert a["inventory"] != b["inventory"] or a["violations"] != b["violations"]
    assert a["status"] != b["status"]


def test_commands_after_exit_ignored_and_not_journaled():
    """Commands after the first EXIT must not alter state or create EVT records."""
    path = CASES / "zexit.moves"
    path.write_text(
        "TAKE torch\nMOVE buffer\nTAKE patch\nWAIT\nMOVE heap\nSEAL canary\n"
        "MOVE canary\nTAKE key\nMOVE vault\nEXIT\nDROP key\nMOVE atrium\n",
        encoding="utf-8",
    )
    try:
        _clear_out()
        _run_ok()
        got = _load_json(TRANS / "zexit.json")
        gen = _generation()
        _assert_transcript_contract(got, "zexit", gen)
        cmds = _filtered(path)
        until_exit = []
        for cmd in cmds:
            until_exit.append(cmd)
            if cmd.split()[0] == "EXIT":
                break
        assert got["moves"] == len(until_exit)
        assert "key" in got["inventory"]
        assert got["path_summary"]["end"] == "vault"
        assert got["visited"][-1] == "vault"
        evts = [
            ln
            for ln in JOURNAL.read_text(encoding="utf-8").splitlines()
            if ln.startswith("EVT|zexit|")
        ]
        assert sum(1 for ln in evts if ln.endswith("|EXIT")) == 1
        assert sum(1 for ln in evts if ln.endswith("|DROP key")) == 0
        assert sum(1 for ln in evts if ln.endswith("|MOVE atrium")) == 0
        man = _load_json(MANIFEST)
        row = next(c for c in man["cases"] if c["case_id"] == "zexit")
        assert row["moves_fp"] == _moves_fp(cmds)
        assert row["status"] == got["status"]
        assert row["score"] == got["score"]
    finally:
        path.unlink(missing_ok=True)
        _clear_out()
        _run_ok()


def test_idempotent_rerun_of_clean_batch():
    """Rerunning an already clean batch keeps transcripts and manifest stable."""
    _clear_out()
    _run_ok()
    man1 = MANIFEST.read_text(encoding="utf-8")
    t1 = {cid: (TRANS / f"{cid}.json").read_text(encoding="utf-8") for cid in _case_ids()}
    _run_ok()
    assert MANIFEST.read_text(encoding="utf-8") == man1
    for cid, body in t1.items():
        assert (TRANS / f"{cid}.json").read_text(encoding="utf-8") == body
    _assert_baseline_digests()
