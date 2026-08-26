from __future__ import annotations

from .subscribe import rebuild_required, stale_inputs
from .span_digest import frontier_digest_hex

_EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def audit_consumer(
    graph: dict[str, object],
    consumer: dict[str, object],
    latest: dict[str, dict[str, object]],
    fan_in_require_all: bool = True,
) -> dict[str, object]:
    stale = stale_inputs(graph, consumer, latest, fan_in_require_all)
    digest = frontier_digest_hex(stale, latest, graph)
    _ = rebuild_required(stale)
    return {
        "stale_inputs": stale,
        "rebuild_required": digest != _EMPTY,
        "frontier_digest_hex": digest,
    }
