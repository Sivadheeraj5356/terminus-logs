"""Behavior checks for PIT feature materialization (Go)."""
from __future__ import annotations

import json
import string
import subprocess
from pathlib import Path

import pytest

OUT = Path("/app/output/pit_report.json")
JOURNAL = Path("/app/output/.pit_journal")
HEX_CHARS = set(string.hexdigits.lower())
# Bound tool runtime so a hung agent binary cannot burn the verifier budget
# (platform kills the run before CTRF/reward → verifier_did_not_run).
COMPILE_TIMEOUT_SEC = 60
TOOL_TIMEOUT_SEC = 15


def _bank_path() -> Path:
    matches = sorted(Path(__file__).resolve().parent.glob("*_bank.json"))
    if not matches:
        raise FileNotFoundError("gold bank missing under /tests")
    return matches[0]


def _bank_slice(fold_id: str) -> dict:
    return json.loads(_bank_path().read_text(encoding="utf-8"))[fold_id]


def _compile_binary() -> None:
    subprocess.run(
        ["bash", "/app/environment/scripts/mk_all.sh"],
        check=True,
        cwd="/app",
        timeout=COMPILE_TIMEOUT_SEC,
    )


def _emit_ledger(fold_id: str) -> dict:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "/app/environment/bin/pitctl",
            "materialize",
            "--fold",
            fold_id,
            "--out",
            str(OUT),
        ],
        check=True,
        timeout=TOOL_TIMEOUT_SEC,
    )
    return json.loads(OUT.read_text(encoding="utf-8"))


def _journal_probe(fold_id: str) -> dict:
    proc = subprocess.run(
        [
            "/app/environment/bin/pitctl",
            "verify",
            "--fold",
            fold_id,
            "--report",
            str(OUT),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=TOOL_TIMEOUT_SEC,
    )
    return json.loads(proc.stdout)


@pytest.fixture(scope="module", autouse=True)
def _warm_toolchain() -> None:
    _compile_binary()


def test_ledger_alpha_matches_gold_bank() -> None:
    """fold_a rows audit and digest match the bank."""
    report = _emit_ledger("fold_a")
    exp = _bank_slice("fold_a")
    assert report["fold_id"] == "fold_a"
    assert report["row_count"] == exp["row_count"]
    assert report["rows"] == exp["rows"]
    assert report["audit_trace"] == exp["audit_trace"]
    assert report["ledger_digest"] == exp["ledger_digest"]
    assert len(report["rows"]) == report["row_count"]


def test_horizon_dual_set_on_bravo() -> None:
    """fold_b keeps late ingest in candidates while excluding it from early choice."""
    report = _emit_ledger("fold_b")
    exp = _bank_slice("fold_b")
    assert report["rows"] == exp["rows"]
    assert report["audit_trace"] == exp["audit_trace"]
    assert report["ledger_digest"] == exp["ledger_digest"]
    for entry in report["audit_trace"]:
        if entry["chosen_rev"]:
            assert entry["chosen_rev"] in entry["candidate_revs"]
            assert entry["policy"] == "asof_wm"
        assert entry["candidate_revs"] == sorted(entry["candidate_revs"])
        assert entry["request_entity"]
        assert entry["resolved_entity"]


def test_identity_chain_poison_on_charlie() -> None:
    """fold_c resolves time-scoped alias chains and rejects poison keyed rows."""
    report = _emit_ledger("fold_c")
    exp = _bank_slice("fold_c")
    assert report["rows"] == exp["rows"]
    assert report["audit_trace"] == exp["audit_trace"]
    assert report["ledger_digest"] == exp["ledger_digest"]
    assert report["row_count"] == len(report["rows"])
    for row in report["rows"]:
        assert "feat_rev" in row
        assert "feat_hash" in row
        assert row["entity_id"] != "poison_z9"
        assert row["entity_id"] != "dead_end_z"


def test_tie_miss_and_revocation_on_delta() -> None:
    """fold_d applies tie break miss policy and revoked exclusion."""
    report = _emit_ledger("fold_d")
    exp = _bank_slice("fold_d")
    assert report["rows"] == exp["rows"]
    assert report["audit_trace"] == exp["audit_trace"]
    assert report["ledger_digest"] == exp["ledger_digest"]
    miss = [a for a in report["audit_trace"] if a["policy"] == "miss"]
    assert miss
    for entry in miss:
        assert entry["chosen_rev"] == ""
        assert entry["candidate_revs"]
        assert entry["policy"] != "asof_wm"


def test_multipack_overlay_last_revision_wins() -> None:
    """later put frames override earlier revisions with the same rev_id."""
    report = _emit_ledger("fold_d")
    exp = _bank_slice("fold_d")
    assert report["rows"] == exp["rows"]
    assert report["audit_trace"] == exp["audit_trace"]
    assert report["ledger_digest"] == exp["ledger_digest"]
    fold_id = "fold_d"
    fold_cfg = json.loads(
        (Path("/app/environment/data/cfgs") / f"{fold_id}.json").read_text(encoding="utf-8")
    )
    packs = fold_cfg["feature_packs"]
    base_frames = json.loads(
        Path(f"/app/environment/data/features/{packs[0]}.json").read_text(encoding="utf-8")
    )
    overlay_frames = json.loads(
        Path(f"/app/environment/data/features/{packs[1]}.json").read_text(encoding="utf-8")
    )
    base = {
        fr["rev"]["rev_id"]: fr["rev"]
        for fr in base_frames
        if fr.get("op") == "put" and fr.get("rev")
    }
    overlay = {
        fr["rev"]["rev_id"]: fr["rev"]
        for fr in overlay_frames
        if fr.get("op") == "put" and fr.get("rev")
    }
    shared = set(base) & set(overlay)
    assert shared
    for rev_id in shared:
        rows = [r for r in report["rows"] if r["feat_rev"] == rev_id]
        assert len(rows) == 1
        assert rows[0]["values"] == overlay[rev_id]["values"]
        assert rows[0]["values"] != base[rev_id]["values"]


def test_kill_frame_marks_revoked() -> None:
    """kill frames mark prior puts revoked so they are never chosen."""
    report = _emit_ledger("fold_b")
    exp = _bank_slice("fold_b")
    assert report["ledger_digest"] == exp["ledger_digest"]
    assert report["rows"] == exp["rows"]
    frames = json.loads(
        Path("/app/environment/data/features/pk_w.json").read_text(encoding="utf-8")
    )
    killed = {fr["rev_id"] for fr in frames if fr.get("op") == "kill"}
    assert killed
    chosen = {a["chosen_rev"] for a in report["audit_trace"]}
    cands = set()
    for a in report["audit_trace"]:
        cands.update(a["candidate_revs"])
    for rev_id in killed:
        assert rev_id not in chosen
        assert rev_id in cands


def test_lag_shifts_valid_from_on_echo() -> None:
    """fold_e lag shifts valid_from horizon without changing asof_ms."""
    report = _emit_ledger("fold_e")
    exp = _bank_slice("fold_e")
    assert report["rows"] == exp["rows"]
    assert report["audit_trace"] == exp["audit_trace"]
    assert report["ledger_digest"] == exp["ledger_digest"]
    for row, want in zip(report["rows"], exp["rows"], strict=True):
        assert row["asof_ms"] == want["asof_ms"]
        assert row["entity_id"] == want["entity_id"]
        assert row["feat_rev"] == want["feat_rev"]


def test_frontier_memo_isolates_event_times() -> None:
    """same entity at different event_ms can select different revisions."""
    report = _emit_ledger("fold_a")
    by_ent: dict[str, set[str]] = {}
    for row in report["rows"]:
        entity_id = row["entity_id"]
        if entity_id not in by_ent:
            by_ent[entity_id] = set()
        by_ent[entity_id].add(row["feat_rev"])
    multi = [revs for revs in by_ent.values() if len(revs) > 1]
    assert multi
    exp = _bank_slice("fold_a")
    assert report["ledger_digest"] == exp["ledger_digest"]


def test_entity_bound_feat_hash_on_alpha() -> None:
    """feat_hash on fold_a matches bank under entity-aware canonical hashing."""
    report = _emit_ledger("fold_a")
    exp = _bank_slice("fold_a")
    for got, want in zip(report["rows"], exp["rows"], strict=True):
        assert got["feat_hash"] == want["feat_hash"]
        assert list(got["values"].keys()) == sorted(got["values"].keys())
        assert got["entity_id"] == want["entity_id"]
        assert got["event_id"] == want["event_id"]


def test_repeat_materialize_is_byte_stable() -> None:
    """two materialize runs of fold_b yield identical reports and matching journals."""
    fold_id = "fold_b"
    first = _emit_ledger(fold_id)
    second = _emit_ledger(fold_id)
    assert first == second
    journal = json.loads((JOURNAL / f"{fold_id}.json").read_text(encoding="utf-8"))
    assert journal["ledger_digest"] == second["ledger_digest"]
    assert journal["row_count"] == second["row_count"]
    assert journal["fold_id"] == fold_id
    assert journal["seg_digests"]
    assert len(journal["ledger_digest"]) == len(second["ledger_digest"])
    assert len(second["ledger_digest"]) > 0
    assert all(c in HEX_CHARS for c in second["ledger_digest"])


def test_journal_segs_reconstruct_ledger() -> None:
    """journal seg_digests reconstruct the report ledger_digest under verify."""
    report = _emit_ledger("fold_a")
    journal = json.loads((JOURNAL / "fold_a.json").read_text(encoding="utf-8"))
    assert len(journal["seg_digests"]) == report["row_count"]
    payload = _journal_probe("fold_a")
    assert payload["reason"] == "match"
    assert payload["report_digest"] == report["ledger_digest"]
    assert payload["journal_digest"] == report["ledger_digest"]


def test_verify_accepts_clean_ledger_pair() -> None:
    """pitctl verify succeeds after a clean materialize."""
    report = _emit_ledger("fold_a")
    payload = _journal_probe("fold_a")
    assert payload["reason"] == "match"
    assert payload["report_digest"] == report["ledger_digest"]
    assert payload["journal_digest"] == report["ledger_digest"]
    assert payload["report_digest"] == payload["journal_digest"]


def test_verify_rejects_tampered_report_digest() -> None:
    """verify succeeds on a clean ledger then fails after digest tamper."""
    _emit_ledger("fold_c")
    good = _journal_probe("fold_c")
    assert good["reason"] == "match"
    report = json.loads(OUT.read_text(encoding="utf-8"))
    report["ledger_digest"] = "f" * len(good["journal_digest"])
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    proc = subprocess.run(
        [
            "/app/environment/bin/pitctl",
            "verify",
            "--fold",
            "fold_c",
            "--report",
            str(OUT),
        ],
        capture_output=True,
        text=True,
        timeout=TOOL_TIMEOUT_SEC,
    )
    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload["reason"] == "journal_mismatch"
    assert payload["report_digest"] != payload["journal_digest"]


def test_five_graded_packs_diverge_on_digest() -> None:
    """five graded folds match bank digests and remain pairwise distinct."""
    digests = []
    for fold_id in ("fold_a", "fold_b", "fold_c", "fold_d", "fold_e"):
        report = _emit_ledger(fold_id)
        exp = _bank_slice(fold_id)
        digests.append(report["ledger_digest"])
        assert report["fold_id"] == fold_id
        assert report["row_count"] == len(report["rows"])
        assert report["ledger_digest"] == exp["ledger_digest"]
        assert report["rows"] == exp["rows"]
        assert report["audit_trace"] == exp["audit_trace"]
    assert len(set(digests)) == 5
    assert all(len(d) == len(digests[0]) for d in digests)
    assert all(all(c in HEX_CHARS for c in d) for d in digests)


def test_revoked_stays_candidate_never_chosen() -> None:
    """fold_b inclusive horizon; revoked revs stay candidates only."""
    fold_id = "fold_b"
    report = _emit_ledger(fold_id)
    exp = _bank_slice(fold_id)
    assert report["rows"] == exp["rows"]
    assert report["ledger_digest"] == exp["ledger_digest"]
    fold_cfg = json.loads(
        Path(f"/app/environment/data/cfgs/{fold_id}.json").read_text(encoding="utf-8")
    )
    pack = fold_cfg["feature_packs"][0]
    frames = json.loads(
        Path(f"/app/environment/data/features/{pack}.json").read_text(encoding="utf-8")
    )
    revoked = set()
    for fr in frames:
        if fr.get("op") == "put" and fr.get("rev") and fr["rev"].get("revoked"):
            revoked.add(fr["rev"]["rev_id"])
        if fr.get("op") == "kill":
            revoked.add(fr["rev_id"])
    assert revoked
    chosen = {a["chosen_rev"] for a in report["audit_trace"]}
    for rev_id in revoked:
        assert rev_id not in chosen
    cands = set()
    for a in report["audit_trace"]:
        cands.update(a["candidate_revs"])
    assert any(rev_id in cands for rev_id in revoked)
    assert report["row_count"] == len(report["audit_trace"])


def test_offline_train_eval_is_leak_free() -> None:
    """clean fold_a materialize yields a leak-free offline train/eval metric."""
    _emit_ledger("fold_a")
    metrics_path = Path("/app/output/train_metrics.json")
    subprocess.run(
        [
            "python3",
            "/app/environment/trainkit/fit_eval.py",
            "--report",
            str(OUT),
            "--out",
            str(metrics_path),
        ],
        check=True,
        timeout=TOOL_TIMEOUT_SEC,
    )
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["fold_id"] == "fold_a"
    assert metrics["leakage_hits"] == 0
    assert metrics["training_ok"] is True
    assert 0.0 <= float(metrics["holdout_accuracy"]) <= 1.0
    assert metrics["train_rows"] >= 1
    assert metrics["holdout_rows"] >= 1
