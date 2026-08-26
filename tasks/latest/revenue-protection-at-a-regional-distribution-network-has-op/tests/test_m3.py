"""Milestone 3: the stable settlement, the circulars, the disputes and the cascade.

The register is not per-account decomposable: admission is bounded by the tightest residual
along an account's whole chain and depletes every ancestor, the tariff bands are indexed
against the SUPPLY POINT's shared cumulative, the next draw to settle is re-chosen from the
state the last settlement left behind, and the condemnation cascade runs to a fixpoint that
severs accounts with nothing locally wrong. Graded byte-for-byte on the example, the
visible corpus and four corpora seeded at verify time.
"""
import pytest

import _corpora as C
import _ref

CORPORA = C.corpora()


@pytest.mark.parametrize("name,data", CORPORA, ids=[n for n, _ in CORPORA])
class TestSettle:
    def test_register_is_byte_exact(self, name, data):
        """Every settled row: the chain-bounded admission, the band the supply point had
        already reached, the peak and shed flags of the slot it settled in, and its
        status."""
        out = C.run_stage(data, "settle")
        reg, res = C.expect(data, 3)
        assert C.read(out, "register.jsonl").decode() == _ref.register_text(
            res["register"])

    def test_all_eight_finding_kinds_are_byte_exact(self, name, data):
        """Including void_fraud and the condemnation of each locked-out circuit."""
        out = C.run_stage(data, "settle")
        reg, res = C.expect(data, 3)
        assert C.read(out, "findings.jsonl").decode() == _ref.findings_text(
            res["findings"])

    def test_closed_case_is_byte_exact(self, name, data):
        """The case census, the exposure ranking, the supply block and the three folds."""
        out = C.run_stage(data, "settle")
        reg, res = C.expect(data, 3)
        assert C.read(out, "summary.json").decode() == _ref.jdump(
            _ref.summary_json(reg, res)) + "\n"

    def test_earlier_commands_still_work(self, name, data):
        """The intake and draws commands keep producing their byte-exact evidence
        and draw-register outputs after settle is added."""
        reg, r1 = C.expect(data, 1)
        assert C.read(C.run_stage(data, "intake"), "evidence.jsonl").decode() == \
            _ref.evidence_text(r1["evidence"])
        reg, r2 = C.expect(data, 2)
        assert C.read(C.run_stage(data, "draws"), "draws.jsonl").decode() == \
            _ref.draws_text(r2["draws"])


def test_the_cascade_severs_accounts_with_nothing_wrong():
    """On the visible corpus the lockout propagates through the supply chain and takes
    down accounts that never replayed, never bypassed and were never disputed."""
    reg, res = C.expect("/app/data", 3)
    rows = res["register"]
    guilty = {r["account"] for r in rows
              if r["status"] in ("replay", "bypass", "suspect", "voided")}
    severed = {r["account"] for r in rows if r["status"] == "severed"}
    assert severed - guilty, "no emergent severance in the graded corpus"
    out = C.run_stage("/app/data", "settle")
    assert C.read(out, "register.jsonl").decode() == _ref.register_text(rows)
