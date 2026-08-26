#!/usr/bin/env python3
"""Build-time fixture generator for the labyrinth oracle.

This script writes the bundled labyrinth world (/app/data/worlds/labyrinth
and /app/docs/gm-chronicle.md) and the hidden catacombs world
(/opt/verifier-fixtures/worlds/catacombs) that the Go binary and the
verifier's pytest suite read at runtime. It runs once during the Docker
image build and is deleted immediately afterward: it is not part of the
shipped agent environment and the Go binary never imports it.

Exits, actions, and items are intentionally written to each world.json in
descending ID order so that a reader relying on on-disk order (instead of
sorting by ID) observes a different order than the ascending contract in
/app/docs/world-schema.md requires.
"""

from __future__ import annotations

import json
import os
from typing import Any


def _reverse_by_id(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: row["id"], reverse=True)


def build_world_json(
    world_id: str,
    start_room: str,
    rooms: list[dict[str, Any]],
    exits: list[dict[str, Any]],
    items: list[dict[str, Any]],
    actions: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "world_id": world_id,
        "start_room": start_room,
        "rooms": rooms,
        "exits": _reverse_by_id(exits),
        "items": _reverse_by_id(items),
        "actions": _reverse_by_id(actions),
    }


def build_chronicle(title: str, sections: list[str], rules: list[str]) -> str:
    """Assemble a long game-master chronicle with @RULE forbidden lines
    interspersed between narrative paragraphs, matching the format in
    /app/docs/rules-format.md.
    """
    parts = [f"# {title}", ""]
    for idx, section in enumerate(sections):
        parts.append(section)
        parts.append("")
        if idx < len(rules):
            parts.append(rules[idx])
            parts.append("")
    for extra_rule in rules[len(sections):]:
        parts.append(extra_rule)
        parts.append("")
    return "\n".join(parts)


LABYRINTH_ROOMS = [
    {"id": "atrium", "title": "The Sunken Atrium"},
    {"id": "gallery", "title": "The Whispering Gallery"},
    {"id": "vault", "title": "The Sealed Vault"},
    {"id": "crossing", "title": "The Bone Crossing"},
    {"id": "sanctum", "title": "The Ember Sanctum"},
]

LABYRINTH_EXITS = [
    {"id": "ex1", "from": "atrium", "to": "gallery", "verb": "go-gallery", "required_items": []},
    {"id": "ex2", "from": "gallery", "to": "vault", "verb": "go-vault", "required_items": ["brass-key"]},
    {"id": "ex3", "from": "gallery", "to": "crossing", "verb": "go-crossing", "required_items": []},
    {"id": "ex4", "from": "crossing", "to": "sanctum", "verb": "go-sanctum", "required_items": ["silver-key", "lantern"]},
    {"id": "ex5", "from": "vault", "to": "atrium", "verb": "go-atrium", "required_items": []},
]

LABYRINTH_ITEMS = [
    {"id": "lantern", "room_id": "atrium"},
    {"id": "torch", "room_id": "gallery"},
    {"id": "brass-key", "room_id": "crossing"},
    {"id": "silver-key", "room_id": "vault"},
]

LABYRINTH_ACTIONS = [
    {"id": "ac1", "room_id": "atrium", "verb": "read", "target": "plaque", "required_items": []},
    {"id": "ac2", "room_id": "gallery", "verb": "search", "target": "urn", "required_items": ["torch"]},
    {"id": "ac3", "room_id": "vault", "verb": "pry", "target": "seal", "required_items": ["brass-key"]},
    {"id": "ac4", "room_id": "sanctum", "verb": "light", "target": "brazier", "required_items": ["lantern"]},
]

LABYRINTH_RULES = [
    "@RULE forbidden room=gallery verb=search target=urn",
    "@RULE forbidden room=vault verb=go-atrium target=atrium",
]

LABYRINTH_LORE = [
    (
        "The Sunken Atrium once welcomed pilgrims through a skylight long since "
        "caved in. Runoff from the upper galleries has pooled here for "
        "generations, and the plaque bolted to the east wall still names the "
        "masons who raised the first labyrinth ring."
    ),
    (
        "Beyond the atrium, the Whispering Gallery earns its name from a "
        "cracked vault seal that lets every footstep echo twice. An old "
        "funerary urn stands near the north arch, its lid already broken by "
        "an expedition that catalogued the gallery decades before this survey."
    ),
    (
        "The Sealed Vault beyond the gallery was built as a one-way descent: "
        "warders bricked the return stair after the last inventory was taken, "
        "so the only path back to the atrium is the narrow service exit."
    ),
    (
        "Past the Bone Crossing, the Ember Sanctum still holds a brazier that "
        "has not been lit since the labyrinth was decommissioned. Wardens "
        "insist a lantern must be carried the whole way to keep the crossing "
        "lit; nothing about the sanctum's brazier concerns the crossing "
        "itself."
    ),
]


CATACOMBS_ROOMS = [
    {"id": "entry", "title": "The Collapsed Entry"},
    {"id": "ossuary", "title": "The Ossuary Row"},
    {"id": "cistern", "title": "The Flooded Cistern"},
    {"id": "reliquary", "title": "The Reliquary"},
    {"id": "abyss", "title": "The Lightless Abyss"},
]

CATACOMBS_EXITS = [
    {"id": "ex1", "from": "entry", "to": "ossuary", "verb": "go-ossuary", "required_items": []},
    {"id": "ex2", "from": "ossuary", "to": "cistern", "verb": "go-cistern", "required_items": ["iron-hook"]},
    {"id": "ex3", "from": "ossuary", "to": "reliquary", "verb": "go-reliquary", "required_items": []},
    {"id": "ex4", "from": "reliquary", "to": "abyss", "verb": "go-abyss", "required_items": ["bone-whistle", "iron-hook"]},
    {"id": "ex5", "from": "cistern", "to": "ossuary", "verb": "go-ossuary-back", "required_items": []},
]

CATACOMBS_ITEMS = [
    {"id": "tallow-candle", "room_id": "entry"},
    {"id": "iron-hook", "room_id": "ossuary"},
    {"id": "rope-coil", "room_id": "cistern"},
    {"id": "bone-whistle", "room_id": "reliquary"},
]

CATACOMBS_ACTIONS = [
    {"id": "ac1", "room_id": "entry", "verb": "read", "target": "inscription", "required_items": []},
    {"id": "ac2", "room_id": "ossuary", "verb": "search", "target": "niche", "required_items": ["tallow-candle"]},
    {"id": "ac3", "room_id": "cistern", "verb": "drain", "target": "sluice", "required_items": ["rope-coil"]},
    {"id": "ac4", "room_id": "reliquary", "verb": "ring", "target": "whistle", "required_items": ["bone-whistle"]},
]

CATACOMBS_RULES = [
    "@RULE forbidden room=cistern verb=drain target=sluice",
    "@RULE forbidden room=ossuary verb=search target=niche",
]

CATACOMBS_LORE = [
    (
        "The Collapsed Entry marks where the old catacomb survey team lost "
        "their first ladder. An inscription carved into the lintel lists the "
        "names of the diggers who mapped the ossuary row beyond it."
    ),
    (
        "The Ossuary Row holds shelf after shelf of sealed niches. One niche "
        "near the south wall was already emptied by the survey team before "
        "this chronicle was written, and nothing worth recording remains in "
        "it."
    ),
    (
        "The Flooded Cistern sits below the ossuary and floods further every "
        "season. A sluice gate could drain it, but draining the cistern also "
        "floods the ossuary's lower shelves, so the warders forbid opening it "
        "under any circumstance."
    ),
    (
        "The Reliquary beyond the ossuary still holds a bone whistle said to "
        "open the sealed door into the Lightless Abyss, but only when carried "
        "alongside the ossuary's iron hook. Neither item alone has ever "
        "opened that door."
    ),
]


def write_world(root: str, world_id: str, start_room, rooms, exits, items, actions) -> None:
    payload = build_world_json(world_id, start_room, rooms, exits, items, actions)
    world_dir = os.path.join(root, world_id)
    os.makedirs(world_dir, exist_ok=True)
    with open(os.path.join(world_dir, "world.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=False)
        fh.write("\n")


def main() -> None:
    bundled_root = "/app/data/worlds"
    hidden_root = "/opt/verifier-fixtures/worlds"

    write_world(
        bundled_root,
        "labyrinth",
        "atrium",
        LABYRINTH_ROOMS,
        LABYRINTH_EXITS,
        LABYRINTH_ITEMS,
        LABYRINTH_ACTIONS,
    )
    chronicle_text = build_chronicle(
        "The Labyrinth Warden's Chronicle", LABYRINTH_LORE, LABYRINTH_RULES
    )
    os.makedirs("/app/docs", exist_ok=True)
    with open("/app/docs/gm-chronicle.md", "w", encoding="utf-8") as fh:
        fh.write(chronicle_text)

    write_world(
        hidden_root,
        "catacombs",
        "entry",
        CATACOMBS_ROOMS,
        CATACOMBS_EXITS,
        CATACOMBS_ITEMS,
        CATACOMBS_ACTIONS,
    )
    catacombs_chronicle = build_chronicle(
        "The Catacombs Warden's Chronicle", CATACOMBS_LORE, CATACOMBS_RULES
    )
    with open(os.path.join(hidden_root, "catacombs", "chronicle.md"), "w", encoding="utf-8") as fh:
        fh.write(catacombs_chronicle)


if __name__ == "__main__":
    main()
