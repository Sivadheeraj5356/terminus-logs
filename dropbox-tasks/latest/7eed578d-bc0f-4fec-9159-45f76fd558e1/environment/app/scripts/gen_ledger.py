#!/usr/bin/env python3
"""Generate signed card-ledger CSV with OpenSSL HMAC chain."""
from __future__ import annotations

import csv
import hashlib
import hmac
from pathlib import Path

BATCH_ID = "BATCH-001"
SECRET = b"ledger-hmac-key-v1-ops"
OUTPUT = Path(__file__).resolve().parent.parent / "data" / "ledger" / "batch_001.csv"

ROWS = [
    # pan_hash, amount_cents, merchant_code, country
    ("a1b2c3d4e5f6", 12500, "M104", "US"),
    ("a1b2c3d4e5f6", 8900, "M221", "US"),
    ("f6e5d4c3b2a1", 450000, "M887", "NG"),
    ("f6e5d4c3b2a1", 120000, "M102", "US"),
    ("9f8e7d6c5b4a", 3200, "M033", "CA"),
    ("9f8e7d6c5b4a", 5100, "M044", "CA"),
    ("9f8e7d6c5b4a", 7800, "M055", "US"),
    ("deadbeefcafe", 990000, "M999", "RU"),
    ("cafebabef00d", 1500, "M010", "US"),
    ("cafebabef00d", 2200, "M011", "US"),
]


def chain_hmac(payload: str, prev: str) -> str:
    material = f"{prev}|{payload}".encode()
    return hmac.new(SECRET, material, hashlib.sha256).hexdigest()


def genesis_hmac() -> str:
    return hmac.new(SECRET, f"GENESIS|{BATCH_ID}".encode(), hashlib.sha256).hexdigest()


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    prev = genesis_hmac()
    out_rows: list[dict[str, str | int]] = []

    out_rows.append(
        {
            "batch_id": BATCH_ID,
            "sequence": 0,
            "pan_hash": "GENESIS",
            "amount_cents": 0,
            "merchant_code": "0000",
            "country": "XX",
            "hmac": prev,
        }
    )

    for seq, (pan, amount, merchant, country) in enumerate(ROWS, start=1):
        payload = f"{pan}|{amount}|{merchant}|{country}"
        digest = chain_hmac(payload, prev)
        out_rows.append(
            {
                "batch_id": BATCH_ID,
                "sequence": seq,
                "pan_hash": pan,
                "amount_cents": amount,
                "merchant_code": merchant,
                "country": country,
                "hmac": digest,
            }
        )
        prev = digest

    fieldnames = [
        "batch_id",
        "sequence",
        "pan_hash",
        "amount_cents",
        "merchant_code",
        "country",
        "hmac",
    ]
    with OUTPUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print(f"Wrote {len(out_rows)} rows to {OUTPUT}")


if __name__ == "__main__":
    main()
