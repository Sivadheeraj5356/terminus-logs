#!/usr/bin/env python3
"""Independent reference simulation for fog-of-war schema_version 3."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ENV = Path("/app/environment")
CASES = ENV / "cases" / "g2"


def sha16(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()[:16]


def sha_full(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def load_mode(mode: str) -> dict:
    path = ENV / "specs_r" / f"{mode}.toml"
    spec = {
        "mode": mode,
        "resident_cap": 8192,
        "decay_modulus": 4,
        "decay_phase": 0,
        "tick_scale": 10,
        "cell_bytes": 64,
        "fade_start": 6,
        "group_header_bytes": 32,
        "observer_metadata_bytes": 16,
    }
    for line in path.read_text().splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"')
        if k in spec and k != "mode":
            if k == "fade_start":
                spec[k] = int(v)
            else:
                spec[k] = int(v)
    return spec


def discover_case_ids(suite: str = "g2") -> list[str]:
    d = ENV / "cases" / suite
    ids = sorted(p.stem for p in d.glob("*.json"))
    return ids or ["c1"]


def load_scenario(case_id: str) -> dict:
    return json.loads((CASES / f"{case_id}.json").read_text())


def lit_mask(reach: int, cx: int, cy: int, slots: int, grid_width: int) -> list[int]:
    width = max(grid_width, 1)
    out = [0] * slots
    for i in range(slots):
        dx = abs((i % width) - cx)
        dy = abs((i // width) - cy)
        if dx + dy <= reach:
            out[i] = 1
    return out


def phases_valid(scenario: dict) -> bool:
    phases = scenario.get("observer_phases") or []
    if not phases:
        return True
    boundaries = sorted(p["until_tick"] for p in phases)
    for a, b in zip(boundaries, boundaries[1:]):
        if b <= a:
            return False
    return True


def active_observers(scenario: dict, tick: int) -> list[dict]:
    phases = scenario.get("observer_phases") or []
    if not phases:
        return scenario["observers"]
    if not phases_valid(scenario):
        return []
    ordered = sorted(phases, key=lambda p: p["until_tick"])
    for phase in ordered:
        if tick < phase["until_tick"]:
            return phase["observers"]
    return ordered[-1]["observers"]


def pack_a(
    explored: list[int], lit: list[int], fixed_pack: bool = True
) -> tuple[list[int], list[int]]:
    if not fixed_pack:
        return list(lit), list(lit)
    out = list(explored)
    for i, src in enumerate(explored):
        if src:
            out[i] = 1
    for i, src in enumerate(lit):
        if src:
            out[i] = 1
    return out, list(lit)


def tick_b(
    fade: list[int],
    tick_ix: int,
    modulus: int,
    phase: int,
    fixed_tick: bool = True,
    every_tick: bool = False,
) -> list[int]:
    if every_tick or not fixed_tick:
        if modulus == 0:
            return list(fade)
        return [max(0, c - 1) for c in fade]
    if modulus == 0:
        return list(fade)
    if tick_ix % modulus == phase % modulus:
        return [max(0, c - 1) for c in fade]
    return list(fade)


def canonicalize(group: list[int]) -> list[int]:
    return sorted(set(group))


def merge_pool(
    pool: dict,
    group: list[int],
    fixed_merge: bool = True,
) -> tuple[int, dict]:
    if not fixed_merge:
        copies = len(group)
        pool["bytes_used"] = pool["slots"] * pool["cell_bytes"] + len(group) * 16
        for oid in group:
            pool["handles"][oid] = group[0]
        return copies, {"group": list(group), "handle": group[0], "copies": copies}

    canon = canonicalize(group)
    handle = canon[0]
    key = tuple(canon)
    if key not in pool["allocated_groups"]:
        pool["allocated_groups"][key] = handle
        for oid in canon:
            pool["handles"][oid] = handle
        distinct = len(pool["allocated_groups"])
        total_memberships = sum(len(g) for g in pool["allocated_groups"])
        pool["bytes_used"] = (
            pool["slots"] * pool["cell_bytes"]
            + distinct * pool["group_header_bytes"]
            + total_memberships * pool["observer_metadata_bytes"]
        )
    return 1, {"group": canon, "handle": handle, "copies": 1}


def simulate(
    scenario: dict,
    ticks: int,
    fixed_pack: bool = True,
    fixed_tick: bool = True,
    fixed_merge: bool = True,
    fixed_geometry: bool = True,
    fixed_phases: bool = True,
    fixed_cadence_marker: bool = True,
    every_tick_decay: bool = False,
) -> dict:
    mode = load_mode(scenario["mode"])
    slots = scenario["slots"]
    width = scenario.get("grid_width") or 4
    if not fixed_geometry:
        width = 4
    explored = [0] * slots
    lit = [0] * slots
    sensor = [0] * slots
    fade = [mode["fade_start"]] * slots
    resident = slots * mode["cell_bytes"] * 2
    peak = resident
    lineage: list[dict] = []
    decay_trace: list[int] = []
    cadence_trace: list[str] = []
    resident_trace: list[str] = []
    plane_trace: list[str] = []
    cadence_trace_v3: list[str] = []
    pool_trace: list[str] = []

    pool = {
        "handles": {},
        "allocated_groups": {},
        "bytes_used": resident,
        "cell_bytes": mode["cell_bytes"],
        "slots": slots,
        "group_header_bytes": mode["group_header_bytes"],
        "observer_metadata_bytes": mode["observer_metadata_bytes"],
    }

    for tick in range(ticks):
        lit = [0] * slots
        sensor = [0] * slots
        if fixed_phases:
            observers = active_observers(scenario, tick)
        else:
            phases = scenario.get("observer_phases") or []
            if not phases:
                observers = scenario["observers"]
            else:
                observers = scenario["observers"]
                for phase in phases:
                    if tick <= phase["until_tick"]:
                        observers = phase["observers"]
                        break
                else:
                    observers = phases[-1]["observers"]

        for obs in observers:
            mask = lit_mask(obs["reach"], obs["cx"], obs["cy"], slots, width)
            lit = [a | b for a, b in zip(lit, mask)]
            sensor = [a | b for a, b in zip(sensor, mask)]

        for i in range(slots):
            if lit[i]:
                explored[i] = 1
                fade[i] = mode["fade_start"]

        frozen = [v > 0 for v in sensor]
        if fixed_cadence_marker and fixed_tick and not every_tick_decay:
            step = (
                1
                if mode["decay_modulus"]
                and tick % mode["decay_modulus"] == mode["decay_phase"] % mode["decay_modulus"]
                else 0
            )
        elif every_tick_decay or not fixed_tick:
            step = 1 if mode["decay_modulus"] else 0
        else:
            step = 1 if mode["decay_modulus"] and tick % mode["decay_modulus"] == 0 else 0

        fade = tick_b(
            fade,
            tick,
            mode["decay_modulus"],
            mode["decay_phase"],
            fixed_tick=fixed_tick,
            every_tick=every_tick_decay,
        )
        for i in range(slots):
            if frozen[i]:
                fade[i] = mode["fade_start"]
        for i in range(slots):
            if explored[i] and not sensor[i]:
                lit[i] = 1 if fade[i] > 0 else 0
        explored, lit = pack_a(explored, lit, fixed_pack=fixed_pack)

        for gid, group in enumerate(scenario.get("ally_groups") or []):
            copies, row = merge_pool(pool, group, fixed_merge=fixed_merge)
            if not any(r["group"] == row["group"] for r in lineage):
                lineage.append(row)
            obs_s = ",".join(str(x) for x in row["group"])
            pool_trace.append(
                f"group:{gid}:observers:{obs_s}:handle:{row['handle']}:copies:{copies}:bytes:{pool['bytes_used']}"
            )

        peak = max(peak, pool["bytes_used"])
        counter_sum = sum(fade)
        explored_count = sum(1 for b in explored if b)
        sensor_count = sum(1 for b in sensor if b)
        stale_count = max(0, explored_count - sensor_count)

        decay_trace.append(counter_sum)
        c = f"tick:{tick}:step:{step}:sum:{counter_sum}"
        cadence_trace.append(c)
        resident_trace.append(f"tick:{tick}:bytes:{pool['bytes_used']}")
        plane_trace.append(
            f"tick:{tick}:sensor:{sensor_count}:explored:{explored_count}:stale:{stale_count}"
        )
        cadence_trace_v3.append(f"tick:{tick}:decay:{step}:fade_checksum:{sha16(c)}")

    plane_a = bytes(explored)
    plane_b = bytes(sensor)
    explored_count = sum(1 for b in explored if b)
    sensor_count = sum(1 for b in sensor if b)
    stale_count = max(0, explored_count - sensor_count)

    cadence_tail = cadence_trace[-12:]
    resident_tail = resident_trace[-12:]
    fade_cs = sha16("|".join(cadence_tail))

    delta_rows = [
        f"idx:{i}:a:{explored[i]}:b:{sensor[i]}"
        for i in range(slots)
        if explored[i] != sensor[i]
    ]
    plane_delta = sha16("|".join(delta_rows) if delta_rows else "delta:none")

    if lineage:
        rows = sorted(
            [
                f"group:{','.join(str(x) for x in row['group'])}:handle:{row['handle']}:copies:{row['copies']}"
                for row in lineage
            ]
        )
        pool_dig = sha16(";".join(rows))
    else:
        pool_dig = sha16("pool:none")

    band = "WITHIN" if peak <= mode["resident_cap"] else "OVER"

    return {
        "peak_bytes": peak,
        "footprint_band": band,
        "plane_a": sha16(plane_a),
        "plane_b": sha16(plane_b),
        "lineage": lineage,
        "decay_trace": decay_trace[-8:],
        "cadence_trace": cadence_tail,
        "resident_trace": resident_tail,
        "explored_count": explored_count,
        "sensor_count": sensor_count,
        "stale_count": stale_count,
        "fade_checksum": fade_cs,
        "observer_pool_digest": pool_dig,
        "plane_delta_digest": plane_delta,
        "plane_trace": plane_trace,
        "cadence_trace_v3": cadence_trace_v3,
        "pool_trace": pool_trace,
    }


def source_digest(suite: str = "g2") -> str:
    rows = []
    for path in sorted((ENV / "cases" / suite).glob("*.json")):
        stem = path.stem
        rel = f"cases/{suite}/{stem}.json"
        rows.append(f"{stem}:{rel}:{sha16(path.read_bytes())}")
    return sha16("|".join(rows))


def scenario_digest(suite: str = "g2") -> str:
    rows = []
    for path in sorted((ENV / "cases" / suite).glob("*.json")):
        rows.append(f"cases/{suite}/{path.name}|{sha_full(path.read_bytes())}")
    for path in sorted((ENV / "specs_r").glob("*.toml")):
        rows.append(f"specs_r/{path.name}|{sha_full(path.read_bytes())}")
    return sha16("|".join(rows))


def run_digest(run: dict) -> str:
    payload = "|".join(
        [
            run["scenario_id"],
            run["footprint_band"],
            str(run["peak_bytes"]),
            run["bitplane_digests"]["plane_a"],
            run["bitplane_digests"]["plane_b"],
            str(run["explored_count"]),
            str(run["sensor_count"]),
            str(run["stale_count"]),
            run["fade_checksum"],
            run["observer_pool_digest"],
            run["plane_delta_digest"],
            ",".join(run["cadence_trace"]),
            ",".join(run["resident_trace"]),
            str(run["recovery_epoch"]),
        ]
    )
    return sha_full(payload)


def run_v3_digest(run: dict) -> str:
    payload = "|".join(
        [
            run["scenario_id"],
            run["run_digest"],
            ";".join(run["plane_trace"]),
            ";".join(run["cadence_trace_v3"]),
            ";".join(run["pool_trace"]),
            ";".join(run["source_refs"]),
        ]
    )
    return sha16(payload)


def ledger_digest(doc: dict) -> str:
    pairs = sorted(f"{r['scenario_id']}:{r['run_digest']}" for r in doc["runs"])
    body = (
        ";".join(pairs)
        + f"|orchestrator:{','.join(doc['orchestrator_phases'])}"
        + f"|worker:{','.join(doc['worker_phases'])}"
        + f"|plane:{doc['plane_trace_digest']}"
        + f"|cadence:{doc['cadence_digest']}"
        + f"|pool:{doc['pool_trace_digest']}"
        + f"|scenario:{doc['scenario_digest']}"
    )
    return sha_full(body)


def ledger_digest_legacy(doc: dict) -> str:
    pairs = sorted(f"{r['scenario_id']}:{r['run_digest']}" for r in doc["runs"])
    body = (
        ";".join(pairs)
        + f"|orchestrator:{','.join(doc['orchestrator_phases'])}"
        + f"|worker:{','.join(doc['worker_phases'])}"
    )
    return sha_full(body)


def phase_digest(orchestrator: list[str], worker: list[str]) -> str:
    return sha16(f"orchestrator:{','.join(orchestrator)}|worker:{','.join(worker)}")


def trace_digest(doc: dict, field: str) -> str:
    rows = []
    for run in doc["runs"]:
        rows.append(f"{run['scenario_id']}|{sha16(';'.join(run[field]))}")
    rows.sort()
    return sha16("|".join(rows))
