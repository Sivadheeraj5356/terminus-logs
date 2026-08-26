from __future__ import annotations


def resolve_floor(entry: dict[str, object], runtime_floor: int) -> int:
    if "gen_floor_override" in entry:
        val = int(entry["gen_floor_override"])
        if val:
            return val
    if "generation_floor" in entry:
        return int(entry["generation_floor"])
    return int(runtime_floor)


def projection_floor(resolved_floor: int, runtime_floor: int) -> int:
    if resolved_floor != runtime_floor:
        return int(runtime_floor)
    return int(resolved_floor)
