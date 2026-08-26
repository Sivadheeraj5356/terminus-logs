"""Milestone 4: the case file in SQLite.

The database carries the same stable settlement the register file reports, so every row is
graded against the reference settlement, not merely against the engine's own files.
"""
import os
import sqlite3
import tempfile

import pytest

import _corpora as C
import _ref

CORPORA = C.corpora(n_hidden=5)


def ingest(data):
    db = os.path.join(tempfile.mkdtemp(prefix="db_"), "case.db")
    C.run(["ingest", "--data", data, "--db", db])
    return db


@pytest.mark.parametrize("name,data", CORPORA, ids=[n for n, _ in CORPORA])
class TestIngest:
    def test_register_table_matches_the_settlement(self, name, data):
        """Every register row stored in SQLite matches the reference settlement
        field for field, with the peak and shed flags stored as integer 1 or 0."""
        db = ingest(data)
        reg, res = C.expect(data, 3)
        con = sqlite3.connect(db)
        con.row_factory = sqlite3.Row
        rows = {r["id"]: r for r in con.execute("SELECT * FROM register")}
        want = res["register"]
        assert len(rows) == len(want)
        for w in want:
            got = rows[w["id"]]
            for k in _ref.REG_KEYS:
                if k in ("peak", "shed"):
                    assert got[k] == int(w[k]), "%s.%s" % (w["id"], k)
                else:
                    assert got[k] == w[k], "%s.%s" % (w["id"], k)

    def test_findings_table_holds_the_exact_lines_in_emission_order(self, name, data):
        """The findings table carries one row per finding, seq its 0-based emission
        position, kind its kind, and body its exact findings.jsonl line."""
        db = ingest(data)
        reg, res = C.expect(data, 3)
        con = sqlite3.connect(db)
        got = list(con.execute("SELECT seq,kind,body FROM findings ORDER BY seq"))
        want = _ref.order_findings(res["findings"])
        assert len(got) == len(want)
        for i, (seq, kind, body) in enumerate(got):
            assert seq == i
            assert kind == want[i]["kind"]
            assert body == _ref.jdump(want[i])

    def test_reingest_refreshes_rather_than_duplicates(self, name, data):
        """Re-running ingest against the same database refreshes the case file
        instead of accumulating a second copy of the rows."""
        db = ingest(data)
        C.run(["ingest", "--data", data, "--db", db])
        reg, res = C.expect(data, 3)
        con = sqlite3.connect(db)
        n = con.execute("SELECT COUNT(*) FROM register").fetchone()[0]
        m = con.execute("SELECT COUNT(*) FROM findings").fetchone()[0]
        assert n == len(res["register"])
        assert m == len(_ref.order_findings(res["findings"]))

    def test_settle_still_works(self, name, data):
        """Adding ingest does not disturb the earlier settle command, which still
        writes the byte-exact summary."""
        reg, res = C.expect(data, 3)
        out = C.run_stage(data, "settle")
        assert C.read(out, "summary.json").decode() == _ref.jdump(
            _ref.summary_json(reg, res)) + "\n"
