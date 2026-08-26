"""Milestone 1 tests: init, add-agent, open-ticket, list-tickets."""
import subprocess
import os
import pytest


def run(args, check=False):
    result = subprocess.run(
        ["/app/app"] + args,
        capture_output=True,
        text=True,
    )
    if check:
        assert result.returncode == 0, f"Non-zero exit: {result.stderr or result.stdout}"
    return result


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "test.db")
    run(["init", path], check=True)
    return path


class TestMilestone1:
    def test_init_creates_db(self, tmp_path):
        path = str(tmp_path / "new.db")
        r = run(["init", path])
        assert r.returncode == 0
        assert os.path.exists(path)

    def test_init_idempotent(self, tmp_path):
        path = str(tmp_path / "new.db")
        run(["init", path], check=True)
        r = run(["init", path])
        assert r.returncode == 0

    def test_init_creates_resolutions_table(self, tmp_path):
        """init must create the resolutions table."""
        import sqlite3
        path = str(tmp_path / "chk.db")
        run(["init", path], check=True)
        conn = sqlite3.connect(path)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert "resolutions" in tables, (
            f"init must create 'resolutions' table. Found tables: {tables}"
        )

    def test_init_creates_resolution_chain_table(self, tmp_path):
        """init must create the resolution_chain table."""
        import sqlite3
        path = str(tmp_path / "chk2.db")
        run(["init", path], check=True)
        conn = sqlite3.connect(path)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        assert "resolution_chain" in tables, (
            f"init must create 'resolution_chain' table. Found tables: {tables}"
        )

    def test_add_agent_ok(self, db):
        r = run(["add-agent", db, "a1", "Alice", "L1"])
        assert r.returncode == 0
        assert "OK agent=a1" in r.stdout

    def test_add_agent_duplicate(self, db):
        run(["add-agent", db, "a1", "Alice", "L1"], check=True)
        r = run(["add-agent", db, "a1", "Alice", "L1"])
        assert r.returncode == 1
        assert "agent already exists: a1" in r.stdout

    def test_add_agent_invalid_tier(self, db):
        r = run(["add-agent", db, "a1", "Alice", "L4"])
        assert r.returncode == 1
        assert "invalid tier: L4" in r.stdout

    def test_add_agent_all_tiers(self, db):
        for i, tier in enumerate(["L1", "L2", "L3"], 1):
            r = run(["add-agent", db, f"a{i}", f"Agent{i}", tier])
            assert r.returncode == 0

    def test_open_ticket_ok(self, db):
        r = run(["open-ticket", db, "t1", "Login broken", "high"])
        assert r.returncode == 0
        assert "OK ticket=t1" in r.stdout

    def test_open_ticket_duplicate(self, db):
        run(["open-ticket", db, "t1", "Login broken", "high"], check=True)
        r = run(["open-ticket", db, "t1", "Login broken", "high"])
        assert r.returncode == 1
        assert "ticket already exists: t1" in r.stdout

    def test_open_ticket_invalid_priority(self, db):
        r = run(["open-ticket", db, "t1", "Login broken", "urgent"])
        assert r.returncode == 1
        assert "invalid priority: urgent" in r.stdout

    def test_open_ticket_all_priorities(self, db):
        for i, pri in enumerate(["low", "medium", "high", "critical"], 1):
            r = run(["open-ticket", db, f"t{i}", f"Issue {i}", pri])
            assert r.returncode == 0

    def test_list_tickets_empty(self, db):
        r = run(["list-tickets", db], check=True)
        assert r.stdout.strip() == ""

    def test_list_tickets_ordered_by_ticket_id(self, db):
        run(["open-ticket", db, "t-z", "Z", "low"], check=True)
        run(["open-ticket", db, "t-a", "A", "high"], check=True)
        run(["open-ticket", db, "t-m", "M", "medium"], check=True)
        r = run(["list-tickets", db], check=True)
        ids = [line.split("\t")[0] for line in r.stdout.strip().splitlines()]
        assert ids == sorted(ids)

    def test_list_tickets_status_open(self, db):
        run(["open-ticket", db, "t1", "Issue", "low"], check=True)
        r = run(["list-tickets", db], check=True)
        cols = r.stdout.strip().split("\t")
        assert cols[1] == "open"

    def test_list_tickets_no_agent_empty_string(self, db):
        run(["open-ticket", db, "t1", "Issue", "low"], check=True)
        r = run(["list-tickets", db], check=True)
        cols = r.stdout.rstrip('\n').split("\t")
        assert cols[2] == ""

    def test_list_tickets_priority_semantic_order(self, db):
        """list-tickets orders by semantic priority DESC: critical>high>medium>low.
        Alphabetical DESC gives medium>low>high>critical (WRONG).
        Uses CASE expression weight, NOT alphabetical sort.
        Verify by checking the ORDER of ticket_ids with known priorities."""
        run(["open-ticket", db, "tp-low", "Low issue", "low"], check=True)
        run(["open-ticket", db, "tp-crit", "Critical issue", "critical"], check=True)
        run(["open-ticket", db, "tp-med", "Medium issue", "medium"], check=True)
        run(["open-ticket", db, "tp-high", "High issue", "high"], check=True)
        r = run(["list-tickets", db], check=True)
        # The ticket_ids encode their priority; verify ordering by ticket_id position
        ids = [line.split("\t")[0] for line in r.stdout.strip().splitlines()
               if line.split("\t")[0].startswith("tp-")]
        expected_order = ["tp-crit", "tp-high", "tp-med", "tp-low"]
        assert ids == expected_order, (
            f"Priority order must be critical>high>medium>low. "
            f"Got ticket order: {ids}, expected: {expected_order}. "
            f"Alphabetical DESC (wrong) gives: medium>low>high>critical."
        )

    def test_list_tickets_high_before_medium_not_alphabetical(self, db):
        """Specifically: 'high' must come before 'medium'. Alphabetically m>h so
        ORDER BY priority DESC puts medium before high (wrong).
        Verify by checking ticket_id order (tna-high must precede tna-med)."""
        run(["open-ticket", db, "tna-med", "Medium issue", "medium"], check=True)
        run(["open-ticket", db, "tna-high", "High issue", "high"], check=True)
        r = run(["list-tickets", db], check=True)
        ids = [ln.split("\t")[0] for ln in r.stdout.strip().splitlines()
               if ln.split("\t")[0] in ("tna-med", "tna-high")]
        assert ids.index("tna-high") < ids.index("tna-med"), (
            f"tna-high (priority=high) must appear before tna-med (priority=medium). "
            f"Got order: {ids}. "
            f"Alphabetically 'm'>'h' so ORDER BY priority DESC is wrong here."
        )

    def test_list_tickets_same_priority_opened_at_tiebreak(self, db):
        """Within same priority, earlier opened_at comes first (ASC tiebreak).
        Catches agents using insertion order or ticket_id instead of opened_at."""
        import sqlite3
        run(["open-ticket", db, "tsame-later", "Later ticket", "high"], check=True)
        run(["open-ticket", db, "tsame-earlier", "Earlier ticket", "high"], check=True)
        conn = sqlite3.connect(db)
        conn.execute("UPDATE tickets SET opened_at='2026-06-01 08:00:00' WHERE ticket_id='tsame-earlier'")
        conn.execute("UPDATE tickets SET opened_at='2026-06-01 09:00:00' WHERE ticket_id='tsame-later'")
        conn.commit()
        conn.close()
        r = run(["list-tickets", db], check=True)
        ids = [ln.split("\t")[0] for ln in r.stdout.strip().splitlines()
               if ln.split("\t")[0] in ("tsame-earlier", "tsame-later")]
        assert ids[0] == "tsame-earlier", (
            f"Same priority: earlier opened_at must come first. ids={ids}"
        )

    def test_list_tickets_same_priority_same_opened_at_ticket_id_tiebreak(self, db):
        """Final tiebreak: same priority AND same opened_at → ticket_id ASC."""
        import sqlite3
        run(["open-ticket", db, "ttt-zzz", "Z ticket", "medium"], check=True)
        run(["open-ticket", db, "ttt-aaa", "A ticket", "medium"], check=True)
        conn = sqlite3.connect(db)
        conn.execute("UPDATE tickets SET opened_at='2026-01-01 00:00:00' WHERE ticket_id='ttt-zzz'")
        conn.execute("UPDATE tickets SET opened_at='2026-01-01 00:00:00' WHERE ticket_id='ttt-aaa'")
        conn.commit()
        conn.close()
        r = run(["list-tickets", db], check=True)
        ids = [ln.split("\t")[0] for ln in r.stdout.strip().splitlines()
               if ln.split("\t")[0] in ("ttt-aaa", "ttt-zzz")]
        assert ids[0] == "ttt-aaa", (
            f"Same priority+opened_at: ticket_id ASC tiebreak. ids={ids}"
        )

    def test_list_tickets_single_ticket_edge_case(self, db):
        """Edge case: exactly one ticket returns exactly one line.
        Format: ticket_id TAB status TAB assigned_agent_id (empty string if unassigned).
        Trailing tab must be present so the 3rd column exists and is empty string."""
        run(["open-ticket", db, "solo-t1", "Solo ticket", "high"], check=True)
        r = run(["list-tickets", db], check=True)
        # Use splitlines() without outer strip() to preserve trailing tab
        lines = r.stdout.rstrip('\n').splitlines()
        assert len(lines) == 1, f"Expected 1 line, got {len(lines)}: {r.stdout!r}"
        cols = lines[0].split("\t")
        assert len(cols) == 3, (
            f"list-tickets line must have 3 tab-separated columns: "
            f"ticket_id, status, assigned_agent_id. Got {len(cols)} cols: {cols!r}"
        )
        assert cols[0] == "solo-t1"
        assert cols[1] == "open"
        assert cols[2] == "", (
            f"Unassigned ticket: assigned_agent_id (col 3) must be empty string, "
            f"got: {cols[2]!r}"
        )

    def test_init_creates_all_four_tables(self, tmp_path):
        """After init, all 4 tables must exist: agents, tickets, resolutions, resolution_chain."""
        import sqlite3
        path = str(tmp_path / "four.db")
        run(["init", path], check=True)
        conn = sqlite3.connect(path)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        for t in ("agents", "tickets", "resolutions", "resolution_chain"):
            assert t in tables, f"init must create table '{t}'. Found: {tables}"

    def test_init_does_not_delete_existing_rows(self, tmp_path):
        """Running init a second time must not delete existing data."""
        import sqlite3
        path = str(tmp_path / "idem.db")
        run(["init", path], check=True)
        run(["add-agent", path, "persist-a1", "PersistAgent", "L2"], check=True)
        run(["init", path], check=True)
        conn = sqlite3.connect(path)
        row = conn.execute("SELECT agent_id FROM agents WHERE agent_id='persist-a1'").fetchone()
        conn.close()
        assert row is not None, "init must not delete existing rows on second run"

    def test_add_agent_stored_correctly(self, db):
        """After add-agent, the row must exist in sqlite with correct agent_id, name, tier."""
        import sqlite3
        run(["add-agent", db, "store-a1", "StoredName", "L3"], check=True)
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT agent_id, name, tier FROM agents WHERE agent_id='store-a1'"
        ).fetchone()
        conn.close()
        assert row is not None, "add-agent must persist the row in the agents table"
        assert row[0] == "store-a1"
        assert row[1] == "StoredName"
        assert row[2] == "L3"

    def test_list_tickets_three_columns(self, db):
        """list-tickets must output exactly 3 tab-separated columns per line."""
        run(["open-ticket", db, "col-t1", "Column test", "medium"], check=True)
        r = run(["list-tickets", db], check=True)
        for line in r.stdout.rstrip("\n").splitlines():
            cols = line.split("\t")
            assert len(cols) == 3, (
                f"list-tickets must have 3 tab-separated columns (ticket_id, status, assigned_agent_id). "
                f"Got {len(cols)} columns: {cols!r}"
            )

    def test_list_tickets_all_same_priority_ordered_by_opened_at(self, db):
        """All tickets same priority: must be ordered by opened_at ASC."""
        import sqlite3
        run(["open-ticket", db, "tsp-c", "C ticket", "low"], check=True)
        run(["open-ticket", db, "tsp-a", "A ticket", "low"], check=True)
        run(["open-ticket", db, "tsp-b", "B ticket", "low"], check=True)
        conn = sqlite3.connect(db)
        conn.execute("UPDATE tickets SET opened_at='2026-06-01 10:00:00' WHERE ticket_id='tsp-a'")
        conn.execute("UPDATE tickets SET opened_at='2026-06-01 11:00:00' WHERE ticket_id='tsp-b'")
        conn.execute("UPDATE tickets SET opened_at='2026-06-01 12:00:00' WHERE ticket_id='tsp-c'")
        conn.commit()
        conn.close()
        r = run(["list-tickets", db], check=True)
        ids = [ln.split("\t")[0] for ln in r.stdout.strip().splitlines()
               if ln.split("\t")[0] in ("tsp-a", "tsp-b", "tsp-c")]
        assert ids == ["tsp-a", "tsp-b", "tsp-c"], (
            f"All same priority: must order by opened_at ASC. ids={ids}"
        )
