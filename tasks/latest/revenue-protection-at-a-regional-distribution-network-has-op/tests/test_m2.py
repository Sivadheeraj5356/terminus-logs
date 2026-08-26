"""Milestone 2: draw reconstruction and the credential-fraud detectors.

Folds reads into draws against the FIRST read of each draw, picks the surviving read, and
flags replays, bypasses and the wholesale quarantine of a compromised account. Graded
byte-for-byte on the example, the visible corpus and four corpora seeded at verify time.
"""
import pytest

import _corpora as C
import _ref

CORPORA = C.corpora()


@pytest.mark.parametrize("name,data", CORPORA, ids=[n for n, _ in CORPORA])
class TestDraws:
    def test_draw_register_is_byte_exact(self, name, data):
        """The folded draws in register order, each with the status the detectors left."""
        out = C.run_stage(data, "draws")
        reg, res = C.expect(data, 2)
        assert C.read(out, "draws.jsonl").decode() == _ref.draws_text(res["draws"])

    def test_fraud_findings_are_byte_exact(self, name, data):
        """The six kinds raised so far, in emission order."""
        out = C.run_stage(data, "draws")
        reg, res = C.expect(data, 2)
        assert C.read(out, "findings.jsonl").decode() == _ref.findings_text(
            res["findings"])

    def test_reconstruction_census_is_byte_exact(self, name, data):
        """Counts by status, the compromised accounts, and the two FNV folds."""
        out = C.run_stage(data, "draws")
        reg, res = C.expect(data, 2)
        assert C.read(out, "draws.json").decode() == _ref.jdump(
            _ref.draws_json(reg, res)) + "\n"

    def test_intake_still_works(self, name, data):
        """Milestone 1's command is untouched."""
        out = C.run_stage(data, "intake")
        reg, res = C.expect(data, 1)
        assert C.read(out, "evidence.jsonl").decode() == _ref.evidence_text(
            res["evidence"])
