"""Milestone 1 tests for JWK rotation grace handling."""

from __future__ import annotations

import base64
import json

import auth_ref


class TestMilestone1:
    """JWK rotation and kid selection checks."""

    def test_active_key_valid_during_grace(self) -> None:
        """Active kid tokens must validate inside the grace window."""
        state = auth_ref.rotation_state()
        token = auth_ref.sign_token(state["active_kid"], "m1-active-grace")
        assert auth_ref.validate(token, epoch=auth_ref.grace_inside_epoch()) == 0

    def test_retiring_key_valid_during_grace(self) -> None:
        """Retiring kid tokens must validate inside the grace window."""
        state = auth_ref.rotation_state()
        token = auth_ref.sign_token(state["retiring_kid"], "m1-retire-grace")
        assert auth_ref.validate(token, epoch=auth_ref.grace_inside_epoch()) == 0

    def test_retiring_key_valid_at_grace_end(self) -> None:
        """Retiring kid tokens must validate on the grace window's last second."""
        state = auth_ref.rotation_state()
        token = auth_ref.sign_token(state["retiring_kid"], "m1-retire-end")
        assert auth_ref.validate(token, epoch=auth_ref.grace_end_epoch()) == 0

    def test_retiring_key_rejected_after_grace(self) -> None:
        """Retiring kid tokens must fail after grace expires."""
        state = auth_ref.rotation_state()
        token = auth_ref.sign_token(state["retiring_kid"], "m1-retire-late")
        assert auth_ref.validate(token, epoch=auth_ref.grace_outside_epoch()) != 0

    def test_unknown_kid_rejected(self) -> None:
        """Tokens with an unknown kid must be rejected."""
        state = auth_ref.rotation_state()
        token = auth_ref.sign_token(state["active_kid"], "m1-unknown-kid")
        header, payload, sig = token.split(".")
        pad = "=" * (-len(header) % 4)
        raw = json.loads(base64.urlsafe_b64decode(header + pad))
        raw["kid"] = "unknown-kid"
        new_header = base64.urlsafe_b64encode(
            json.dumps(raw, separators=(",", ":")).encode()
        ).rstrip(b"=").decode()
        bad = f"{new_header}.{payload}.{sig}"
        assert auth_ref.validate(bad, epoch=auth_ref.grace_inside_epoch()) != 0

    def test_missing_kid_rejected(self) -> None:
        """Tokens without a kid header must be rejected."""
        state = auth_ref.rotation_state()
        token = auth_ref.sign_token_missing_kid(state["active_kid"], "m1-missing-kid")
        assert auth_ref.validate(token, epoch=auth_ref.grace_inside_epoch()) != 0

    def test_grace_follows_rotation_state_not_service_toml(self) -> None:
        """Grace end must use rotation-state.json when service.toml grace is shorter."""
        state = auth_ref.rotation_state()
        service_grace = 600
        epoch = int(state["rotated_at"]) + service_grace + 100
        assert epoch <= auth_ref.grace_end_epoch(state)
        token = auth_ref.sign_token(state["retiring_kid"], "m1-grace-source")
        assert auth_ref.validate(token, epoch=epoch) == 0

    def test_variant_seed_shifts_grace_boundary(self) -> None:
        """Grace boundary must track rotation-state.json after variant seed mutation."""
        state = auth_ref.rotation_state()
        token = auth_ref.sign_token(state["retiring_kid"], "m1-variant-boundary")
        assert auth_ref.validate(token, epoch=auth_ref.grace_end_epoch(state)) == 0
        assert auth_ref.validate(token, epoch=auth_ref.grace_outside_epoch(state)) != 0
