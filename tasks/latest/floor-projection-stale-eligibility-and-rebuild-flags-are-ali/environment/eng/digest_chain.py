from __future__ import annotations

import hashlib
import json


def chain_nodes(rows: list[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(json.dumps(row, sort_keys=True).encode("utf-8"))
    return digest.hexdigest()
