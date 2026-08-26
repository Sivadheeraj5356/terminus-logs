"""Path normalization helpers."""

from __future__ import annotations


def normalize_rel_path(prefix: str, path: str) -> str:
    joined = path.lstrip("/")
    if prefix:
        joined = f"{prefix.rstrip('/')}/{path.lstrip('/')}"
    parts: list[str] = []
    for part in joined.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)
