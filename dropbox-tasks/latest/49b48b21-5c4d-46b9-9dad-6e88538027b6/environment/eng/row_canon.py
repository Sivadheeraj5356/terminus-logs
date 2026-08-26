from __future__ import annotations

import hashlib
import json

from .constants import DIGEST_ROW_KEYS


def frontier_digest_hex(
    stale_inputs: list[str],
    latest: dict[str, dict[str, object]],
    graph: dict[str, object] | None = None,
) -> str:
    _ = graph
    order = list(stale_inputs)
    lines: list[str] = []
    for node in order:
        if node not in latest:
            continue
        event = latest[node]
        payload = {key: event[key] for key in DIGEST_ROW_KEYS}
        lines.append(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    body = "\n".join(lines)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
