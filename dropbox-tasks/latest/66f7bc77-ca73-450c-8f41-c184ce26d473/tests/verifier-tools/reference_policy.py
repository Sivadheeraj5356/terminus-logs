"""Reference policy parsing for latency ceiling precedence."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

DEFAULT_CEILING_MS = 45.0
WAIVER_DIR = Path("/app/archives/comms")
EVAL_CLOCK = Path("/app/config/eval-clock.toml")
EVAL_WINDOW_DAYS = 14


def _eval_as_of() -> date:
  text = EVAL_CLOCK.read_text()
  match = re.search(r'as_of_date\s*=\s*"(\d{4}-\d{2}-\d{2})"', text)
  if match is None:
    raise ValueError("as_of_date not found in eval clock config")
  return date.fromisoformat(match.group(1))


def _waiver_files() -> list[Path]:
  return sorted(WAIVER_DIR.glob("latency-waiver-*.eml"))


def _waiver_revert_date(content: str) -> date | None:
  match = re.search(r"Revert after (\d{4}-\d{2}-\d{2})", content)
  if match is None:
    return None
  return date.fromisoformat(match.group(1))


def _waiver_ceiling(content: str) -> float | None:
  match = re.search(r"ceiling from 45 ms to \*\*(\d+(?:\.\d+)?) ms\*\*", content)
  if match is None:
    return None
  return float(match.group(1))


def _batch_mentioned_in_waiver(batch_id: str, content: str) -> bool:
  escaped = re.escape(batch_id)
  return re.search(rf"(?<![\w-]){escaped}(?![\w-])", content) is not None


def waiver_active(batch_id: str) -> bool:
  """Return whether a batch-specific latency waiver is in effect."""
  as_of = _eval_as_of()
  for path in _waiver_files():
    text = path.read_text()
    if not _batch_mentioned_in_waiver(batch_id, text):
      continue
    revert = _waiver_revert_date(text)
    if revert is not None and as_of < revert:
      return True
  return False


def latency_ceiling_ms(batch_id: str) -> float:
  """Return effective p99 latency ceiling for a batch."""
  as_of = _eval_as_of()
  best = DEFAULT_CEILING_MS
  for path in _waiver_files():
    text = path.read_text()
    if not _batch_mentioned_in_waiver(batch_id, text):
      continue
    revert = _waiver_revert_date(text)
    if revert is None or as_of >= revert:
      continue
    ceiling = _waiver_ceiling(text)
    if ceiling is not None:
      best = max(best, ceiling)
  return best


def eval_is_fresh(eval_completed_at: str) -> bool:
  """Return whether the evaluation date is within the active window."""
  as_of = _eval_as_of()
  completed = date.fromisoformat(eval_completed_at)
  earliest = date.fromordinal(as_of.toordinal() - EVAL_WINDOW_DAYS)
  return completed >= earliest
