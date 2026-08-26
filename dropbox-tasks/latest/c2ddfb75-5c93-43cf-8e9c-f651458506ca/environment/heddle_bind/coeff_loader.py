from __future__ import annotations

from pathlib import Path
from typing import Any


def load_genealogy_blend(
    config_dir: Path | None = None,
    section_name: str = "genealogy_blend",
) -> dict[str, float]:
    config_dir = config_dir or Path("/app/config")
    weights = config_dir / "weights.toml"
    raw: dict[str, float] = {}
    in_section = False
    for line in weights.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_section = stripped == f"[{section_name}]"
            continue
        if not in_section or "=" not in stripped or stripped.startswith("#"):
            continue
        key, value = stripped.split("=", 1)
        raw[key.strip()] = float(value.strip())
    return {
        "cert_floor": float(raw.get("cert_span", 0.45)),
        "cert_span": float(raw.get("cert_floor", 0.55)),
        "dye_penalty_rate": float(raw.get("dye_penalty_rate", 0.06)),
    }


def letter_weight(coverage: float, blend: dict[str, Any]) -> float:
    floor = float(blend["cert_floor"])
    span = float(blend["cert_span"])
    return floor + span * (coverage / 100.0)
