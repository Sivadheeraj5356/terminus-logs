"""Milestone 3 tests for lifecycle validation and audit export."""

from __future__ import annotations

import auth_ref


class TestMilestone3:
    """Token lifecycle and rotation audit checks."""

    def setup_method(self) -> None:
        """Reset ledger and audit output before each test."""
        auth_ref.reset_db()

    def test_active_token_valid_before_revoke(self) -> None:
        """Unrevoked tokens signed with the active kid must validate."""
        state = auth_ref.rotation_state()
        token = auth_ref.sign_token(state["active_kid"], "m3-live")
        assert auth_ref.validate(token) == 0

    def test_revoked_token_rejected(self) -> None:
        """Validation must fail after the jti is revoked."""
        state = auth_ref.rotation_state()
        jti = "m3-revoked"
        token = auth_ref.sign_token(state["active_kid"], jti)
        assert auth_ref.validate(token) == 0
        auth_ref.revoke(jti, "compromised")
        assert auth_ref.validate(token) != 0

    def test_expired_token_rejected(self) -> None:
        """Validation must reject tokens whose exp is before the service clock."""
        state = auth_ref.rotation_state()
        now = auth_ref.clock_epoch()
        token = auth_ref.sign_token_expired(state["active_kid"], "m3-expired", now)
        assert auth_ref.validate(token) != 0

    def test_exp_equal_to_clock_still_valid(self) -> None:
        """Tokens whose exp equals the service clock must still validate."""
        state = auth_ref.rotation_state()
        now = auth_ref.clock_epoch()
        token = auth_ref.sign_token_with_exp(state["active_kid"], "m3-exp-equal", now)
        assert auth_ref.validate(token) == 0

    def test_expired_token_rejected_with_auth_clock_epoch_override(self) -> None:
        """exp checks must honor AUTH_CLOCK_EPOCH when the override is set."""
        state = auth_ref.rotation_state()
        override = auth_ref.clock_epoch() + 100000
        token = auth_ref.sign_token_expired(state["active_kid"], "m3-exp-override", override)
        assert auth_ref.validate(token, epoch=override) != 0

    def test_token_without_exp_valid_with_auth_clock_epoch_override(self) -> None:
        """Tokens without exp must still validate when AUTH_CLOCK_EPOCH is overridden."""
        state = auth_ref.rotation_state()
        override = auth_ref.clock_epoch() + 9999
        token = auth_ref.sign_token(state["active_kid"], "m3-no-exp-override")
        assert auth_ref.validate(token, epoch=override) == 0

    def test_audit_export_matches_contract(self) -> None:
        """Audit JSONL must follow sorted event_seq contract formatting."""
        jtis = ["m3-audit-b", "m3-audit-a"]
        for jti in jtis:
            auth_ref.revoke(jti, "audit")
        auth_ref.export_audit()
        lines = auth_ref.AUDIT.read_text(encoding="utf-8").strip().splitlines()
        assert lines == auth_ref.expected_audit_lines(jtis)

    def test_audit_export_is_repeatable(self) -> None:
        """Two consecutive exports must produce identical bytes."""
        auth_ref.revoke("m3-repeat", "audit")
        auth_ref.export_audit()
        first = auth_ref.AUDIT.read_bytes()
        auth_ref.export_audit()
        second = auth_ref.AUDIT.read_bytes()
        assert first == second
