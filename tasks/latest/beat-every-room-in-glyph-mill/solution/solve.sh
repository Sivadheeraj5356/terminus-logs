#!/bin/bash
set -euo pipefail
mkdir -p /app/recovered
cat > /app/recovered/glyph_tool.py <<'PYTOOL'

#!/usr/bin/env python3
import argparse, json, re, subprocess, sys, tomllib
from pathlib import Path
import lmdb, yaml

TOOL = "/usr/local/bin/glyph-mill"

def read_rooms(root: Path):
    env = lmdb.open(str(root / "hints.lmdb"), readonly=True, lock=False, max_dbs=1)
    out = {}
    with env.begin() as txn:
        ids = json.loads(txn.get(b"rooms").decode())
        for room in ids:
            out[room] = json.loads(txn.get(f"room:{room}".encode()).decode())
    env.close()
    return out

def trace_room(root: Path, room: str):
    # Ask the runtime to resolve this room and emit a fresh, nonce-tagged
    # syscall trace of exactly which rule files it opened. The overlay a room
    # loads is decided by logic inside the (now non-importable) runtime, and
    # the grading user has no privilege to attach a debugger or inspect the
    # daemon's file descriptors, so this runtime-provided trace is the only
    # genuine evidence available - a statically-computed guess carries no
    # valid nonce and is rejected.
    proc = subprocess.run(
        [TOOL, "--root", str(root), "trace", room], text=True, capture_output=True, timeout=30
    )
    if proc.returncode != 0:
        raise SystemExit(f"trace failed for {room}: {proc.stderr}")
    raw_lines = [line for line in proc.stdout.splitlines() if line.strip()]
    # Only count files the runtime actually opened successfully (trailing
    # "= <fd>"); a rejected candidate lookup ("= -1 ENOENT ...") shows up in
    # the same trace but never contributed to this room's rules.
    paths = sorted(
        {
            m.group(1)
            for line in raw_lines
            if re.search(r"=\s*\d+\b", line)
            for m in [re.search(r'"([^"]+\.(?:yaml|toml))"', line)]
            if m
        }
    )
    lines = [line for line in raw_lines if any(Path(p).name in line for p in paths)]
    return paths, lines

def discovery(root: Path):
    rooms = read_rooms(root)
    entries = []
    for room_id in sorted(rooms):
        room = rooms[room_id]
        files, excerpt = trace_room(root, room_id)
        entries.append({
            "room": room_id,
            "title": room["title"],
            "lmdb_key": f"room:{room_id}",
            "glyphs": list(room["glyphs"]),
            "max_moves": int(room["max_moves"]),
            "loaded_files": files,
            "trace_excerpt": excerpt,
        })
    return {"schema_version": 1, "rooms": entries}

def load_rulebook(root: Path):
    rooms = read_rooms(root)
    core = yaml.safe_load((root / "rules" / "core.yaml").read_text())
    disc = {r["room"]: r for r in discovery(root)["rooms"]}
    out_rooms = []
    for room_id in sorted(rooms):
        room = rooms[room_id]
        palette = yaml.safe_load((root / "rules" / "palettes" / f"{room['palette']}.yaml").read_text())
        with (root / "rules" / "packs" / f"{room['pack']}.toml").open("rb") as f:
            pack = tomllib.load(f)
        loaded = disc[room_id]["loaded_files"]
        # The overlay is whichever runtime-loaded file lives under rules/overlays;
        # it is discovered from trace evidence, never guessed from the layout.
        overlay_file = next(p for p in loaded if Path(p).parent.name == "overlays")
        overlay = yaml.safe_load(Path(overlay_file).read_text())
        pivot = pack["walk"]["pivot"]
        # A room's own hint record can override the pack's stride.
        stride = int(room["stride_override"]) if "stride_override" in room else int(pack["walk"]["stride"])
        out_rooms.append({
            "room": room_id,
            "title": room["title"],
            "start": int(room["start"]),
            "target": int(room["target"]),
            "beacons": {str(k): int(v) for k, v in room.get("beacons", {}).items()},
            "salt": int(room["salt"]),
            "palette": room["palette"],
            "pack": room["pack"],
            "glyphs": list(room["glyphs"]),
            "glyph_values": {k: int(v) for k, v in sorted(palette["symbols"].items())},
            "mask": int(palette["mask"]),
            "max_moves": int(room["max_moves"]),
            "cycle": list(pack["walk"]["cycle"]),
            "stride": stride,
            "pivot": pivot,
            "turn_bias": int(core["turns"][pivot]),
            "overlay": Path(overlay_file).stem,
            "mask_shift": int(overlay["mask_shift"]),
            "rotation": int(overlay["rotation"]),
            "loaded_files": loaded,
        })
    return {"schema_version": 1, "grid": {"width": int(core["grid"]["width"]), "height": int(core["grid"]["height"]), "directions": core["directions"]}, "rooms": out_rooms}

def solve_room(grid, room):
    width, height = grid["width"], grid["height"]
    dirs = grid["directions"]
    cycle = room["cycle"]

    def step(state, glyph, index, prev):
        prev_term = room["turn_bias"] if prev is None else prev
        dindex = (room["glyph_values"][glyph] + room["mask"] + room["mask_shift"]
                  + room["salt"] + state + index * room["stride"]
                  + room["turn_bias"] + prev_term * room["rotation"]) % len(cycle)
        dx, dy = dirs[cycle[dindex]]
        x, y = state % width, state // width
        return ((y + dy) % height) * width + ((x + dx) % width), dindex

    # Layered BFS over (position, previous cycle index): the walk formula is
    # Markovian in that pair, so exact-length routes are found in
    # O(max_moves * cells * |cycle| * |glyphs|) instead of |glyphs|^max_moves.
    # Beacon constraints prune each affected layer to the required cell.
    beacons = {int(k): v for k, v in room.get("beacons", {}).items()}
    layers = [{(room["start"], None): None}]
    for i in range(room["max_moves"]):
        nxt = {}
        for (state, prev) in layers[-1]:
            for glyph in room["glyphs"]:
                key = step(state, glyph, i, prev)
                if key not in nxt:
                    nxt[key] = ((state, prev), glyph)
        if (i + 1) in beacons:
            nxt = {k: v for k, v in nxt.items() if k[0] == beacons[i + 1]}
        layers.append(nxt)
    final = next((k for k in layers[-1] if k[0] == room["target"]), None)
    if final is None:
        raise SystemExit(f"no route for {room['room']}")
    seq = []
    key = final
    for i in range(room["max_moves"], 0, -1):
        parent, glyph = layers[i][key]
        seq.append(glyph)
        key = parent
    seq.reverse()
    return seq

def solve_route(root: Path):
    rb = load_rulebook(root)
    route = []
    for room in rb["rooms"]:
        route.append({"room": room["room"], "glyphs": solve_room(rb["grid"], room)})
    return {"schema_version": 1, "rooms": route}

def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n")

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ["discover", "normalize", "solve"]:
        sp = sub.add_parser(name)
        sp.add_argument("--root", required=True)
        sp.add_argument("--out", required=True)
    args = p.parse_args()
    root = Path(args.root).resolve()
    if args.cmd == "discover":
        data = discovery(root)
    elif args.cmd == "normalize":
        data = load_rulebook(root)
    else:
        data = solve_route(root)
    write_json(args.out, data)
if __name__ == "__main__":
    main()

PYTOOL
chmod +x /app/recovered/glyph_tool.py
python /app/recovered/glyph_tool.py discover --root /app/glyph-mill --out /app/recovered/discovery.json
python /app/recovered/glyph_tool.py normalize --root /app/glyph-mill --out /app/recovered/rulebook.json
python /app/recovered/glyph_tool.py solve --root /app/glyph-mill --out /app/recovered/winning_route.json
glyph-mill --root /app/glyph-mill replay /app/recovered/winning_route.json
