"""Independent reference for CipherGrid puzzle-league digests and move scoring."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path


def round_half_away(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def format_fixed2(value: float) -> str:
    return f"{round_half_away(value):.2f}"


@dataclass
class Glyph:
    glyph_id: str
    weight: float
    family: str


@dataclass
class Cell:
    cell_id: str
    x: int
    y: int
    neighbors: list[str]


@dataclass
class Move:
    player_id: str
    cell_id: str
    tick: int


@dataclass
class Archive:
    root: str
    cells: list[Cell]
    solution: dict[str, str]
    glyphs: dict[str, Glyph]
    moves: list[Move]


@dataclass
class PlayerScore:
    player_id: str
    points: float
    moves: int
    combo_points: float = 0.0
    rivalry_points: float = 0.0


@dataclass
class LayoutNode:
    name: str
    x: float
    y: float


CHAIN_TIP_PATH = Path("/app/var/match_chain_tip.txt")


def load_archive(root: str | Path) -> Archive:
    root = Path(root)
    cells_doc = json.loads((root / "cells.json").read_text())
    cells = [
        Cell(
            cell_id=c["id"],
            x=c["x"],
            y=c["y"],
            neighbors=list(c["neighbors"]),
        )
        for c in cells_doc["cells"]
    ]
    solution = dict(cells_doc["solution"])

    glyphs: dict[str, Glyph] = {}
    current: str | None = None
    weight = 0.0
    family = ""
    for raw in (root / "glyphs.toml").read_text().splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            if current is not None:
                glyphs[current] = Glyph(current, weight, family)
            current = line[1:-1]
            weight = 0.0
            family = ""
            continue
        if line.startswith("weight"):
            weight = float(line.split("=", 1)[1].strip())
        elif line.startswith("family"):
            val = line.split("=", 1)[1].strip()
            family = val.strip('"')
    if current is not None:
        glyphs[current] = Glyph(current, weight, family)

    moves: list[Move] = []
    for raw in (root / "moves.jsonl").read_text().splitlines():
        line = raw.strip()
        if not line:
            continue
        row = json.loads(line)
        moves.append(
            Move(
                player_id=row["player_id"],
                cell_id=row["cell_id"],
                tick=row["tick"],
            )
        )

    return Archive(str(root), cells, solution, glyphs, moves)


def cell_by_id(archive: Archive, cell_id: str) -> Cell:
    for cell in archive.cells:
        if cell.cell_id == cell_id:
            return cell
    raise KeyError(cell_id)


def cell_family(archive: Archive, cell_id: str) -> str:
    glyph_id = archive.solution[cell_id]
    return archive.glyphs[glyph_id].family


def cells_share_family(archive: Archive, a: str, b: str) -> bool:
    return cell_family(archive, a) == cell_family(archive, b)


def neighbor_family_matches(archive: Archive, cell_id: str) -> int:
    played_family = cell_family(archive, cell_id)
    cell = cell_by_id(archive, cell_id)
    count = 0
    for nb in cell.neighbors:
        if cell_family(archive, nb) == played_family:
            count += 1
    return count


def cells_are_neighbors(archive: Archive, a: str, b: str) -> bool:
    return b in cell_by_id(archive, a).neighbors


def unplayed_same_family_count(
    archive: Archive, family: str, prior_move_count: int
) -> int:
    played = {m.cell_id for m in archive.moves[:prior_move_count]}
    count = 0
    for cell in archive.cells:
        if cell_family(archive, cell.cell_id) != family:
            continue
        if cell.cell_id in played:
            continue
        count += 1
    return count


def pressure_factor(archive: Archive, cell_id: str, prior_move_count: int) -> float:
    fam = cell_family(archive, cell_id)
    remaining = unplayed_same_family_count(archive, fam, prior_move_count)
    return 1.0 + 0.05 * remaining


def base_move_points(archive: Archive, cell_id: str) -> float:
    glyph_id = archive.solution[cell_id]
    weight = archive.glyphs[glyph_id].weight
    matches = neighbor_family_matches(archive, cell_id)
    return round_half_away(weight + matches * 2.0)


def move_points(archive: Archive, cell_id: str, move_index: int = 0) -> float:
    base = base_move_points(archive, cell_id)
    factor = pressure_factor(archive, cell_id, move_index)
    return round_half_away(base * factor)


def fold_scores(archive: Archive) -> tuple[list[PlayerScore], str]:
    totals: dict[str, list[float | int]] = {}
    for idx, move in enumerate(archive.moves):
        pts = move_points(archive, move.cell_id, idx)
        bucket = totals.setdefault(move.player_id, [0.0, 0])
        bucket[0] = float(bucket[0]) + pts
        bucket[1] = int(bucket[1]) + 1

    players: list[PlayerScore] = []
    lines: list[str] = []
    for player_id in sorted(totals):
        total = round_half_away(float(totals[player_id][0]))
        move_count = int(totals[player_id][1])
        players.append(PlayerScore(player_id, total, move_count, 0.0, 0.0))
        lines.append(f"{player_id}|{format_fixed2(total)}|{move_count}")

    digest = hashlib.sha256("\n".join(lines).encode()).hexdigest()
    return players, digest


def fold_combo(archive: Archive) -> tuple[dict[str, tuple[float, int]], str]:
    by_player: dict[str, list[Move]] = {}
    for move in archive.moves:
        by_player.setdefault(move.player_id, []).append(move)

    combo_map: dict[str, tuple[float, int]] = {}
    lines: list[str] = []
    for player_id in sorted(by_player):
        moves = sorted(by_player[player_id], key=lambda m: (m.tick, m.cell_id))
        raw = 0.0
        streak = 0
        max_streak = 0
        prev_family: str | None = None
        for move in moves:
            fam = cell_family(archive, move.cell_id)
            if prev_family is not None and prev_family == fam:
                streak += 1
                raw += 0.25 * (streak - 1)
            else:
                streak = 1
            prev_family = fam
            max_streak = max(max_streak, streak)
        combo_points = round_half_away(raw)
        combo_map[player_id] = (combo_points, max_streak)
        lines.append(f"{player_id}|{format_fixed2(combo_points)}|{max_streak}")

    digest = hashlib.sha256("\n".join(lines).encode()).hexdigest()
    return combo_map, digest


def fold_rivalry(archive: Archive) -> tuple[dict[str, float], str]:
    totals: dict[str, float] = {m.player_id: 0.0 for m in archive.moves}
    moves = archive.moves
    for i, a in enumerate(moves):
        for b in moves[i + 1 :]:
            if a.player_id == b.player_id:
                continue
            if abs(a.tick - b.tick) > 1:
                continue
            if not cells_are_neighbors(archive, a.cell_id, b.cell_id):
                continue
            if not cells_share_family(archive, a.cell_id, b.cell_id):
                continue
            totals[a.player_id] = totals.get(a.player_id, 0.0) + 0.5
            totals[b.player_id] = totals.get(b.player_id, 0.0) + 0.5

    rivalry_map = {pid: round_half_away(raw) for pid, raw in totals.items()}
    lines = [f"{pid}|{format_fixed2(rivalry_map[pid])}" for pid in sorted(rivalry_map)]
    digest = hashlib.sha256("\n".join(lines).encode()).hexdigest()
    return rivalry_map, digest


def board_fingerprint(archive: Archive) -> str:
    lines: list[str] = []
    for cell in sorted(archive.cells, key=lambda c: c.cell_id):
        glyph_id = archive.solution[cell.cell_id]
        family = archive.glyphs[glyph_id].family
        deg = len(cell.neighbors)
        lines.append(f"{cell.cell_id}|{glyph_id}|{family}|{deg}")
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def playtest_seal(
    season_score_digest: str,
    layout_digest: str,
    combo_digest: str,
    board_fp: str,
) -> str:
    payload = f"{season_score_digest}|{layout_digest}|{combo_digest}|{board_fp}"
    return hashlib.sha256(payload.encode()).hexdigest()


def match_chain_digest(prior: str, seal: str, rivalry_digest: str) -> str:
    payload = f"{prior}|{seal}|{rivalry_digest}"
    return hashlib.sha256(payload.encode()).hexdigest()


def match_crown(seal: str, rivalry_digest: str, chain: str) -> str:
    payload = f"{seal}|{rivalry_digest}|{chain}"
    return hashlib.sha256(payload.encode()).hexdigest()


def oriented_edge(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def cell_on_tape(archive: Archive, cell_id: str) -> bool:
    return any(m.cell_id == cell_id for m in archive.moves)


def is_echo_dotted(archive: Archive, a: str, b: str) -> bool:
    return (
        cells_share_family(archive, a, b)
        and cell_on_tape(archive, a)
        and cell_on_tape(archive, b)
    )


def build_dot(archive: Archive) -> str:
    lines = ["digraph ciphergrid {"]
    cell_ids = sorted(c.cell_id for c in archive.cells)
    for cid in cell_ids:
        lines.append(f'  "{cid}";')

    seen_adj: set[tuple[str, str]] = set()
    for cell in archive.cells:
        for nb in cell.neighbors:
            edge = oriented_edge(cell.cell_id, nb)
            if edge in seen_adj:
                continue
            seen_adj.add(edge)
            lines.append(f'  "{edge[0]}" -> "{edge[1]}";')

    seen_family: set[tuple[str, str]] = set()
    for cell in archive.cells:
        for nb in cell.neighbors:
            if not cells_share_family(archive, cell.cell_id, nb):
                continue
            edge = oriented_edge(cell.cell_id, nb)
            if edge in seen_family:
                continue
            seen_family.add(edge)
            lines.append(f'  "{edge[0]}" -> "{edge[1]}" [style=dashed];')

    seen_echo: set[tuple[str, str]] = set()
    for cell in archive.cells:
        for nb in cell.neighbors:
            if not is_echo_dotted(archive, cell.cell_id, nb):
                continue
            edge = oriented_edge(cell.cell_id, nb)
            if edge in seen_echo:
                continue
            seen_echo.add(edge)
            lines.append(f'  "{edge[0]}" -> "{edge[1]}" [style=dotted];')

    lines.append("}")
    return "\n".join(lines) + "\n"


def run_dot_plain(dot_path: Path) -> list[LayoutNode]:
    output = subprocess.check_output(
        ["dot", "-Tplain", str(dot_path)], text=True, stderr=subprocess.STDOUT
    )
    nodes: list[LayoutNode] = []
    for raw in output.splitlines():
        parts = raw.split()
        if len(parts) >= 4 and parts[0] == "node":
            nodes.append(LayoutNode(parts[1], float(parts[2]), float(parts[3])))
    return nodes


def layout_digest_from_nodes(nodes: list[LayoutNode]) -> str:
    ordered = sorted(nodes, key=lambda n: n.name)
    lines = [f"{n.name}|{format_fixed2(n.x)}|{format_fixed2(n.y)}" for n in ordered]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def topology_digest(archive: Archive, var_dir: Path | None = None) -> tuple[str, str]:
    var_dir = var_dir or Path("/app/var")
    var_dir.mkdir(parents=True, exist_ok=True)
    slug = Path(archive.root).name
    dot_path = var_dir / f"ciphergrid_{slug}.dot"
    dot_path.write_text(build_dot(archive))
    nodes = run_dot_plain(dot_path)
    return layout_digest_from_nodes(nodes), str(dot_path)


def read_prior_tip(tip_path: Path | None = None) -> str:
    tip_path = tip_path or CHAIN_TIP_PATH
    if not tip_path.is_file():
        return ""
    return tip_path.read_text(encoding="utf-8").strip()


def write_tip(digest: str, tip_path: Path | None = None) -> None:
    tip_path = tip_path or CHAIN_TIP_PATH
    tip_path.parent.mkdir(parents=True, exist_ok=True)
    tip_path.write_text(digest + "\n", encoding="utf-8")


def evaluate_archive(
    root: str | Path,
    var_dir: Path | None = None,
    *,
    prior_tip: str | None = None,
    persist_tip: bool = True,
) -> dict:
    archive = load_archive(root)
    var_dir = var_dir or Path("/app/var")
    tip_path = var_dir / "match_chain_tip.txt"
    players, season_digest = fold_scores(archive)
    combo_map, combo_digest = fold_combo(archive)
    rivalry_map, rivalry_digest = fold_rivalry(archive)
    for player in players:
        combo_points, _max = combo_map.get(player.player_id, (0.0, 0))
        player.combo_points = combo_points
        player.rivalry_points = rivalry_map.get(player.player_id, 0.0)
    layout_digest, dot_path = topology_digest(archive, var_dir)
    board_fp = board_fingerprint(archive)
    seal = playtest_seal(season_digest, layout_digest, combo_digest, board_fp)
    prior = read_prior_tip(tip_path) if prior_tip is None else prior_tip
    chain = match_chain_digest(prior, seal, rivalry_digest)
    if persist_tip:
        write_tip(chain, tip_path)
    crown = match_crown(seal, rivalry_digest, chain)
    return {
        "archive": str(root),
        "cell_count": len(archive.cells),
        "move_count": len(archive.moves),
        "players": [
            {
                "player_id": p.player_id,
                "points": round_half_away(p.points),
                "moves": p.moves,
                "combo_points": round_half_away(p.combo_points),
                "rivalry_points": round_half_away(p.rivalry_points),
            }
            for p in sorted(players, key=lambda p: p.player_id)
        ],
        "layout_digest": layout_digest,
        "season_score_digest": season_digest,
        "topology_dot_path": dot_path,
        "combo_digest": combo_digest,
        "board_fingerprint": board_fp,
        "playtest_seal": seal,
        "rivalry_digest": rivalry_digest,
        "match_chain_digest": chain,
        "match_crown": crown,
    }


def digest_only(root: str | Path, var_dir: Path | None = None) -> dict:
    report = evaluate_archive(root, var_dir)
    return {
        "layout_digest": report["layout_digest"],
        "season_score_digest": report["season_score_digest"],
        "combo_digest": report["combo_digest"],
        "board_fingerprint": report["board_fingerprint"],
        "playtest_seal": report["playtest_seal"],
        "rivalry_digest": report["rivalry_digest"],
        "match_chain_digest": report["match_chain_digest"],
        "match_crown": report["match_crown"],
    }
