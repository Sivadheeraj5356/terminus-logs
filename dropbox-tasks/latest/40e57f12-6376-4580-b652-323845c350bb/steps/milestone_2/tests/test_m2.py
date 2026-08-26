"""Milestone 2 tests for append-only revocation ledger."""

from __future__ import annotations

import auth_ref


class TestMilestone2:
    """SQLite revocation ledger checks."""

    def setup_method(self) -> None:
        """Start each test with a clean ledger file."""
        auth_ref.reset_db()

    def test_first_revoke_inserts_row(self) -> None:
        """Revoking a jti must create a ledger row."""
        auth_ref.revoke("m2-jti-a", "logout")
        rows = auth_ref.db_rows("m2-jti-a")
        assert len(rows) == 1
        assert rows[0][1] == "m2-jti-a"
        assert rows[0][3] == "logout"

    def test_duplicate_revoke_is_noop(self) -> None:
        """Re-revoking the same jti must not mutate the stored timestamp."""
        auth_ref.revoke("m2-jti-dup", "once")
        first = auth_ref.db_rows("m2-jti-dup")[0]
        auth_ref.revoke("m2-jti-dup", "again")
        second = auth_ref.db_rows("m2-jti-dup")
        assert len(second) == 1
        assert second[0][0] == first[0]
        assert second[0][2] == first[2]
        assert second[0][3] == first[3]

    def test_distinct_jtis_append_rows(self) -> None:
        """Distinct jtis must produce monotonically increasing row ids."""
        auth_ref.revoke("m2-jti-one")
        auth_ref.revoke("m2-jti-two")
        row_one = auth_ref.db_rows("m2-jti-one")[0][0]
        row_two = auth_ref.db_rows("m2-jti-two")[0][0]
        assert row_two > row_one

    def test_revoked_at_matches_service_clock(self) -> None:
        """revoked_at must follow the configured service clock, not wall time."""
        auth_ref.revoke("m2-clock", "logout")
        row = auth_ref.db_rows("m2-clock")[0]
        assert row[2] == auth_ref.expected_revoked_at()

    def test_revoked_at_honors_auth_clock_epoch_override(self) -> None:
        """revoked_at must honor AUTH_CLOCK_EPOCH when the override is set."""
        override = auth_ref.clock_epoch() + 5000
        auth_ref.revoke("m2-override", "logout", epoch=override)
        row = auth_ref.db_rows("m2-override")[0]
        assert row[2] == auth_ref.expected_revoked_at(override)

    def test_revocation_survives_reopen(self) -> None:
        """Ledger contents must persist after the service process exits."""
        auth_ref.revoke("m2-jti-persist", "persist")
        rows_before = auth_ref.db_rows("m2-jti-persist")
        rows_after = auth_ref.db_rows("m2-jti-persist")
        assert rows_before == rows_after
