"""Shared helpers for JWT rotation tests."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from pathlib import Path

import jwt
from cryptography.hazmat.primitives.serialization import load_pem_private_key

CONFIG = Path("/app/auth/config/service.toml")
ROTATION = Path("/app/auth/keys/rotation-state.json")
KEYS_DIR = Path("/app/auth/keys")
DB = Path("/app/auth/data/revocations.db")
AUDIT = Path("/app/auth/out/rotation-audit.jsonl")
TOKENSVC = Path("/app/auth/bin/tokensvc")


def rotation_state() -> dict:
    """Load rotation-state.json."""
    return json.loads(ROTATION.read_text(encoding="utf-8"))


def clock_epoch() -> int:
    """Return configured clock epoch from service.toml."""
    for line in CONFIG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("clock_epoch"):
            return int(line.split("=", 1)[1].strip())
    raise ValueError("clock_epoch missing")


def sign_token(kid: str, jti: str, epoch: int | None = None) -> str:
    """Sign an EdDSA JWT with the private key for kid."""
    pem_path = KEYS_DIR / f"{kid}.pem"
    private_key = load_pem_private_key(pem_path.read_bytes(), password=None)
    return jwt.encode(
        {"jti": jti, "sub": "client"},
        private_key,
        algorithm="EdDSA",
        headers={"kid": kid},
    )


def sign_token_missing_kid(kid: str, jti: str) -> str:
    """Sign an EdDSA JWT without a kid header."""
    pem_path = KEYS_DIR / f"{kid}.pem"
    private_key = load_pem_private_key(pem_path.read_bytes(), password=None)
    return jwt.encode(
        {"jti": jti, "sub": "client"},
        private_key,
        algorithm="EdDSA",
    )


def run_tokensvc(args: list[str], epoch: int | None = None) -> subprocess.CompletedProcess[str]:
    """Invoke tokensvc with optional AUTH_CLOCK_EPOCH override."""
    env = os.environ.copy()
    if epoch is not None:
        env["AUTH_CLOCK_EPOCH"] = str(epoch)
    return subprocess.run(
        [str(TOKENSVC), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def validate(token: str, epoch: int | None = None) -> int:
    """Return tokensvc validate exit code."""
    return run_tokensvc(["validate", token], epoch=epoch).returncode


def revoke(jti: str, reason: str = "test") -> None:
    """Revoke a token jti via tokensvc."""
    proc = run_tokensvc(["revoke", jti, reason])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)


def export_audit() -> None:
    """Write rotation audit export."""
    proc = run_tokensvc(["export-audit"])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)


def db_rows(jti: str) -> list[tuple[int, str, str, str]]:
    """Fetch revocation rows for a jti ordered by id."""
    conn = sqlite3.connect(DB)
    try:
        return conn.execute(
            "SELECT id, jti, revoked_at, reason FROM revocations WHERE jti = ? ORDER BY id",
            (jti,),
        ).fetchall()
    finally:
        conn.close()


def reset_db() -> None:
    """Remove revocation database for isolated tests."""
    if DB.exists():
        DB.unlink()


def grace_inside_epoch(state: dict | None = None) -> int:
    """Return a clock inside the rotation grace window."""
    state = state or rotation_state()
    return int(state["rotated_at"] + 100)


def grace_end_epoch(state: dict | None = None) -> int:
    """Return the final second inside the grace window."""
    state = state or rotation_state()
    return int(state["rotated_at"] + state["grace_seconds"])


def grace_outside_epoch(state: dict | None = None) -> int:
    """Return a clock one second after grace expires."""
    return grace_end_epoch(state) + 1


def expected_revoked_at(epoch: int | None = None) -> str:
    """Return RFC3339 UTC timestamp for the service clock."""
    from datetime import datetime, timezone

    base = epoch if epoch is not None else clock_epoch()
    return datetime.fromtimestamp(base, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def expected_audit_lines(jtis: list[str]) -> list[str]:
    """Build expected JSONL audit lines from contract offsets."""
    state = rotation_state()
    epoch = clock_epoch()
    from datetime import datetime, timezone

    def ts(offset: int) -> str:
        return datetime.fromtimestamp(epoch + offset, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    events = [
        {
            "event_seq": 1,
            "event_type": "key_promoted",
            "kid": state["active_kid"],
            "ts": ts(0),
        },
        {
            "event_seq": 2,
            "event_type": "key_retired",
            "kid": state["retiring_kid"],
            "ts": ts(10),
        },
    ]
    for i, jti in enumerate(sorted(jtis)):
        events.append(
            {
                "event_seq": 100 + i,
                "event_type": "token_revoked",
                "jti": jti,
                "ts": ts(20 + i),
            }
        )
    events.sort(key=lambda e: e["event_seq"])
    return [json.dumps(e, separators=(",", ":")) for e in events]
