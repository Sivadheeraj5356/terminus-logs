"""Reparse published yard evidence and receipt closure."""
from __future__ import annotations

from pathlib import Path


STATE_MEMBERS = [
    "generation",
    "accepted.order",
    "effective.units",
    "enablement.state",
    "transaction.jobs",
    "boot.trace",
    "change.account",
    "reconcile.receipt",
]


def state_dir(yard: Path) -> Path:
    return yard / "var/lib/unitgraph"


def assert_state_closed(yard: Path) -> None:
    d = state_dir(yard)
    assert d.is_dir()
    names = sorted(p.name for p in d.iterdir())
    assert names == sorted(STATE_MEMBERS)
    receipt = (d / "reconcile.receipt").read_text().strip()
    assert len(receipt) == 64
    assert all(c in "0123456789abcdef" for c in receipt)


def receipt_of(yard: Path) -> str:
    return (state_dir(yard) / "reconcile.receipt").read_text().strip()
