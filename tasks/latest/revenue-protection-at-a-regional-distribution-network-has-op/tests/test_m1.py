"""Milestone 1: evidence intake.

Parses the packed binary meter exports, verifies the nibble-swapped checksums, resolves
reads to accounts and delivery points, and raises the three intake findings (tamper,
spoliation, misdeclare). Graded byte-for-byte against an independent reference on the
worked example, the visible corpus, and four corpora seeded at verify time.
"""
import pytest

import _corpora as C
import _ref

CORPORA = C.corpora()


@pytest.mark.parametrize("name,data", CORPORA, ids=[n for n, _ in CORPORA])
class TestIntake:
    def test_evidence_log_is_byte_exact(self, name, data):
        """Every surviving, resolved read is logged, in (segment, ordinal) order, with
        the reporting utility and the CLAIMED class."""
        out = C.run_stage(data, "intake")
        reg, res = C.expect(data, 1)
        assert C.read(out, "evidence.jsonl").decode() == _ref.evidence_text(
            res["evidence"])

    def test_intake_findings_are_byte_exact(self, name, data):
        """Tampered records, truncated segments and class understatements, grouped by
        kind and ordered within a kind by (segment, record)."""
        out = C.run_stage(data, "intake")
        reg, res = C.expect(data, 1)
        assert C.read(out, "findings.jsonl").decode() == _ref.findings_text(
            res["findings"])

    def test_intake_census_is_byte_exact(self, name, data):
        """The census, the per-utility exposure ranking and the two FNV folds."""
        out = C.run_stage(data, "intake")
        reg, res = C.expect(data, 1)
        assert C.read(out, "intake.json").decode() == _ref.jdump(
            _ref.intake_json(reg, res)) + "\n"


def test_missing_flag_exits_2():
    """Every subcommand exits 2 when one of its required flags is absent, including
    serve without --port and serve without --db."""
    import subprocess
    cases = [
        ["intake", "--data", "/app/data"],       # missing --out
        ["draws", "--out", "/tmp/o"],            # missing --data
        ["settle", "--data", "/app/data"],       # missing --out
        ["ingest", "--data", "/app/data"],       # missing --db
        ["serve", "--db", "/tmp/x.db"],          # missing --port
        ["serve", "--port", "8080"],             # missing --db
    ]
    for argv in cases:
        r = subprocess.run([C.BIN] + argv, capture_output=True)
        assert r.returncode == 2, argv
