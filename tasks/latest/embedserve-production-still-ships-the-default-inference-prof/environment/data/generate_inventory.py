"""Bootstrap the EmbedServe inventory SQLite database."""
from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path("/app/environment")
DB = Path("/app/data/embedserve_inventory.db")


def main() -> None:
    DB.parent.mkdir(parents=True, exist_ok=True)
    if DB.exists():
        DB.unlink()
    conn = sqlite3.connect(DB)
    try:
        conn.executescript((ROOT / "sql/schema.sql").read_text(encoding="utf-8"))
        conn.executescript((ROOT / "sql/seed_inventory.sql").read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()
    print(f"initialized {DB}")


if __name__ == "__main__":
    main()
