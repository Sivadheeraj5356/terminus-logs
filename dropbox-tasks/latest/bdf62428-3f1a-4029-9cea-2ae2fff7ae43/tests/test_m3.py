"""Milestone 3 tests: chain-verify and sla-report."""
import subprocess
import sqlite3
import hmac
import hashlib
import math
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


class TestMilestone3:
    def test_chain_verify_empty_ok(self, db):
        r = run_ok(["chain-verify", db])
        assert "OK" in r.stdout

    def test_chain_verify_valid_chain_ok(self, db):
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a001"])
        r = run_ok(["chain-verify", db])
        assert r.stdout.strip() == "OK"

    def test_chain_verify_tampered_hash(self, db):
        run_ok(["resolve-ticket", db, "t001", "a001"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE resolution_chain SET current_hash='deadbeef' WHERE chain_id=1")
        conn.commit()
        conn.close()
        r = run(["chain-verify", db])
        assert r.returncode == 1
        assert "TAMPERED" in r.stdout

    def test_chain_verify_tampered_resolution_minutes(self, db):
        run_ok(["resolve-ticket", db, "t001", "a001"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE resolution_chain SET resolution_minutes=9999 WHERE chain_id=1")
        conn.commit()
        conn.close()
        r = run(["chain-verify", db])
        assert r.returncode == 1
        assert "TAMPERED 1" in r.stdout

    def test_chain_verify_second_entry_prev_hash(self, db):
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE resolution_chain SET current_hash='badhash' WHERE chain_id=1")
        conn.commit()
        conn.close()
        r = run(["chain-verify", db])
        assert r.returncode == 1

    def test_chain_verify_exit_zero_clean(self, db):
        run_ok(["resolve-ticket", db, "t001", "a001"])
        r = run(["chain-verify", db])
        assert r.returncode == 0

    def test_sla_report_empty(self, db):
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        assert lines["total_tickets"] == "3"
        assert float(lines["sla_met_pct"]) == 0.0

    def test_sla_report_empty_all_seven_fields(self, db):
        """No resolutions: ALL SEVEN sla-report fields must be present and correctly
        zero-valued, not just total_tickets/sla_met_pct (a subset check is not enough)."""
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        assert len(lines) == 7, f"Expected 7 fields, got {len(lines)}: {r.stdout!r}"
        assert lines["total_tickets"] == "3", (
            f"db fixture opens 3 tickets, 0 resolved: total_tickets must be 3. got: {lines!r}"
        )
        assert lines["sla_met_pct"] == "0.0000", f"got: {lines!r}"
        assert lines["p50_resolution_minutes"] == "0", f"got: {lines!r}"
        assert lines["p75_resolution_minutes"] == "0", f"got: {lines!r}"
        assert lines["p95_resolution_minutes"] == "0", f"got: {lines!r}"
        assert lines["std_resolution"] == "0.0000", f"got: {lines!r}"
        assert lines["avg_resolution_minutes"] == "0.0000", f"got: {lines!r}"

    def test_sla_report_format(self, db):
        run_ok(["resolve-ticket", db, "t001", "a001"])
        r = run_ok(["sla-report", db])
        lines = r.stdout.strip().splitlines()
        assert len(lines) == 7, f"sla-report must have 7 lines, got {len(lines)}: {r.stdout!r}"
        keys = [ln.split("=")[0] for ln in lines]
        assert keys == ["total_tickets", "sla_met_pct", "p50_resolution_minutes",
                        "p75_resolution_minutes", "p95_resolution_minutes", "std_resolution",
                        "avg_resolution_minutes"]

    def test_sla_met_pct_four_decimal_places(self, db):
        run_ok(["resolve-ticket", db, "t001", "a001"])
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        pct_str = lines["sla_met_pct"]
        assert "." in pct_str
        assert len(pct_str.split(".")[1]) == 4

    def test_sla_report_total_tickets_count(self, db):
        run_ok(["resolve-ticket", db, "t001", "a001"])
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        assert lines["total_tickets"] == "3"

    def test_sla_report_nearest_rank_p50(self, db):
        # Insert 3 resolutions with known minutes via direct db manipulation
        # then verify p50 uses nearest-rank not linear interpolation
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        run_ok(["resolve-ticket", db, "t003", "a001"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE resolutions SET resolution_minutes=10 WHERE resolution_id=1")
        conn.execute("UPDATE resolutions SET resolution_minutes=30 WHERE resolution_id=2")
        conn.execute("UPDATE resolutions SET resolution_minutes=50 WHERE resolution_id=3")
        conn.commit()
        conn.close()
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        # n=3, p50: rank=ceil(0.5*3)=ceil(1.5)=2, sorted=[10,30,50], value=30
        assert float(lines["p50_resolution_minutes"]) == 30.0

    def test_sla_report_population_stddev(self, db):
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE resolutions SET resolution_minutes=10 WHERE resolution_id=1")
        conn.execute("UPDATE resolutions SET resolution_minutes=20 WHERE resolution_id=2")
        conn.commit()
        conn.close()
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        # population stddev of [10, 20]: mean=15, variance=((10-15)^2+(20-15)^2)/2=25, std=5.0
        assert abs(float(lines["std_resolution"]) - 5.0) < 0.001


_HMAC_KEY = b"support-queue-secret-2026"


def _compute_hmac(data: str) -> str:
    return hmac.new(_HMAC_KEY, data.encode(), hashlib.sha256).hexdigest()


class TestHardPrecisionTraps:
    """Precision traps targeting common agent implementation mistakes."""

    def test_hmac_first_entry_independent_verification(self, db):
        """Independently compute the HMAC for the first chain entry and verify it matches.
        Data format: chain_id|RESOLVE|ticket_id|agent_id|resolution_minutes|sla_met|resolved_at|prev_hash
        First entry prev_hash must be empty string "".
        This test catches agents that: use wrong key, wrong data format, wrong field order."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT chain_id, ticket_id, agent_id, resolution_minutes, sla_met, resolved_at, current_hash "
            "FROM resolution_chain WHERE chain_id=1"
        ).fetchone()
        conn.close()
        chain_id, ticket_id, agent_id, res_min, sla_met, resolved_at, stored_hash = row
        sla_str = "true" if sla_met else "false"
        data = f"{chain_id}|RESOLVE|{ticket_id}|{agent_id}|{res_min}|{sla_str}|{resolved_at}|"
        expected_hash = _compute_hmac(data)
        assert stored_hash == expected_hash, (
            f"HMAC mismatch for chain_id=1: stored={stored_hash[:16]}... "
            f"expected={expected_hash[:16]}... "
            f"data_used='{data[:60]}...'"
        )

    def test_hmac_second_entry_uses_prev_hash(self, db):
        """Second chain entry's prev_hash must equal first entry's current_hash exactly."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        conn = sqlite3.connect(db)
        row1 = conn.execute(
            "SELECT chain_id, ticket_id, agent_id, resolution_minutes, sla_met, resolved_at, current_hash "
            "FROM resolution_chain WHERE chain_id=1"
        ).fetchone()
        row2 = conn.execute(
            "SELECT chain_id, ticket_id, agent_id, resolution_minutes, sla_met, resolved_at, current_hash "
            "FROM resolution_chain WHERE chain_id=2"
        ).fetchone()
        conn.close()
        prev_hash = row1[6]
        chain_id, ticket_id, agent_id, res_min, sla_met, resolved_at, stored_hash = row2
        sla_str = "true" if sla_met else "false"
        data = f"{chain_id}|RESOLVE|{ticket_id}|{agent_id}|{res_min}|{sla_str}|{resolved_at}|{prev_hash}"
        expected_hash = _compute_hmac(data)
        assert stored_hash == expected_hash, (
            f"Chain entry 2 HMAC mismatch: prev_hash chaining failed. "
            f"stored={stored_hash[:16]}... expected={expected_hash[:16]}..."
        )

    def test_population_stddev_four_values(self, db):
        """Population stddev (divide by n NOT n-1) with 4 known values.
        Catches agents using sample stddev (Bessel's correction) which differs significantly."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        run_ok(["resolve-ticket", db, "t003", "a001"])
        run_ok(["add-agent", db, "a003", "Carol", "L1"])
        run_ok(["open-ticket", db, "t004", "Test", "low"])
        run_ok(["resolve-ticket", db, "t004", "a003"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE resolutions SET resolution_minutes=10 WHERE resolution_id=1")
        conn.execute("UPDATE resolutions SET resolution_minutes=20 WHERE resolution_id=2")
        conn.execute("UPDATE resolutions SET resolution_minutes=30 WHERE resolution_id=3")
        conn.execute("UPDATE resolutions SET resolution_minutes=40 WHERE resolution_id=4")
        conn.commit()
        conn.close()
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        vals = [10, 20, 30, 40]
        mean = sum(vals) / len(vals)
        pop_var = sum((v - mean) ** 2 for v in vals) / len(vals)
        expected_std = math.sqrt(pop_var)
        actual_std = float(lines["std_resolution"])
        assert abs(actual_std - expected_std) < 0.005, (
            f"std_resolution={actual_std:.4f} expected population stddev={expected_std:.4f}. "
            f"Use n (not n-1): variance=sum((x-mean)^2)/n"
        )

    def test_nearest_rank_p95_boundary(self, db):
        """p95 with n=20 resolved: rank=ceil(0.95*20)=19, 19th sorted value.
        Catches agents using linear interpolation instead of nearest-rank."""
        for i in range(20):
            tid = f"tpct{i:03d}"
            priority = "critical" if i < 3 else "high"
            run_ok(["open-ticket", db, tid, "test", priority])
            run_ok(["resolve-ticket", db, tid, "a001"])
        conn = sqlite3.connect(db)
        rows = conn.execute("SELECT resolution_id FROM resolutions ORDER BY resolution_id").fetchall()
        for idx, (rid,) in enumerate(rows):
            conn.execute("UPDATE resolutions SET resolution_minutes=? WHERE resolution_id=?", (idx + 1, rid))
        conn.commit()
        conn.close()
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        n_resolved = len(rows)
        rank = math.ceil(0.95 * n_resolved)
        sorted_vals = sorted(range(1, n_resolved + 1))
        expected_p95 = float(sorted_vals[rank - 1])
        actual_p95 = float(lines["p95_resolution_minutes"])
        assert abs(actual_p95 - expected_p95) < 0.005, (
            f"p95={actual_p95} expected nearest-rank={expected_p95} (rank={rank} of n={n_resolved}). "
            f"Use ceil(q*n) not linear interpolation."
        )

    def test_sla_boundary_exact_high_priority(self, db):
        """SLA for 'high' priority is <= 240 minutes (not strictly <).
        Set opened_at to exactly 240 minutes ago -> resolve-ticket stdout must show sla_met=true.
        Set opened_at to 241 minutes ago -> resolve-ticket stdout must show sla_met=false.
        Catches off-by-one errors in SLA boundary computation."""
        run_ok(["add-agent", db, "a003", "Carol", "L2"])
        run_ok(["open-ticket", db, "t_bnd1", "Boundary test", "high"])
        run_ok(["open-ticket", db, "t_bnd2", "Over boundary", "high"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE tickets SET opened_at=datetime('now', '-14400 seconds') WHERE ticket_id='t_bnd1'")
        conn.execute("UPDATE tickets SET opened_at=datetime('now', '-14460 seconds') WHERE ticket_id='t_bnd2'")
        conn.commit()
        conn.close()
        r_met = run_ok(["resolve-ticket", db, "t_bnd1", "a003"])
        r_not_met = run_ok(["resolve-ticket", db, "t_bnd2", "a003"])
        assert "sla_met=true" in r_met.stdout, (
            f"Ticket open exactly 14400s (240 min) for 'high' priority: "
            f"resolve-ticket must output 'sla_met=true' (SLA is <= 240, boundary is inclusive). "
            f"Use <= not < for SLA check. got stdout: {r_met.stdout!r}"
        )
        assert "sla_met=false" in r_not_met.stdout, (
            f"Ticket open 14460s (241 min) for 'high' priority (SLA=240): "
            f"resolve-ticket must output 'sla_met=false'. "
            f"got stdout: {r_not_met.stdout!r}"
        )

    def test_population_stddev_n3_diverges_from_sample(self, db):
        """N=3 values [3,6,9]: pop_std=sqrt(6)=2.4495, sample_std=sqrt(9)=3.0000.
        This is the most discriminating N for spotting Bessel correction errors."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        run_ok(["resolve-ticket", db, "t003", "a001"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE resolutions SET resolution_minutes=3 WHERE resolution_id=1")
        conn.execute("UPDATE resolutions SET resolution_minutes=6 WHERE resolution_id=2")
        conn.execute("UPDATE resolutions SET resolution_minutes=9 WHERE resolution_id=3")
        conn.commit()
        conn.close()
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        # pop_std([3,6,9]): mean=6, variance=(9+0+9)/3=6, std=sqrt(6)=2.4495
        # sample_std([3,6,9]): variance=(9+0+9)/2=9, std=sqrt(9)=3.0000 (wrong)
        expected = math.sqrt(6)
        actual = float(lines["std_resolution"])
        assert abs(actual - expected) < 0.0005, (
            f"std_resolution={actual:.4f} but pop_std([3,6,9])={expected:.4f}. "
            f"Sample stddev (wrong) gives 3.0000. Must divide by n=3 not n-1=2."
        )

    def test_nearest_rank_p75_n4_ceiling_trap(self, db):
        """N=4 sorted [10,20,30,40]: p75 rank=ceil(0.75*4)=ceil(3.0)=3, value=30.
        Linear interpolation gives 32.5 here, nearest-rank must return 30."""
        run_ok(["add-agent", db, "a003", "Carol", "L1"])
        run_ok(["open-ticket", db, "t004", "Fourth ticket", "low"])
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        run_ok(["resolve-ticket", db, "t003", "a001"])
        run_ok(["resolve-ticket", db, "t004", "a003"])
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT resolution_id FROM resolutions ORDER BY resolution_id"
        ).fetchall()
        for (rid,), val in zip(rows, [10, 20, 30, 40]):
            conn.execute(
                "UPDATE resolutions SET resolution_minutes=? WHERE resolution_id=?", (val, rid)
            )
        conn.commit()
        conn.close()
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        p75 = float(lines["p75_resolution_minutes"])
        # ceil(0.75*4)=ceil(3.0)=3, 3rd of [10,20,30,40]=30
        # linear interpolation (wrong): 0.75*(4-1)=2.25 (0-based) -> 30+0.25*10=32.5
        assert abs(p75 - 30.0) < 0.005, (
            f"p75={p75} expected 30 using nearest-rank ceil(0.75*4)=3. "
            f"Linear interpolation gives 32.5, which is wrong per spec."
        )

    def test_chain_verify_wrong_key_hash_detected(self, db):
        """A syntactically valid HMAC-SHA256 computed with the WRONG key must be flagged TAMPERED.
        Catches agents that skip key validation or use a hardcoded fallback."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT chain_id, ticket_id, agent_id, resolution_minutes, sla_met, resolved_at "
            "FROM resolution_chain WHERE chain_id=1"
        ).fetchone()
        chain_id, ticket_id, agent_id, res_min, sla_met, resolved_at = row
        sla_str = "true" if sla_met else "false"
        data = f"{chain_id}|RESOLVE|{ticket_id}|{agent_id}|{res_min}|{sla_str}|{resolved_at}|"
        wrong_key = b"wrong-key-2026"
        wrong_hash = hmac.new(wrong_key, data.encode(), hashlib.sha256).hexdigest()
        conn.execute(
            "UPDATE resolution_chain SET current_hash=? WHERE chain_id=1", (wrong_hash,)
        )
        conn.commit()
        conn.close()
        r = run(["chain-verify", db])
        assert r.returncode == 1, (
            f"Wrong-key HMAC must be detected as TAMPERED, got exit 0. output={r.stdout!r}"
        )
        assert "TAMPERED 1" in r.stdout, (
            f"Expected 'TAMPERED 1' in output, got: {r.stdout!r}"
        )

    def test_chain_verify_reports_all_tampered_not_just_first(self, db):
        """Tamper chain_id=1 and chain_id=3; both must appear in output before exit.
        Agents that stop at the first bad row miss chain_id=3."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        run_ok(["resolve-ticket", db, "t003", "a001"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE resolution_chain SET current_hash='badhash1ff' WHERE chain_id=1")
        conn.execute("UPDATE resolution_chain SET current_hash='badhash3ff' WHERE chain_id=3")
        conn.commit()
        conn.close()
        r = run(["chain-verify", db])
        assert r.returncode == 1
        output = r.stdout
        assert "TAMPERED 1" in output, (
            f"Expected TAMPERED 1 in output but got: {output!r}"
        )
        assert "TAMPERED 3" in output, (
            f"Expected TAMPERED 3 in output (agent stopped early): {output!r}"
        )

    def test_sla_met_pct_two_thirds_precision(self, db):
        """2 of 3 resolutions met SLA: pct=66.6667 at 4dp, not 66.666 or 66.6666.
        Catches truncation vs rounding errors in the percentage formula."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        run_ok(["resolve-ticket", db, "t003", "a001"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE resolutions SET sla_met=1 WHERE resolution_id=1")
        conn.execute("UPDATE resolutions SET sla_met=1 WHERE resolution_id=2")
        conn.execute("UPDATE resolutions SET sla_met=0 WHERE resolution_id=3")
        conn.commit()
        conn.close()
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        pct_str = lines["sla_met_pct"]
        expected = round(2 / 3 * 100, 4)
        actual = float(pct_str)
        assert abs(actual - expected) < 0.00005, (
            f"sla_met_pct={pct_str!r} expected {expected:.4f} (2/3*100 rounded to 4dp=66.6667). "
            f"Truncation gives 66.6666."
        )
        assert "." in pct_str and len(pct_str.split(".")[1]) == 4, (
            f"sla_met_pct must have exactly 4 decimal places, got: {pct_str!r}"
        )

    def test_std_resolution_zero_four_decimal_places(self, db):
        """All resolutions with same minutes: std_resolution must be '0.0000', not '0' or '0.0'.
        Catches agents that skip formatting when std is exactly zero."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        run_ok(["resolve-ticket", db, "t003", "a001"])
        conn = sqlite3.connect(db)
        for rid in (1, 2, 3):
            conn.execute(
                "UPDATE resolutions SET resolution_minutes=30 WHERE resolution_id=?", (rid,)
            )
        conn.commit()
        conn.close()
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        std_str = lines["std_resolution"]
        assert std_str == "0.0000", (
            f"std_resolution={std_str!r} must be '0.0000' when all values are identical. "
            f"Population stddev of equal values is exactly zero, formatted to 4dp."
        )

    def test_nearest_rank_p50_n2_is_smaller_value(self, db):
        """N=2 nearest-rank p50 = 1st (smallest) value, NOT the average.
        ceil(0.5*2)=ceil(1.0)=1, sorted=[10,20], p50=10.
        Averaging trap (common 'median' shortcut for even n): (10+20)/2=15 — wrong per spec."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT resolution_id FROM resolutions ORDER BY resolution_id"
        ).fetchall()
        for (rid,), val in zip(rows, [10, 20]):
            conn.execute(
                "UPDATE resolutions SET resolution_minutes=? WHERE resolution_id=?", (val, rid)
            )
        conn.commit()
        conn.close()
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        p50 = float(lines["p50_resolution_minutes"])
        assert abs(p50 - 10.0) < 0.005, (
            f"p50={p50} but nearest-rank ceil(0.5*2)=1, 1st of [10,20]=10. "
            f"Averaging middle two (common even-n shortcut) gives 15, which is wrong per spec."
        )

    def test_nearest_rank_p50_n4_not_linear_interpolation(self, db):
        """N=4 sorted [10,20,30,40]: nearest-rank p50=20, linear interpolation gives 25.
        ceil(0.5*4)=ceil(2.0)=2, 2nd value=20.
        Linear: 0-based index=0.5*(4-1)=1.5 → 20+0.5*(30-20)=25 (wrong)."""
        run_ok(["add-agent", db, "a003", "Carol", "L1"])
        run_ok(["open-ticket", db, "t_x4", "Fourth ticket", "medium"])
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        run_ok(["resolve-ticket", db, "t003", "a001"])
        run_ok(["resolve-ticket", db, "t_x4", "a003"])
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT resolution_id FROM resolutions ORDER BY resolution_id"
        ).fetchall()
        for (rid,), val in zip(rows, [10, 20, 30, 40]):
            conn.execute(
                "UPDATE resolutions SET resolution_minutes=? WHERE resolution_id=?", (val, rid)
            )
        conn.commit()
        conn.close()
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        p50 = float(lines["p50_resolution_minutes"])
        assert abs(p50 - 20.0) < 0.005, (
            f"p50={p50} for n=4 [10,20,30,40]: nearest-rank ceil(0.5*4)=2 gives 20. "
            f"Linear interpolation (wrong) gives 25."
        )

    def test_hmac_chain_sla_met_false_string_in_data(self, db):
        """When sla_met=false the chain data must use the string 'false', not '0' or 'False'.
        Manipulate opened_at to 2 hours ago so critical ticket exceeds 60-min SLA threshold.
        Then verify chain-verify passes AND the stored HMAC independently matches 'false' in data."""
        run_ok(["open-ticket", db, "t_crit2", "Critical SLA miss", "critical"])
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE tickets SET opened_at=datetime('now', '-2 hours') WHERE ticket_id='t_crit2'"
        )
        conn.commit()
        conn.close()
        run_ok(["resolve-ticket", db, "t_crit2", "a001"])
        r_verify = run(["chain-verify", db])
        assert r_verify.returncode == 0, (
            f"chain-verify must pass when sla_met=false: {r_verify.stdout!r}"
        )
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT chain_id, ticket_id, agent_id, resolution_minutes, sla_met, resolved_at, "
            "current_hash, prev_hash FROM resolution_chain ORDER BY chain_id LIMIT 1"
        ).fetchone()
        conn.close()
        chain_id, ticket_id, agent_id, res_min, sla_met_str, resolved_at, stored_hash, prev_hash = row
        assert sla_met_str == "false", (
            f"resolution_chain.sla_met must be 'false' for critical ticket >60 min, got {sla_met_str!r}. "
            f"Do not store '0' or 'False'."
        )
        data = (
            f"{chain_id}|RESOLVE|{ticket_id}|{agent_id}|{res_min}|"
            f"{sla_met_str}|{resolved_at}|{prev_hash}"
        )
        expected_hash = _compute_hmac(data)
        assert stored_hash == expected_hash, (
            f"HMAC mismatch for sla_met=false entry: stored={stored_hash[:16]}... "
            f"expected={expected_hash[:16]}... data='{data[:80]}...'"
        )

    def test_resolution_minutes_floor_not_round(self, db):
        """resolution_minutes = floor(elapsed_seconds / 60), not round().
        At 119 seconds elapsed: floor(119/60)=1 (correct), round(119/60)=2 (wrong).
        Catches agents using floating-point round or ceil instead of integer floor."""
        run_ok(["open-ticket", db, "t_floor", "Floor test", "medium"])
        conn = sqlite3.connect(db)
        conn.execute(
            "UPDATE tickets SET opened_at=datetime('now', '-119 seconds') WHERE ticket_id='t_floor'"
        )
        conn.commit()
        conn.close()
        run_ok(["resolve-ticket", db, "t_floor", "a001"])
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT resolution_minutes FROM resolutions WHERE ticket_id='t_floor'"
        ).fetchone()
        conn.close()
        assert row[0] == 1, (
            f"resolution_minutes={row[0]} for 119s elapsed. "
            f"floor(119/60)=1 (correct). round(119/60)=2 (wrong). Must use floor/integer division."
        )

    def test_sla_met_pct_zero_with_existing_resolutions_four_dp(self, db):
        """0 of 3 resolutions met SLA: pct must be '0.0000', not '0' or '0.0'.
        Distinct from the no-resolutions case: n=3, count_met=0, pct=0/3*100=0.0000."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        run_ok(["resolve-ticket", db, "t003", "a001"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE resolutions SET sla_met=0 WHERE resolution_id=1")
        conn.execute("UPDATE resolutions SET sla_met=0 WHERE resolution_id=2")
        conn.execute("UPDATE resolutions SET sla_met=0 WHERE resolution_id=3")
        conn.commit()
        conn.close()
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        pct_str = lines["sla_met_pct"]
        assert pct_str == "0.0000", (
            f"sla_met_pct={pct_str!r} must be '0.0000' when 0 of 3 resolutions met SLA. "
            f"Format must use exactly 4 decimal places even when value is zero."
        )


class TestHMACSecretEnvVar:
    """Tests that HMAC key is read from HMAC_SECRET env var, not hardcoded."""

    def test_hmac_secret_env_var_override_resolve_and_verify(self, db):
        """If HMAC_SECRET env var is set, all HMAC ops must use that key.
        Resolve a ticket with HMAC_SECRET=alt-chain-key-2026, then chain-verify
        with the same env var must return OK.
        Catches agents that hardcode 'support-queue-secret-2026'."""
        import os
        env = {**os.environ, "HMAC_SECRET": "alt-chain-key-2026"}
        r = subprocess.run(
            ["/app/app", "resolve-ticket", db, "t001", "a001"],
            capture_output=True, text=True, env=env,
        )
        assert r.returncode == 0, f"resolve-ticket with alt HMAC_SECRET failed: {r.stdout} {r.stderr}"
        rv = subprocess.run(
            ["/app/app", "chain-verify", db],
            capture_output=True, text=True, env=env,
        )
        assert rv.returncode == 0, (
            f"chain-verify with same alt HMAC_SECRET must return OK. "
            f"got exit={rv.returncode} out={rv.stdout!r}"
        )
        assert rv.stdout.strip() == "OK"

    def test_hmac_secret_env_var_hash_matches_independently(self, db):
        """Independently compute the HMAC with the alt key and verify it matches the stored hash.
        This directly checks that resolve-ticket used HMAC_SECRET, not a hardcoded key."""
        import os
        alt_key = b"alt-chain-key-2026"
        env = {**os.environ, "HMAC_SECRET": "alt-chain-key-2026"}
        subprocess.run(
            ["/app/app", "resolve-ticket", db, "t001", "a001"],
            capture_output=True, text=True, env=env,
        )
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT chain_id, ticket_id, agent_id, resolution_minutes, sla_met, resolved_at, "
            "current_hash, prev_hash FROM resolution_chain WHERE chain_id=1"
        ).fetchone()
        conn.close()
        chain_id, ticket_id, agent_id, res_min, sla_met_val, resolved_at, stored_hash, prev_hash = row
        sla_str = "true" if sla_met_val in ("true", 1, True) else "false"
        data = (
            f"{chain_id}|RESOLVE|{ticket_id}|{agent_id}|{res_min}|"
            f"{sla_str}|{resolved_at}|{prev_hash}"
        )
        expected_with_alt_key = hmac.new(alt_key, data.encode(), hashlib.sha256).hexdigest()
        expected_with_default = hmac.new(b"support-queue-secret-2026", data.encode(), hashlib.sha256).hexdigest()
        assert stored_hash == expected_with_alt_key, (
            f"Stored hash must match HMAC with alt key='alt-chain-key-2026'. "
            f"stored={stored_hash[:16]}... alt_key_hash={expected_with_alt_key[:16]}... "
            f"default_key_hash={expected_with_default[:16]}... "
            f"If stored matches default_key_hash, agent hardcoded the HMAC key."
        )

    def test_hmac_secret_wrong_env_var_fails_verify(self, db):
        """Chain built with alt key must fail chain-verify when using default (no env var).
        Proves chain-verify also reads HMAC_SECRET — not just resolve-ticket."""
        import os
        env_alt = {**os.environ, "HMAC_SECRET": "alt-chain-key-2026"}
        subprocess.run(
            ["/app/app", "resolve-ticket", db, "t001", "a001"],
            capture_output=True, text=True, env=env_alt,
        )
        # Verify WITHOUT alt key (env not set → uses default or hardcoded key)
        rv = subprocess.run(
            ["/app/app", "chain-verify", db],
            capture_output=True, text=True,
        )
        assert rv.returncode == 1, (
            "chain-verify without HMAC_SECRET must detect tampering for alt-key chain. "
            "Got exit 0 (OK) — agent is not reading HMAC_SECRET in chain-verify."
        )
        assert "TAMPERED" in rv.stdout, (
            f"Expected 'TAMPERED' in output, got: {rv.stdout!r}"
        )


class TestAvgResolutionMinutes:
    """Tests for avg_resolution_minutes field in sla-report."""

    def test_sla_report_has_avg_resolution_minutes_field(self, db):
        """sla-report must output 7 lines; 7th line is avg_resolution_minutes."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        r = run_ok(["sla-report", db])
        lines = r.stdout.strip().splitlines()
        assert len(lines) == 7, f"Expected 7 lines, got {len(lines)}: {r.stdout!r}"
        assert lines[6].startswith("avg_resolution_minutes="), (
            f"7th line must be avg_resolution_minutes=..., got: {lines[6]!r}"
        )

    def test_avg_resolution_minutes_two_values_whole(self, db):
        """[10, 20] → avg=15.0 → 'avg_resolution_minutes=15.0000'."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        conn = sqlite3.connect(db)
        rows = conn.execute("SELECT resolution_id FROM resolutions ORDER BY resolution_id").fetchall()
        conn.execute("UPDATE resolutions SET resolution_minutes=10 WHERE resolution_id=?", (rows[0][0],))
        conn.execute("UPDATE resolutions SET resolution_minutes=20 WHERE resolution_id=?", (rows[1][0],))
        conn.commit()
        conn.close()
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        assert lines["avg_resolution_minutes"] == "15.0000", (
            f"avg([10,20])=15.0 must be '15.0000'. got: {lines.get('avg_resolution_minutes')!r}"
        )

    def test_avg_resolution_minutes_float_division_trap(self, db):
        """[10, 21] → avg=15.5 → '15.5000'. Integer division gives 15 (wrong).
        This is the primary precision trap for avg_resolution_minutes."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        conn = sqlite3.connect(db)
        rows = conn.execute("SELECT resolution_id FROM resolutions ORDER BY resolution_id").fetchall()
        conn.execute("UPDATE resolutions SET resolution_minutes=10 WHERE resolution_id=?", (rows[0][0],))
        conn.execute("UPDATE resolutions SET resolution_minutes=21 WHERE resolution_id=?", (rows[1][0],))
        conn.commit()
        conn.close()
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        assert lines["avg_resolution_minutes"] == "15.5000", (
            f"avg([10,21])=(10+21)/2=15.5→'15.5000'. "
            f"Integer division gives '15'. got: {lines.get('avg_resolution_minutes')!r}"
        )

    def test_avg_resolution_minutes_three_values(self, db):
        """[10, 20, 30] → avg=20 → '20.0000'."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        run_ok(["resolve-ticket", db, "t003", "a001"])
        conn = sqlite3.connect(db)
        rows = conn.execute("SELECT resolution_id FROM resolutions ORDER BY resolution_id").fetchall()
        conn.execute("UPDATE resolutions SET resolution_minutes=10 WHERE resolution_id=?", (rows[0][0],))
        conn.execute("UPDATE resolutions SET resolution_minutes=20 WHERE resolution_id=?", (rows[1][0],))
        conn.execute("UPDATE resolutions SET resolution_minutes=30 WHERE resolution_id=?", (rows[2][0],))
        conn.commit()
        conn.close()
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        assert lines["avg_resolution_minutes"] == "20.0000", (
            f"avg([10,20,30])=20.0→'20.0000'. got: {lines.get('avg_resolution_minutes')!r}"
        )

    def test_avg_resolution_minutes_repeating_decimal(self, db):
        """[10, 20, 30, 40] → avg=25.0 → '25.0000'; [10, 11, 12] → avg=11.0 → '11.0000'."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        run_ok(["resolve-ticket", db, "t003", "a001"])
        conn = sqlite3.connect(db)
        rows = conn.execute("SELECT resolution_id FROM resolutions ORDER BY resolution_id").fetchall()
        conn.execute("UPDATE resolutions SET resolution_minutes=10 WHERE resolution_id=?", (rows[0][0],))
        conn.execute("UPDATE resolutions SET resolution_minutes=11 WHERE resolution_id=?", (rows[1][0],))
        conn.execute("UPDATE resolutions SET resolution_minutes=12 WHERE resolution_id=?", (rows[2][0],))
        conn.commit()
        conn.close()
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        assert lines["avg_resolution_minutes"] == "11.0000", (
            f"avg([10,11,12])=11.0→'11.0000'. got: {lines.get('avg_resolution_minutes')!r}"
        )

    def test_avg_resolution_minutes_empty_resolutions(self, db):
        """No resolutions: avg_resolution_minutes=0.0000."""
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        assert lines["avg_resolution_minutes"] == "0.0000", (
            f"No resolutions: avg_resolution_minutes must be '0.0000'. "
            f"got: {lines.get('avg_resolution_minutes')!r}"
        )

    def test_avg_resolution_minutes_four_dp_format_zero(self, db):
        """avg_resolution_minutes=0.0000 (not '0' or '0.0' or '.0000')."""
        r = run_ok(["sla-report", db])
        lines = r.stdout.strip().splitlines()
        avg_line = next((ln for ln in lines if ln.startswith("avg_resolution_minutes=")), None)
        assert avg_line is not None, "avg_resolution_minutes line must be present"
        avg_str = avg_line.split("=")[1]
        assert "." in avg_str, f"avg_resolution_minutes must have decimal point: {avg_str!r}"
        assert len(avg_str.split(".")[1]) == 4, (
            f"avg_resolution_minutes must have exactly 4 decimal places: {avg_str!r}"
        )


class TestPriorityStats:
    """Precision trap tests for the priority-stats command."""

    def _setup_with_resolutions(self, db, priority_minutes):
        """Setup tickets+resolutions for given {priority: [minutes_list]} dict."""
        run_ok(["add-agent", db, "ag001", "Agent1", "L1"])
        idx = 0
        for priority, minutes_list in priority_minutes.items():
            for mins in minutes_list:
                idx += 1
                tid = f"tk{idx:04d}"
                run_ok(["open-ticket", db, tid, f"ticket {idx}", priority])
                run_ok(["resolve-ticket", db, tid, "ag001"])
                conn = sqlite3.connect(db)
                conn.execute(
                    "UPDATE resolutions SET resolution_minutes=? WHERE ticket_id=?", (mins, tid)
                )
                conn.commit()
                conn.close()

    def test_priority_stats_header(self, db):
        """priority-stats prints TSV header with exactly 5 columns."""
        self._setup_with_resolutions(db, {"high": [60]})
        r = run_ok(["priority-stats", db])
        first_line = r.stdout.strip().splitlines()[0]
        assert first_line == "priority\tresolution_count\tavg_resolution_minutes\tstddev_resolution\tp75_resolution_minutes", (
            f"Header mismatch: got {first_line!r}"
        )

    def test_priority_stats_sort_alphabetical_not_severity(self, db):
        """priority-stats sorts by priority name ASC (alphabetical), NOT by severity level.
        Alphabetical order: critical < high < low < medium.
        Severity order (wrong): critical > high > medium > low.
        This is the main sort trap: agents often sort by severity level."""
        self._setup_with_resolutions(db, {
            "medium": [60],
            "low": [30],
            "critical": [15],
            "high": [45],
        })
        r = run_ok(["priority-stats", db])
        data_lines = r.stdout.strip().splitlines()[1:]
        priorities = [ln.split("\t")[0] for ln in data_lines]
        assert priorities == ["critical", "high", "low", "medium"], (
            f"priorities must be sorted alphabetically ASC: critical,high,low,medium. "
            f"Severity order (wrong) would be: critical,high,medium,low. got: {priorities}"
        )

    def test_priority_stats_resolution_count_per_priority(self, db):
        """priority-stats resolution_count counts only resolutions for that specific priority."""
        self._setup_with_resolutions(db, {
            "high": [60, 120, 180],
            "low": [30],
        })
        r = run_ok(["priority-stats", db])
        rows = {ln.split("\t")[0]: ln.split("\t") for ln in r.stdout.strip().splitlines()[1:] if ln}
        assert rows["high"][1] == "3", f"high has 3 resolutions, got: {rows['high'][1]!r}"
        assert rows["low"][1] == "1", f"low has 1 resolution, got: {rows['low'][1]!r}"

    def test_priority_stats_population_stddev_not_sample(self, db):
        """stddev_resolution uses population stddev (÷N) not sample (÷N-1).
        high: [60,120]: pop_std=30.0000, sample_std=42.4264 — catches Bessel correction."""
        self._setup_with_resolutions(db, {"high": [60, 120]})
        r = run_ok(["priority-stats", db])
        rows = {ln.split("\t")[0]: ln.split("\t") for ln in r.stdout.strip().splitlines()[1:] if ln}
        std = float(rows["high"][3])
        assert abs(std - 30.0) < 0.001, (
            f"pop_stddev([60,120])=30.0000. Sample stddev=42.4264. got: {std:.4f}. "
            f"Must use ÷N not ÷(N-1)."
        )
        assert abs(std - 42.4264) > 1.0, "agent incorrectly used sample stddev (N-1 denominator)"

    def test_priority_stats_stddev_four_decimal_places(self, db):
        """stddev_resolution is formatted to exactly 4 decimal places."""
        self._setup_with_resolutions(db, {"medium": [10, 20, 30]})
        r = run_ok(["priority-stats", db])
        rows = {ln.split("\t")[0]: ln.split("\t") for ln in r.stdout.strip().splitlines()[1:] if ln}
        std_str = rows["medium"][3]
        assert "." in std_str, f"stddev must have decimal point: {std_str!r}"
        assert len(std_str.split(".")[1]) == 4, (
            f"stddev must have exactly 4 decimal places: {std_str!r}"
        )

    def test_priority_stats_p75_nearest_rank_n3(self, db):
        """p75 uses nearest-rank ceil(0.75*N): N=3, [10,20,30], rank=ceil(2.25)=3, p75=30.
        Linear interpolation gives 0.75*(30-10)+10=25 (wrong).
        floor(0.75*3)=2 → sorted[1]=20 (also wrong)."""
        self._setup_with_resolutions(db, {"high": [10, 20, 30]})
        r = run_ok(["priority-stats", db])
        rows = {ln.split("\t")[0]: ln.split("\t") for ln in r.stdout.strip().splitlines()[1:] if ln}
        p75 = float(rows["high"][4])
        assert abs(p75 - 30.0) < 0.005, (
            f"N=3 [10,20,30]: ceil(0.75*3)=3 → sorted[2]=30. "
            f"Linear interpolation (wrong)=25. floor gives 20. got: {p75}"
        )

    def test_priority_stats_p75_nearest_rank_n2(self, db):
        """N=2 [60,120]: rank=ceil(0.75*2)=ceil(1.5)=2, p75=120.0000.
        If agent uses floor(0.75*2)=1 → sorted[0]=60 (wrong)."""
        self._setup_with_resolutions(db, {"critical": [60, 120]})
        r = run_ok(["priority-stats", db])
        rows = {ln.split("\t")[0]: ln.split("\t") for ln in r.stdout.strip().splitlines()[1:] if ln}
        p75 = float(rows["critical"][4])
        assert abs(p75 - 120.0) < 0.005, (
            f"N=2 [60,120]: ceil(0.75*2)=2 → sorted[1]=120. "
            f"floor(0.75*2)=1 → sorted[0]=60 (wrong). got: {p75}"
        )

    def test_priority_stats_avg_two_decimal_places_not_four(self, db):
        """avg_resolution_minutes uses exactly 2 decimal places (not 4 like stddev/p75).
        Catches agents that apply uniform 4dp formatting to all fields."""
        self._setup_with_resolutions(db, {"medium": [30, 60]})
        r = run_ok(["priority-stats", db])
        rows = {ln.split("\t")[0]: ln.split("\t") for ln in r.stdout.strip().splitlines()[1:] if ln}
        avg_str = rows["medium"][2]
        assert "." in avg_str, f"avg must have decimal point: {avg_str!r}"
        assert len(avg_str.split(".")[1]) == 2, (
            f"avg_resolution_minutes must have exactly 2 decimal places (not 4). "
            f"got: {avg_str!r}"
        )

    def test_priority_stats_avg_bankers_rounding_half_even_down(self, db):
        """HALF_EVEN rounding: 8 resolutions summing to 13 → avg=1.625.
        bankersRound(1300,8): q=162 (even), r=4, doubled=8=denom → stays 162 → '1.62'.
        Standard round-half-up gives '1.63'. Catches non-banker's implementations."""
        run_ok(["add-agent", db, "ag099", "AgentX", "L1"])
        values = [1, 1, 1, 1, 1, 1, 1, 6]
        for i, mins in enumerate(values):
            tid = f"bk{i:04d}"
            run_ok(["open-ticket", db, tid, f"ticket {i}", "low"])
            run_ok(["resolve-ticket", db, tid, "ag099"])
            conn = sqlite3.connect(db)
            conn.execute("UPDATE resolutions SET resolution_minutes=? WHERE ticket_id=?", (mins, tid))
            conn.commit()
            conn.close()
        r = run_ok(["priority-stats", db])
        rows = {ln.split("\t")[0]: ln.split("\t") for ln in r.stdout.strip().splitlines()[1:] if ln}
        avg_str = rows["low"][2]
        assert avg_str == "1.62", (
            f"HALF_EVEN(1.625): 2nd decimal='2' (even) → banker's rounds DOWN → '1.62'. "
            f"Standard half-up gives '1.63'. got: {avg_str!r}"
        )

    def test_priority_stats_stddev_zero_for_single_resolution(self, db):
        """priority-stats stddev=0.0000 when a priority has exactly one resolution.
        Population variance of one element is always zero."""
        self._setup_with_resolutions(db, {"critical": [45]})
        r = run_ok(["priority-stats", db])
        rows = {ln.split("\t")[0]: ln.split("\t") for ln in r.stdout.strip().splitlines()[1:] if ln}
        assert rows["critical"][3] == "0.0000", (
            f"single resolution → stddev must be '0.0000'. got: {rows['critical'][3]!r}"
        )

    def test_priority_stats_p75_four_decimal_places(self, db):
        """p75_resolution_minutes is formatted to exactly 4 decimal places."""
        self._setup_with_resolutions(db, {"high": [60, 120]})
        r = run_ok(["priority-stats", db])
        rows = {ln.split("\t")[0]: ln.split("\t") for ln in r.stdout.strip().splitlines()[1:] if ln}
        p75_str = rows["high"][4]
        assert "." in p75_str, f"p75 must have decimal point: {p75_str!r}"
        assert len(p75_str.split(".")[1]) == 4, (
            f"p75_resolution_minutes must have exactly 4 decimal places: {p75_str!r}"
        )

    def test_priority_stats_empty_header_only(self, db):
        """Zero resolutions anywhere: priority-stats must print ONLY the header row,
        with no data rows at all (documented empty-state format)."""
        r = run_ok(["priority-stats", db])
        lines = r.stdout.strip("\n").splitlines()
        assert len(lines) == 1, (
            f"Expected header-only output with zero resolutions, got {len(lines)} lines: {r.stdout!r}"
        )
        assert lines[0] == (
            "priority\tresolution_count\tavg_resolution_minutes\tstddev_resolution\tp75_resolution_minutes"
        ), f"Header mismatch: {lines[0]!r}"

    def test_priority_stats_only_shows_resolved_priorities(self, db):
        """priority-stats only shows priorities that have at least one resolution.
        Unresolved ticket priorities must NOT appear in the output."""
        self._setup_with_resolutions(db, {"high": [60]})
        run_ok(["open-ticket", db, "unresTick", "Unresolved", "critical"])
        # critical has open ticket but no resolution
        r = run_ok(["priority-stats", db])
        rows = {ln.split("\t")[0]: ln.split("\t") for ln in r.stdout.strip().splitlines()[1:] if ln}
        assert "high" in rows, "high must appear (has resolution)"
        assert "critical" not in rows, (
            f"critical must NOT appear (no resolution). got rows: {list(rows.keys())}"
        )


class TestTicketAnalytics:
    """Precision traps for ticket-analytics: sample stddev, P25 ceil trap, IQR, CV."""

    def _setup_analytics(self, db, minutes_list, priority="medium"):
        """Set up resolutions with controlled resolution_minutes."""
        run_ok(["add-agent", db, "ana01", "Analyst", "L1"])
        for i, mins in enumerate(minutes_list):
            tid = f"ana{i:04d}"
            run_ok(["open-ticket", db, tid, f"ticket {i}", priority])
            run_ok(["resolve-ticket", db, tid, "ana01"])
            conn = sqlite3.connect(db)
            conn.execute(
                "UPDATE resolutions SET resolution_minutes=? WHERE ticket_id=?", (mins, tid)
            )
            conn.commit()
            conn.close()

    def test_ticket_analytics_format(self, db):
        """ticket-analytics must output exactly 5 lines with correct field names in order."""
        self._setup_analytics(db, [10, 20, 30])
        r = run_ok(["ticket-analytics", db])
        lines = r.stdout.strip().splitlines()
        assert len(lines) == 5, (
            f"ticket-analytics must have 5 lines, got {len(lines)}: {r.stdout!r}"
        )
        keys = [ln.split("=")[0] for ln in lines]
        assert keys == [
            "total_resolved", "p25_resolution_minutes", "iqr_resolution_minutes",
            "sample_std_resolution", "cv_resolution",
        ], f"Field names/order wrong: {keys}"

    def test_ticket_analytics_empty(self, db):
        """No resolutions: all fields zero with correct format."""
        r = run_ok(["ticket-analytics", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        assert lines["total_resolved"] == "0"
        assert lines["sample_std_resolution"] == "0.0000"
        assert lines["cv_resolution"] == "0.0000"

    def test_ticket_analytics_total_resolved(self, db):
        """total_resolved counts rows in resolutions, not tickets table."""
        self._setup_analytics(db, [10, 20, 30])
        r = run_ok(["ticket-analytics", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        assert lines["total_resolved"] == "3", (
            f"total_resolved must be 3 (resolutions count). got: {lines['total_resolved']!r}"
        )

    def test_ticket_analytics_p25_n5_ceil_trap(self, db):
        """N=5 [10,20,30,40,50]: P25 rank=ceil(0.25*5)=ceil(1.25)=2, sorted[1]=20.
        Floor trap: floor(0.25*5)=floor(1.25)=1 -> sorted[0]=10 (wrong).
        This is the key P25 discriminating case where ceil vs floor diverge."""
        self._setup_analytics(db, [10, 20, 30, 40, 50])
        r = run_ok(["ticket-analytics", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        p25_str = lines["p25_resolution_minutes"]
        p25 = float(p25_str)
        assert abs(p25 - 20.0) < 0.005, (
            f"N=5 [10,20,30,40,50]: P25=ceil(0.25*5)=2->sorted[1]=20. "
            f"floor gives sorted[0]=10 (wrong). got: {p25}"
        )
        assert "." not in p25_str, (
            f"p25_resolution_minutes must be an integer (no decimal point). "
            f"got: {p25_str!r}"
        )

    def test_ticket_analytics_iqr_n5_discriminating(self, db):
        """N=5 [5,10,20,40,60]: P25=ceil(0.25*5)=2->10, P75=ceil(0.75*5)=4->40, IQR=30.
        Floor method: P25=floor(1.25)=1->5, P75=floor(3.75)=3->20, IQR=15 (wrong).
        This dataset makes floor-IQR and ceil-IQR diverge clearly."""
        self._setup_analytics(db, [5, 10, 20, 40, 60])
        r = run_ok(["ticket-analytics", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        iqr_str = lines["iqr_resolution_minutes"]
        iqr = float(iqr_str)
        assert abs(iqr - 30.0) < 0.005, (
            f"N=5 [5,10,20,40,60]: P25->10, P75->40, IQR=30. "
            f"Floor method gives P25->5, P75->20, IQR=15 (wrong). got: {iqr}"
        )
        assert "." not in iqr_str, (
            f"iqr_resolution_minutes must be an integer (no decimal point). "
            f"got: {iqr_str!r}"
        )

    def test_ticket_analytics_iqr_n4(self, db):
        """N=4 [10,20,30,40]: P25=ceil(1.0)=1->10, P75=ceil(3.0)=3->30, IQR=20."""
        self._setup_analytics(db, [10, 20, 30, 40])
        r = run_ok(["ticket-analytics", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        iqr_str = lines["iqr_resolution_minutes"]
        iqr = float(iqr_str)
        assert abs(iqr - 20.0) < 0.005, (
            f"N=4 [10,20,30,40]: P25=1->10, P75=3->30, IQR=20. got: {iqr}"
        )
        assert "." not in iqr_str, (
            f"iqr_resolution_minutes must be an integer (no decimal point). "
            f"got: {iqr_str!r}"
        )

    def test_ticket_analytics_sample_stddev_n3_vs_population(self, db):
        """ticket-analytics uses SAMPLE stddev (N-1), NOT population (N).
        N=3 [3,6,9]: sample_std=sqrt(9)=3.0000, pop_std=sqrt(6)~2.4495.
        This INVERTS sla-report which uses population. Agents applying uniform
        stddev everywhere fail one of the two commands."""
        self._setup_analytics(db, [3, 6, 9])
        r = run_ok(["ticket-analytics", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        std = float(lines["sample_std_resolution"])
        # sample: variance=[(3-6)^2+(6-6)^2+(9-6)^2]/(3-1)=[9+0+9]/2=9, std=3.0
        assert abs(std - 3.0) < 0.0005, (
            f"sample_std([3,6,9])=sqrt(9)=3.0000. "
            f"Population std (wrong)=sqrt(6)~2.4495. got: {std:.4f}. "
            f"Must divide by N-1=2, not N=3."
        )
        assert abs(std - 2.4495) > 0.1, (
            "agent incorrectly used population stddev (N) instead of sample stddev (N-1)"
        )

    def test_ticket_analytics_sample_stddev_n2_max_divergence(self, db):
        """N=2 [10,20]: sample_std=sqrt(50)~7.0711, pop_std=5.0000.
        Maximum divergence at small N. sample_var=(50+50)/(2-1)=50, std=sqrt(50)~7.0711.
        pop_var=(25+25)/2=25, std=5.0000."""
        self._setup_analytics(db, [10, 20])
        r = run_ok(["ticket-analytics", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        std = float(lines["sample_std_resolution"])
        expected = math.sqrt(50)
        assert abs(std - expected) < 0.0005, (
            f"sample_std([10,20])=sqrt(50)~{expected:.4f}. "
            f"pop_std=5.0000 (wrong). got: {std:.4f}"
        )

    def test_ticket_analytics_sample_stddev_n1_zero(self, db):
        """N=1: sample stddev is undefined (0); output 0.0000."""
        self._setup_analytics(db, [42])
        r = run_ok(["ticket-analytics", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        std_str = lines["sample_std_resolution"]
        assert std_str == "0.0000", (
            f"sample_std with N=1 must be '0.0000' (undefined). got: {std_str!r}"
        )

    def test_ticket_analytics_cv_uses_sample_std(self, db):
        """CV = sample_std / mean * 100. N=2 [10,20]: mean=15.
        CV with sample_std=sqrt(50)~7.0711: CV~47.1405.
        CV with pop_std=5.0: CV=33.3333.
        Must use sample_std -> CV > 40."""
        self._setup_analytics(db, [10, 20])
        r = run_ok(["ticket-analytics", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        cv = float(lines["cv_resolution"])
        expected = math.sqrt(50) / 15 * 100
        assert abs(cv - expected) < 0.005, (
            f"CV=sample_std/mean*100={expected:.4f}. got: {cv:.4f}. "
            f"Using pop_std=5.0 gives CV=33.3333 (wrong)."
        )

    def test_ticket_analytics_cv_zero_when_no_variance(self, db):
        """N=1: sample_std=0.0000, CV=0.0000 (std/mean=0)."""
        self._setup_analytics(db, [30])
        r = run_ok(["ticket-analytics", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        cv_str = lines["cv_resolution"]
        assert cv_str == "0.0000", (
            f"CV with N=1 (sample_std=0) must be '0.0000'. got: {cv_str!r}"
        )

    def test_ticket_analytics_sample_std_four_decimal_places(self, db):
        """sample_std_resolution must be formatted to exactly 4 decimal places."""
        self._setup_analytics(db, [10, 20, 30])
        r = run_ok(["ticket-analytics", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        std_str = lines["sample_std_resolution"]
        assert "." in std_str, f"sample_std must have decimal point: {std_str!r}"
        assert len(std_str.split(".")[1]) == 4, (
            f"sample_std must have exactly 4 decimal places: {std_str!r}"
        )

    def test_ticket_analytics_p25_n4_no_trap(self, db):
        """N=4: ceil(0.25*4)=ceil(1.0)=1->sorted[0]=10. Ceil and floor agree at exact multiples."""
        self._setup_analytics(db, [10, 20, 30, 40])
        r = run_ok(["ticket-analytics", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        p25_str = lines["p25_resolution_minutes"]
        p25 = float(p25_str)
        assert abs(p25 - 10.0) < 0.005, (
            f"N=4 [10,20,30,40]: ceil(0.25*4)=1->sorted[0]=10. got: {p25}"
        )
        assert "." not in p25_str, (
            f"p25_resolution_minutes must be an integer (no decimal point). "
            f"got: {p25_str!r}"
        )


class TestChainLinkPropagation:
    """Tests for HMAC chain link integrity propagation."""

    def test_chain_link_propagation_tamper_cascades(self, db):
        """Tampering chain_id=1's current_hash forces chain_id=2 to be flagged too.
        chain_id=2's stored prev_hash (= original hash of chain_id=1) no longer
        matches what chain-verify tracks (= tampered hash 'badhash'). Both must appear.
        Catches agents that only check HMAC but skip the prev_hash linkage check."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        run_ok(["resolve-ticket", db, "t003", "a001"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE resolution_chain SET current_hash='badhash' WHERE chain_id=1")
        conn.commit()
        conn.close()
        r = run(["chain-verify", db])
        assert r.returncode == 1
        output = r.stdout
        assert "TAMPERED 1" in output, (
            f"chain_id=1 HMAC mismatch must be reported. got: {output!r}"
        )
        assert "TAMPERED 2" in output, (
            f"chain_id=2 prev_hash linkage break must be reported. "
            f"chain_id=2.prev_hash=original_hash!='badhash'. got: {output!r}"
        )

    def test_chain_verify_middle_tamper_cascades_only_downstream(self, db):
        """Tamper chain_id=2's current_hash: chain_id=1 is OK, chain_id=2 HMAC fails,
        chain_id=3 prev_hash linkage breaks. Verify chain_id=1 NOT in output.
        Tests that upstream-clean entries are not falsely flagged."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        run_ok(["resolve-ticket", db, "t003", "a001"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE resolution_chain SET current_hash='midbad' WHERE chain_id=2")
        conn.commit()
        conn.close()
        r = run(["chain-verify", db])
        assert r.returncode == 1
        output = r.stdout
        assert "TAMPERED 1" not in output, (
            f"chain_id=1 is clean and must NOT be flagged. got: {output!r}"
        )
        assert "TAMPERED 2" in output, (
            f"chain_id=2 HMAC mismatch must be reported. got: {output!r}"
        )
        assert "TAMPERED 3" in output, (
            f"chain_id=3 prev_hash linkage break must be reported. got: {output!r}"
        )


class TestAdditionalPrecisionTraps:
    """Additional precision traps for M3 commands."""

    def test_chain_verify_empty_chain_no_tampered_lines(self, db):
        """Empty chain: output must be exactly 'OK' with no TAMPERED lines."""
        r = run_ok(["chain-verify", db])
        output = r.stdout.strip()
        assert output == "OK", (
            f"Empty chain: output must be exactly 'OK'. got: {output!r}"
        )
        assert "TAMPERED" not in output, (
            f"Empty chain must not produce any TAMPERED lines. got: {output!r}"
        )

    def test_sla_report_nearest_rank_p50_n2_not_average(self, db):
        """N=2 [10,20]: nearest-rank p50=ceil(0.5*2)=1 -> sorted[0]=10, NOT average 15."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        conn = sqlite3.connect(db)
        rows = conn.execute("SELECT resolution_id FROM resolutions ORDER BY resolution_id").fetchall()
        conn.execute("UPDATE resolutions SET resolution_minutes=10 WHERE resolution_id=?", (rows[0][0],))
        conn.execute("UPDATE resolutions SET resolution_minutes=20 WHERE resolution_id=?", (rows[1][0],))
        conn.commit()
        conn.close()
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        p50 = float(lines["p50_resolution_minutes"])
        assert abs(p50 - 10.0) < 0.005, (
            f"N=2 [10,20]: nearest-rank ceil(0.5*2)=1 -> 10. Averaging gives 15 (wrong). got: {p50}"
        )

    def test_sla_met_pct_exact_rounding_66_6667(self, db):
        """3 resolutions, 2 met SLA: sla_met_pct must be 66.6667 not 66.6666."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        run_ok(["resolve-ticket", db, "t002", "a002"])
        run_ok(["resolve-ticket", db, "t003", "a001"])
        conn = sqlite3.connect(db)
        rows = conn.execute("SELECT resolution_id FROM resolutions ORDER BY resolution_id").fetchall()
        conn.execute("UPDATE resolutions SET sla_met=1 WHERE resolution_id=?", (rows[0][0],))
        conn.execute("UPDATE resolutions SET sla_met=1 WHERE resolution_id=?", (rows[1][0],))
        conn.execute("UPDATE resolutions SET sla_met=0 WHERE resolution_id=?", (rows[2][0],))
        conn.commit()
        conn.close()
        r = run_ok(["sla-report", db])
        lines = {ln.split("=")[0]: ln.split("=")[1] for ln in r.stdout.strip().splitlines()}
        pct_str = lines["sla_met_pct"]
        assert pct_str == "66.6667", (
            f"2/3 * 100 rounded to 4dp (HALF_UP) = 66.6667 not 66.6666. got: {pct_str!r}"
        )

    def test_chain_verify_correct_key_ok_wrong_key_fails(self, db):
        """Build chain with default key -> chain-verify OK. Rebuild with custom key -> default-key verify TAMPERED."""
        import os
        # Resolve with default key (no env)
        run_ok(["resolve-ticket", db, "t001", "a001"])
        # Verify with default key: must be OK
        rv_ok = run(["chain-verify", db])
        assert rv_ok.returncode == 0, (
            f"chain-verify with default key on default-key chain must exit 0. got: {rv_ok.stdout!r}"
        )
        assert rv_ok.stdout.strip() == "OK"

        # Now build a fresh db and resolve with custom key
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            alt_db = f.name
        run_ok(["init", alt_db])
        run_ok(["add-agent", alt_db, "ca1", "AltAgent", "L1"])
        run_ok(["open-ticket", alt_db, "ct1", "AltTicket", "medium"])
        env = {**os.environ, "HMAC_SECRET": "alt-secret-for-chain-test"}
        r_alt = subprocess.run(
            ["/app/app", "resolve-ticket", alt_db, "ct1", "ca1"],
            capture_output=True, text=True, env=env,
        )
        assert r_alt.returncode == 0

        # Verify WITHOUT the custom key (default key) -> must detect TAMPERED
        rv_bad = subprocess.run(
            ["/app/app", "chain-verify", alt_db],
            capture_output=True, text=True,
        )
        assert rv_bad.returncode == 1, (
            f"chain-verify with default key on alt-key chain must exit 1. got: {rv_bad.stdout!r}"
        )
        assert "TAMPERED" in rv_bad.stdout, (
            f"Expected TAMPERED in output. got: {rv_bad.stdout!r}"
        )


class TestWorkloadBalance:
    """Precision traps for workload-balance: tier capacity constants, LEFT JOIN, utilization format."""

    def test_workload_balance_empty_no_agents(self, db):
        """With agents already added in db fixture, workload-balance shows all agents with 0 open."""
        r = run_ok(["workload-balance", db])
        lines = r.stdout.strip().splitlines()
        # db fixture has 2 agents: a001 (L1), a002 (L2)
        assert len(lines) == 2, (
            f"workload-balance must show all 2 agents even with zero open tickets. "
            f"got {len(lines)} lines: {r.stdout!r}"
        )

    def test_workload_balance_format(self, db):
        """Output format must be: <agent_id> tier=<tier> open=<N> utilization=<4dp>."""
        r = run_ok(["workload-balance", db])
        for line in r.stdout.strip().splitlines():
            parts = line.split()
            assert len(parts) == 4, (
                f"Each line must have 4 space-separated parts. got: {line!r}"
            )
            assert parts[1].startswith("tier="), f"2nd field must start with 'tier=': {line!r}"
            assert parts[2].startswith("open="), f"3rd field must start with 'open=': {line!r}"
            assert parts[3].startswith("utilization="), f"4th field must start with 'utilization=': {line!r}"
            util_str = parts[3].split("=")[1]
            assert "." in util_str, f"utilization must have decimal point: {line!r}"
            assert len(util_str.split(".")[1]) == 4, (
                f"utilization must be formatted to exactly 4 decimal places: {line!r}"
            )

    def test_workload_balance_open_values_are_positive_and_correct(self, db):
        """Explicitly assert the numeric open= counts themselves (not just the derived
        utilization percentage or the zero-open case). a001 gets 2 open tickets assigned,
        a002 gets 1. Both must show the real positive open counts, catching an
        implementation that always prints open=0 (or a wrong constant) while still
        deriving a plausible-looking utilization from a separately-tracked count."""
        conn = sqlite3.connect(db)
        conn.execute("UPDATE tickets SET assigned_agent_id='a001' WHERE ticket_id IN ('t001','t002')")
        conn.execute("UPDATE tickets SET assigned_agent_id='a002' WHERE ticket_id='t003'")
        conn.commit()
        conn.close()
        r = run_ok(["workload-balance", db])
        open_counts = {}
        for line in r.stdout.strip().splitlines():
            parts = line.split()
            aid = parts[0]
            open_counts[aid] = int(parts[2].split("=")[1])
        assert open_counts["a001"] == 2, (
            f"a001 has 2 open assigned tickets (t001, t002): open=2 expected. got: {open_counts}"
        )
        assert open_counts["a002"] == 1, (
            f"a002 has 1 open assigned ticket (t003): open=1 expected. got: {open_counts}"
        )
        assert open_counts["a001"] > 0 and open_counts["a002"] > 0, (
            f"Both agents have real open assignments; open counts must be positive. got: {open_counts}"
        )

    def test_workload_balance_l1_capacity_5(self, db):
        """L1 capacity is 5: 1 open ticket = 20.0000% utilization (not 10% for cap=10 or 5% for cap=20).
        Catches agents that use wrong tier capacity constants."""
        # t001 is open and unassigned in fixture — assign it via direct SQL
        conn = sqlite3.connect(db)
        conn.execute("UPDATE tickets SET assigned_agent_id='a001' WHERE ticket_id='t001'")
        conn.commit()
        conn.close()
        r = run_ok(["workload-balance", db])
        rows = {}
        for line in r.stdout.strip().splitlines():
            parts = line.split()
            aid = parts[0]
            util = float(parts[3].split("=")[1])
            rows[aid] = util
        assert abs(rows["a001"] - 20.0) < 0.0001, (
            f"L1 agent with 1 open ticket: utilization=1/5*100=20.0000. "
            f"If capacity=10: 10.0%. If capacity=20: 5.0%. got: {rows['a001']:.4f}"
        )

    def test_workload_balance_l2_capacity_15(self, db):
        """L2 capacity is 15: 3 open tickets = 20.0000% utilization.
        Common wrong answers: cap=10 gives 30.0%, cap=20 gives 15.0%."""
        # Assign 3 tickets to a002 (L2) directly
        conn = sqlite3.connect(db)
        conn.execute("UPDATE tickets SET assigned_agent_id='a002' WHERE ticket_id='t001'")
        conn.execute("UPDATE tickets SET assigned_agent_id='a002' WHERE ticket_id='t002'")
        conn.execute("UPDATE tickets SET assigned_agent_id='a002' WHERE ticket_id='t003'")
        conn.commit()
        conn.close()
        r = run_ok(["workload-balance", db])
        rows = {}
        for line in r.stdout.strip().splitlines():
            parts = line.split()
            aid = parts[0]
            util = float(parts[3].split("=")[1])
            rows[aid] = util
        assert abs(rows["a002"] - 20.0) < 0.0001, (
            f"L2 agent with 3 open tickets: utilization=3/15*100=20.0000. "
            f"Cap=10 gives 30.0%, cap=20 gives 15.0%. got: {rows['a002']:.4f}"
        )

    def test_workload_balance_l3_capacity_30(self, db):
        """L3 capacity is 30: 6 open tickets = 20.0000% utilization.
        Common wrong: cap=20 gives 30.0%, cap=40 gives 15.0%."""
        run_ok(["add-agent", db, "ag_l3", "L3Agent", "L3"])
        for i in range(6):
            tid = f"wbl3_{i:03d}"
            run_ok(["open-ticket", db, tid, f"ticket {i}", "low"])
            conn = sqlite3.connect(db)
            conn.execute(
                "UPDATE tickets SET assigned_agent_id='ag_l3' WHERE ticket_id=?", (tid,)
            )
            conn.commit()
            conn.close()
        r = run_ok(["workload-balance", db])
        rows = {}
        for line in r.stdout.strip().splitlines():
            parts = line.split()
            aid = parts[0]
            util = float(parts[3].split("=")[1])
            rows[aid] = util
        assert abs(rows["ag_l3"] - 20.0) < 0.0001, (
            f"L3 agent with 6 open tickets: utilization=6/30*100=20.0000. "
            f"Cap=20 gives 30.0%, cap=40 gives 15.0%. got: {rows['ag_l3']:.4f}"
        )

    def test_workload_balance_zero_open_included(self, db):
        """Agents with zero open assigned tickets must appear with utilization=0.0000.
        Catches agents that use INNER JOIN instead of LEFT JOIN."""
        # No ticket assignments, all agents should appear
        r = run_ok(["workload-balance", db])
        rows = {}
        for line in r.stdout.strip().splitlines():
            parts = line.split()
            aid = parts[0]
            open_count = int(parts[2].split("=")[1])
            util = float(parts[3].split("=")[1])
            rows[aid] = (open_count, util)
        assert "a001" in rows, "a001 must appear even with 0 open assigned tickets"
        assert "a002" in rows, "a002 must appear even with 0 open assigned tickets"
        assert rows["a001"][0] == 0, f"a001 open count must be 0. got: {rows['a001'][0]}"
        assert abs(rows["a001"][1] - 0.0) < 0.0001, (
            f"a001 utilization must be 0.0000. got: {rows['a001'][1]:.4f}"
        )

    def test_workload_balance_resolved_tickets_not_counted(self, db):
        """Only OPEN tickets count toward utilization. Resolved tickets must be excluded.
        Catches agents that count all assigned tickets regardless of status."""
        run_ok(["resolve-ticket", db, "t001", "a001"])
        # t001 is now resolved but assigned_agent_id=a001
        r = run_ok(["workload-balance", db])
        rows = {}
        for line in r.stdout.strip().splitlines():
            parts = line.split()
            aid = parts[0]
            open_count = int(parts[2].split("=")[1])
            rows[aid] = open_count
        assert rows["a001"] == 0, (
            f"a001 has 1 resolved ticket but 0 open assigned. open must be 0. "
            f"got: {rows['a001']}"
        )

    def test_workload_balance_sort_utilization_desc_then_agent_id_asc(self, db):
        """Sort by utilization DESC, then agent_id ASC for ties.
        Catches agents that sort by agent_id only or utilization ASC."""
        run_ok(["add-agent", db, "ag_l3b", "L3B", "L3"])
        # Assign 1 ticket to a001 (L1): util=1/5*100=20.0000
        # Assign 2 tickets to a002 (L2): util=2/15*100=13.3333
        # ag_l3b (L3): 0 open: util=0.0000
        conn = sqlite3.connect(db)
        conn.execute("UPDATE tickets SET assigned_agent_id='a001' WHERE ticket_id='t001'")
        conn.execute("UPDATE tickets SET assigned_agent_id='a002' WHERE ticket_id='t002'")
        conn.execute("UPDATE tickets SET assigned_agent_id='a002' WHERE ticket_id='t003'")
        conn.commit()
        conn.close()
        r = run_ok(["workload-balance", db])
        lines = r.stdout.strip().splitlines()
        agent_ids = [ln.split()[0] for ln in lines]
        # Expected: a001 (20.0%) > a002 (13.3333%) > ag_l3b (0%) > a001 already first
        # wait: a001=20%, a002=13.3333%, ag_l3b=0% — so order is a001, a002, ag_l3b
        # but db fixture also has a001 and a002; ag_l3b added here
        assert agent_ids[0] == "a001", (
            f"a001 (util=20.0000) must be first. got: {agent_ids[0]!r}. full: {agent_ids}"
        )
        assert agent_ids[1] == "a002", (
            f"a002 (util=13.3333) must be second. got: {agent_ids[1]!r}. full: {agent_ids}"
        )
        assert agent_ids[-1] == "ag_l3b", (
            f"ag_l3b (util=0.0000) must be last. got: {agent_ids[-1]!r}. full: {agent_ids}"
        )

    def test_workload_balance_sort_tiebreak_agent_id_asc(self, db):
        """When two agents have equal utilization, sort by agent_id ASC.
        Both L1 with 1 open ticket each -> both 20.0000%, sort by agent_id.
        'a001' < 'z999' alphabetically so a001 must come first."""
        # Add another L1 agent with id that sorts after a001
        run_ok(["add-agent", db, "z999_l1", "ZAgent", "L1"])
        # Open and assign 1 ticket to each L1 agent
        run_ok(["open-ticket", db, "tie001", "Tie ticket 1", "low"])
        run_ok(["open-ticket", db, "tie002", "Tie ticket 2", "low"])
        conn = sqlite3.connect(db)
        conn.execute("UPDATE tickets SET assigned_agent_id='a001' WHERE ticket_id='tie001'")
        conn.execute("UPDATE tickets SET assigned_agent_id='z999_l1' WHERE ticket_id='tie002'")
        conn.commit()
        conn.close()
        r = run_ok(["workload-balance", db])
        lines = r.stdout.strip().splitlines()
        agent_ids = [ln.split()[0] for ln in lines]
        utils = {ln.split()[0]: float(ln.split()[3].split("=")[1]) for ln in lines}
        # Both a001 and z999_l1 have util=20.0000; a001 < z999_l1 alphabetically
        idx_a01 = agent_ids.index("a001")
        idx_z99 = agent_ids.index("z999_l1")
        assert abs(utils["z999_l1"] - utils["a001"]) < 0.0001, (
            f"Both agents must have equal utilization=20.0000. "
            f"z999_l1={utils['z999_l1']:.4f}, a001={utils['a001']:.4f}"
        )
        assert idx_a01 < idx_z99, (
            f"Tie-break by agent_id ASC: 'a001' < 'z999_l1' so a001 must come first. "
            f"got order: {agent_ids}"
        )

    def test_workload_balance_over_100_pct_allowed(self, db):
        """Utilization can exceed 100% if open tickets exceed capacity.
        L1 capacity=5: 7 open tickets = 140.0000%."""
        for i in range(7):
            tid = f"over{i:03d}"
            run_ok(["open-ticket", db, tid, f"over ticket {i}", "low"])
            conn = sqlite3.connect(db)
            conn.execute(
                "UPDATE tickets SET assigned_agent_id='a001' WHERE ticket_id=?", (tid,)
            )
            conn.commit()
            conn.close()
        r = run_ok(["workload-balance", db])
        rows = {}
        for line in r.stdout.strip().splitlines():
            parts = line.split()
            aid = parts[0]
            util = float(parts[3].split("=")[1])
            rows[aid] = util
        assert abs(rows["a001"] - 140.0) < 0.0001, (
            f"L1 agent with 7 open tickets: 7/5*100=140.0000. "
            f"got: {rows['a001']:.4f}"
        )

    def test_workload_balance_utilization_precision_non_integer(self, db):
        """L2 capacity=15: 1 open ticket = 6.6667% (HALF_UP rounding at 4dp).
        Catches agents that truncate or use wrong rounding."""
        conn = sqlite3.connect(db)
        conn.execute("UPDATE tickets SET assigned_agent_id='a002' WHERE ticket_id='t001'")
        conn.commit()
        conn.close()
        r = run_ok(["workload-balance", db])
        rows = {}
        for line in r.stdout.strip().splitlines():
            parts = line.split()
            aid = parts[0]
            util_str = parts[3].split("=")[1]
            rows[aid] = util_str
        # 1/15 * 100 = 6.666...7 -> 6.6667 (HALF_UP) or 6.6667 (standard float)
        assert rows["a002"] == "6.6667", (
            f"L2 1 ticket: 1/15*100=6.6667. Truncation gives 6.6666. "
            f"got: {rows['a002']!r}"
        )
