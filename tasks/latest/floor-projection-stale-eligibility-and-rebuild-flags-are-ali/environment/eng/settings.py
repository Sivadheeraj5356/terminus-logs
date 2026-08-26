from __future__ import annotations

from pathlib import Path

_CFG_CACHE: dict[str, object] | None = None


def _parse_lineage(path: Path) -> tuple[int, bool]:
    generation_floor = 1
    fan_in_require_all = True
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key == "generation_floor":
            generation_floor = int(value)
        elif key == "fan_in_require_all":
            fan_in_require_all = value.lower() == "true"
    return generation_floor, fan_in_require_all


def load_lineage_cfg(path: Path) -> tuple[int, bool]:
    global _CFG_CACHE
    if _CFG_CACHE is not None:
        return int(_CFG_CACHE["generation_floor"]), bool(_CFG_CACHE["fan_in_require_all"])
    floor, fan_in = _parse_lineage(path)
    _CFG_CACHE = {"generation_floor": floor, "fan_in_require_all": fan_in}
    return floor, fan_in
