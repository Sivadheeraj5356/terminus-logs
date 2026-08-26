"""Independent reference implementation for the labyrinth oracle contract.

This module re-implements world loading, chronicle rule parsing, hint
gathering, and attestation digests directly from the documented contract
under /app/docs, without importing or shelling out to the Go service under
test. It reads only plain JSON and markdown files; there is no database of
any kind involved.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

RULE_PATTERN = re.compile(r"^@RULE forbidden room=(\S+) verb=(\S+) target=(\S+)\s*$")

BUNDLED_WORLDS_ROOT = Path("/app/data/worlds")
HIDDEN_WORLDS_ROOT = Path("/opt/verifier-fixtures/worlds")
BUNDLED_CHRONICLE_PATH = Path("/app/docs/gm-chronicle.md")

KIND_RANK = {"move": 0, "action": 1, "take": 2}


def load_world(world_id: str) -> dict[str, Any]:
    for root in (BUNDLED_WORLDS_ROOT, HIDDEN_WORLDS_ROOT):
        path = root / world_id / "world.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"no world.json for world_id={world_id}")


def chronicle_path_for(world_id: str) -> Path:
    if world_id in ("", "labyrinth"):
        return BUNDLED_CHRONICLE_PATH
    return HIDDEN_WORLDS_ROOT / world_id / "chronicle.md"


def load_forbidden_rules(world_id: str) -> list[tuple[str, str, str]]:
    text = chronicle_path_for(world_id).read_text(encoding="utf-8")
    rules: list[tuple[str, str, str]] = []
    for line in text.splitlines():
        m = RULE_PATTERN.match(line)
        if m:
            rules.append((m.group(1), m.group(2), m.group(3)))
    return rules


def is_forbidden(rules: list[tuple[str, str, str]], room: str, verb: str, target: str) -> bool:
    return (room, verb, target) in rules


def exits_ascending(world: dict[str, Any], room: str) -> list[dict[str, Any]]:
    rows = [e for e in world["exits"] if e["from"] == room]
    return sorted(rows, key=lambda e: e["id"])


def actions_ascending(world: dict[str, Any], room: str) -> list[dict[str, Any]]:
    rows = [a for a in world["actions"] if a["room_id"] == room]
    return sorted(rows, key=lambda a: a["id"])


def items_ascending(world: dict[str, Any], room: str) -> list[dict[str, Any]]:
    rows = [i for i in world["items"] if i["room_id"] == room]
    return sorted(rows, key=lambda i: i["id"])


def gather_candidates(world: dict[str, Any], room: str) -> list[dict[str, Any]]:
    """Reproduce the probe stage's raw candidate gather: exits, then
    actions, then items, each ascending by id, numbered by order_seq
    starting at 1.
    """
    out: list[dict[str, Any]] = []
    seq = 1
    for e in exits_ascending(world, room):
        out.append(
            {
                "kind": "move",
                "verb": e["verb"],
                "target": e["to"],
                "required_items": list(e["required_items"]),
                "order_seq": seq,
            }
        )
        seq += 1
    for a in actions_ascending(world, room):
        out.append(
            {
                "kind": "action",
                "verb": a["verb"],
                "target": a["target"],
                "required_items": list(a["required_items"]),
                "order_seq": seq,
            }
        )
        seq += 1
    for it in items_ascending(world, room):
        out.append(
            {
                "kind": "take",
                "verb": "take",
                "target": it["id"],
                "required_items": [],
                "order_seq": seq,
            }
        )
        seq += 1
    return out


def inventory_ok(required: list[str], inventory: list[str]) -> bool:
    return set(required).issubset(set(inventory))


def expected_hints(
    world: dict[str, Any],
    room: str,
    inventory: list[str],
    consumed: list[str],
    forbidden: list[tuple[str, str, str]],
) -> list[dict[str, str]]:
    """Reproduce the assemble stage's filter and sort over a fresh gather:
    every required item held, target not already consumed or taken, and
    no chronicle forbidden rule matching room/verb/target.
    """
    hints: list[dict[str, str]] = []
    for c in gather_candidates(world, room):
        if not inventory_ok(c["required_items"], inventory):
            continue
        if c["kind"] == "take":
            if c["target"] in inventory:
                continue
        else:
            if c["target"] in consumed:
                continue
        if is_forbidden(forbidden, room, c["verb"], c["target"]):
            continue
        hints.append({"kind": c["kind"], "verb": c["verb"], "target": c["target"]})

    hints.sort(key=lambda h: (KIND_RANK.get(h["kind"], 99), h["verb"], h["target"]))
    return hints


def chronicle_digest(world_id: str) -> str:
    raw = chronicle_path_for(world_id).read_bytes()
    return hashlib.sha256(raw).hexdigest()


def session_state_digest(
    world_id: str,
    room: str,
    inventory: list[str],
    consumed: list[str],
    failed: list[tuple[str, str]],
) -> str:
    payload = {
        "world_id": world_id,
        "room": room,
        "inventory": sorted(inventory),
        "consumed": sorted(consumed),
        "failed": [
            {"verb": v, "target": t}
            for v, t in sorted(failed, key=lambda pair: (pair[0], pair[1]))
        ],
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def candidate_digest(candidates: list[dict[str, Any]]) -> str:
    raw = json.dumps(candidates, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def route_digest(hints: list[dict[str, str]]) -> str:
    lines = [f"{h['kind']}:{h['verb']}:{h['target']}" for h in hints]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def abort_digest(session_id: str, gather_seq: int, reason: str) -> str:
    body = f"{session_id}:{gather_seq}:{reason}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
