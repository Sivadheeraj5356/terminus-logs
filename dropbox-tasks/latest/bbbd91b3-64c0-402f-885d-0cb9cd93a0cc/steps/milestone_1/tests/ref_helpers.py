"""Independent reference adjudicator for k9 trace contract."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

ENV = Path("/app/environment")
FIX = ENV / "fixtures"


def _start_grid() -> list[int]:
    grid = [ord(" ")] * 64
    back = b"rnbqkbnr"
    for i in range(8):
        grid[i] = back[i] - 32
        grid[56 + i] = back[i]
    for i in range(8):
        grid[8 + i] = ord("P")
        grid[48 + i] = ord("p")
    return grid


def _placement_hash(cells: list[int]) -> int:
    h = 0xCBF29CE484222325
    for c in cells:
        h ^= c
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def _rights_mask(rights: list[bool]) -> int:
    m = 0
    for i, b in enumerate(rights):
        if b:
            m |= 1 << i
    return m


def _apply_uci(
    grid: list[int], side_white: bool, rights: list[bool], ep: int | None, mv: str
) -> tuple[bool, int | None, bool, int]:
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
    if pr == ord("p"):
        if abs(r1 - r0) == 2:
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


def _irreversible(mv: str, captured: bool, from_piece: int) -> bool:
    if captured:
        return True
    if (from_piece | 0x20) == ord("p"):
        return True
    # A king move from the e-file to the g- or c-file is a castle.
    # Castle moves are irreversible because the resulting position can never
    # repeat with the original castling rights.
    if len(mv) == 4 and mv[0] == "e" and mv[2] in "gc":
        return True
    return False


def _full_key(grid: list[int], side_white: bool, rights: list[bool], ep: int | None) -> tuple:
    ph = _placement_hash(grid)
    side = 1 if side_white else 2
    rm = _rights_mask(rights)
    epv = ep if ep is not None else 64
    return (ph, side, rm, epv)


def fn_load(name: str) -> list[str]:
    lines = (FIX / name).read_text().splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def fn_trace(moves: list[str]) -> list[tuple]:
    grid = _start_grid()
    side_white = True
    rights = [True, True, True, True]
    ep: int | None = None
    counts: Counter = Counter()
    rows: list[tuple] = []
    for ply, mv in enumerate(moves, 1):
        f0, r0 = ord(mv[0]) - ord("a"), int(mv[1]) - 1
        from_piece = grid[r0 * 8 + f0]
        side_white, ep, captured, _ = _apply_uci(grid, side_white, rights, ep, mv)
        if _irreversible(mv, captured, from_piece):
            counts = Counter()
        key = _full_key(grid, side_white, rights, ep)
        counts[key] += 1
        code = "H" if counts[key] >= 3 else "N"
        digest = ref_digest(grid, side_white, rights, ep)
        rows.append((ply, code, _rights_mask(rights), ep if ep is not None else 64, f"{digest:016x}"))
    return rows


def ref_digest(grid_cells: list[int], side_white: bool, rights: list[bool], ep: int | None) -> int:
    h = _placement_hash(grid_cells)
    h ^= 1 if side_white else 2
    h ^= _rights_mask(rights) << 8
    if ep is not None:
        h ^= (ep + 1) << 16
    return h & 0xFFFFFFFFFFFFFFFF
