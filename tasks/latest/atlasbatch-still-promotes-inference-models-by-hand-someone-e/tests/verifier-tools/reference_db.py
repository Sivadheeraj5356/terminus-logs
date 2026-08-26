"""Reference database queries for promotion decisions."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path("/app/data/eval.db")


def load_candidate(db_path: Path, candidate_id: str) -> dict | None:
  """Return candidate row as dict or None if missing."""
  conn = sqlite3.connect(db_path)
  conn.row_factory = sqlite3.Row
  try:
    row = conn.execute(
      "SELECT * FROM candidates WHERE candidate_id = ?",
      (candidate_id,),
    ).fetchone()
    if row is None:
      return None
    return dict(row)
  finally:
    conn.close()
