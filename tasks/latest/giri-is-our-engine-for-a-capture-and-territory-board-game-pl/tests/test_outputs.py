import json
import os
import re
import sqlite3
import subprocess
from pathlib import Path

import pytest

import oracle as O

APP = Path(os.getenv("APP_DIR", "/app"))
BIN = APP / "target" / "release" / "giri"
BOARD = APP / "board.spec"
GAMES = APP / "games"
TMP = Path(os.getenv("GIRI_TMP", "/tmp/giri_test"))
TMP.mkdir(parents=True, exist_ok=True)
DB = TMP / "primary.db"
DB2 = TMP / "second.db"


def run(args, check=True):
    return subprocess.run(
        [str(BIN)] + args, capture_output=True, text=True, check=check
    )


@pytest.fixture(scope="session")
def adj():
    return O.load_board(BOARD)


@pytest.fixture(scope="session")
def replayed():
    run(["replay", "--board", str(BOARD), "--games", str(GAMES), "--db", str(DB)])
    return DB


@pytest.fixture(scope="session")
def rows(replayed):
    con = sqlite3.connect(replayed)
    cols = "game_id,first_illegal,reason,black_score,white_score,black_captures,white_captures,moves_played,final_board"
    out = {}
    for r in con.execute(f"SELECT {cols} FROM games"):
        out[r[0]] = {
            "first_illegal": r[1], "reason": r[2], "black_score": r[3],
            "white_score": r[4], "black_captures": r[5], "white_captures": r[6],
            "moves_played": r[7], "final_board": r[8],
        }
    con.close()
    return out


@pytest.fixture(scope="session")
def expected(adj):
    out = {}
    for p in sorted(GAMES.glob("*.log")):
        r = O.evaluate(p.read_text(), adj)
        out[p.stem] = {
            "first_illegal": -1 if r["first_illegal"] is None else r["first_illegal"],
            "reason": r["reason"] or "",
            "black_score": r["black_score"], "white_score": r["white_score"],
            "black_captures": r["black_captures"], "white_captures": r["white_captures"],
            "moves_played": r["played"], "final_board": r["board_str"],
            "board": r["board"],
        }
    return out


def make_dot(game, db=DB):
    dot = TMP / f"{game}.dot"
    svg = TMP / f"{game}.svg"
    run(["graph", "--board", str(BOARD), "--game", game, "--db", str(db),
         "--dot", str(dot), "--svg", str(svg)])
    return dot, svg


def parse_dot(text):
    nodes, edges = {}, set()
    for line in text.splitlines():
        line = line.strip()
        m = re.match(
            r'^(c\d+) \[kind="(\w+)" color="(\w+)" size="(\d+)" members="([^"]*)"\];$',
            line)
        if m:
            cid, kind, color, size, members = m.groups()
            nodes[cid] = (kind, color, tuple(members.split()))
            assert int(size) == len(members.split())
            continue
        m = re.match(r"^(c\d+) -- (c\d+);$", line)
        if m:
            edges.add(tuple(sorted(m.groups())))
    nsig = set(nodes.values())
    esig = {tuple(sorted((nodes[a], nodes[b]))) for a, b in edges}
    return nsig, esig


def oracle_sig(board, adj):
    sig = O.graph_signature(board, adj)
    nsig = {(k, c, tuple(m)) for (k, c, _s, m) in sig["nodes"]}
    esig = set()
    for (s1, s2) in sig["edges"]:
        esig.add(tuple(sorted(((s1[0], s1[1], tuple(s1[2])),
                               (s2[0], s2[1], tuple(s2[2]))))))
    return nsig, esig


# ---------- structure ----------

def test_binary_exists():
    assert BIN.exists(), f"engine binary not found at {BIN}"


def test_binary_built_from_crate():
    with open(BIN, "rb") as fh:
        assert fh.read(4) == b"\x7fELF", f"{BIN} is not a native executable"
    prints = APP / "target" / "release" / ".fingerprint"
    assert prints.is_dir(), "no cargo build fingerprints under target/release"
    assert any(p.name.startswith("giri-") for p in prints.iterdir()), \
        f"{BIN} was not produced by cargo from the giri crate"


def test_sqlite_schema(replayed):
    con = sqlite3.connect(replayed)
    gcols = {r[1] for r in con.execute("PRAGMA table_info(games)")}
    scols = {r[1] for r in con.execute("PRAGMA table_info(superko_sites)")}
    con.close()
    assert {"game_id", "first_illegal", "reason", "black_score", "white_score",
            "black_captures", "white_captures", "moves_played",
            "final_board"} <= gcols
    assert {"game_id", "move_index"} <= scols


def test_all_games_have_rows(rows, expected):
    assert set(rows) == set(expected)


def test_parse_board_spec(adj):
    # board.spec is an arbitrary graph, not a grid
    assert len(adj) >= 60
    for a in adj:
        for b in adj[a]:
            assert a in adj[b]


# ---------- full-corpus oracle sweep (long_context: needs whole-history replay) ----------

def test_oracle_corpus_sweep(rows, expected):
    bad = []
    for gid, exp in expected.items():
        got = rows[gid]
        for k in ("first_illegal", "reason", "black_score", "white_score",
                  "black_captures", "white_captures", "moves_played", "final_board"):
            if got[k] != exp[k]:
                bad.append((gid, k, exp[k], got[k]))
    assert not bad, bad[:10]


def test_first_illegal_move_index(rows, expected):
    for gid, exp in expected.items():
        assert rows[gid]["first_illegal"] == exp["first_illegal"], gid
        assert rows[gid]["reason"] == exp["reason"], gid


def test_final_board_reconstruction(rows, expected):
    for gid, exp in expected.items():
        assert rows[gid]["final_board"] == exp["final_board"], gid


def test_capture_counts(rows, expected):
    for gid, exp in expected.items():
        assert rows[gid]["black_captures"] == exp["black_captures"], gid
        assert rows[gid]["white_captures"] == exp["white_captures"], gid


def test_canonical_board_format(rows, adj):
    names = sorted(adj)
    for gid, row in rows.items():
        toks = row["final_board"].split(";")
        assert [t.split(":")[0] for t in toks] == names, gid
        assert all(t.split(":")[1] in ("B", "W", ".") for t in toks)


# ---------- rule precedence tension pairs ----------

def test_capture_before_suicide_legal(rows):
    # a move filling the placing group's last liberty is legal when it captures
    r = rows["capture_not_suicide"]
    assert r["first_illegal"] == -1
    assert r["reason"] == ""


def test_suicide_rejected_no_capture(rows, expected):
    r = rows["suicide_reject"]
    assert r["reason"] == "suicide"
    assert r["first_illegal"] == expected["suicide_reject"]["first_illegal"]


def test_self_atari_is_legal(rows):
    assert rows["self_atari"]["first_illegal"] == -1


def _superko_gap(game, adj, fi):
    moves = O.parse_log((GAMES / f"{game}.log").read_text(), set(adj))
    positions = _positions(moves, adj, fi)
    repeated = positions[-1]
    gap = len(positions) - 1 - positions.index(repeated)
    # a checker that only compares against the immediately preceding board would
    # not see this repeat
    immediate_miss = positions[-2] != positions[-1]
    return gap, immediate_miss


def test_positional_superko_full_history(rows, adj):
    # the repeat is far back; only whole-history positional superko rejects it
    r = rows["ko_longrange"]
    assert r["reason"] == "superko"
    gap, immediate_miss = _superko_gap("ko_longrange", adj, r["first_illegal"])
    assert gap >= 4
    assert immediate_miss


def test_simple_ko_negative_control(rows, adj):
    # a shorter repetition cycle; still not the immediately preceding position,
    # so a naive immediate-only ko rule already fails here too
    r = rows["ko_simple"]
    assert r["reason"] == "superko"
    gap, immediate_miss = _superko_gap("ko_simple", adj, r["first_illegal"])
    assert gap >= 2
    assert immediate_miss
    gap_long, _ = _superko_gap("ko_longrange", adj, rows["ko_longrange"]["first_illegal"])
    assert gap_long > gap


def _positions(moves, adj, upto):
    board = {n: None for n in adj}
    seq = [O.canonical(board)]
    for i, mv in enumerate(moves):
        if i > upto:
            break
        color = "B" if i % 2 == 0 else "W"
        if mv[0] == "pass":
            continue
        node = mv[1]
        board = dict(board)
        board[node] = color
        opp = "W" if color == "B" else "B"
        dead = O.opponent_dead(board, adj, opp)
        for n in dead:
            board[n] = None
        seq.append(O.canonical(board))
    return seq


# ---------- passes ----------

def test_pass_is_legal(rows):
    assert rows["self_atari"]["first_illegal"] == -1
    assert rows["two_pass"]["first_illegal"] == -1


def test_two_pass_termination(rows, expected):
    # trailing moves after the second consecutive pass are not played
    r = rows["two_pass"]
    assert r["first_illegal"] == -1
    assert r["moves_played"] == expected["two_pass"]["moves_played"]
    assert r["final_board"] == expected["two_pass"]["final_board"]


# ---------- occupied ----------

def test_occupied_rejected(rows, expected):
    r = rows["occupied_reject"]
    assert r["reason"] == "occupied"
    assert r["first_illegal"] == expected["occupied_reject"]["first_illegal"]


# ---------- scoring: neutral regions ----------

def _naive_score(board, adj):
    # WRONG on purpose: assigns any region touching >=1 color to a single color,
    # ignoring the both-colors -> neutral rule.
    black = sum(1 for n in board if board[n] == "B")
    white = sum(1 for n in board if board[n] == "W")
    seen = set()
    for n in board:
        if board[n] is None and n not in seen:
            region = O._component(n, adj, board, None, seen)
            border = set()
            for r in region:
                for nb in adj[r]:
                    if board[nb] is not None:
                        border.add(board[nb])
            if "B" in border:
                black += len(region)
            elif "W" in border:
                white += len(region)
    return black, white


def test_neutral_region_scores_neither(rows, expected, adj):
    board = expected["neutral_region"]["board"]
    # the game genuinely has an empty region bordering both colors
    seen = set()
    both = False
    for n in board:
        if board[n] is None and n not in seen:
            region = O._component(n, adj, board, None, seen)
            border = {board[nb] for r in region for nb in adj[r] if board[nb]}
            if border == {"B", "W"}:
                both = True
    assert both
    nb, nw = _naive_score(board, adj)
    got = rows["neutral_region"]
    assert (got["black_score"], got["white_score"]) == (
        expected["neutral_region"]["black_score"],
        expected["neutral_region"]["white_score"])
    assert (got["black_score"], got["white_score"]) != (nb, nw)


def test_area_score_single_color_region(rows, expected, adj):
    # at least one game has a single-color region contributing territory
    found = False
    for gid, exp in expected.items():
        board = exp["board"]
        stones = sum(1 for n in board if board[n])
        if exp["black_score"] + exp["white_score"] > stones:
            found = True
            assert rows[gid]["black_score"] == exp["black_score"]
            assert rows[gid]["white_score"] == exp["white_score"]
    assert found


# ---------- multi-stone / simultaneous capture ----------

def test_simultaneous_opponent_capture(rows, expected):
    # games where a color removed more than one opponent stone exercise
    # simultaneous group removal; counts must match the oracle
    multi = [g for g, e in expected.items()
             if e["black_captures"] > 1 or e["white_captures"] > 1]
    assert multi
    for g in multi:
        assert rows[g]["black_captures"] == expected[g]["black_captures"]
        assert rows[g]["white_captures"] == expected[g]["white_captures"]


# ---------- graph output (tool_specific: graphviz) ----------

def test_dot_group_region_nodes_edges(adj, expected, replayed):
    sample = [p.stem for p in sorted(GAMES.glob("game_00*.log"))][:12]
    sample += ["neutral_region", "self_atari", "capture_not_suicide"]
    for gid in sample:
        dot, _svg = make_dot(gid)
        en = parse_dot(dot.read_text())
        orc = oracle_sig(expected[gid]["board"], adj)
        assert en == orc, gid


def test_dot_svg_rendered_valid(replayed):
    dot, svg = make_dot("game_0000")
    text = svg.read_text()
    assert "<svg" in text
    # independently confirm dot accepts the emitted graph
    p = subprocess.run(["dot", "-Tsvg", str(dot)], capture_output=True, text=True)
    assert p.returncode == 0
    assert "<svg" in p.stdout


def test_store_graph_score_consistency(adj, expected, replayed):
    # the stored final board and the emitted graph must describe one position
    for gid in ["game_0001", "neutral_region", "capture_not_suicide"]:
        dot, _ = make_dot(gid)
        nsig, _ = parse_dot(dot.read_text())
        black_stones = sum(len(m) for (k, c, m) in nsig if c == "black")
        white_stones = sum(len(m) for (k, c, m) in nsig if c == "white")
        board = expected[gid]["board"]
        assert black_stones == sum(1 for n in board if board[n] == "B")
        assert white_stones == sum(1 for n in board if board[n] == "W")


# ---------- db_interaction: report reads back from the store ----------

def test_report_matches_store(rows, replayed):
    for gid in ["game_0000", "ko_longrange", "suicide_reject"]:
        p = run(["report", "--game", gid, "--db", str(replayed)])
        obj = json.loads(p.stdout.strip())
        assert obj["game_id"] == gid
        assert obj["first_illegal"] == rows[gid]["first_illegal"]
        assert obj["reason"] == rows[gid]["reason"]
        assert obj["black_score"] == rows[gid]["black_score"]
        assert obj["final_board"] == rows[gid]["final_board"]


def test_superko_rejection_sites_stored(replayed, expected):
    con = sqlite3.connect(replayed)
    got = {(r[0], r[1]) for r in con.execute("SELECT game_id,move_index FROM superko_sites")}
    con.close()
    want = {(g, e["first_illegal"]) for g, e in expected.items() if e["reason"] == "superko"}
    assert got == want
    assert want  # superko is actually exercised


def test_sqlite_result_rows(replayed, expected):
    con = sqlite3.connect(replayed)
    for gid in ["capture_not_suicide", "neutral_region", "ko_simple"]:
        r = con.execute(
            "SELECT black_score,white_score,black_captures,white_captures FROM games WHERE game_id=?",
            (gid,)).fetchone()
        e = expected[gid]
        assert r == (e["black_score"], e["white_score"], e["black_captures"], e["white_captures"])
    con.close()


# ---------- determinism ----------

def test_deterministic_two_runs(replayed):
    run(["replay", "--board", str(BOARD), "--games", str(GAMES), "--db", str(DB2)])
    c1 = sqlite3.connect(DB)
    c2 = sqlite3.connect(DB2)
    q = "SELECT * FROM games ORDER BY game_id"
    r1, r2 = list(c1.execute(q)), list(c2.execute(q))
    s1 = list(c1.execute("SELECT * FROM superko_sites ORDER BY game_id,move_index"))
    s2 = list(c2.execute("SELECT * FROM superko_sites ORDER BY game_id,move_index"))
    c1.close()
    c2.close()
    assert r1 == r2
    assert s1 == s2


def test_bytewise_replay_idempotent(replayed):
    d1, _ = make_dot("game_0002", DB)
    b1 = d1.read_bytes()
    run(["replay", "--board", str(BOARD), "--games", str(GAMES), "--db", str(DB2)])
    dot2 = TMP / "game_0002_b.dot"
    svg2 = TMP / "game_0002_b.svg"
    run(["graph", "--board", str(BOARD), "--game", "game_0002", "--db", str(DB2),
         "--dot", str(dot2), "--svg", str(svg2)])
    assert b1 == dot2.read_bytes()


# ---------- malformed ----------

def test_parse_reject_malformed_log():
    p = run(["replay", "--board", str(BOARD), "--games", str(GAMES / "malformed"),
             "--db", str(TMP / "m.db")], check=False)
    assert p.returncode != 0


def test_malformed_move_out_of_range(tmp_path):
    d = tmp_path / "mg"
    d.mkdir()
    (d / "oor.log").write_text("n00\nzzz99\n")
    p = run(["replay", "--board", str(BOARD), "--games", str(d),
             "--db", str(tmp_path / "x.db")], check=False)
    assert p.returncode != 0


# ---------- robustness ----------

def test_all_pass_game_no_panic(tmp_path):
    d = tmp_path / "pg"
    d.mkdir()
    (d / "allpass.log").write_text("pass\npass\n")
    db = tmp_path / "p.db"
    run(["replay", "--board", str(BOARD), "--games", str(d), "--db", str(db)])
    con = sqlite3.connect(db)
    r = con.execute("SELECT black_score,white_score,moves_played FROM games WHERE game_id='allpass'").fetchone()
    con.close()
    assert r == (0, 0, 2)


def test_large_connected_group(tmp_path, adj):
    # black fills a large connected region while white passes between moves;
    # the final group must be scored correctly (iterative flood fill)
    order = sorted(adj)
    moves = []
    for n in order:
        moves.append(n)
        moves.append("pass")
    text = "\n".join(moves) + "\n"
    r = O.evaluate(text, adj)
    d = tmp_path / "lg"
    d.mkdir()
    (d / "big.log").write_text(text)
    db = tmp_path / "b.db"
    run(["replay", "--board", str(BOARD), "--games", str(d), "--db", str(db)])
    con = sqlite3.connect(db)
    got = con.execute(
        "SELECT first_illegal,reason,black_score,white_score,final_board FROM games WHERE game_id='big'").fetchone()
    con.close()
    exp = (-1 if r["first_illegal"] is None else r["first_illegal"],
           r["reason"] or "", r["black_score"], r["white_score"], r["board_str"])
    assert got == exp


def test_arbitrary_graph_not_grid(adj):
    degs = sorted(len(adj[n]) for n in adj)
    assert degs[0] == 1  # a pendant node exists
    assert degs[-1] >= 5  # a high-degree node exists (never true on a lattice)
