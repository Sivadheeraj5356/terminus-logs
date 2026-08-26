from __future__ import annotations

from pathlib import Path

OUTPUT = Path("/app/output/lineage_frontier.json")

DIGEST_ROW_KEYS = ("node", "hash", "gen", "seq")
# Digest body row order follows reverse of forward_topo on stale nodes.
