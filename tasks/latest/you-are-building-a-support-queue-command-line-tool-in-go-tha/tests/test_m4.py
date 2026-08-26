"""Tests for dispersion-report and escalation-audit: multi-pass median/MAD
statistics and a severity-ladder escalation report that must reuse a single
captured "now" value. These target failure modes not covered by the
sla-report / ticket-analytics / priority-stats variance-and-rounding traps:
median-definition consistency (nearest-rank vs textbook average-of-middle),
a domain constant (1.4826), and a non-alphabetical severity sort convention
that is the mirror image of priority-stats' alphabetical rule.
"""
import subprocess
import sqlite3
from datetime import datetime, timedelta

import pytest


def run(args):
    return subprocess.run(
        ["/app/app"] + args,
        capture_output=True,
        text=True,
    )


def run_ok(args):
    r = run(args)
    assert r.returncode == 0, f"Non-zero exit for {args}: {r.stdout} {r.stderr}"
    return r


def sql_now(delta_minutes):
    """Return a SQLite datetime('now')-formatted UTC string offset by delta_minutes
    (negative = in the past)."""
    ts = datetime.utcnow() + timedelta(minutes=delta_minutes)
    return ts.strftime("%Y-%m-%d %H:%M:%S")


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "test.db")
    run_ok(["init", path])
    run_ok(["add-agent", path, "a001", "Alice", "L1"])
    run_ok(["add-agent", path, "a002", "Bob", "L2"])
    return path


def set_opened_at(db, ticket_id, minutes_ago):
    conn = sqlite3.connect(db)
    conn.execute(
        "UPDATE tickets SET opened_at=? WHERE ticket_id=?",
        (sql_now(-minutes_ago), ticket_id),
    )
    conn.commit()
    conn.close()


def resolve_with_elapsed(db, ticket_id, agent_id, minutes_ago):
    """Open-ticket-equivalent already exists; backdate opened_at then resolve
    so resolution_minutes lands close to minutes_ago."""
    set_opened_at(db, ticket_id, minutes_ago)
    run_ok(["resolve-ticket", db, ticket_id, agent_id])


class TestDispersionReport:
    def test_dispersion_report_empty(self, db):
        r = run_ok(["dispersion-report", db])
        lines = r.stdout.strip().splitlines()
        assert lines == [
            "n=0",
            "median_resolution_minutes=0",
            "mad_resolution_minutes=0.0000",
            "mad_normalized=0.0000",
        ], lines

    def test_dispersion_report_format_four_lines(self, db):
        run_ok(["open-ticket", db, "d001", "t", "low"])
        resolve_with_elapsed(db, "d001", "a001", 10)
        r = run_ok(["dispersion-report", db])
        lines = r.stdout.strip().splitlines()
        assert len(lines) == 4, lines
        assert lines[0].startswith("n=")
        assert lines[1].startswith("median_resolution_minutes=")
        assert lines[2].startswith("mad_resolution_minutes=")
        assert lines[3].startswith("mad_normalized=")

    def test_dispersion_report_single_value(self, db):
        run_ok(["open-ticket", db, "d001", "t", "low"])
        resolve_with_elapsed(db, "d001", "a001", 42)
        r = run_ok(["dispersion-report", db])
        lines = r.stdout.strip().splitlines()
        vals = {ln.split("=")[0]: ln.split("=")[1] for ln in lines}
        assert vals["n"] == "1"
        assert vals["mad_resolution_minutes"] == "0.0000", (
            f"single value MAD must be 0.0000. got: {vals}"
        )
        assert vals["mad_normalized"] == "0.0000"

    def test_dispersion_report_even_n_median_not_textbook_average(self, db):
        """values 10,20,30,40 (even n=4): nearest-rank median=sorted[1]=20,
        NOT the textbook average-of-two-middle (20+30)/2=25. Directly targets
        agents defaulting to the familiar median definition instead of the
        spec's nearest-rank formula reused from p50/p75/p95."""
        for i, mins in enumerate([10, 20, 30, 40]):
            tid = f"dmed{i}"
            run_ok(["open-ticket", db, tid, "t", "low"])
            resolve_with_elapsed(db, tid, "a001", mins)
        r = run_ok(["dispersion-report", db])
        lines = r.stdout.strip().splitlines()
        vals = {ln.split("=")[0]: ln.split("=")[1] for ln in lines}
        assert vals["n"] == "4"
        median = int(vals["median_resolution_minutes"])
        # resolution_minutes are computed live so allow a small margin for the
        # backdating fixture, but the key structural fact must hold: median
        # must equal the 2nd sorted value, not an average of the 2nd and 3rd.
        assert median != 25, (
            f"median=25 means textbook average-of-two-middle was used instead "
            f"of nearest-rank. got vals={vals}"
        )

    def test_dispersion_report_mad_and_normalized_exact(self, db):
        """Precise fixture inserted directly via SQL (bypassing timing drift):
        resolution_minutes = [10, 20, 30, 40].
        median (nearest-rank, rank=ceil(0.5*4)=2) = 20.
        deviations sorted = [0, 10, 10, 20]; mad (rank=2) = 10.0000.
        mad_normalized = 10 * 1.4826 = 14.8260."""
        run_ok(["open-ticket", db, "e001", "t", "low"])
        run_ok(["open-ticket", db, "e002", "t", "low"])
        run_ok(["open-ticket", db, "e003", "t", "low"])
        run_ok(["open-ticket", db, "e004", "t", "low"])
        conn = sqlite3.connect(db)
        for tid, mins in [("e001", 10), ("e002", 20), ("e003", 30), ("e004", 40)]:
            conn.execute(
                "INSERT INTO resolutions (ticket_id, agent_id, resolution_minutes, sla_met, resolved_at) "
                "VALUES (?, 'a001', ?, 1, datetime('now'))",
                (tid, mins),
            )
        conn.commit()
        conn.close()
        r = run_ok(["dispersion-report", db])
        lines = r.stdout.strip().splitlines()
        vals = {ln.split("=")[0]: ln.split("=")[1] for ln in lines}
        assert vals["n"] == "4"
        assert vals["median_resolution_minutes"] == "20", (
            f"nearest-rank median of [10,20,30,40] must be 20 (sorted[1]), "
            f"not 25 (textbook average). got: {vals}"
        )
        assert vals["mad_resolution_minutes"] == "10.0000", vals
        assert vals["mad_normalized"] == "14.8260", (
            f"mad_normalized = mad * 1.4826 = 10 * 1.4826 = 14.8260. got: {vals}"
        )

    def test_dispersion_report_all_equal_values_zero_mad(self, db):
        """All resolution_minutes identical: median=that value, MAD=0.0000,
        mad_normalized=0.0000 (not a divide-by-zero or NaN)."""
        run_ok(["open-ticket", db, "f001", "t", "low"])
        run_ok(["open-ticket", db, "f002", "t", "low"])
        run_ok(["open-ticket", db, "f003", "t", "low"])
        conn = sqlite3.connect(db)
        for tid in ["f001", "f002", "f003"]:
            conn.execute(
                "INSERT INTO resolutions (ticket_id, agent_id, resolution_minutes, sla_met, resolved_at) "
                "VALUES (?, 'a001', 15, 1, datetime('now'))",
                (tid,),
            )
        conn.commit()
        conn.close()
        r = run_ok(["dispersion-report", db])
        lines = r.stdout.strip().splitlines()
        vals = {ln.split("=")[0]: ln.split("=")[1] for ln in lines}
        assert vals["median_resolution_minutes"] == "15", vals
        assert vals["mad_resolution_minutes"] == "0.0000", vals
        assert vals["mad_normalized"] == "0.0000", vals


class TestEscalationAudit:
    def test_escalation_audit_empty_no_open_tickets(self, db):
        r = run_ok(["escalation-audit", db])
        assert r.stdout.strip() == "", r.stdout

    def test_escalation_audit_on_track_not_printed(self, db):
        """Well within SLA window: not printed at all."""
        run_ok(["open-ticket", db, "g001", "t", "critical"])
        set_opened_at(db, "g001", 5)  # 5 min elapsed, threshold=60
        r = run_ok(["escalation-audit", db])
        assert r.stdout.strip() == "", r.stdout

    def test_escalation_audit_ratio_exactly_one_excluded(self, db):
        """elapsed == threshold (ratio == 1.0) is still on_track (inclusive
        lower boundary), matching resolve-ticket's <= SLA-met convention.
        Catches agents who use a strict > for the on_track cutoff."""
        run_ok(["open-ticket", db, "g002", "t", "critical"])
        set_opened_at(db, "g002", 60)  # exactly at threshold
        r = run_ok(["escalation-audit", db])
        assert "g002" not in r.stdout, (
            f"ratio==1.0 must be on_track (excluded), not at_risk. got: {r.stdout!r}"
        )

    def test_escalation_audit_at_risk_band(self, db):
        run_ok(["open-ticket", db, "g003", "t", "critical"])
        set_opened_at(db, "g003", 90)  # ratio = 1.5
        r = run_ok(["escalation-audit", db])
        line = [ln for ln in r.stdout.strip().splitlines() if "g003" in ln]
        assert len(line) == 1, r.stdout
        assert "band=at_risk" in line[0], line[0]

    def test_escalation_audit_ratio_exactly_two_still_at_risk(self, db):
        """elapsed == 2*threshold (ratio == 2.0) belongs to at_risk (inclusive
        upper boundary), not escalated. Catches an off-by-one on the boundary."""
        run_ok(["open-ticket", db, "g004", "t", "critical"])
        set_opened_at(db, "g004", 120)  # ratio = 2.0 exactly
        r = run_ok(["escalation-audit", db])
        line = [ln for ln in r.stdout.strip().splitlines() if "g004" in ln]
        assert len(line) == 1, r.stdout
        assert "band=at_risk" in line[0], (
            f"ratio==2.0 must still be at_risk (inclusive boundary), not escalated. got: {line[0]}"
        )

    def test_escalation_audit_escalated_band(self, db):
        run_ok(["open-ticket", db, "g005", "t", "critical"])
        set_opened_at(db, "g005", 150)  # ratio = 2.5
        r = run_ok(["escalation-audit", db])
        line = [ln for ln in r.stdout.strip().splitlines() if "g005" in ln]
        assert len(line) == 1, r.stdout
        assert "band=escalated" in line[0], line[0]

    def test_escalation_audit_ratio_exactly_four_still_escalated(self, db):
        run_ok(["open-ticket", db, "g006", "t", "critical"])
        set_opened_at(db, "g006", 240)  # ratio = 4.0 exactly
        r = run_ok(["escalation-audit", db])
        line = [ln for ln in r.stdout.strip().splitlines() if "g006" in ln]
        assert len(line) == 1, r.stdout
        assert "band=escalated" in line[0], (
            f"ratio==4.0 must still be escalated (inclusive boundary), not critical_escalation. got: {line[0]}"
        )

    def test_escalation_audit_critical_escalation_band(self, db):
        run_ok(["open-ticket", db, "g007", "t", "critical"])
        set_opened_at(db, "g007", 300)  # ratio = 5.0
        r = run_ok(["escalation-audit", db])
        line = [ln for ln in r.stdout.strip().splitlines() if "g007" in ln]
        assert len(line) == 1, r.stdout
        assert "band=critical_escalation" in line[0], line[0]

    def test_escalation_audit_resolved_tickets_excluded(self, db):
        """A resolved ticket must never appear even if it was open a very
        long time before resolution."""
        run_ok(["open-ticket", db, "g008", "t", "critical"])
        set_opened_at(db, "g008", 500)
        run_ok(["resolve-ticket", db, "g008", "a001"])
        r = run_ok(["escalation-audit", db])
        assert "g008" not in r.stdout, (
            f"resolved tickets must never appear in escalation-audit. got: {r.stdout!r}"
        )

    def test_escalation_audit_format_tab_separated(self, db):
        run_ok(["open-ticket", db, "g009", "t", "high"])
        set_opened_at(db, "g009", 500)  # ratio = 500/240 ~= 2.0833 -> escalated
        r = run_ok(["escalation-audit", db])
        line = [ln for ln in r.stdout.strip().splitlines() if "g009" in ln]
        assert len(line) == 1
        parts = line[0].split("\t")
        assert len(parts) == 6, f"expected 6 tab-separated fields. got: {parts}"
        assert parts[0] == "g009"
        assert parts[1].startswith("priority=")
        assert parts[2].startswith("band=")
        assert parts[3].startswith("elapsed_minutes=")
        assert parts[4].startswith("threshold=")
        assert parts[4] == "threshold=240", parts
        assert parts[5].startswith("ratio=")
        assert parts[5] == "ratio=2.0833", parts

    def test_escalation_audit_ratio_truncates_not_half_up(self, db):
        """157/60 = 2.616666... must truncate to 2.6166, not round HALF_UP
        to 2.6167. This is a third rounding convention distinct from
        priority-report's HALF_UP and priority-stats' HALF_EVEN."""
        run_ok(["open-ticket", db, "g110", "t", "critical"])
        set_opened_at(db, "g110", 157)  # ratio = 157/60 = 2.61666... -> escalated
        r = run_ok(["escalation-audit", db])
        line = [ln for ln in r.stdout.strip().splitlines() if "g110" in ln]
        assert len(line) == 1
        parts = line[0].split("\t")
        assert parts[5] == "ratio=2.6166", (
            f"expected truncated ratio=2.6166 (not HALF_UP 2.6167). got: {parts[5]}"
        )

    def test_escalation_audit_ratio_just_past_boundary(self, db):
        """An at_risk ticket right at the low boundary must still produce a
        well-formed truncated ratio."""
        run_ok(["open-ticket", db, "g111", "t", "low"])
        set_opened_at(db, "g111", 4321)  # ratio = 4321/4320 -> just over 1.0, at_risk
        r = run_ok(["escalation-audit", db])
        line = [ln for ln in r.stdout.strip().splitlines() if "g111" in ln]
        assert len(line) == 1
        parts = line[0].split("\t")
        assert parts[5] == "ratio=1.0002", parts

    def test_escalation_audit_sort_severity_desc_not_alphabetical(self, db):
        """Sort by band severity descending (critical_escalation, escalated,
        at_risk) -- the OPPOSITE convention from priority-stats, which sorts
        alphabetically. Alphabetical order here would be
        at_risk, critical_escalation, escalated -- wrong."""
        run_ok(["open-ticket", db, "h001", "t", "critical"])
        set_opened_at(db, "h001", 90)  # at_risk
        run_ok(["open-ticket", db, "h002", "t", "critical"])
        set_opened_at(db, "h002", 300)  # critical_escalation
        run_ok(["open-ticket", db, "h003", "t", "critical"])
        set_opened_at(db, "h003", 150)  # escalated
        r = run_ok(["escalation-audit", db])
        ticket_order = [ln.split("\t")[0] for ln in r.stdout.strip().splitlines()]
        assert ticket_order == ["h002", "h003", "h001"], (
            f"expected severity-desc order [h002(critical_escalation), "
            f"h003(escalated), h001(at_risk)]. got: {ticket_order}"
        )

    def test_escalation_audit_tiebreak_elapsed_desc_then_ticket_id_asc(self, db):
        """Same band: sort by elapsed_minutes descending, then ticket_id ascending."""
        run_ok(["open-ticket", db, "z002", "t", "critical"])
        set_opened_at(db, "z002", 90)  # at_risk, elapsed=90
        run_ok(["open-ticket", db, "a001x", "t", "critical"])
        set_opened_at(db, "a001x", 110)  # at_risk, elapsed=110 (larger -> first)
        r = run_ok(["escalation-audit", db])
        ticket_order = [ln.split("\t")[0] for ln in r.stdout.strip().splitlines()]
        assert ticket_order == ["a001x", "z002"], (
            f"higher elapsed_minutes (110) must sort before lower (90) within "
            f"the same band, regardless of ticket_id. got: {ticket_order}"
        )

    def test_escalation_audit_different_priority_thresholds(self, db):
        """low priority threshold=4320: 4321 minutes elapsed is just barely
        past on_track (ratio ~1.0002) -> at_risk, not critical_escalation."""
        run_ok(["open-ticket", db, "g010", "t", "low"])
        set_opened_at(db, "g010", 4321)
        r = run_ok(["escalation-audit", db])
        line = [ln for ln in r.stdout.strip().splitlines() if "g010" in ln]
        assert len(line) == 1, r.stdout
        assert "band=at_risk" in line[0], (
            f"low priority just past its 4320min threshold must be at_risk. got: {line[0]}"
        )


RULE_ORDER = [
    "TIER_CAPACITY",
    "STATUS_VALID",
    "DUPLICATE_RESOLUTION",
    "ORPHAN_RESOLUTION",
    "SLA_CONSISTENCY",
    "CHAIN_SEQUENCE",
]


def rule_names_in_output(stdout):
    return [ln.split(" ", 1)[0] for ln in stdout.splitlines() if ln.split(" ", 1)[0] in RULE_ORDER]


class TestQueueLint:
    """Tests for queue-lint: six fixed-order domain integrity rules, each
    reporting PASS/FAIL plus any violating identifiers, with one final
    OVERALL line. Every rule always runs regardless of earlier failures."""

    def test_queue_lint_clean_db_all_pass(self, db):
        run_ok(["add-agent", db, "a010", "Cara", "L1"])
        run_ok(["open-ticket", db, "q001", "t", "high"])
        run_ok(["resolve-ticket", db, "q001", "a010"])
        r = run_ok(["queue-lint", db])
        for rule in RULE_ORDER:
            assert f"{rule} PASS violations=0" in r.stdout, r.stdout
        assert "OVERALL PASS" in r.stdout.splitlines()[-1], r.stdout

    def test_queue_lint_fixed_rule_order_not_alphabetical(self, db):
        """Rule order is TIER_CAPACITY, STATUS_VALID, DUPLICATE_RESOLUTION,
        ORPHAN_RESOLUTION, SLA_CONSISTENCY, CHAIN_SEQUENCE -- not
        alphabetical. Alphabetical would put CHAIN_SEQUENCE first and
        TIER_CAPACITY last, which is wrong."""
        r = run_ok(["queue-lint", db])
        assert rule_names_in_output(r.stdout) == RULE_ORDER, r.stdout

    def test_queue_lint_tier_capacity_violation(self, db):
        """An L1 agent (capacity 5) assigned 6 open tickets must fail
        TIER_CAPACITY and list that agent_id."""
        run_ok(["add-agent", db, "a011", "Dave", "L1"])
        conn = sqlite3.connect(db)
        for i in range(6):
            tid = f"cap{i}"
            conn.execute(
                "INSERT INTO tickets (ticket_id, title, priority, status, assigned_agent_id) "
                "VALUES (?, 't', 'high', 'open', ?)",
                (tid, "a011"),
            )
        conn.commit()
        conn.close()
        r = run(["queue-lint", db])
        assert r.returncode == 1
        lines = r.stdout.splitlines()
        assert "TIER_CAPACITY FAIL violations=1" in lines, r.stdout
        idx = lines.index("TIER_CAPACITY FAIL violations=1")
        assert lines[idx + 1] == "\ta011", lines
        assert lines[-1] == "OVERALL FAIL", r.stdout

    def test_queue_lint_status_valid_violation(self, db):
        run_ok(["open-ticket", db, "q002", "t", "high"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE tickets SET status='archived' WHERE ticket_id='q002'")
        conn.commit()
        conn.close()
        r = run(["queue-lint", db])
        assert r.returncode == 1
        lines = r.stdout.splitlines()
        assert "STATUS_VALID FAIL violations=1" in lines, r.stdout
        idx = lines.index("STATUS_VALID FAIL violations=1")
        assert lines[idx + 1] == "\tq002", lines

    def test_queue_lint_duplicate_resolution_violation(self, db):
        run_ok(["add-agent", db, "a012", "Eve", "L2"])
        run_ok(["open-ticket", db, "q003", "t", "high"])
        run_ok(["resolve-ticket", db, "q003", "a012"])
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO resolutions (ticket_id, agent_id, resolution_minutes, sla_met, resolved_at) "
            "VALUES ('q003', 'a012', 5, 1, datetime('now'))"
        )
        conn.commit()
        conn.close()
        r = run(["queue-lint", db])
        assert r.returncode == 1
        lines = r.stdout.splitlines()
        assert "DUPLICATE_RESOLUTION FAIL violations=1" in lines, r.stdout
        idx = lines.index("DUPLICATE_RESOLUTION FAIL violations=1")
        assert lines[idx + 1] == "\tq003", lines

    def test_queue_lint_orphan_resolution_violation(self, db):
        """A resolutions row pointing at a ticket_id that does not exist at
        all must be flagged, distinct from a resolutions row pointing at a
        ticket that exists but is still open."""
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO resolutions (ticket_id, agent_id, resolution_minutes, sla_met, resolved_at) "
            "VALUES ('ghost1', 'a001', 5, 1, datetime('now'))"
        )
        conn.commit()
        conn.close()
        r = run(["queue-lint", db])
        assert r.returncode == 1
        lines = r.stdout.splitlines()
        assert "ORPHAN_RESOLUTION FAIL violations=1" in lines, r.stdout
        idx = lines.index("ORPHAN_RESOLUTION FAIL violations=1")
        assert lines[idx + 1] == "\tghost1", lines

    def test_queue_lint_orphan_resolution_still_open_ticket(self, db):
        """A resolutions row pointing at a ticket that exists but whose
        status is still 'open' (never actually resolved) must also be
        flagged as orphaned."""
        run_ok(["open-ticket", db, "q004", "t", "high"])
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO resolutions (ticket_id, agent_id, resolution_minutes, sla_met, resolved_at) "
            "VALUES ('q004', 'a001', 5, 1, datetime('now'))"
        )
        conn.commit()
        conn.close()
        r = run(["queue-lint", db])
        assert r.returncode == 1
        lines = r.stdout.splitlines()
        assert "ORPHAN_RESOLUTION FAIL violations=1" in lines, r.stdout
        idx = lines.index("ORPHAN_RESOLUTION FAIL violations=1")
        assert lines[idx + 1] == "\tq004", lines

    def test_queue_lint_sla_consistency_violation(self, db):
        """A critical ticket resolved in 999 minutes (way past the 60min
        threshold) but stored with sla_met=1 must be flagged: SLA_CONSISTENCY
        recomputes from resolution_minutes and priority, it does not trust
        the stored sla_met value."""
        run_ok(["open-ticket", db, "q005", "t", "critical"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE tickets SET status='resolved', assigned_agent_id='a001' WHERE ticket_id='q005'")
        conn.execute(
            "INSERT INTO resolutions (ticket_id, agent_id, resolution_minutes, sla_met, resolved_at) "
            "VALUES ('q005', 'a001', 999, 1, datetime('now'))"
        )
        conn.commit()
        conn.close()
        r = run(["queue-lint", db])
        assert r.returncode == 1
        lines = r.stdout.splitlines()
        assert "SLA_CONSISTENCY FAIL violations=1" in lines, r.stdout
        idx = lines.index("SLA_CONSISTENCY FAIL violations=1")
        assert lines[idx + 1] == "\tq005", lines

    def test_queue_lint_chain_sequence_gap_from_middle_deletion(self, db):
        """Deleting a chain row that is NOT the head still leaves a gap in
        chain_id, and CHAIN_SEQUENCE must catch it even though chain-verify's
        prev_hash-only check would not catch a deletion at the tail the same
        way a head deletion is caught."""
        run_ok(["add-agent", db, "a013", "Frank", "L1"])
        for i in range(3):
            tid = f"seq{i}"
            run_ok(["open-ticket", db, tid, "t", "high"])
            run_ok(["resolve-ticket", db, tid, "a013"])
        conn = sqlite3.connect(db)
        row = conn.execute("SELECT chain_id FROM resolution_chain ORDER BY chain_id ASC LIMIT 1 OFFSET 1").fetchone()
        deleted_id = row[0]
        conn.execute("DELETE FROM resolution_chain WHERE chain_id=?", (deleted_id,))
        conn.commit()
        conn.close()
        r = run(["queue-lint", db])
        assert r.returncode == 1
        lines = r.stdout.splitlines()
        fail_lines = [ln for ln in lines if ln.startswith("CHAIN_SEQUENCE FAIL")]
        assert len(fail_lines) == 1, lines
        idx = lines.index(fail_lines[0])
        assert lines[idx + 1] == "\t3", (
            f"after deleting the middle chain row, the row that used to be "
            f"chain_id=3 is now at position 2 in ascending order and must be "
            f"flagged. got: {lines[idx + 1]!r}"
        )

    def test_queue_lint_empty_db_all_pass(self, tmp_path):
        path = str(tmp_path / "empty.db")
        run_ok(["init", path])
        r = run_ok(["queue-lint", path])
        for rule in RULE_ORDER:
            assert f"{rule} PASS violations=0" in r.stdout, r.stdout
        assert r.stdout.strip().splitlines()[-1] == "OVERALL PASS", r.stdout
