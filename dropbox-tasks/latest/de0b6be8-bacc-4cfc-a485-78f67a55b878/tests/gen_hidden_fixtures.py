#!/usr/bin/env python3
"""Generate verifier-only observation profiles."""

import json
import pathlib

ROOT = pathlib.Path("/opt/verifier-fixtures")


def write(name, rows):
    d = ROOT / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "observations.jsonl").write_text(
        "".join(json.dumps(x, separators=(",", ":")) + "\n" for x in rows)
    )


def base(
    i,
    src,
    contractor,
    malware,
    beacon,
    actor,
    start,
    end,
    tool="euv-7",
    rel=9000,
):
    return {
        "id": i,
        "indicator": i,
        "source": src,
        "contractor": contractor,
        "malware": malware,
        "beacon": beacon,
        "toolcell": tool,
        "actor": actor,
        "start": start,
        "end": end,
        "reliability_bp": rel,
    }


write(
    "alias-window",
    [
        base(
            "hid-a",
            "hidden-one",
            "ZEphyr Field",
            "lumenrat",
            "h-1",
            "actor-red",
            220,
            240,
        ),
        base(
            "hid-b",
            "hidden-two",
            "Zephyr Optics",
            "lumenrat",
            "h-2",
            "actor-red",
            240,
            260,
        ),
    ],
)
write(
    "veto-objective",
    [
        base(
            "hid-c",
            "hidden-three",
            "Omega",
            "dustkit",
            "shared-cloud",
            "actor-green",
            300,
            340,
        ),
        base(
            "hid-d",
            "hidden-four",
            "Omega",
            "dustkit",
            "shared-cloud",
            "actor-violet",
            310,
            350,
        ),
        base(
            "hid-e",
            "hidden-five",
            "Omega",
            "dustkit",
            "private-9",
            "actor-green",
            340,
            370,
        ),
    ],
)
