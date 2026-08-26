"""Milestone 2 tests: resolve-ticket with SLA tracking."""
import hashlib
import hmac as hmac_lib
import os
import sqlite3
import subprocess
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


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "test.db")
    run_ok(["init", path])
    run_ok(["add-agent", path, "a001", "Alice", "L1"])
    run_ok(["add-agent", path, "a002", "Bob", "L2"])
    run_ok(["open-ticket", path, "t001", "Login issue", "high"])
    run_ok(["open-ticket", path, "t002", "Server down", "critical"])
    run_ok(["open-ticket", path, "t003", "Slow response", "medium"])
    return path


class TestMilestone2:
    def test_resolve_ticket_ok(self, db):
        r = run_ok(["resolve-ticket", db, "t001", "a001"])
        assert "OK resolved ticket=t001" in r.stdout

    def test_resolve_ticket_sla_met_in_output(self, db):
        r = run_ok(["resolve-ticket", db, "t001", "a001"])
        assert "sla_met=" in r.stdout

    def test_resolve_ticket_sla_breach_stdout(self, db):
        """When SLA is breached (sla_met=false), the output must include 'sla_met=false'."""
        run_ok(["open-ticket", db, "t_breach", "Breach test", "critical"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE tickets SET opened_at=datetime('now', '-3661 seconds') WHERE ticket_id='t_breach'")
        conn.commit()
        conn.close()
        r = run_ok(["resolve-ticket", db, "t_breach", "a001"])
        assert "sla_met=false" in r.stdout, (
            f"When SLA is breached (critical ticket >60 min), output must contain 'sla_met=false'. "
            f"got: {r.stdout!r}"
        )

    def test_resolve_ticket_not_found(self, db):
        r = run(["resolve-ticket", db, "no-such", "a001"])
        assert r.returncode == 1
        assert "ticket not found: no-such" in r.stdout

    def test_resolve_ticket_agent_not_found(self, db):
        r = run(["resolve-ticket", db, "t001", "no-agent"])
        assert r.returncode == 1
        assert "agent not found: no-agent" in r.stdout

    def test_resolve_ticket_already_resolved(self, db):
        run_ok(["resolve-ticket", db, "t001", "a001"])
        r = run(["resolve-ticket", db, "t001", "a001"])
        assert r.returncode == 1
        assert "ticket already resolved: t001" in r.stdout

    def test_resolve_updates_status(self, db):
        run_ok(["resolve-ticket", db, "t001", "a001"])
        r = run_ok(["list-tickets", db])
        for line in r.stdout.strip().splitlines():
            cols = line.split("\t")
            if cols[0] == "t001":
                assert cols[1] == "resolved"
                assert cols[2] == "a001"
                break
        else:
            pytest.fail("t001 not found in list-tickets output")

    def test_resolve_assigns_agent(self, db):
        run_ok(["resolve-ticket", db, "t001", "a002"])
        r = run_ok(["list-tickets", db])
        for line in r.stdout.strip().splitlines():
            cols = line.split("\t")
            if cols[0] == "t001":
                assert cols[2] == "a002"
                break

    def test_sla_met_critical_immediate(self, db):
        r = run_ok(["resolve-ticket", db, "t002", "a001"])
        assert "sla_met=true" in r.stdout

    def test_sla_met_medium_immediate(self, db):
        r = run_ok(["resolve-ticket", db, "t003", "a001"])
        assert "sla_met=true" in r.stdout

    def test_multiple_resolutions_different_agents(self, db):
        r1 = run_ok(["resolve-ticket", db, "t001", "a001"])
        r2 = run_ok(["resolve-ticket", db, "t002", "a002"])
        assert "OK resolved ticket=t001" in r1.stdout
        assert "OK resolved ticket=t002" in r2.stdout

    def test_resolution_output_format(self, db):
        r = run_ok(["resolve-ticket", db, "t001", "a001"])
        assert "sla_met=true" in r.stdout or "sla_met=false" in r.stdout


class TestTicketSchema:
    """Verifies ticket rows have all expected fields, correctly typed and valued."""

    def test_ticket_schema_fields_present_and_typed(self, db):
        """After open-ticket, the tickets row must have all expected columns with
        correct types/values: ticket_id, title, priority, status='open',
        assigned_agent_id=NULL (unassigned), opened_at is a non-empty timestamp string."""
        run_ok(["open-ticket", db, "t_schema", "Schema check", "high"])
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT ticket_id, title, priority, status, assigned_agent_id, opened_at "
            "FROM tickets WHERE ticket_id='t_schema'"
        ).fetchone()
        conn.close()
        assert row is not None, "ticket row must exist after open-ticket"
        ticket_id, title, priority, status, assigned_agent_id, opened_at = row
        assert ticket_id == "t_schema"
        assert title == "Schema check"
        assert priority == "high"
        assert status == "open"
        assert assigned_agent_id is None, (
            f"Unassigned ticket must have NULL assigned_agent_id, got {assigned_agent_id!r}"
        )
        assert isinstance(opened_at, str) and len(opened_at) > 0, (
            f"opened_at must be a non-empty timestamp string, got {opened_at!r}"
        )

    def test_ticket_schema_after_resolve_fields_updated(self, db):
        """After resolve-ticket, status must become 'resolved' and assigned_agent_id
        must be set to the resolving agent's id — verified directly against the
        tickets table schema, not just via list-tickets output."""
        run_ok(["resolve-ticket", db, "t001", "a002"])
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT status, assigned_agent_id FROM tickets WHERE ticket_id='t001'"
        ).fetchone()
        conn.close()
        assert row == ("resolved", "a002"), (
            f"Expected (status='resolved', assigned_agent_id='a002'), got: {row!r}"
        )


class TestValidationOrderResolvedBeforeAgent:
    """Confirms 'ticket already resolved' is checked before 'agent not found'."""

    def test_resolved_ticket_rejected_before_agent_check(self, db):
        """A ticket that is ALREADY resolved, when resolve-ticket is attempted again with
        a nonexistent agent, must fail with 'ticket already resolved', not 'agent not found'.
        This confirms the status check happens before the agent-existence check, per the
        documented validation order (ticket existence, then status, then agent existence)."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        r = run(["resolve-ticket", db, "t001", "no-such-agent"])
        assert r.returncode == 1
        assert "ticket already resolved: t001" in r.stdout, (
            f"Resolved ticket + nonexistent agent must fail with 'ticket already resolved', "
            f"not 'agent not found'. got: {r.stdout!r}"
        )
        assert "agent not found" not in r.stdout, (
            f"Must not print 'agent not found' when ticket is already resolved (checked first). "
            f"got: {r.stdout!r}"
        )


class TestPriorityReport:
    """Tests for priority-report command: precision traps for ordering and breach_rate."""

    def test_priority_report_all_zero_no_resolutions(self, db):
        """No resolutions: all 4 priorities output total=0 breached=0 breach_rate=0.0000."""
        r = run_ok(["priority-report", db])
        lines = r.stdout.strip().splitlines()
        assert len(lines) == 4, f"Must output exactly 4 lines, got {len(lines)}: {r.stdout!r}"
        for line in lines:
            assert "total=0" in line, f"No resolutions: total must be 0. line={line!r}"
            assert "breached=0" in line, f"No resolutions: breached must be 0. line={line!r}"
            assert "breach_rate=0.0000" in line, (
                f"No resolutions: breach_rate must be '0.0000'. line={line!r}"
            )

    def test_priority_report_semantic_order_not_alphabetical(self, db):
        """Output must be in semantic priority order: critical, high, medium, low.
        Alphabetical order is: critical, high, low, medium — 'low' before 'medium' is WRONG.
        Catches agents that sort output alphabetically."""
        r = run_ok(["priority-report", db])
        lines = r.stdout.strip().splitlines()
        assert len(lines) == 4
        priorities = [line.split()[0] for line in lines]
        assert priorities == ["critical", "high", "medium", "low"], (
            f"Priority order must be critical>high>medium>low. Got: {priorities}. "
            f"Alphabetical (wrong) gives critical,high,low,medium — note 'low' before 'medium'."
        )

    def test_priority_report_breach_rate_one_third_precision(self, db):
        """1 breached of 3 resolved: breach_rate=0.3333 (not 0.333 or 0.33 or 33.3%).
        Catches truncation (gives 0.3333 for 1/3? Actually truncation of 0.33333 to 4dp gives 0.3333.
        The real trap: value must use 4dp not 2dp, and format as decimal not percentage)."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a001"])
        run_ok(["resolve-ticket", db, "t003", "a001"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE tickets SET priority='high' WHERE ticket_id IN ('t001','t002','t003')")
        conn.execute("UPDATE resolutions SET sla_met=0 WHERE resolution_id=1")
        conn.execute("UPDATE resolutions SET sla_met=1 WHERE resolution_id=2")
        conn.execute("UPDATE resolutions SET sla_met=1 WHERE resolution_id=3")
        conn.commit()
        conn.close()
        r = run_ok(["priority-report", db])
        lines = r.stdout.strip().splitlines()
        high_line = next(ln for ln in lines if ln.startswith("high"))
        assert "breach_rate=0.3333" in high_line, (
            f"1/3 breach_rate must be 0.3333, got: {high_line!r}"
        )

    def test_priority_report_breach_rate_two_thirds_rounds_up(self, db):
        """2 breached of 3: breach_rate=0.6667 (not 0.6666 truncated).
        This tests proper rounding at the 4th decimal place."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a001"])
        run_ok(["resolve-ticket", db, "t003", "a001"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE tickets SET priority='high' WHERE ticket_id IN ('t001','t002','t003')")
        conn.execute("UPDATE resolutions SET sla_met=0 WHERE resolution_id=1")
        conn.execute("UPDATE resolutions SET sla_met=0 WHERE resolution_id=2")
        conn.execute("UPDATE resolutions SET sla_met=1 WHERE resolution_id=3")
        conn.commit()
        conn.close()
        r = run_ok(["priority-report", db])
        lines = r.stdout.strip().splitlines()
        high_line = next(ln for ln in lines if ln.startswith("high"))
        assert "breach_rate=0.6667" in high_line, (
            f"2/3 breach_rate must be 0.6667 (round up, not truncate to 0.6666). got: {high_line!r}"
        )

    def test_priority_report_all_four_always_shown(self, db):
        """All 4 priority lines always shown even if a priority has no resolutions."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        r = run_ok(["priority-report", db])
        lines = r.stdout.strip().splitlines()
        assert len(lines) == 4, f"Must always output 4 lines, got {len(lines)}"
        shown = [ln.split()[0] for ln in lines]
        for p in ["critical", "high", "medium", "low"]:
            assert p in shown, (
                f"'{p}' must always appear even with 0 resolutions. Got: {shown}"
            )

    def test_priority_report_all_breached_rate_1(self, db):
        """All resolutions breached for a priority: breach_rate=1.0000."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE tickets SET priority='high' WHERE ticket_id='t001'")
        conn.execute("UPDATE resolutions SET sla_met=0 WHERE resolution_id=1")
        conn.commit()
        conn.close()
        r = run_ok(["priority-report", db])
        lines = r.stdout.strip().splitlines()
        high_line = next(ln for ln in lines if ln.startswith("high"))
        assert "breach_rate=1.0000" in high_line, (
            f"All breached: breach_rate must be 1.0000. got: {high_line!r}"
        )

    def test_priority_report_zero_breach_format_not_integer(self, db):
        """breach_rate=0.0000 not '0' or '0.0' or '.0000'. Must have exactly 4 decimal places."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE tickets SET priority='high' WHERE ticket_id='t001'")
        conn.execute("UPDATE resolutions SET sla_met=1 WHERE resolution_id=1")
        conn.commit()
        conn.close()
        r = run_ok(["priority-report", db])
        lines = r.stdout.strip().splitlines()
        high_line = next(ln for ln in lines if ln.startswith("high"))
        assert "breach_rate=0.0000" in high_line, (
            f"Zero breach_rate must be '0.0000' (4dp), got: {high_line!r}"
        )

    def test_priority_report_breach_rate_half_up_1_of_32(self, db):
        """1 breach out of 32 resolutions: breach_rate must be 0.0313 (genuine HALF_UP rounding).
        1/32 = 0.03125 exactly; a naive float format that falls back to round-half-to-even
        ("banker's rounding") would incorrectly produce 0.0312. This is the discriminating
        case: 1-out-of-2 or 1-out-of-3 never land on an exact tie at the 4th decimal digit,
        so they cannot distinguish HALF_UP from banker's rounding the way 1/32 does."""
        run_ok(["add-agent", db, "hu001", "HalfUpAgent", "L1"])
        for i in range(32):
            tid = f"hu{i:04d}"
            run_ok(["open-ticket", db, tid, f"ticket {i}", "high"])
            run_ok(["resolve-ticket", db, tid, "hu001"])
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE resolutions SET sla_met=0 WHERE resolution_id="
            "(SELECT resolution_id FROM resolutions ORDER BY resolution_id LIMIT 1)"
        )
        conn.commit()
        conn.close()
        r = run_ok(["priority-report", db])
        lines = r.stdout.strip().splitlines()
        high_line = next(ln for ln in lines if ln.startswith("high"))
        assert "total=32" in high_line, f"Expected total=32, got: {high_line!r}"
        assert "breached=1" in high_line, f"Expected breached=1, got: {high_line!r}"
        assert "breach_rate=0.0313" in high_line, (
            f"1/32=0.03125 must round HALF_UP to 0.0313 (5th digit is exactly 5, round up). "
            f"Round-half-to-even (banker's, wrong here) gives 0.0312. got: {high_line!r}"
        )

    def test_priority_report_multi_record_positive_totals_correct(self, db):
        """5 resolved tickets across 2 priorities: totals/breached must be exact positive
        integers reflecting the real aggregate, not just non-crashing/zero placeholder output."""
        run_ok(["open-ticket", db, "tm1", "m1", "high"])
        run_ok(["open-ticket", db, "tm2", "m2", "high"])
        run_ok(["open-ticket", db, "tm3", "m3", "high"])
        run_ok(["open-ticket", db, "tm4", "m4", "low"])
        run_ok(["open-ticket", db, "tm5", "m5", "low"])
        for tid in ["tm1", "tm2", "tm3", "tm4", "tm5"]:
            run_ok(["resolve-ticket", db, tid, "a001"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE resolutions SET sla_met=0 WHERE ticket_id IN ('tm1','tm2')")
        conn.execute("UPDATE resolutions SET sla_met=1 WHERE ticket_id='tm3'")
        conn.execute("UPDATE resolutions SET sla_met=0 WHERE ticket_id='tm4'")
        conn.execute("UPDATE resolutions SET sla_met=1 WHERE ticket_id='tm5'")
        conn.commit()
        conn.close()
        r = run_ok(["priority-report", db])
        lines = r.stdout.strip().splitlines()
        high_line = next(ln for ln in lines if ln.startswith("high"))
        low_line = next(ln for ln in lines if ln.startswith("low"))
        assert "total=3" in high_line and "breached=2" in high_line, (
            f"high must show total=3 breached=2 (real counts across multiple records). got: {high_line!r}"
        )
        assert "total=2" in low_line and "breached=1" in low_line, (
            f"low must show total=2 breached=1 (real counts across multiple records). got: {low_line!r}"
        )
        assert "breach_rate=0.6667" in high_line, f"high breach_rate must be 2/3=0.6667. got: {high_line!r}"
        assert "breach_rate=0.5000" in low_line, f"low breach_rate must be 1/2=0.5000. got: {low_line!r}"

    def test_priority_report_counts_only_resolutions_not_open_tickets(self, db):
        """total counts only resolved tickets (resolutions table rows), not open tickets.
        Open tickets must not inflate the total count."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        # t002 and t003 remain open
        r = run_ok(["priority-report", db])
        lines = r.stdout.strip().splitlines()
        high_line = next(ln for ln in lines if ln.startswith("high"))
        assert "total=1" in high_line, (
            f"total must count only resolved tickets (resolutions rows), not open. "
            f"t001 is high priority, resolved. t002/t003 still open. got: {high_line!r}"
        )

    def test_priority_report_sla_margin_avg_zero_when_no_sla_met(self, db):
        """All resolutions breached for a priority: sla_margin_avg=0.00 (no SLA-met rows
        to average, and the count for the zero-total case must also give 0.00)."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE tickets SET priority='high' WHERE ticket_id='t001'")
        conn.execute("UPDATE resolutions SET sla_met=0 WHERE ticket_id='t001'")
        conn.commit()
        conn.close()
        r = run_ok(["priority-report", db])
        lines = r.stdout.strip().splitlines()
        high_line = next(ln for ln in lines if ln.startswith("high"))
        assert "sla_margin_avg=0.00" in high_line, (
            f"No SLA-met resolutions -> sla_margin_avg must be '0.00'. got: {high_line!r}"
        )

    def test_priority_report_sla_margin_avg_excludes_breached_resolutions(self, db):
        """sla_margin_avg averages only SLA-met resolutions. One SLA-met resolution with a
        margin of 10, plus one breached resolution that would drag the average down (or
        negative) if wrongly folded in, must still give exactly 10.00 — the breached row
        is excluded from both the sum and the count, not counted as a zero/negative margin."""
        run_ok(["open-ticket", db, "tma", "margin a", "high"])
        run_ok(["open-ticket", db, "tmb", "margin b", "high"])
        run_ok(["resolve-ticket", db, "tma", "a001"])
        run_ok(["resolve-ticket", db, "tmb", "a001"])
        conn = sqlite3.connect(db)
        # high threshold = 240. tma: resolution_minutes=230 -> margin=10, sla_met=1 (met).
        conn.execute("UPDATE resolutions SET resolution_minutes=230, sla_met=1 WHERE ticket_id='tma'")
        # tmb: resolution_minutes=300 -> breached (sla_met=0), must be fully excluded.
        conn.execute("UPDATE resolutions SET resolution_minutes=300, sla_met=0 WHERE ticket_id='tmb'")
        conn.commit()
        conn.close()
        r = run_ok(["priority-report", db])
        lines = r.stdout.strip().splitlines()
        high_line = next(ln for ln in lines if ln.startswith("high"))
        assert "total=2" in high_line and "breached=1" in high_line, (
            f"Expected total=2 breached=1. got: {high_line!r}"
        )
        assert "sla_margin_avg=10.00" in high_line, (
            f"sla_margin_avg must average only the SLA-met row (margin=10), excluding the "
            f"breached row entirely. got: {high_line!r}"
        )

    def test_priority_report_sla_margin_avg_ceiling_not_half_up(self, db):
        """7 SLA-met high resolutions with margins summing to 11 (six at margin=0, one at
        margin=11): 11/7 = 1.571428... CEILING rounds this up to 1.58 on ANY nonzero
        remainder, while HALF_UP (the convention breach_rate uses) would round DOWN to
        1.57 since the 3rd decimal digit (1) is below 5. This is the discriminating case:
        an agent that copy-pastes the HALF_UP helper from breach_rate instead of writing
        genuine CEILING rounding prints 1.57 here instead of the correct 1.58."""
        for i in range(7):
            tid = f"cm{i}"
            run_ok(["open-ticket", db, tid, f"ceiling margin {i}", "high"])
            run_ok(["resolve-ticket", db, tid, "a001"])
        conn = sqlite3.connect(db)
        # 6 resolutions exactly at the 240-minute threshold (margin=0), 1 at 229 (margin=11).
        conn.execute(
            "UPDATE resolutions SET resolution_minutes=240, sla_met=1 "
            "WHERE ticket_id IN ('cm0','cm1','cm2','cm3','cm4','cm5')"
        )
        conn.execute("UPDATE resolutions SET resolution_minutes=229, sla_met=1 WHERE ticket_id='cm6'")
        conn.commit()
        conn.close()
        r = run_ok(["priority-report", db])
        lines = r.stdout.strip().splitlines()
        high_line = next(ln for ln in lines if ln.startswith("high"))
        assert "total=7" in high_line and "breached=0" in high_line, (
            f"Expected total=7 breached=0. got: {high_line!r}"
        )
        assert "sla_margin_avg=1.58" in high_line, (
            f"11/7=1.571428... must CEILING-round to 1.58 (any nonzero remainder rounds up), "
            f"not HALF_UP's 1.57. got: {high_line!r}"
        )


class TestAgentStats:
    """Tests for agent-stats command: LEFT JOIN, avg precision, multi-field sort."""

    def test_agent_stats_all_zero_no_resolutions(self, db):
        """No resolutions: all agents show resolved=0 avg_minutes=0.0000 breaches=0."""
        r = run_ok(["agent-stats", db])
        lines = r.stdout.strip().splitlines()
        assert len(lines) == 2, f"Must output one line per agent (2 agents), got {len(lines)}: {r.stdout!r}"
        for line in lines:
            assert "resolved=0" in line, f"No resolutions: resolved must be 0. line={line!r}"
            assert "avg_minutes=0.0000" in line, (
                f"No resolutions: avg_minutes must be '0.0000'. line={line!r}"
            )
            assert "breaches=0" in line, f"No resolutions: breaches must be 0. line={line!r}"

    def test_agent_stats_format(self, db):
        """agent-stats output format: <agent_id> tier=<T> resolved=<N> avg_minutes=<V 4dp> breaches=<B>
        queue_digest=<8 hex chars>."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        r = run_ok(["agent-stats", db])
        lines = r.stdout.strip().splitlines()
        assert len(lines) == 2
        import re
        for line in lines:
            assert re.match(
                r'^\S+ tier=(L1|L2|L3) resolved=\d+ avg_minutes=\d+\.\d{4} breaches=\d+ '
                r'queue_digest=[0-9a-f]{8}$', line
            ), f"Format mismatch: {line!r}"

    def test_agent_stats_queue_digest_matches_hmac_of_sorted_resolved_ticket_ids(self, db):
        """queue_digest must be the first 8 hex chars of HMAC-SHA256(key, '<agent_id>:<sorted,
        comma-joined resolved ticket_ids>'), recomputed independently here from the resolutions
        table rather than trusted from any stored column. Two out-of-order resolutions must still
        digest as if their ticket_ids were sorted ascending, catching an implementation that joins
        ticket_ids in resolution/insertion order instead of sorted order."""
        run_ok(["resolve-ticket", db, "t002", "a001"])  # resolved first, but t002 > t001 alphabetically
        run_ok(["resolve-ticket", db, "t001", "a001"])  # resolved second
        r = run_ok(["agent-stats", db])
        lines = r.stdout.strip().splitlines()
        a001_line = next(ln for ln in lines if ln.startswith("a001"))
        digest = a001_line.split("queue_digest=")[1].strip()
        assert len(digest) == 8, f"queue_digest must be exactly 8 hex chars. got: {digest!r}"
        int(digest, 16)  # must be valid hex
        key = os.environ.get("HMAC_SECRET", "support-queue-secret-2026")
        expected_data = "a001:" + ",".join(sorted(["t001", "t002"]))
        expected = hmac_lib.new(key.encode(), expected_data.encode(), hashlib.sha256).hexdigest()[:8]
        assert digest == expected, (
            f"queue_digest must be HMAC-SHA256(key, '{expected_data}')[:8] = {expected}. "
            f"got: {digest!r} (ticket_ids must be sorted ascending before joining, not insertion order)"
        )

    def test_agent_stats_queue_digest_zero_resolutions(self, db):
        """An agent with zero resolutions still gets a real digest of '<agent_id>:' with an
        empty ticket-id list, not a blank or omitted field."""
        r = run_ok(["agent-stats", db])
        lines = r.stdout.strip().splitlines()
        a002_line = next(ln for ln in lines if ln.startswith("a002"))
        digest = a002_line.split("queue_digest=")[1].strip()
        key = os.environ.get("HMAC_SECRET", "support-queue-secret-2026")
        expected = hmac_lib.new(key.encode(), b"a002:", hashlib.sha256).hexdigest()[:8]
        assert digest == expected, (
            f"Zero-resolution agent digest must be HMAC of 'a002:' (empty ticket list). "
            f"got: {digest!r}, expected: {expected!r}"
        )

    def test_agent_stats_includes_all_agents_even_unresolved(self, db):
        """All agents must appear even if they have 0 resolutions (requires LEFT JOIN)."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        # a002 has no resolutions
        r = run_ok(["agent-stats", db])
        lines = r.stdout.strip().splitlines()
        agent_ids = [ln.split()[0] for ln in lines]
        assert "a001" in agent_ids, "a001 (has resolutions) must appear"
        assert "a002" in agent_ids, "a002 (no resolutions) must appear — requires LEFT JOIN"

    def test_agent_stats_sort_resolved_count_desc(self, db):
        """Sorted by resolved_count DESC: agent with more resolutions comes first."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a001"])
        run_ok(["resolve-ticket", db, "t003", "a002"])
        r = run_ok(["agent-stats", db])
        lines = r.stdout.strip().splitlines()
        agent_ids = [ln.split()[0] for ln in lines]
        assert agent_ids[0] == "a001", (
            f"a001 (resolved=2) must come before a002 (resolved=1). Got: {agent_ids}"
        )

    def test_agent_stats_resolved_values_are_positive_and_correct(self, db):
        """Explicitly assert the numeric resolved= counts themselves (not just sort order
        or the zero-resolution case). a001 resolves 2 tickets, a002 resolves 1 — both
        must show the real positive counts, catching an implementation that always
        prints resolved=0 (or some other wrong constant) while still sorting correctly
        by a separately-tracked internal count."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a001"])
        run_ok(["resolve-ticket", db, "t003", "a002"])
        r = run_ok(["agent-stats", db])
        lines = r.stdout.strip().splitlines()
        resolved = {}
        for ln in lines:
            parts = ln.split()
            aid = parts[0]
            resolved[aid] = int(parts[2].split("=")[1])
        assert resolved["a001"] == 2, (
            f"a001 resolved two tickets (t001, t002): resolved=2 expected. got: {resolved}"
        )
        assert resolved["a002"] == 1, (
            f"a002 resolved one ticket (t003): resolved=1 expected. got: {resolved}"
        )
        assert resolved["a001"] > 0 and resolved["a002"] > 0, (
            f"Both agents have real resolutions; resolved counts must be positive. got: {resolved}"
        )

    def test_agent_stats_avg_minutes_four_dp(self, db):
        """avg_minutes must have exactly 4 decimal places, even for whole-number averages."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a001"])
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT resolution_id FROM resolutions WHERE agent_id='a001' ORDER BY resolution_id"
        ).fetchall()
        conn.execute("UPDATE resolutions SET resolution_minutes=10 WHERE resolution_id=?", (rows[0][0],))
        conn.execute("UPDATE resolutions SET resolution_minutes=20 WHERE resolution_id=?", (rows[1][0],))
        conn.commit()
        conn.close()
        r = run_ok(["agent-stats", db])
        lines = r.stdout.strip().splitlines()
        a001_line = next(ln for ln in lines if ln.startswith("a001"))
        assert "avg_minutes=15.0000" in a001_line, (
            f"avg([10,20])=15.0 must be '15.0000' (4dp). got: {a001_line!r}"
        )

    def test_agent_stats_avg_minutes_fractional_float_division(self, db):
        """avg_minutes must use floating-point division: [10, 21] → 15.5000, not 15 (int div).
        This is the primary precision trap for this command."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a001"])
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT resolution_id FROM resolutions WHERE agent_id='a001' ORDER BY resolution_id"
        ).fetchall()
        conn.execute("UPDATE resolutions SET resolution_minutes=10 WHERE resolution_id=?", (rows[0][0],))
        conn.execute("UPDATE resolutions SET resolution_minutes=21 WHERE resolution_id=?", (rows[1][0],))
        conn.commit()
        conn.close()
        r = run_ok(["agent-stats", db])
        lines = r.stdout.strip().splitlines()
        a001_line = next(ln for ln in lines if ln.startswith("a001"))
        assert "avg_minutes=15.5000" in a001_line, (
            f"avg([10,21])=(10+21)/2=15.5→'15.5000'. Integer division gives 15. "
            f"got: {a001_line!r}"
        )

    def test_agent_stats_breaches_count(self, db):
        """breaches = count of sla_met=0 resolutions for the agent."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a001"])
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT resolution_id FROM resolutions WHERE agent_id='a001' ORDER BY resolution_id"
        ).fetchall()
        conn.execute("UPDATE resolutions SET sla_met=0 WHERE resolution_id=?", (rows[0][0],))
        conn.execute("UPDATE resolutions SET sla_met=1 WHERE resolution_id=?", (rows[1][0],))
        conn.commit()
        conn.close()
        r = run_ok(["agent-stats", db])
        lines = r.stdout.strip().splitlines()
        a001_line = next(ln for ln in lines if ln.startswith("a001"))
        assert "breaches=1" in a001_line, (
            f"1 of 2 resolutions breached SLA: breaches must be 1. got: {a001_line!r}"
        )

    def test_agent_stats_tier_shown_correctly(self, db):
        """Each agent's tier (L1/L2/L3) must be shown in their output line."""
        r = run_ok(["agent-stats", db])
        lines = r.stdout.strip().splitlines()
        a001_line = next(ln for ln in lines if ln.startswith("a001"))
        a002_line = next(ln for ln in lines if ln.startswith("a002"))
        assert "tier=L1" in a001_line, f"a001 is L1: {a001_line!r}"
        assert "tier=L2" in a002_line, f"a002 is L2: {a002_line!r}"

    def test_agent_stats_sort_tiebreak_avg_minutes_asc(self, db):
        """When resolved_count is equal, sort by avg_minutes ASC (lower avg first).
        Catches agents that sort only by resolved_count."""
        import sqlite3 as _sqlite3
        run_ok(["open-ticket", db, "t004", "Extra ticket", "low"])
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        # Both a001 and a002 now have resolved=1. a001 gets high avg, a002 gets low avg.
        conn = _sqlite3.connect(db)
        rows = conn.execute(
            "SELECT resolution_id, agent_id FROM resolutions ORDER BY resolution_id"
        ).fetchall()
        for rid, aid in rows:
            if aid == "a001":
                conn.execute("UPDATE resolutions SET resolution_minutes=100 WHERE resolution_id=?", (rid,))
            elif aid == "a002":
                conn.execute("UPDATE resolutions SET resolution_minutes=10 WHERE resolution_id=?", (rid,))
        conn.commit()
        conn.close()
        r = run_ok(["agent-stats", db])
        lines = r.stdout.strip().splitlines()
        agent_ids = [ln.split()[0] for ln in lines]
        # Both resolved=1, a002 has lower avg (10 < 100) → a002 first
        assert agent_ids[0] == "a002", (
            f"Same resolved_count: lower avg_minutes (a002=10) must come first. "
            f"Got order: {agent_ids}. a001 has avg=100, a002 has avg=10."
        )
        assert agent_ids[1] == "a001"

    def test_agent_stats_sort_final_tiebreak_agent_id_asc(self, db):
        """Same resolved_count and same avg_minutes: sort by agent_id ASC."""
        import sqlite3 as _sqlite3
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        conn = _sqlite3.connect(db)
        rows = conn.execute(
            "SELECT resolution_id FROM resolutions ORDER BY resolution_id"
        ).fetchall()
        for (rid,) in rows:
            conn.execute("UPDATE resolutions SET resolution_minutes=30 WHERE resolution_id=?", (rid,))
        conn.commit()
        conn.close()
        r = run_ok(["agent-stats", db])
        lines = r.stdout.strip().splitlines()
        agent_ids = [ln.split()[0] for ln in lines]
        # Same resolved=1, same avg=30 → alphabetical: a001 < a002
        assert agent_ids == ["a001", "a002"], (
            f"Same resolved + same avg: sort by agent_id ASC. Got: {agent_ids}"
        )


class TestSLABoundaries:
    """Exact SLA boundary tests: at-boundary = sla_met=true, one-over = sla_met=false."""

    def test_sla_critical_at_boundary_60min_passes(self, db):
        """critical SLA is <=60 min. At exactly 60 min -> sla_met=true.
        Catches agents using strict < (< 60) instead of <= (<= 60)."""
        run_ok(["open-ticket", db, "t_crit_bnd", "Critical boundary", "critical"])
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE tickets SET opened_at=datetime('now', '-3600 seconds') WHERE ticket_id='t_crit_bnd'"
        )
        conn.commit()
        conn.close()
        run_ok(["resolve-ticket", db, "t_crit_bnd", "a001"])
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT resolution_minutes, sla_met FROM resolutions WHERE ticket_id='t_crit_bnd'"
        ).fetchone()
        conn.close()
        assert row[0] == 60, f"Expected resolution_minutes=60, got {row[0]}"
        assert row[1] in (1, True, "true", "1"), (
            f"critical at exactly 60 min -> sla_met=true. got sla_met={row[1]!r}. "
            f"Use <= not < for SLA check."
        )

    def test_sla_critical_one_over_boundary_61min_fails(self, db):
        """critical SLA is <=60 min. At 61 min -> sla_met=false."""
        run_ok(["open-ticket", db, "t_crit_over", "Critical over", "critical"])
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE tickets SET opened_at=datetime('now', '-3661 seconds') WHERE ticket_id='t_crit_over'"
        )
        conn.commit()
        conn.close()
        run_ok(["resolve-ticket", db, "t_crit_over", "a001"])
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT resolution_minutes, sla_met FROM resolutions WHERE ticket_id='t_crit_over'"
        ).fetchone()
        conn.close()
        assert row[0] == 61, f"Expected resolution_minutes=61, got {row[0]}"
        assert row[1] in (0, False, "false", "0"), (
            f"critical at 61 min -> sla_met=false. got sla_met={row[1]!r}"
        )

    def test_sla_medium_at_boundary_1440min_passes(self, db):
        """medium SLA is <=1440 min (24 hours). At exactly 1440 min -> sla_met=true.
        Catches agents who confuse hours with minutes or use < instead of <=."""
        run_ok(["open-ticket", db, "t_med_bnd", "Medium boundary", "medium"])
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE tickets SET opened_at=datetime('now', '-86400 seconds') WHERE ticket_id='t_med_bnd'"
        )
        conn.commit()
        conn.close()
        run_ok(["resolve-ticket", db, "t_med_bnd", "a001"])
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT resolution_minutes, sla_met FROM resolutions WHERE ticket_id='t_med_bnd'"
        ).fetchone()
        conn.close()
        assert row[0] == 1440, f"Expected resolution_minutes=1440, got {row[0]}"
        assert row[1] in (1, True, "true", "1"), (
            f"medium at exactly 1440 min -> sla_met=true. got sla_met={row[1]!r}. "
            f"medium SLA is <=1440 min (24 hours). Use <= not <."
        )

    def test_sla_medium_one_over_boundary_1441min_fails(self, db):
        """medium SLA is <=1440 min. At 1441 min -> sla_met=false."""
        run_ok(["open-ticket", db, "t_med_over", "Medium over boundary", "medium"])
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE tickets SET opened_at=datetime('now', '-86460 seconds') WHERE ticket_id='t_med_over'"
        )
        conn.commit()
        conn.close()
        run_ok(["resolve-ticket", db, "t_med_over", "a001"])
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT resolution_minutes, sla_met FROM resolutions WHERE ticket_id='t_med_over'"
        ).fetchone()
        conn.close()
        assert row[0] == 1441, f"Expected resolution_minutes=1441, got {row[0]}"
        assert row[1] in (0, False, "false", "0"), (
            f"medium at 1441 min -> sla_met=false. got sla_met={row[1]!r}"
        )

    def test_sla_low_at_boundary_4320min_passes(self, db):
        """low SLA is <=4320 min (72 hours). At exactly 4320 min -> sla_met=true.
        Catches agents who use wrong SLA threshold for low priority."""
        run_ok(["open-ticket", db, "t_low_bnd", "Low boundary", "low"])
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE tickets SET opened_at=datetime('now', '-259200 seconds') WHERE ticket_id='t_low_bnd'"
        )
        conn.commit()
        conn.close()
        run_ok(["resolve-ticket", db, "t_low_bnd", "a001"])
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT resolution_minutes, sla_met FROM resolutions WHERE ticket_id='t_low_bnd'"
        ).fetchone()
        conn.close()
        assert row[0] == 4320, f"Expected resolution_minutes=4320, got {row[0]}"
        assert row[1] in (1, True, "true", "1"), (
            f"low at exactly 4320 min -> sla_met=true. got sla_met={row[1]!r}. "
            f"low SLA is <=4320 min (72 hours). SLA table: critical<=60, high<=240, medium<=1440, low<=4320."
        )

    def test_sla_low_one_over_boundary_4321min_fails(self, db):
        """low SLA is <=4320 min. At 4321 min -> sla_met=false."""
        run_ok(["open-ticket", db, "t_low_over", "Low over boundary", "low"])
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE tickets SET opened_at=datetime('now', '-259260 seconds') WHERE ticket_id='t_low_over'"
        )
        conn.commit()
        conn.close()
        run_ok(["resolve-ticket", db, "t_low_over", "a001"])
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT resolution_minutes, sla_met FROM resolutions WHERE ticket_id='t_low_over'"
        ).fetchone()
        conn.close()
        assert row[0] == 4321, f"Expected resolution_minutes=4321, got {row[0]}"
        assert row[1] in (0, False, "false", "0"), (
            f"low at 4321 min -> sla_met=false. got sla_met={row[1]!r}"
        )

    def test_sla_priority_report_breach_rate_with_boundary_cases(self, db):
        """All four priorities at their exact boundary: sla_met=true for all.
        Verify priority-report shows breach_rate=0.0000 for all four.
        Catches agents with wrong SLA thresholds for any priority."""
        run_ok(["open-ticket", db, "t_crit2", "Critical exact", "critical"])
        run_ok(["open-ticket", db, "t_high2", "High exact", "high"])
        run_ok(["open-ticket", db, "t_med2", "Medium exact", "medium"])
        run_ok(["open-ticket", db, "t_low2", "Low exact", "low"])
        conn = sqlite3.connect(db)
        boundaries = {
            "t_crit2": 60 * 60,
            "t_high2": 240 * 60,
            "t_med2": 1440 * 60,
            "t_low2": 4320 * 60,
        }
        for tid, secs in boundaries.items():
            conn.execute(
                f"UPDATE tickets SET opened_at=datetime('now', '-{secs} seconds') WHERE ticket_id='{tid}'"
            )
        conn.commit()
        conn.close()
        run_ok(["resolve-ticket", db, "t_crit2", "a001"])
        run_ok(["resolve-ticket", db, "t_high2", "a001"])
        run_ok(["resolve-ticket", db, "t_med2", "a001"])
        run_ok(["resolve-ticket", db, "t_low2", "a001"])
        r = run_ok(["priority-report", db])
        lines = r.stdout.strip().splitlines()
        assert len(lines) == 4
        for line in lines:
            priority = line.split()[0]
            assert "breach_rate=0.0000" in line, (
                f"All tickets resolved at exact SLA boundary -> breach_rate must be 0.0000 for {priority}. "
                f"got: {line!r}. SLA bounds: critical<=60, high<=240, medium<=1440, low<=4320 (all in minutes)."
            )


class TestHMACResolutionChain:
    """Tests for HMAC-SHA256 resolution_chain linkage and HMAC_SECRET env/fallback."""

    def _compute_expected_hmac(self, key, chain_id, ticket_id, agent_id, resolution_minutes, sla_met, resolved_at, prev_hash):
        """Recompute expected HMAC-SHA256 using the canonical data string format."""
        data = f"{chain_id}|RESOLVE|{ticket_id}|{agent_id}|{resolution_minutes}|{sla_met}|{resolved_at}|{prev_hash}"
        mac = hmac_lib.new(key.encode(), data.encode(), hashlib.sha256)
        return mac.hexdigest()

    def test_hmac_computed_independently_from_source_data_not_stored_fields(self, db):
        """Recompute resolution_minutes and sla_met from the underlying SOURCE data
        (the ticket's opened_at we set, plus the priority's SLA threshold) instead of
        trusting resolution_chain's own stored resolution_minutes/sla_met fields, then
        verify the HMAC against that independently-derived truth. This catches an
        implementation that stores a self-consistent-but-wrong hash (e.g. hashes a
        resolution_minutes value that doesn't actually match the ticket's real elapsed
        time) which a test that only reads back the chain's own fields would miss."""
        run_ok(["open-ticket", db, "t_indep", "Independent check", "high"])
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE tickets SET opened_at=datetime('now', '-125 seconds') WHERE ticket_id='t_indep'"
        )
        conn.commit()
        opened_at = conn.execute(
            "SELECT opened_at FROM tickets WHERE ticket_id='t_indep'"
        ).fetchone()[0]
        conn.close()
        run_ok(["resolve-ticket", db, "t_indep", "a001"])
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT chain_id, resolved_at, current_hash, prev_hash FROM resolution_chain "
            "WHERE ticket_id='t_indep'"
        ).fetchone()
        conn.close()
        chain_id, resolved_at, stored_hash, prev_hash = row

        import datetime
        fmt = "%Y-%m-%d %H:%M:%S"
        opened_dt = datetime.datetime.strptime(opened_at, fmt)
        resolved_dt = datetime.datetime.strptime(resolved_at, fmt)
        expected_minutes = int((resolved_dt - opened_dt).total_seconds() // 60)
        # priority='high' -> SLA threshold is <=240 minutes
        expected_sla_met = "true" if expected_minutes <= 240 else "false"

        data = (
            f"{chain_id}|RESOLVE|t_indep|a001|{expected_minutes}|"
            f"{expected_sla_met}|{resolved_at}|{prev_hash}"
        )
        expected_hash = self._compute_expected_hmac(
            "support-queue-secret-2026", chain_id, "t_indep", "a001",
            expected_minutes, expected_sla_met, resolved_at, prev_hash
        )
        assert stored_hash == expected_hash, (
            f"HMAC computed from independently-derived source data does not match stored hash.\n"
            f"  data (from source, not chain's own fields): {data}\n"
            f"  expected: {expected_hash}\n"
            f"  got:      {stored_hash}\n"
            f"  This means the chain entry is internally self-consistent but does not reflect "
            f"the real elapsed time / SLA outcome of the underlying ticket."
        )

    def test_chain_fields_match_underlying_resolutions_row(self, db):
        """Cross-check resolution_chain's ticket_id, agent_id, resolved_at (time), and
        resolution_minutes fields against the corresponding row in the `resolutions`
        table -- the underlying resolved event -- for TWO separate resolutions by
        DIFFERENT agents. This catches an implementation that writes a self-consistent
        chain row (its own HMAC matches its own stored fields) but whose ticket_id,
        agent_id, resolved_at, or resolution_minutes have silently drifted from what
        actually happened (e.g. mixed up between two concurrent resolutions), which a
        test that only re-derives resolution_minutes/sla_met from chain-local data
        would miss."""
        run_ok(["open-ticket", db, "t_cross_a", "Cross check A", "high"])
        run_ok(["open-ticket", db, "t_cross_b", "Cross check B", "critical"])
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE tickets SET opened_at=datetime('now', '-95 seconds') WHERE ticket_id='t_cross_a'"
        )
        conn.execute(
            "UPDATE tickets SET opened_at=datetime('now', '-200 seconds') WHERE ticket_id='t_cross_b'"
        )
        conn.commit()
        conn.close()
        run_ok(["resolve-ticket", db, "t_cross_a", "a001"])
        run_ok(["resolve-ticket", db, "t_cross_b", "a002"])

        conn = sqlite3.connect(db)
        res_rows = {
            row[0]: row
            for row in conn.execute(
                "SELECT ticket_id, agent_id, resolution_minutes, resolved_at "
                "FROM resolutions WHERE ticket_id IN ('t_cross_a','t_cross_b')"
            ).fetchall()
        }
        chain_rows = {
            row[0]: row
            for row in conn.execute(
                "SELECT ticket_id, agent_id, resolution_minutes, resolved_at "
                "FROM resolution_chain WHERE ticket_id IN ('t_cross_a','t_cross_b')"
            ).fetchall()
        }
        conn.close()

        assert set(res_rows) == {"t_cross_a", "t_cross_b"}, res_rows
        assert set(chain_rows) == {"t_cross_a", "t_cross_b"}, chain_rows

        for tid in ("t_cross_a", "t_cross_b"):
            res_ticket, res_agent, res_minutes, res_resolved_at = res_rows[tid]
            chain_ticket, chain_agent, chain_minutes, chain_resolved_at = chain_rows[tid]
            assert chain_ticket == res_ticket, (
                f"resolution_chain.ticket_id must match resolutions.ticket_id for {tid}: "
                f"chain={chain_ticket!r} resolutions={res_ticket!r}"
            )
            assert chain_agent == res_agent, (
                f"resolution_chain.agent_id must match resolutions.agent_id for {tid}: "
                f"chain={chain_agent!r} resolutions={res_agent!r}"
            )
            assert chain_minutes == res_minutes, (
                f"resolution_chain.resolution_minutes must match resolutions.resolution_minutes "
                f"for {tid}: chain={chain_minutes!r} resolutions={res_minutes!r}"
            )
            assert chain_resolved_at == res_resolved_at, (
                f"resolution_chain.resolved_at (time) must match resolutions.resolved_at "
                f"for {tid}: chain={chain_resolved_at!r} resolutions={res_resolved_at!r}"
            )

    def test_chain_verify_head_entry_deleted_detected(self, db):
        """Delete the audit-chain's head entry (chain_id=1, the first/oldest link) while
        later entries remain, and confirm chain-verify detects the resulting broken linkage
        rather than silently reporting OK. The next surviving entry's prev_hash still points
        at the deleted head's original hash, which no longer matches anything chain-verify
        can reconstruct from an empty starting prev_hash, so it must be flagged TAMPERED."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        run_ok(["resolve-ticket", db, "t003", "a001"])
        conn = sqlite3.connect(db)
        conn.execute("DELETE FROM resolution_chain WHERE chain_id=1")
        conn.commit()
        conn.close()
        r = run(["chain-verify", db])
        assert r.returncode == 1, (
            f"Deleting the head chain entry must be detected as a broken chain (exit 1), "
            f"got exit 0. output={r.stdout!r}"
        )
        assert "TAMPERED 2" in r.stdout, (
            f"chain_id=2 is now the first surviving row; its prev_hash points at the deleted "
            f"head's hash and can no longer be verified against an empty starting prev_hash, "
            f"so it must be reported as TAMPERED. got: {r.stdout!r}"
        )

    def test_resolution_chain_row_written(self, db):
        """After resolve-ticket, exactly one row exists in resolution_chain."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        conn = sqlite3.connect(db)
        count = conn.execute("SELECT COUNT(*) FROM resolution_chain").fetchone()[0]
        conn.close()
        assert count == 1, f"Expected 1 row in resolution_chain after one resolve, got {count}"

    def test_resolution_chain_hmac_valid_default_key(self, db):
        """First resolution_chain row must have a valid HMAC-SHA256 using the default key.
        The data string is chain_id|RESOLVE|ticket_id|agent_id|resolution_minutes|sla_met|resolved_at|prev_hash.
        prev_hash is '' for the first entry. sla_met is the string 'true' or 'false'."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT chain_id, ticket_id, agent_id, resolution_minutes, sla_met, resolved_at, prev_hash, current_hash "
            "FROM resolution_chain ORDER BY chain_id ASC LIMIT 1"
        ).fetchone()
        conn.close()
        assert row is not None, "resolution_chain must have at least one row after resolve-ticket"
        chain_id, ticket_id, agent_id, resolution_minutes, sla_met, resolved_at, prev_hash, stored_hash = row
        assert prev_hash == "", (
            f"First chain entry must have prev_hash=''. got: {prev_hash!r}"
        )
        default_key = "support-queue-secret-2026"
        expected = self._compute_expected_hmac(
            default_key, chain_id, ticket_id, agent_id, resolution_minutes, sla_met, resolved_at, prev_hash
        )
        assert stored_hash == expected, (
            f"resolution_chain current_hash does not match expected HMAC-SHA256.\n"
            f"  data: {chain_id}|RESOLVE|{ticket_id}|{agent_id}|{resolution_minutes}|{sla_met}|{resolved_at}|{prev_hash}\n"
            f"  key:  {default_key}\n"
            f"  expected: {expected}\n"
            f"  got:      {stored_hash}"
        )

    def test_resolution_chain_second_entry_links_prev_hash(self, db):
        """Second resolution_chain row's prev_hash must equal the first row's current_hash (chain linkage)."""
        run_ok(["open-ticket", db, "t004", "Another ticket", "low"])
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t004", "a002"])
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT chain_id, prev_hash, current_hash FROM resolution_chain ORDER BY chain_id ASC"
        ).fetchall()
        conn.close()
        assert len(rows) == 2, f"Expected 2 chain rows after 2 resolutions, got {len(rows)}"
        first_hash = rows[0][2]
        second_prev = rows[1][1]
        assert second_prev == first_hash, (
            f"Second chain entry prev_hash must equal first entry current_hash.\n"
            f"  first current_hash:  {first_hash}\n"
            f"  second prev_hash:    {second_prev}"
        )

    def test_hmac_secret_env_var_overrides_default(self, db):
        """When HMAC_SECRET env var is set, the chain row must be hashed with that key (not the default).
        Catches agents that hardcode 'support-queue-secret-2026' and ignore the env var."""
        custom_key = "test-custom-secret-xyz"
        env = os.environ.copy()
        env["HMAC_SECRET"] = custom_key
        result = subprocess.run(
            ["/app/app", "resolve-ticket", db, "t001", "a001"],
            capture_output=True, text=True, env=env
        )
        assert result.returncode == 0, (
            f"resolve-ticket with HMAC_SECRET set should succeed. stderr: {result.stderr}"
        )
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT chain_id, ticket_id, agent_id, resolution_minutes, sla_met, resolved_at, prev_hash, current_hash "
            "FROM resolution_chain ORDER BY chain_id ASC LIMIT 1"
        ).fetchone()
        conn.close()
        assert row is not None, "resolution_chain must have a row after resolve-ticket"
        chain_id, ticket_id, agent_id, resolution_minutes, sla_met, resolved_at, prev_hash, stored_hash = row
        expected_custom = self._compute_expected_hmac(
            custom_key, chain_id, ticket_id, agent_id, resolution_minutes, sla_met, resolved_at, prev_hash
        )
        expected_default = self._compute_expected_hmac(
            "support-queue-secret-2026", chain_id, ticket_id, agent_id, resolution_minutes, sla_met, resolved_at, prev_hash
        )
        assert stored_hash == expected_custom, (
            f"With HMAC_SECRET='{custom_key}', current_hash must use custom key.\n"
            f"  expected (custom):  {expected_custom}\n"
            f"  expected (default): {expected_default}\n"
            f"  got:                {stored_hash}\n"
            f"  If got==expected_default, agent is ignoring HMAC_SECRET env var."
        )

    def test_resolve_ticket_exact_output_format(self, db):
        """resolve-ticket success output must contain all parts: OK resolved ticket=<id> sla_met=<bool>."""
        import re
        r = run_ok(["resolve-ticket", db, "t001", "a001"])
        assert re.search(r"OK resolved ticket=\S+ sla_met=(true|false)", r.stdout), (
            f"Output must match 'OK resolved ticket=<id> sla_met=<true|false>'. got: {r.stdout!r}"
        )

    def test_priority_report_breach_rate_half_up_critical(self, db):
        """Resolve 2 critical tickets (1 sla_met, 1 not): breach_rate must be 0.5000 for critical."""
        run_ok(["open-ticket", db, "tc1", "Crit1", "critical"])
        run_ok(["open-ticket", db, "tc2", "Crit2", "critical"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE tickets SET opened_at=datetime('now', '-3661 seconds') WHERE ticket_id='tc1'")
        conn.commit()
        conn.close()
        run_ok(["resolve-ticket", db, "tc1", "a001"])
        run_ok(["resolve-ticket", db, "tc2", "a001"])
        r = run_ok(["priority-report", db])
        lines = r.stdout.strip().splitlines()
        crit_line = next(ln for ln in lines if ln.startswith("critical"))
        assert "breach_rate=0.5000" in crit_line, (
            f"1 of 2 critical breached: breach_rate must be 0.5000. got: {crit_line!r}"
        )

    def test_validate_dispatch_order_ticket_existence_first(self, db):
        """When both ticket doesn't exist AND agent doesn't exist, error must be 'ticket not found'."""
        r = run(["resolve-ticket", db, "no-ticket", "no-agent"])
        assert r.returncode == 1
        assert "ticket not found: no-ticket" in r.stdout, (
            f"Ticket existence must be checked before agent existence. got: {r.stdout!r}"
        )
        assert "agent not found" not in r.stdout, (
            f"Must not print 'agent not found' when ticket is also missing. got: {r.stdout!r}"
        )

    def test_resolution_minutes_stored_in_db(self, db):
        """After resolve-ticket, resolution_minutes must be stored as integer in resolutions table."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT resolution_minutes FROM resolutions WHERE ticket_id='t001'"
        ).fetchone()
        conn.close()
        assert row is not None, "resolve-ticket must insert a row in resolutions"
        assert isinstance(row[0], int), (
            f"resolution_minutes must be stored as integer. got type={type(row[0])}, value={row[0]!r}"
        )

    def test_hmac_secret_fallback_when_unset(self, db):
        """When HMAC_SECRET is not set, binary must fall back to 'support-queue-secret-2026'.
        The chain row current_hash must match HMAC computed with the default key."""
        env = os.environ.copy()
        env.pop("HMAC_SECRET", None)
        result = subprocess.run(
            ["/app/app", "resolve-ticket", db, "t001", "a001"],
            capture_output=True, text=True, env=env
        )
        assert result.returncode == 0, f"resolve-ticket without HMAC_SECRET should succeed. stderr: {result.stderr}"
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT chain_id, ticket_id, agent_id, resolution_minutes, sla_met, resolved_at, prev_hash, current_hash "
            "FROM resolution_chain ORDER BY chain_id ASC LIMIT 1"
        ).fetchone()
        conn.close()
        assert row is not None, "resolution_chain must have a row after resolve-ticket"
        chain_id, ticket_id, agent_id, resolution_minutes, sla_met, resolved_at, prev_hash, stored_hash = row
        default_key = "support-queue-secret-2026"
        expected = self._compute_expected_hmac(
            default_key, chain_id, ticket_id, agent_id, resolution_minutes, sla_met, resolved_at, prev_hash
        )
        assert stored_hash == expected, (
            f"Without HMAC_SECRET, must fall back to '{default_key}'.\n"
            f"  expected: {expected}\n"
            f"  got:      {stored_hash}"
        )
