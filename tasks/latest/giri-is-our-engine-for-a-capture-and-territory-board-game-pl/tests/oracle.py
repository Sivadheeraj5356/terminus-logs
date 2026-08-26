"""Reference rules engine for giri. Pure read/compute, no file generation.

This is the ground-truth reimplementation used by the verifier to derive
expected results from the board spec and each move log at test time.
"""

from __future__ import annotations

import os
from collections import deque
from pathlib import Path


class MalformedLog(Exception):
    pass


class MalformedBoard(Exception):
    pass


def parse_board(text: str) -> dict[str, list[str]]:
    adj: dict[str, set[str]] = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if parts[0] == "node":
            if len(parts) != 2:
                raise MalformedBoard("bad node line")
            adj.setdefault(parts[1], set())
        elif parts[0] == "edge":
            if len(parts) != 3:
                raise MalformedBoard("bad edge line")
            a, b = parts[1], parts[2]
            if a not in adj or b not in adj:
                raise MalformedBoard("edge references unknown node")
            if a == b:
                raise MalformedBoard("self loop")
            adj[a].add(b)
            adj[b].add(a)
        else:
            raise MalformedBoard("unknown directive")
    return {k: sorted(v) for k, v in adj.items()}


def parse_log(text: str, nodes: set[str]) -> list[tuple]:
    moves: list[tuple] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 1:
            raise MalformedLog("move must be a single token")
        tok = parts[0]
        if tok == "pass":
            moves.append(("pass",))
        elif tok in nodes:
            moves.append(("play", tok))
        else:
            raise MalformedLog(f"unknown intersection {tok}")
    return moves


def _component(start, adj, board, want, seen):
    comp = {start}
    seen.add(start)
    q = deque([start])
    while q:
        cur = q.popleft()
        for nb in adj[cur]:
            if nb in seen:
                continue
            if board[nb] == want:
                seen.add(nb)
                comp.add(nb)
                q.append(nb)
    return comp


def group_of(node, adj, board):
    color = board[node]
    return _component(node, adj, board, color, set())


def liberties(group, adj, board):
    libs = set()
    for n in group:
        for nb in adj[n]:
            if board[nb] is None:
                libs.add(nb)
    return len(libs)


def opponent_dead(board, adj, opp):
    dead = set()
    seen = set()
    for n in board:
        if board[n] == opp and n not in seen:
            grp = _component(n, adj, board, opp, seen)
            if liberties(grp, adj, board) == 0:
                dead |= grp
    return dead


def canonical(board):
    return ";".join(f"{n}:{board[n] or '.'}" for n in sorted(board))


def replay(moves, adj):
    board = {n: None for n in adj}
    history = {canonical(board)}
    prev_pass = False
    first_illegal = None
    reason = None
    black_cap = 0
    white_cap = 0
    played = 0
    for i, mv in enumerate(moves):
        color = "B" if i % 2 == 0 else "W"
        if mv[0] == "pass":
            played = i + 1
            if prev_pass:
                break
            prev_pass = True
            continue
        node = mv[1]
        if board[node] is not None:
            first_illegal, reason = i, "occupied"
            break
        board[node] = color
        opp = "W" if color == "B" else "B"
        dead = opponent_dead(board, adj, opp)
        for n in dead:
            board[n] = None
        removed = len(dead)
        placed = group_of(node, adj, board)
        if liberties(placed, adj, board) == 0 and removed == 0:
            board[node] = None
            first_illegal, reason = i, "suicide"
            break
        key = canonical(board)
        if key in history:
            for n in dead:
                board[n] = opp
            board[node] = None
            first_illegal, reason = i, "superko"
            break
        history.add(key)
        if color == "B":
            black_cap += removed
        else:
            white_cap += removed
        prev_pass = False
        played = i + 1
    return {
        "first_illegal": first_illegal,
        "reason": reason,
        "board": board,
        "black_captures": black_cap,
        "white_captures": white_cap,
        "played": played,
    }


def area_score(board, adj):
    black = sum(1 for n in board if board[n] == "B")
    white = sum(1 for n in board if board[n] == "W")
    seen = set()
    for n in board:
        if board[n] is None and n not in seen:
            region = _component(n, adj, board, None, seen)
            border = set()
            for r in region:
                for nb in adj[r]:
                    if board[nb] is not None:
                        border.add(board[nb])
            if border == {"B"}:
                black += len(region)
            elif border == {"W"}:
                white += len(region)
    return black, white


def components(board, adj):
    seen = set()
    comps = []
    for n in sorted(board):
        if n in seen:
            continue
        color = board[n]
        comp = _component(n, adj, board, color, seen)
        kind = "region" if color is None else "group"
        col = {"B": "black", "W": "white", None: "empty"}[color]
        comps.append({"kind": kind, "color": col, "members": tuple(sorted(comp))})
    comps.sort(key=lambda c: c["members"])
    return comps


def graph_signature(board, adj):
    comps = components(board, adj)
    idx = {}
    for i, c in enumerate(comps):
        for m in c["members"]:
            idx[m] = i
    nodes = [(c["kind"], c["color"], len(c["members"]), c["members"]) for c in comps]
    edges = set()
    for a in adj:
        for b in adj[a]:
            if idx[a] != idx[b]:
                lo, hi = sorted((idx[a], idx[b]))
                edges.add((lo, hi))
    edge_sigs = set()
    for lo, hi in edges:
        s1 = (comps[lo]["kind"], comps[lo]["color"], comps[lo]["members"])
        s2 = (comps[hi]["kind"], comps[hi]["color"], comps[hi]["members"])
        edge_sigs.add(tuple(sorted((s1, s2))))
    return {"nodes": nodes, "edges": edge_sigs}


def evaluate(log_text, adj):
    moves = parse_log(log_text, set(adj))
    r = replay(moves, adj)
    black, white = area_score(r["board"], adj)
    r["black_score"] = black
    r["white_score"] = white
    r["board_str"] = canonical(r["board"])
    return r


def load_board(path):
    return parse_board(Path(path).read_text())


def load_games(games_dir):
    games = {}
    for p in sorted(Path(games_dir).glob("*.log")):
        games[p.stem] = p.read_text()
    return games


if __name__ == "__main__":
    import json
    import sys

    board_path = sys.argv[1]
    games_dir = sys.argv[2]
    adj = load_board(board_path)
    out = {}
    for gid, text in load_games(games_dir).items():
        try:
            r = evaluate(text, adj)
        except MalformedLog as e:
            out[gid] = {"malformed": str(e)}
            continue
        out[gid] = {
            "first_illegal": r["first_illegal"],
            "reason": r["reason"],
            "black_score": r["black_score"],
            "white_score": r["white_score"],
            "black_captures": r["black_captures"],
            "white_captures": r["white_captures"],
            "board": r["board_str"],
        }
    json.dump(out, sys.stdout, indent=2, default=str)
    print(os.linesep, end="")
