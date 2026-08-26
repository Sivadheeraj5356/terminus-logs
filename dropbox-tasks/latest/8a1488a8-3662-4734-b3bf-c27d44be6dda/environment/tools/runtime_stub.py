from __future__ import annotations

import tomllib
from pathlib import Path

"""Runtime reload scaffold — semantics live in /app/doc/merge_contract.txt."""


def read_default_list_mode(path: Path = Path("/app/cfg/runtime.toml")) -> str:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    runtime = data.get("runtime", data)
    return str(runtime.get("default_list_mode", "replace"))
