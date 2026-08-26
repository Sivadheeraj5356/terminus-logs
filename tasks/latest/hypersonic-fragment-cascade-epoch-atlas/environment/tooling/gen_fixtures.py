#!/usr/bin/env python3
"""Generate bundled and hidden fixture catalogs for the cascade simulator."""

import json
import math
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def write_catalog(catalog_dir, manifest, bodies, flares):
    os.makedirs(catalog_dir, exist_ok=True)
    with open(os.path.join(catalog_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    with open(os.path.join(catalog_dir, "bodies.jsonl"), "w") as f:
        for b in bodies:
            f.write(json.dumps(b) + "\n")
    with open(os.path.join(catalog_dir, "flares.jsonl"), "w") as f:
        for fl in flares:
            f.write(json.dumps(fl) + "\n")


LEO_ALPHA_MANIFEST = {
    "mission_slot": "LEO-ALPHA-7",
    "dt_sec": 0.05,
    "horizon_sec": 5.0,
    "fragment_count": 4,
    "min_sep_m": 10.0,
}

R = 6371000 + 400000
v_circ = math.sqrt(3.986004418e14 / R)

LEO_ALPHA_BODIES = [
    {
        "id": "SAT-A",
        "mass_kg": 500.0,
        "radius_m": 2.0,
        "pos_m": {"x": R, "y": 0.0, "z": 0.0},
        "vel_mps": {"x": 0.0, "y": v_circ, "z": 0.0},
        "cd": 2.2,
    },
    {
        "id": "DEB-B",
        "mass_kg": 50.0,
        "radius_m": 1.0,
        "pos_m": {"x": R + 0.5, "y": 0.0, "z": 0.0},
        "vel_mps": {"x": -5.0, "y": v_circ, "z": 0.0},
        "cd": 2.5,
    },
    {
        "id": "DEB-C",
        "mass_kg": 80.0,
        "radius_m": 0.8,
        "pos_m": {"x": R + 500.0, "y": 800.0, "z": 50.0},
        "vel_mps": {"x": -5.0, "y": v_circ * 0.98, "z": 2.0},
        "cd": 2.2,
    },
]

LEO_ALPHA_FLARES = [
    {"t_sec": 25.0, "density_scale": 3.0},
]

LEO_BRAVO_MANIFEST = {
    "mission_slot": "LEO-BRAVO-2",
    "dt_sec": 0.05,
    "horizon_sec": 4.0,
    "fragment_count": 4,
    "min_sep_m": 5.0,
}

LEO_BRAVO_BODIES = [
    {
        "id": "OBJ-X",
        "mass_kg": 300.0,
        "radius_m": 1.5,
        "pos_m": {"x": R, "y": 0.0, "z": 0.0},
        "vel_mps": {"x": 0.0, "y": v_circ, "z": 0.0},
        "cd": 2.2,
    },
    {
        "id": "OBJ-Y",
        "mass_kg": 100.0,
        "radius_m": 1.2,
        "pos_m": {"x": R + 0.4, "y": 0.0, "z": 0.0},
        "vel_mps": {"x": -4.0, "y": v_circ, "z": 0.0},
        "cd": 1.8,
    },
]

LEO_BRAVO_FLARES = [
    {"t_sec": 10.0, "density_scale": 2.0},
    {"t_sec": 20.0, "density_scale": 5.0},
]


FLARE_TRAP_MANIFEST = {
    "mission_slot": "FLARE-TRAP-1",
    "dt_sec": 0.05,
    "horizon_sec": 5.0,
    "fragment_count": 4,
    "min_sep_m": 8.0,
}

FLARE_TRAP_BODIES = [
    {
        "id": "HI-A",
        "mass_kg": 400.0,
        "radius_m": 1.8,
        "pos_m": {"x": R, "y": 0.0, "z": 0.0},
        "vel_mps": {"x": 0.0, "y": v_circ, "z": 0.0},
        "cd": 2.2,
    },
    {
        "id": "HI-B",
        "mass_kg": 60.0,
        "radius_m": 1.0,
        "pos_m": {"x": R + 0.6, "y": 0.0, "z": 0.0},
        "vel_mps": {"x": -3.0, "y": v_circ, "z": 0.0},
        "cd": 3.0,
    },
]

FLARE_TRAP_FLARES = [
    {"t_sec": 5.0, "density_scale": 8.0},
    {"t_sec": 15.0, "density_scale": 0.5},
    {"t_sec": 30.0, "density_scale": 12.0},
]


CHAIN_MANIFEST = {
    "mission_slot": "CHAIN-RXN-1",
    "dt_sec": 0.05,
    "horizon_sec": 6.0,
    "fragment_count": 3,
    "min_sep_m": 5.0,
}

CHAIN_BODIES = [
    {
        "id": "P1",
        "mass_kg": 200.0,
        "radius_m": 1.5,
        "pos_m": {"x": R, "y": 0.0, "z": 0.0},
        "vel_mps": {"x": 0.0, "y": v_circ, "z": 0.0},
        "cd": 2.2,
    },
    {
        "id": "P2",
        "mass_kg": 150.0,
        "radius_m": 1.2,
        "pos_m": {"x": R + 0.5, "y": 0.0, "z": 0.0},
        "vel_mps": {"x": -2.0, "y": v_circ, "z": 0.0},
        "cd": 2.2,
    },
    {
        "id": "P3",
        "mass_kg": 100.0,
        "radius_m": 1.0,
        "pos_m": {"x": R + 1.8, "y": 0.0, "z": 0.0},
        "vel_mps": {"x": -1.0, "y": v_circ, "z": 0.0},
        "cd": 2.4,
    },
]

CHAIN_FLARES = [
    {"t_sec": 8.0, "density_scale": 4.0},
]


write_catalog(os.path.join(BASE, "catalogs", "leo-alpha"),
              LEO_ALPHA_MANIFEST, LEO_ALPHA_BODIES, LEO_ALPHA_FLARES)
write_catalog(os.path.join(BASE, "catalogs", "leo-bravo"),
              LEO_BRAVO_MANIFEST, LEO_BRAVO_BODIES, LEO_BRAVO_FLARES)

opt = os.path.join(BASE, "opt-fixtures")
write_catalog(os.path.join(opt, "flare-trap"),
              FLARE_TRAP_MANIFEST, FLARE_TRAP_BODIES, FLARE_TRAP_FLARES)
write_catalog(os.path.join(opt, "chain-reaction"),
              CHAIN_MANIFEST, CHAIN_BODIES, CHAIN_FLARES)

print("Fixtures generated.")
