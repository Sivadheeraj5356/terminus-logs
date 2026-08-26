from __future__ import annotations

import hashlib
import json

from .constants import DIGEST_ROW_KEYS
from .dag import reverse_topo


def frontier_digest_hex(
    stale_inputs: list[str],
    latest: dict[str, dict[str, object]],
    graph: dict[str, object] | None = None,
) -> str:
    if graph is None:
        order = sorted(stale_inputs)
    else:
        order = reverse_topo(stale_inputs, graph)
    lines: list[str] = []
    for node in order:
        if node not in latest:
            continue
        event = latest[node]
        payload = {key: event[key] for key in DIGEST_ROW_KEYS}
        lines.append(json.dumps(payload, separators=(",", ":"), sort_keys=True))
    body = "\n".join(lines)
    if lines:
        body = body + "\n"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
