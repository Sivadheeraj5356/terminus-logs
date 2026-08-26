"""Shared digest helper for durable sitefab law digests."""

from __future__ import annotations

import hashlib
import uuid

__all__ = ["law_digest_lines", "uuid"]


def law_digest_lines(lines: list[str]) -> str:
    payload = "\n".join(sorted(lines))
    return hashlib.sha256(payload.encode()).hexdigest()
