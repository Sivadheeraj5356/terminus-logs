"""Verifier-only row reference derived from fixture bytes (not solver-visible)."""

from __future__ import annotations

import json
from pathlib import Path

PUBLIC_SEQ = Path("/app/cases/seq")
NORMAL = 0


def _parse_kv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        for item in line.split():
            if "=" in item:
                key, value = item.split("=", 1)
                out[key] = value
    return out


def _scan_sectors(n: int, tail: int, rank_a: int, rank_b: int, epoch: int) -> list[int]:
    if n == 0:
        return [0]
    if n == 3:
        return [0, max(tail, 512)]
    if n == 2:
        return [0, 64, rank_a]
    if n == 1 and rank_b > epoch:
        return [0, 64, rank_b]
    return [0, 64]


def expected_rows(n: int, seq_root: Path = PUBLIC_SEQ, ledger_root: Path | None = None) -> list[dict]:
    root = seq_root / f"s{n}"
    ledger_path = (ledger_root or seq_root) / f"s{n}" / "b0.evt"
    xfer = _parse_kv(root / "a0.evt")
    ledger = _parse_kv(ledger_path)
    res = _parse_kv(root / "p0.res")
    source = str(xfer.get("source", "na"))
    target = str(xfer.get("target", "na"))
    anchor = int(ledger.get("anchor", "0"))
    settle = int(ledger.get("settle", "0"))
    tail = int(res.get("tail", "0"))
    rank_a = int(res.get("rank_a", "0"))
    rank_b = int(res.get("rank_b", "0"))
    epoch = int(res.get("epoch", "0"))
    rows: list[dict] = [
        {
            "scenario": n,
            "phase": "sr5",
            "target": source,
            "marker": "done",
            "sequence": settle + 2,
            "epoch": NORMAL,
        },
        {
            "scenario": n,
            "phase": "sk8",
            "target": source,
            "marker": "clean",
            "sequence": settle + 1,
            "epoch": NORMAL,
        },
        {
            "scenario": n,
            "phase": "fp3",
            "target": source,
            "marker": "release",
            "sequence": anchor,
            "epoch": NORMAL,
        },
    ]
    for sec in _scan_sectors(n, tail, rank_a, rank_b, epoch):
        rows.append(
            {
                "scenario": n,
                "phase": "xr4",
                "target": target,
                "marker": f"sample_{sec}",
                "sequence": settle + sec + 1,
                "epoch": NORMAL,
            }
        )
    return rows


def sort_rows(rows: list[dict]) -> list[dict]:
    phase_order = {"sk8": 0, "fp3": 1, "sr5": 2, "xr4": 3}
    return sorted(
        rows,
        key=lambda r: (
            r["scenario"],
            phase_order.get(r["phase"], 9),
            r["target"],
            r["marker"],
            r["sequence"],
        ),
    )


def full_rows(ledger_overlays: dict[int, Path] | None = None) -> list[dict]:
    overlays = ledger_overlays or {}
    rows: list[dict] = []
    for n in range(4):
        rows.extend(expected_rows(n, PUBLIC_SEQ, overlays.get(n)))
    return sort_rows(rows)


def full_rows_multi(overlay_indices: list[int]) -> list[dict]:
    overlays = {n: HIDDEN for n in overlay_indices}
    return full_rows(overlays)


if __name__ == "__main__":
    import sys

    HIDDEN = Path("/tests/hidden/seq")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "epoch":
        n = int(sys.argv[2])
        overlay = int(sys.argv[3]) if len(sys.argv) > 3 else None
        ledger_root = HIDDEN if overlay == n else None
        print(json.dumps(sort_rows(expected_rows(n, PUBLIC_SEQ, ledger_root)), sort_keys=True))
    elif cmd == "full":
        overlay = int(sys.argv[2]) if len(sys.argv) > 2 else None
        overlays = {overlay: HIDDEN} if overlay is not None else None
        print(json.dumps(full_rows(overlays), sort_keys=True))
    elif cmd == "full_multi":
        indices = [int(x) for x in sys.argv[2:]]
        print(json.dumps(full_rows_multi(indices), sort_keys=True))
    else:
        raise SystemExit("usage: row_canon.py epoch N [overlay_n] | full [overlay_n] | full_multi i [j ...]")
