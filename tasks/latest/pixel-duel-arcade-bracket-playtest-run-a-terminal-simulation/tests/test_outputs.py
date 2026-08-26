"""Pixel Duel arcade playtest verifier — seven deskctl simulation atlas snapshots.

Ingest lanes load rival CSV fixtures from /app/data; export probes write JSON
snapshots under /app/output. Stages run in dependency order (ledgers -> referee
-> verdicts -> combos -> seal -> rules -> fw). Hidden verifier fixtures under
/opt/verifier-fixtures/ exercise alternate ingest and firmware policy paths.
Each probe regenerates its own snapshot through deskctl and asserts against the
public contracts in /app/docs. Digest assertions use independent reference_*
recomputations so the snapshots cannot be hardcoded.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path

MERGE = Path("/app/output/rival_merge.json")
POLL = Path("/app/output/referee_poll.json")
VERDICTS = Path("/app/output/verdict_snapshots.json")
COMBO_OUTPUT = Path("/app/output/combo_audit.json")
SEAL_OUTPUT = Path("/app/output/bracket_seal.json")
RULES_OUTPUT = Path("/app/output/rules_audit.json")
FW_OUTPUT = Path("/app/output/fw_audit.json")
POLICY_JSON = Path("/app/config/firmware_policy.json")

TB3_Q7_A_SWAP = Path("/opt/verifier-fixtures/TB3_q7_a_swap.csv")
TB3_POLICY_LIMIT = Path("/opt/verifier-fixtures/TB3_policy_limit.json")

Q7_A = Path("/app/data/q7_a.csv")
Q7_B = Path("/app/data/q7_b.csv")
OVERLAY_CSV = Path("/app/data/q7_overlay.csv")
SEED_SQL = Path("/app/data/seed_bootstrap.sql")
SQLITE_DB = Path("/app/run/move_rules.sqlite")


# ---------------------------------------------------------------------------
# Stage 1 — rival ledger merge (tb3-pixel-duel-01)
# ---------------------------------------------------------------------------


def _m1_run_ledgers_probe() -> dict:
    """Remove stale merge output and regenerate rival_merge.json through deskctl."""
    MERGE.unlink(missing_ok=True)
    subprocess.run(["bash", "/app/scripts/desk_init.sh"], check=True)
    subprocess.run(["bash", "/app/scripts/build_all.sh"], check=True)
    subprocess.run(["bash", "/app/scripts/milestone_probes.sh", "ledgers"], check=True)
    assert MERGE.is_file(), "ledgers probe must create rival_merge.json"
    return json.loads(MERGE.read_text())


def _m1_boot_and_probe() -> dict:
    """Run the full ledgers probe pipeline."""
    return _m1_run_ledgers_probe()


class TestLedgerMerge:
    """Ledger merge probe checks (tb3-pixel-duel-01)."""

    def test_m1_probe_regenerates_output(self) -> None:
        """Playtest replay must regenerate rival_merge.json after deleting the prior snapshot."""
        data = _m1_boot_and_probe()
        assert data["schema_tag"] == "tb3-pixel-duel-01"

    def test_m1_schema_tag(self) -> None:
        """rival_merge.json must carry the stage-1 schema tag."""
        data = _m1_boot_and_probe()
        assert data["schema_tag"] == "tb3-pixel-duel-01"

    def test_m1_q7_a_rows(self) -> None:
        """q7_a lane row count must match the bundled sample data."""
        data = _m1_boot_and_probe()
        assert data["q7_a_rows"] == 4

    def test_m1_q7_b_rows(self) -> None:
        """q7_b lane row count must match the bundled sample data."""
        data = _m1_boot_and_probe()
        assert data["q7_b_rows"] == 4

    def test_m1_merged_count(self) -> None:
        """Merged round count must cover every distinct round_id across both lanes."""
        data = _m1_boot_and_probe()
        assert data["merged_count"] == 4

    def test_m1_dispute_ids(self) -> None:
        """Disputed round ids must list rounds where lane winners diverge."""
        data = _m1_boot_and_probe()
        assert data["dispute_ids"] == [102, 103]

    def test_m1_round_order(self) -> None:
        """Merged rounds must sort by round_id even when q7_a row order differs."""
        original_a = Q7_A.read_text()
        shuffled = """round_id,cabinet_tag,p1_action,p2_action,winner_side
103,red-cab,up,down,side_a
101,red-cab,strike,blink,side_a
104,red-cab,blink,strike,side_b
102,red-cab,left,right,side_b
"""
        try:
            Q7_A.write_text(shuffled)
            data = _m1_run_ledgers_probe()
            rounds = [row["round_id"] for row in data["merged_rounds"]]
            assert rounds == [101, 102, 103, 104]
        finally:
            Q7_A.write_text(original_a)
            _m1_run_ledgers_probe()

    def test_m1_merged_round_winners(self) -> None:
        """Each merged_round must carry per-lane winner sides from both CSVs."""
        data = _m1_boot_and_probe()
        expected = {
            101: {"q7_a_winner": "side_a", "q7_b_winner": "side_a"},
            102: {"q7_a_winner": "side_b", "q7_b_winner": "side_a"},
            103: {"q7_a_winner": "side_a", "q7_b_winner": "side_b"},
            104: {"q7_a_winner": "side_b", "q7_b_winner": "side_b"},
        }
        by_id = {row["round_id"]: row for row in data["merged_rounds"]}
        assert set(by_id) == set(expected)
        for rid, winners in expected.items():
            row = by_id[rid]
            assert row["q7_a_winner"] == winners["q7_a_winner"]
            assert row["q7_b_winner"] == winners["q7_b_winner"]

    def test_m1_dynamic_row_count(self) -> None:
        """Appending a q7_a row must increase parsed row and merge counts."""
        original_a = Q7_A.read_text()
        try:
            Q7_A.write_text(original_a.rstrip("\n") + "\n105,red-cab,jab,cross,side_a\n")
            data = _m1_run_ledgers_probe()
            assert data["q7_a_rows"] == 5
            assert data["merged_count"] == 5
        finally:
            Q7_A.write_text(original_a)
            _m1_run_ledgers_probe()

    def test_m1_dynamic_dispute_ids(self) -> None:
        """Aligning a previously disputed winner must shrink dispute_ids."""
        original_a = Q7_A.read_text()
        try:
            lines = original_a.strip().splitlines()
            lines[2] = "102,red-cab,left,right,side_a"
            Q7_A.write_text("\n".join(lines) + "\n")
            data = _m1_run_ledgers_probe()
            assert data["dispute_ids"] == [103]
        finally:
            Q7_A.write_text(original_a)
            _m1_run_ledgers_probe()


# ---------------------------------------------------------------------------
# Stage 2 — referee poll (tb3-pixel-duel-02)
# ---------------------------------------------------------------------------


def _m2_boot_and_probe() -> dict:
    """Remove stale output and regenerate referee_poll.json through deskctl."""
    POLL.unlink(missing_ok=True)
    subprocess.run(["bash", "/app/scripts/ref_svc_start.sh"], check=True)
    subprocess.run(["bash", "/app/scripts/milestone_probes.sh", "referee"], check=True)
    assert POLL.is_file(), "referee probe must create referee_poll.json"
    return json.loads(POLL.read_text())


class TestRefereePoll:
    """Referee poll probe checks (tb3-pixel-duel-02)."""

    def test_m2_probe_regenerates_output(self) -> None:
        """Rerunning the referee probe must recreate poll data matching the merge disputes."""
        assert MERGE.is_file(), "rival_merge.json from stage 1 is required"
        merge = json.loads(MERGE.read_text())
        data = _m2_boot_and_probe()
        assert data["schema_tag"] == "tb3-pixel-duel-02"
        assert data["dispute_count"] == len(merge.get("dispute_ids", []))

    def test_m2_schema_tag(self) -> None:
        """referee_poll.json must carry the stage-2 schema tag."""
        data = _m2_boot_and_probe()
        assert data["schema_tag"] == "tb3-pixel-duel-02"

    def test_m2_dispute_count(self) -> None:
        """Live poll must return both disputed rounds from the merge snapshot."""
        data = _m2_boot_and_probe()
        assert data["dispute_count"] == 2

    def test_m2_ruling_side_102(self) -> None:
        """Round 102 ruling must match the live referee service."""
        data = _m2_boot_and_probe()
        row = next(d for d in data["disputes"] if d["round_id"] == 102)
        assert row["ruling_side"] == "side_b"

    def test_m2_ruling_side_103(self) -> None:
        """Round 103 ruling must match the live referee service."""
        data = _m2_boot_and_probe()
        row = next(d for d in data["disputes"] if d["round_id"] == 103)
        assert row["ruling_side"] == "side_a"

    def test_m2_fw_q7_a(self) -> None:
        """q7_a firmware must come from the referee cabinet_meta block."""
        data = _m2_boot_and_probe()
        assert data["fw_q7_a"] == "1.4.2"

    def test_m2_fw_q7_b(self) -> None:
        """q7_b firmware must come from the referee cabinet_meta block."""
        data = _m2_boot_and_probe()
        assert data["fw_q7_b"] == "1.4.1"


# ---------------------------------------------------------------------------
# Stage 3 — verdict snapshots (tb3-pixel-duel-03)
# ---------------------------------------------------------------------------


def reference_verdicts_digest(verdicts: list[dict]) -> str:
    """Independently recompute batch_digest from the produced verdicts array."""
    normalized = [dict(sorted(row.items())) for row in verdicts]
    canonical = json.dumps(normalized, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _m3_boot_and_probe() -> dict:
    """Remove stale output and regenerate verdict_snapshots.json through deskctl."""
    assert MERGE.is_file(), "rival_merge.json from stage 1 is required"
    assert POLL.is_file(), "referee_poll.json from stage 2 is required"
    VERDICTS.unlink(missing_ok=True)
    subprocess.run(["bash", "/app/scripts/milestone_probes.sh", "verdicts"], check=True)
    assert VERDICTS.is_file(), "verdicts probe must create verdict_snapshots.json"
    return json.loads(VERDICTS.read_text())


def _m3_verdict(data: dict, round_id: int) -> dict:
    """Return the verdict object for a given round_id."""
    return next(v for v in data["verdicts"] if v["round_id"] == round_id)


class TestVerdictSnapshots:
    """Verdict snapshot probe checks (tb3-pixel-duel-03)."""

    def test_m3_probe_regenerates_output(self) -> None:
        """Rerunning the verdicts probe must recreate a snapshot with every round."""
        data = _m3_boot_and_probe()
        assert data["schema_tag"] == "tb3-pixel-duel-03"
        assert len(data["verdicts"]) == 4

    def test_m3_schema_tag(self) -> None:
        """verdict_snapshots.json must carry the stage-3 schema tag."""
        data = _m3_boot_and_probe()
        assert data["schema_tag"] == "tb3-pixel-duel-03"

    def test_m3_void_round(self) -> None:
        """Round 103 must void when move sequences violate imported rules."""
        data = _m3_boot_and_probe()
        row = _m3_verdict(data, 103)
        assert row["winner"] == "void"
        assert row["resolution_source"] == "rule_void"
        assert row["moves_valid"] is False

    def test_m3_referee_round(self) -> None:
        """Round 102 must follow the referee ruling when lanes disagree."""
        data = _m3_boot_and_probe()
        row = _m3_verdict(data, 102)
        assert row["winner"] == "side_b"
        assert row["resolution_source"] == "referee"
        assert row["moves_valid"] is True

    def test_m3_agree_round(self) -> None:
        """Round 101 must keep the shared lane winner when lanes agree."""
        data = _m3_boot_and_probe()
        row = _m3_verdict(data, 101)
        assert row["winner"] == "side_a"
        assert row["resolution_source"] == "cabinet_agree"
        assert row["moves_valid"] is True

    def test_m3_agree_round_104(self) -> None:
        """Round 104 must keep the shared lane winner when lanes agree."""
        data = _m3_boot_and_probe()
        row = _m3_verdict(data, 104)
        assert row["winner"] == "side_b"
        assert row["resolution_source"] == "cabinet_agree"
        assert row["moves_valid"] is True

    def test_m3_batch_digest(self) -> None:
        """Verdict atlas batch_digest must match the independent replay hash invariant."""
        data = _m3_boot_and_probe()
        assert data["batch_digest"] == reference_verdicts_digest(data["verdicts"])


# ---------------------------------------------------------------------------
# Stage 4 — combo audit and bracket seal (tb3-pixel-duel-04/05)
# ---------------------------------------------------------------------------


def _m4_run_combos_probe() -> dict:
    """Remove stale combo output and regenerate combo_audit.json through deskctl."""
    COMBO_OUTPUT.unlink(missing_ok=True)
    subprocess.run(["bash", "/app/scripts/milestone_probes.sh", "combos"], check=True)
    assert COMBO_OUTPUT.is_file(), "combos probe must create combo_audit.json"
    return json.loads(COMBO_OUTPUT.read_text())


def _m4_boot_combos_probe() -> dict:
    """Run the combos probe pipeline after verifying stage-3 output exists."""
    assert VERDICTS.is_file(), "verdict_snapshots.json from stage 3 is required"
    return _m4_run_combos_probe()


def reference_seal_digest(combo_total: int, void_ids: list[int], upstream: str) -> str:
    """Independently recompute seal_digest from the canonical seal bundle."""
    payload = {
        "combo_total": combo_total,
        "overlay_void_ids": void_ids,
        "upstream_digest": upstream,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _m4_run_seal_probe() -> dict:
    """Remove stale seal output and regenerate bracket_seal.json through deskctl."""
    SEAL_OUTPUT.unlink(missing_ok=True)
    subprocess.run(["bash", "/app/scripts/milestone_probes.sh", "seal"], check=True)
    assert SEAL_OUTPUT.is_file(), "seal probe must create bracket_seal.json"
    return json.loads(SEAL_OUTPUT.read_text())


def _m4_boot_seal_probe() -> dict:
    """Run the seal probe pipeline after verifying upstream artifacts exist."""
    assert VERDICTS.is_file(), "verdict_snapshots.json from stage 3 is required"
    assert COMBO_OUTPUT.is_file(), "combo_audit.json from this stage is required"
    assert OVERLAY_CSV.is_file(), "q7_overlay.csv overlay data is required"
    return _m4_run_seal_probe()


def _m4_overlay(data: dict, round_id: int) -> dict:
    """Return the overlay verdict object for a given round_id."""
    return next(v for v in data["overlay_verdicts"] if v["round_id"] == round_id)


class TestComboAuditAndSeal:
    """Combo audit and bracket seal probe checks (tb3-pixel-duel-04/05)."""

    def test_m4_probe_regenerates_output(self) -> None:
        """Rerunning the combos probe must recreate combo_audit.json."""
        data = _m4_boot_combos_probe()
        assert data["schema_tag"] == "tb3-pixel-duel-04"

    def test_m4_schema_tag(self) -> None:
        """combo_audit.json must carry the stage-4 schema tag."""
        data = _m4_boot_combos_probe()
        assert data["schema_tag"] == "tb3-pixel-duel-04"

    def test_m4_combo_total(self) -> None:
        """Combo score atlas total must sum matched move-chain prefixes on playtest rounds."""
        data = _m4_boot_combos_probe()
        assert data["combo_total"] == 5

    def test_m4_rounds_scored(self) -> None:
        """Only move-valid rounds with a prefix hit count as scored."""
        data = _m4_boot_combos_probe()
        assert data["rounds_scored"] == 2

    def test_m4_skips_void_round(self) -> None:
        """Round 103 must not appear in combo hits after rule void."""
        data = _m4_boot_combos_probe()
        hit_ids = [row["round_id"] for row in data["combo_hits"]]
        assert 103 not in hit_ids

    def test_m4_hit_round_101(self) -> None:
        """Round 101 must match the strike,blink chain prefix."""
        data = _m4_boot_combos_probe()
        row = next(h for h in data["combo_hits"] if h["round_id"] == 101)
        assert row["chain_id"] == 1
        assert row["bonus_pts"] == 3
        assert row["matched_prefix"] == "strike,blink"

    def test_m4_hit_round_104(self) -> None:
        """Round 104 must match the blink,strike chain prefix."""
        data = _m4_boot_combos_probe()
        row = next(h for h in data["combo_hits"] if h["round_id"] == 104)
        assert row["chain_id"] == 2
        assert row["bonus_pts"] == 2
        assert row["matched_prefix"] == "blink,strike"

    def test_m4_hit_order(self) -> None:
        """Combo hits must be sorted by round_id ascending."""
        data = _m4_boot_combos_probe()
        ids = [row["round_id"] for row in data["combo_hits"]]
        assert ids == sorted(ids)
        assert ids == [101, 104]

    def test_m4_reads_from_sqlite(self) -> None:
        """combo_total must track bonus_pts values loaded from combo_rules."""
        conn = sqlite3.connect(SQLITE_DB)
        original_pts = conn.execute(
            "SELECT bonus_pts FROM combo_rules WHERE chain_id = 1"
        ).fetchone()[0]
        try:
            conn.execute("UPDATE combo_rules SET bonus_pts = 7 WHERE chain_id = 1")
            conn.commit()
            data = _m4_run_combos_probe()
            assert data["combo_total"] == 9
            row = next(h for h in data["combo_hits"] if h["round_id"] == 101)
            assert row["bonus_pts"] == 7
        finally:
            conn.execute(
                "UPDATE combo_rules SET bonus_pts = ? WHERE chain_id = 1",
                (original_pts,),
            )
            conn.commit()
            conn.close()
            _m4_run_combos_probe()

    def test_m4_respects_verdicts_filtering(self) -> None:
        """Voiding a round in verdict_snapshots must exclude it from combo hits."""
        original = VERDICTS.read_text()
        try:
            vdata = json.loads(original)
            for verdict in vdata["verdicts"]:
                if verdict["round_id"] == 101:
                    verdict["moves_valid"] = False
            VERDICTS.write_text(json.dumps(vdata) + "\n")
            data = _m4_run_combos_probe()
            hit_ids = [row["round_id"] for row in data["combo_hits"]]
            assert 101 not in hit_ids
            assert data["rounds_scored"] == 1
            assert data["combo_total"] == 2
        finally:
            VERDICTS.write_text(original)
            _m4_run_combos_probe()

    def test_m4_seal_probe_regenerates_output(self) -> None:
        """Rerunning the seal probe must recreate bracket_seal.json."""
        data = _m4_boot_seal_probe()
        assert data["schema_tag"] == "tb3-pixel-duel-05"

    def test_m4_seal_schema_tag(self) -> None:
        """bracket_seal.json must carry the stage-5 schema tag."""
        data = _m4_boot_seal_probe()
        assert data["schema_tag"] == "tb3-pixel-duel-05"

    def test_m4_seal_overlay_rows(self) -> None:
        """Overlay CSV must contribute two data rows excluding blanks."""
        data = _m4_boot_seal_probe()
        assert data["overlay_rows"] == 2

    def test_m4_seal_forfeit_void(self) -> None:
        """Forfeit overlay rows must void regardless of winner_side."""
        data = _m4_boot_seal_probe()
        assert data["overlay_void_ids"] == [105]
        row = _m4_overlay(data, 105)
        assert row["winner"] == "void"
        assert row["resolution_source"] == "forfeit"

    def test_m4_seal_overlay_lane_row(self) -> None:
        """Non-forfeit overlay rows keep winner_side with overlay_lane source."""
        data = _m4_boot_seal_probe()
        row = _m4_overlay(data, 106)
        assert row["winner"] == "side_a"
        assert row["resolution_source"] == "overlay_lane"

    def test_m4_seal_upstream_digest(self) -> None:
        """Seal bundle must chain the stage-3 batch_digest."""
        data = _m4_boot_seal_probe()
        verdicts = json.loads(VERDICTS.read_text())
        assert data["upstream_digest"] == verdicts["batch_digest"]

    def test_m4_seal_combo_total(self) -> None:
        """Seal bundle must copy combo_total from combo audit."""
        data = _m4_boot_seal_probe()
        assert data["combo_total"] == 5

    def test_m4_seal_digest(self) -> None:
        """Bracket seal_digest must match the independent seal atlas replay recipe."""
        data = _m4_boot_seal_probe()
        assert data["seal_digest"] == reference_seal_digest(
            data["combo_total"],
            data["overlay_void_ids"],
            data["upstream_digest"],
        )


# ---------------------------------------------------------------------------
# Stage 5 — move-rule store audit and firmware policy audit (tb3-pixel-duel-06/07)
# ---------------------------------------------------------------------------


def reference_store_digest(
    action_count: int,
    blocked_count: int,
    combo_count: int,
    orphan_round_ids: list[int],
) -> str:
    """Independently recompute store_digest from the canonical store summary."""
    payload = {
        "action_count": action_count,
        "blocked_count": blocked_count,
        "combo_count": combo_count,
        "orphan_round_ids": orphan_round_ids,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def reference_fw_audit_digest(
    fw_q7_a: str,
    fw_q7_b: str,
    patch_drift: int,
    policy_excess: int,
) -> str:
    """Independently recompute fw_audit_digest from the canonical firmware audit."""
    payload = {
        "fw_q7_a": fw_q7_a,
        "fw_q7_b": fw_q7_b,
        "patch_drift": patch_drift,
        "policy_excess": policy_excess,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _m5_run_rules_probe() -> dict:
    """Regenerate rules_audit.json through deskctl."""
    RULES_OUTPUT.unlink(missing_ok=True)
    subprocess.run(["bash", "/app/scripts/milestone_probes.sh", "rules"], check=True)
    assert RULES_OUTPUT.is_file(), "rules probe must create rules_audit.json"
    return json.loads(RULES_OUTPUT.read_text())


def _m5_boot_rules_probe() -> dict:
    """Initialize the store from seed SQL and run the rules probe pipeline."""
    assert SEED_SQL.is_file(), "seed_bootstrap.sql is required to materialize the store"
    subprocess.run(["bash", "/app/scripts/desk_init.sh"], check=True)
    return _m5_run_rules_probe()


def _m5_run_fw_probe() -> dict:
    """Regenerate fw_audit.json through deskctl."""
    FW_OUTPUT.unlink(missing_ok=True)
    subprocess.run(["bash", "/app/scripts/milestone_probes.sh", "fw"], check=True)
    assert FW_OUTPUT.is_file(), "fw probe must create fw_audit.json"
    return json.loads(FW_OUTPUT.read_text())


def _m5_boot_fw_probe() -> dict:
    """Run the firmware audit probe pipeline after verifying poll output exists."""
    assert POLL.is_file(), "referee_poll.json from stage 2 is required"
    return _m5_run_fw_probe()


class TestRulesAndFirmwareAudit:
    """Move-rule store and firmware policy audit probe checks (tb3-pixel-duel-06/07)."""

    def test_m5_rules_probe_regenerates_output(self) -> None:
        """Rerunning the rules probe must recreate rules_audit.json."""
        data = _m5_boot_rules_probe()
        assert data["schema_tag"] == "tb3-pixel-duel-06"

    def test_m5_rules_schema_tag(self) -> None:
        """rules_audit.json must carry the stage-6 schema tag."""
        data = _m5_boot_rules_probe()
        assert data["schema_tag"] == "tb3-pixel-duel-06"

    def test_m5_action_count(self) -> None:
        """legal_actions row count must reflect the seeded store."""
        data = _m5_boot_rules_probe()
        assert data["action_count"] == 10

    def test_m5_combo_count(self) -> None:
        """combo_rules row count must be loaded from the materialized store."""
        data = _m5_boot_rules_probe()
        assert data["combo_count"] == 2

    def test_m5_blocked_count(self) -> None:
        """blocked_actions row count must be loaded from the materialized store."""
        data = _m5_boot_rules_probe()
        assert data["blocked_count"] == 1

    def test_m5_orphan_round_ids(self) -> None:
        """Overlay-only legal rows must surface as orphan round ids."""
        data = _m5_boot_rules_probe()
        assert data["orphan_round_ids"] == [106]

    def test_m5_store_digest(self) -> None:
        """Move-rule store_digest must match the independent planner store atlas recipe."""
        data = _m5_boot_rules_probe()
        assert data["store_digest"] == reference_store_digest(
            data["action_count"],
            data["blocked_count"],
            data["combo_count"],
            data["orphan_round_ids"],
        )

    def test_m5_desk_init_materializes_seed(self) -> None:
        """desk_init must execute seed SQL so combo_rules exists before probing."""
        subprocess.run(["bash", "/app/scripts/desk_init.sh"], check=True)
        conn = sqlite3.connect(SQLITE_DB)
        combo_count = conn.execute("SELECT COUNT(*) FROM combo_rules").fetchone()[0]
        conn.close()
        assert combo_count == 2

    def test_m5_dynamic_blocked_count(self) -> None:
        """Inserting a blocked action must increase blocked_count on re-probe."""
        subprocess.run(["bash", "/app/scripts/desk_init.sh"], check=True)
        conn = sqlite3.connect(SQLITE_DB)
        try:
            conn.execute(
                "INSERT INTO blocked_actions (action_token, reason) VALUES ('jab', 'test')"
            )
            conn.commit()
            data = _m5_run_rules_probe()
            assert data["blocked_count"] == 2
        finally:
            conn.close()
            subprocess.run(["bash", "/app/scripts/desk_init.sh"], check=True)
            _m5_run_rules_probe()

    def test_m5_fw_probe_regenerates_output(self) -> None:
        """Rerunning the fw probe must recreate fw_audit.json."""
        data = _m5_boot_fw_probe()
        assert data["schema_tag"] == "tb3-pixel-duel-07"

    def test_m5_fw_schema_tag(self) -> None:
        """fw_audit.json must carry the stage-7 schema tag."""
        data = _m5_boot_fw_probe()
        assert data["schema_tag"] == "tb3-pixel-duel-07"

    def test_m5_fw_q7_a(self) -> None:
        """Firmware audit must copy the red cabinet poll string."""
        data = _m5_boot_fw_probe()
        assert data["fw_q7_a"] == "1.4.2"

    def test_m5_fw_q7_b(self) -> None:
        """Firmware audit must copy the blue cabinet poll string."""
        data = _m5_boot_fw_probe()
        assert data["fw_q7_b"] == "1.4.1"

    def test_m5_patch_drift(self) -> None:
        """Patch drift must compare semver patch fields when major.minor match."""
        data = _m5_boot_fw_probe()
        assert data["patch_drift"] == 1

    def test_m5_policy_limit(self) -> None:
        """policy_limit must mirror firmware_policy.json max_patch_drift."""
        data = _m5_boot_fw_probe()
        assert data["policy_limit"] == 1

    def test_m5_policy_excess(self) -> None:
        """policy_excess must be zero when drift stays within the configured limit."""
        data = _m5_boot_fw_probe()
        assert data["policy_excess"] == 0

    def test_m5_fw_audit_digest(self) -> None:
        """Firmware fw_audit_digest must match the independent cabinet replay audit invariant."""
        data = _m5_boot_fw_probe()
        assert data["fw_audit_digest"] == reference_fw_audit_digest(
            data["fw_q7_a"],
            data["fw_q7_b"],
            data["patch_drift"],
            data["policy_excess"],
        )

    def test_m5_dynamic_patch_drift(self) -> None:
        """Mutating poll firmware must recompute patch drift and policy excess."""
        original = POLL.read_text()
        try:
            poll = json.loads(original)
            poll["fw_q7_b"] = "1.4.4"
            POLL.write_text(json.dumps(poll) + "\n")
            data = _m5_run_fw_probe()
            assert data["patch_drift"] == 2
            assert data["policy_excess"] == 1
        finally:
            POLL.write_text(original)
            _m5_run_fw_probe()

    def test_m5_major_family_mismatch(self) -> None:
        """Different major.minor families must report drift 100 and excess 99."""
        original = POLL.read_text()
        try:
            poll = json.loads(original)
            poll["fw_q7_b"] = "2.0.0"
            POLL.write_text(json.dumps(poll) + "\n")
            data = _m5_run_fw_probe()
            assert data["patch_drift"] == 100
            assert data["policy_excess"] == 99
        finally:
            POLL.write_text(original)
            _m5_run_fw_probe()


class TestHiddenVerifierFixtures:
    """Hidden ingest and export traps using /opt/verifier-fixtures/."""

    def test_tb3_hidden_merge_reduces_disputes(self) -> None:
        """Hidden ingest fixture aligns lane 102 so only round 103 stays disputed."""
        assert TB3_Q7_A_SWAP.is_file(), "TB3 ingest fixture must be mounted"
        original_a = Q7_A.read_text()
        try:
            Q7_A.write_text(TB3_Q7_A_SWAP.read_text())
            data = _m1_run_ledgers_probe()
            assert data["dispute_ids"] == [103]
        finally:
            Q7_A.write_text(original_a)
            _m1_run_ledgers_probe()

    def test_tb3_hidden_fw_policy_excess(self) -> None:
        """Hidden TB3 policy limit zero forces policy excess when firmware drifts."""
        assert TB3_POLICY_LIMIT.is_file(), "TB3 policy fixture must be mounted"
        original_policy = POLICY_JSON.read_text()
        try:
            POLICY_JSON.write_text(TB3_POLICY_LIMIT.read_text())
            data = _m5_boot_fw_probe()
            assert data["policy_limit"] == 0
            assert data["policy_excess"] == 1
        finally:
            POLICY_JSON.write_text(original_policy)
            _m5_run_fw_probe()
