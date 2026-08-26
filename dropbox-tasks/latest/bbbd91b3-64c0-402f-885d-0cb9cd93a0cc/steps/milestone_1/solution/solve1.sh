#!/bin/bash
set -euo pipefail
APP=/app
ENV="${APP}/environment"
OUT="${APP}/output"
mkdir -p "${OUT}"

bash "${ENV}/scripts/build_q7m.sh"

python3 - <<'PY'
import json
import subprocess
from collections import Counter
from pathlib import Path

APP = Path("/app")
ENV = APP / "environment"
OUT = APP / "output"
FIX = ENV / "fixtures"
FIXTURES = ["seq_r4.pgn", "seq_u8.pgn"]


def _start_grid():
    grid = [ord(" ")] * 64
    back = b"rnbqkbnr"
    for i in range(8):
        grid[i] = back[i] - 32
        grid[56 + i] = back[i]
    for i in range(8):
        grid[8 + i] = ord("P")
        grid[48 + i] = ord("p")
    return grid


def _placement_hash(cells):
    h = 0xCBF29CE484222325
    for c in cells:
        h ^= c
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def _rights_mask(rights):
    m = 0
    for i, b in enumerate(rights):
        if b:
            m |= 1 << i
    return m


def _apply_uci(grid, side_white, rights, ep, mv):
    f0, r0, f1, r1 = (
        ord(mv[0]) - ord("a"),
        int(mv[1]) - 1,
        ord(mv[2]) - ord("a"),
        int(mv[3]) - 1,
    )
    from_sq = r0 * 8 + f0
    to_sq = r1 * 8 + f1
    piece = grid[from_sq]
    captured = grid[to_sq] != ord(" ")
    grid[to_sq] = piece
    grid[from_sq] = ord(" ")
    ep = None
    pr = piece | 0x20
    if pr == ord("p") and abs(r1 - r0) == 2:
        ep = r0 * 8 + f0
    if pr == ord("k"):
        if side_white:
            rights[0] = rights[1] = False
        else:
            rights[2] = rights[3] = False
    if pr == ord("r"):
        if side_white:
            if from_sq == 0:
                rights[1] = False
            if from_sq == 7:
                rights[0] = False
        else:
            if from_sq == 56:
                rights[3] = False
            if from_sq == 63:
                rights[2] = False
    side_white = not side_white
    return side_white, ep, captured, piece


def _irreversible(mv, captured, from_piece):
    if captured:
        return True
    if (from_piece | 0x20) == ord("p"):
        return True
    if len(mv) == 4 and mv[0] == "e" and mv[2] in "gc":
        return True
    return False


def _full_key(grid, side_white, rights, ep):
    ph = _placement_hash(grid)
    side = 1 if side_white else 2
    rm = _rights_mask(rights)
    epv = ep if ep is not None else 64
    return (ph, side, rm, epv)


def load_moves(name):
    lines = (FIX / name).read_text().splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def ref_trace(moves):
    grid = _start_grid()
    side_white = True
    rights = [True, True, True, True]
    ep = None
    counts = Counter()
    rows = []
    for ply, mv in enumerate(moves, 1):
        f0, r0 = ord(mv[0]) - ord("a"), int(mv[1]) - 1
        from_piece = grid[r0 * 8 + f0]
        side_white, ep, captured, _ = _apply_uci(grid, side_white, rights, ep, mv)
        if _irreversible(mv, captured, from_piece):
            counts = Counter()
        key = _full_key(grid, side_white, rights, ep)
        counts[key] += 1
        code = "H" if counts[key] >= 3 else "N"
        rows.append((ply, code))
    return rows


def run_seq(name, out):
    script = f"/app/environment/fixtures/{name}"
    subprocess.run(
        [
            "/app/environment/bin/q7m",
            "run-seq",
            "--script",
            script,
            "--out",
            str(out),
        ],
        check=True,
    )
    return [json.loads(line) for line in out.read_text().splitlines()]


mismatches = []
for fx in FIXTURES:
    trace = OUT / f"m1_{fx}.jsonl"
    ref = ref_trace(load_moves(fx))
    eng = run_seq(fx, trace)
    for r, e in zip(ref, eng):
        if r[1] != e["outcome_code"]:
            mismatches.append(
                {
                    "fixture": fx,
                    "ply": r[0],
                    "engine": e["outcome_code"],
                    "reference": r[1],
                }
            )

doc = {
    "schema": "k9-mismatch-v1",
    "fixtures": FIXTURES,
    "mismatches": mismatches,
}
(OUT / "m1_mismatch_report.json").write_text(json.dumps(doc, indent=2) + "\n")
PY
