"""Settlement CSV reader for the production reconciliation CLI."""

from __future__ import annotations

import csv
from pathlib import Path

from lib.report_schema import INPUT_FIELDS, normalize_amount, parse_radix


def read_settlements(path: Path) -> list[dict[str, str | int]]:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != INPUT_FIELDS:
            raise ValueError(f"unexpected settlement header: {reader.fieldnames!r}")
        rows: list[dict[str, str | int]] = []
        for row in reader:
            rows.append(
                {
                    "settlement_id": row["settlement_id"],
                    "amount_decimal": normalize_amount(row["amount_decimal"]),
                    "radix_base": parse_radix(row["radix_base"]),
                }
            )
    return rows
