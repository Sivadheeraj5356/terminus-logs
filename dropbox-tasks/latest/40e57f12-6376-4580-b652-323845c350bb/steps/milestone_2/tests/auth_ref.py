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


def sign_token(kid: str, jti: str) -> str:
    """Sign an EdDSA JWT with the private key for kid."""
    pem_path = KEYS_DIR / f"{kid}.pem"
    private_key = load_pem_private_key(pem_path.read_bytes(), password=None)
    return jwt.encode(
        {"jti": jti, "sub": "client"},
        private_key,
        algorithm="EdDSA",
        headers={"kid": kid},
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


def revoke(jti: str, reason: str = "test", epoch: int | None = None) -> None:
    """Revoke a token jti via tokensvc."""
    proc = run_tokensvc(["revoke", jti, reason], epoch=epoch)
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


def expected_revoked_at(epoch: int | None = None) -> str:
    """Return RFC3339 UTC timestamp for the service clock."""
    from datetime import datetime, timezone

    base = epoch if epoch is not None else clock_epoch()
    return datetime.fromtimestamp(base, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
