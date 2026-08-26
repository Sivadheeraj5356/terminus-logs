from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
WORKSPACE = APP / "workspace"
OUT = APP / "output" / "sgf-pack"
SRC = APP / "environment" / "tools" / "sgfpack"
BOARD_SIZE = 5
PROP_RE = re.compile(r"([A-Za-z_]+)\[([^\]]*)\]")


@pytest.fixture(scope="session")
def sgfpack_bin(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the command from the source tree the solver edited."""
    env = os.environ.copy()
    env.update({"GOPROXY": "off", "GOTOOLCHAIN": "local"})
    subprocess.run(["go", "test", "./..."], cwd=SRC, check=True, text=True, capture_output=True, env=env)
    out_dir = tmp_path_factory.mktemp("sgfpack-bin")
    binary = out_dir / "sgfpack"
    subprocess.run(["go", "build", "-o", str(binary), "."], cwd=SRC, check=True, text=True, capture_output=True, env=env)
    return binary


def run_sgfpack(binary: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(binary), *args], check=check, text=True, capture_output=True)


def fresh_workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    shutil.copytree(WORKSPACE, root)
    state = root / "register" / "repair_state.json"
    state.write_text('[{"game_id":"stale","journal_seq":0}]\n', encoding="utf-8")
    return root


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def append_tsv(path: Path, row: list[str]) -> None:
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write("\t".join(row) + "\n")


def sha256_path(path: Path) -> str:
    result = subprocess.run(["sha256sum", str(path)], check=True, text=True, capture_output=True)
    return result.stdout.split()[0]


def parse_sgf(path: Path) -> tuple[dict[str, str], list[tuple[str, str]], str]:
    raw = path.read_text(encoding="utf-8").strip()
    assert raw.startswith("(") and raw.endswith(")"), f"{path} is not a single SGF tree"
    parts = [part.strip() for part in raw[1:-1].split(";") if part.strip()]
    assert parts, f"{path} contains no SGF game-tree entries"
    props = {m.group(1): m.group(2) for m in PROP_RE.finditer(parts[0])}
    moves: list[tuple[str, str]] = []
    for part in parts[1:]:
        found = None
        for match in PROP_RE.finditer(part):
            if match.group(1) in {"B", "W"}:
                found = (match.group(1), match.group(2))
                break
        assert found is not None, f"{path} contains a non-move entry {part!r}"
        moves.append(found)
    return props, moves, raw + "\n"


def camera_rows(root: Path, game_id: str) -> list[tuple[int, str, str, str]]:
    rows: list[tuple[int, str, str, str]] = []
    for line in (root / "evidence" / "camera" / f"{game_id}.moves").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        ply_s, color, coord, status = line.split("\t")
        rows.append((int(ply_s), color, "" if coord == "pass" else coord, status))
    return sorted(rows)


def official_camera_moves(root: Path, card: dict[str, str]) -> list[tuple[str, str]]:
    overturned = int(card["overturned_ply"] or 0)
    moves: list[tuple[str, str]] = []
    saw_overturn = False
    for ply, color, coord, status in camera_rows(root, card["game_id"]):
        if status == "played":
            if card["reason"] == "superko-forfeit" and overturned and ply >= overturned:
                continue
            moves.append((color, coord))
        elif status == "overturned-superko":
            saw_overturn = True
            assert ply == overturned
        else:
            raise AssertionError(f"{card['game_id']} has unexpected camera status {status}")
    if card["reason"] == "superko-forfeit":
        assert saw_overturn
    return moves


def neighbors(x: int, y: int):
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
            yield nx, ny


def board_key(board: list[list[str]]) -> str:
    return "".join("".join(row) for row in board)


def group_and_liberties(board: list[list[str]], x: int, y: int):
    color = board[y][x]
    group = {(x, y)}
    libs = set()
    stack = [(x, y)]
    while stack:
        px, py = stack.pop()
        for nx, ny in neighbors(px, py):
            value = board[ny][nx]
            if value == ".":
                libs.add((nx, ny))
            elif value == color and (nx, ny) not in group:
                group.add((nx, ny))
                stack.append((nx, ny))
    return group, libs


def replay(moves: list[tuple[str, str]], result_tag: str, props: dict[str, str]) -> dict[str, int | str]:
    board = [["." for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    history = {board_key(board)}
    expected_color = "B"
    consecutive_passes = 0
    for index, (color, coord) in enumerate(moves, start=1):
        assert color == expected_color, f"ply {index} has {color}, expected {expected_color}"
        expected_color = "W" if expected_color == "B" else "B"
        if coord == "":
            consecutive_passes += 1
            continue
        consecutive_passes = 0
        assert len(coord) == 2 and "a" <= coord[0] <= "e" and "a" <= coord[1] <= "e"
        x = ord(coord[0]) - ord("a")
        y = ord(coord[1]) - ord("a")
        assert board[y][x] == ".", f"occupied coordinate at ply {index}: {coord}"
        board[y][x] = color
        opponent = "W" if color == "B" else "B"
        for nx, ny in list(neighbors(x, y)):
            if board[ny][nx] == opponent:
                group, libs = group_and_liberties(board, nx, ny)
                if not libs:
                    for gx, gy in group:
                        board[gy][gx] = "."
        _, libs = group_and_liberties(board, x, y)
        assert libs, f"self-capture at ply {index}: {color}[{coord}]"
        key = board_key(board)
        assert key not in history, f"positional-superko repeat at ply {index}: {color}[{coord}]"
        history.add(key)
    black_score = sum(cell == "B" for row in board for cell in row)
    white_score = sum(cell == "W" for row in board for cell in row)
    if result_tag.endswith("+F"):
        assert props.get("ADJ") == "superko-forfeit"
        assert props.get("FP", "").isdigit()
        result = result_tag
        reason = "superko-forfeit"
    else:
        assert consecutive_passes >= 2, "scored records must end with two consecutive passes"
        if black_score > white_score:
            result = f"B+{black_score - white_score}"
        elif white_score > black_score:
            result = f"W+{white_score - black_score}"
        else:
            result = "0"
        reason = "score"
    assert result == result_tag
    return {
        "black_score": black_score,
        "white_score": white_score,
        "result": result,
        "reason": reason,
        "legal_ply_count": len(moves),
    }


def active_journal(root: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in read_tsv(root / "register" / "adjudication-journal.tsv"):
        if row["active"].lower() != "true":
            continue
        if row["game_id"] not in out or int(row["journal_seq"]) > int(out[row["game_id"]]["journal_seq"]):
            out[row["game_id"]] = row
    return out


def expected_points(result: str) -> tuple[str, str]:
    if result.startswith("B+"):
        return "1", "0"
    if result.startswith("W+"):
        return "0", "1"
    return "0", "0"


def assert_repaired_archive(root: Path) -> None:
    cards = {row["game_id"]: row for row in read_tsv(root / "evidence" / "referee" / "referee_cards.tsv")}
    rounds = {row["game_id"]: row for row in read_tsv(root / "register" / "rounds.tsv")}
    state = json.loads((root / "register" / "repair_state.json").read_text(encoding="utf-8"))
    state_by_game = {row["game_id"]: row for row in state}
    journal = active_journal(root)
    assert list(state_by_game) == sorted(state_by_game)
    assert set(rounds) == set(cards) == set(state_by_game) == set(journal)
    for game_id, card in cards.items():
        row = rounds[game_id]
        assert row["round"] == card["round"]
        assert row["board"] == card["board"]
        assert row["black"] == card["black"]
        assert row["white"] == card["white"]
        assert row["record"] == f"records/current/{game_id}.sgf"
        assert row["result"] == card["expected_result"]
        assert row["reason"] == card["reason"]
        assert (row["black_points"], row["white_points"]) == expected_points(card["expected_result"])
        props, moves, _ = parse_sgf(root / row["record"])
        assert props["ID"] == game_id
        assert props["PB"] == card["black"]
        assert props["PW"] == card["white"]
        assert props["RO"] == card["round"]
        assert props["RE"] == card["expected_result"]
        assert moves == official_camera_moves(root, card)
        replayed = replay(moves, props["RE"], props)
        entry = state_by_game[game_id]
        assert entry["journal_seq"] == int(journal[game_id]["journal_seq"])
        assert entry["journal_event"] == journal[game_id]["journal_event"]
        assert entry["camera_sha256"] == sha256_path(root / "evidence" / "camera" / f"{game_id}.moves")
        assert entry["record_sha256"] == sha256_path(root / row["record"])
        assert entry["result"] == row["result"]
        assert entry["reason"] == row["reason"]
        assert entry["legal_ply_count"] == replayed["legal_ply_count"]


def compute_standings(root: Path) -> list[dict[str, str | int]]:
    rounds = {row["game_id"]: row for row in read_tsv(root / "register" / "rounds.tsv")}
    players = sorted({row["black"] for row in rounds.values()} | {row["white"] for row in rounds.values()})
    wins = {player: 0 for player in players}
    losses = {player: 0 for player in players}
    defeated = {player: [] for player in players}
    opponents = {player: [] for player in players}
    margin = {player: 0 for player in players}
    for row in rounds.values():
        props, moves, _ = parse_sgf(root / row["record"])
        replayed = replay(moves, props["RE"], props)
        b = row["black"]
        w = row["white"]
        opponents[b].append(w)
        opponents[w].append(b)
        stone_margin = int(replayed["black_score"]) - int(replayed["white_score"])
        if row["result"].startswith("B+"):
            wins[b] += 1
            losses[w] += 1
            defeated[b].append(w)
            margin[b] += stone_margin
            margin[w] -= stone_margin
        elif row["result"].startswith("W+"):
            wins[w] += 1
            losses[b] += 1
            defeated[w].append(b)
            margin[w] -= stone_margin
            margin[b] += stone_margin
    table = []
    for player in players:
        table.append({
            "player": player,
            "wins": wins[player],
            "losses": losses[player],
            "sos": sum(wins[opp] for opp in opponents[player]),
            "sodos": sum(wins[opp] for opp in defeated[player]),
            "stone_margin": margin[player],
        })
    table.sort(key=lambda row: (-int(row["wins"]), -int(row["sos"]), -int(row["sodos"]), str(row["player"])))
    for rank, row in enumerate(table, start=1):
        row["rank"] = rank
    return table


def snapshot_tree(path: Path) -> dict[str, bytes]:
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in sorted(path.rglob("*")) if p.is_file()}


def test_cli_repairs_real_workspace_and_writes_official_pack(sgfpack_bin: Path):
    """The repaired command must rebuild the real archive and the official pack from source evidence."""
    if OUT.exists():
        shutil.rmtree(OUT)
    run_sgfpack(sgfpack_bin, "repair", "--root", str(WORKSPACE))
    assert_repaired_archive(WORKSPACE)
    run_sgfpack(sgfpack_bin, "audit", "--root", str(WORKSPACE))
    run_sgfpack(sgfpack_bin, "export", "--root", str(WORKSPACE), "--out", str(OUT))
    assert (OUT / "manifest.json").is_file()
    for row in read_tsv(WORKSPACE / "register" / "rounds.tsv"):
        assert (OUT / "records" / f"{row['game_id']}.sgf").read_bytes() == (WORKSPACE / row["record"]).read_bytes()


def test_export_manifest_state_and_standings_are_derived_from_replay(sgfpack_bin: Path, tmp_path: Path):
    """Manifest, adjudications, and standings must be derived from repaired records and replay state."""
    root = fresh_workspace(tmp_path)
    out = tmp_path / "pack"
    run_sgfpack(sgfpack_bin, "repair", "--root", str(root))
    run_sgfpack(sgfpack_bin, "export", "--root", str(root), "--out", str(out))
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    adjudications = json.loads((out / "adjudications.json").read_text(encoding="utf-8"))
    assert manifest["ruleset"] == "TTB-PSK-5"
    assert manifest["board_size"] == 5
    assert manifest["record_count"] == len(read_tsv(root / "register" / "rounds.tsv"))
    assert manifest["source_rounds_sha256"] == sha256_path(root / "register" / "rounds.tsv")
    assert manifest["repair_state_sha256"] == sha256_path(root / "register" / "repair_state.json")
    assert manifest["records"] == adjudications
    expected = compute_standings(root)
    actual = read_tsv(out / "standings.tsv")
    assert len(actual) == len(expected)
    for got, want in zip(actual, expected):
        for key in ["rank", "player", "wins", "losses", "sos", "sodos", "stone_margin"]:
            assert str(got[key]) == str(want[key])


def test_repair_is_idempotent_after_stale_state_and_stale_output(sgfpack_bin: Path, tmp_path: Path):
    """Repair and export must converge even when state and output contain stale bytes."""
    root = fresh_workspace(tmp_path)
    out = tmp_path / "pack"
    run_sgfpack(sgfpack_bin, "repair", "--root", str(root))
    run_sgfpack(sgfpack_bin, "export", "--root", str(root), "--out", str(out))
    first_workspace = snapshot_tree(root / "register") | snapshot_tree(root / "records" / "current")
    first_output = snapshot_tree(out)
    (root / "register" / "repair_state.json").write_text('[{"game_id":"old","journal_seq":99}]\n', encoding="utf-8")
    first_game = read_tsv(root / "register" / "rounds.tsv")[0]["game_id"]
    (out / "records" / f"{first_game}.stale").write_text("(;GM[1])\n", encoding="utf-8")
    (out / "manifest.json").write_text('{"ruleset":"stale"}\n', encoding="utf-8")
    run_sgfpack(sgfpack_bin, "repair", "--root", str(root))
    run_sgfpack(sgfpack_bin, "export", "--root", str(root), "--out", str(out))
    assert snapshot_tree(root / "register") | snapshot_tree(root / "records" / "current") == first_workspace
    assert snapshot_tree(out) == first_output


def test_dynamic_superko_forfeit_record_is_rebuilt_without_current_record_trust(sgfpack_bin: Path, tmp_path: Path):
    """A new forfeit game must be reconstructed from camera and referee evidence, not from current SGF text."""
    root = fresh_workspace(tmp_path)
    game_id = "HX7"
    cards = read_tsv(root / "evidence" / "referee" / "referee_cards.tsv")
    source_card = next(row for row in cards if row["reason"] == "superko-forfeit")
    journal_rows = read_tsv(root / "register" / "adjudication-journal.tsv")
    inactive_event = next(row["journal_event"] for row in journal_rows if row["game_id"] == source_card["game_id"] and row["active"].lower() == "false")
    active_event = next(row["journal_event"] for row in journal_rows if row["game_id"] == source_card["game_id"] and row["active"].lower() == "true")
    shutil.copyfile(root / "evidence" / "camera" / f"{source_card['game_id']}.moves", root / "evidence" / "camera" / f"{game_id}.moves")
    append_tsv(root / "evidence" / "referee" / "referee_cards.tsv", [game_id, "4", "1", source_card["black"], source_card["white"], source_card["expected_result"], source_card["reason"], source_card["overturned_ply"], source_card["forfeit_winner"]])
    append_tsv(root / "register" / "adjudication-journal.tsv", [game_id, "7", "false", inactive_event, "Raw board feed included the attempted recapture."])
    append_tsv(root / "register" / "adjudication-journal.tsv", [game_id, "11", "true", active_event, "Referee stopped the record at the repeated position."])
    append_tsv(root / "register" / "rounds.tsv", [game_id, "4", "1", source_card["white"], source_card["black"], f"records/current/{game_id}.sgf", "W+R", "resignation", "0", "1"])
    (root / "records" / "current" / f"{game_id}.sgf").write_text(
        f"(;GM[1]FF[4]CA[UTF-8]AP[old]SZ[5]RU[TTB-PSK-5]KM[0]EV[Harbor House 5x5 Cup]RO[4]ID[{game_id}]PB[{source_card['white']}]PW[{source_card['black']}]RE[W+R];B[aa];W[bb])\n",
        encoding="utf-8",
    )
    run_sgfpack(sgfpack_bin, "repair", "--root", str(root))
    assert_repaired_archive(root)
    props, moves, _ = parse_sgf(root / "records" / "current" / f"{game_id}.sgf")
    assert props["PB"] == source_card["black"]
    assert props["PW"] == source_card["white"]
    assert props["RE"] == source_card["expected_result"]
    assert props["FP"] == source_card["overturned_ply"]
    assert len(moves) == 23
    assert moves[-1] == ("B", "ab")


def test_active_journal_sequence_is_numeric_and_repair_state_is_rebuilt(sgfpack_bin: Path, tmp_path: Path):
    """The state file must record the highest active journal sequence, independent of row order."""
    root = fresh_workspace(tmp_path)
    cards = read_tsv(root / "evidence" / "referee" / "referee_cards.tsv")
    target_game = next(row["game_id"] for row in cards if row["reason"] == "score" and row["expected_result"].startswith("W+"))
    event = active_journal(root)[target_game]["journal_event"]
    append_tsv(root / "register" / "adjudication-journal.tsv", [target_game, "9", "false", event, "A stale row from the abandoned draft."])
    append_tsv(root / "register" / "adjudication-journal.tsv", [target_game, "10", "true", event, "Late import of the same active camera authority."])
    append_tsv(root / "register" / "adjudication-journal.tsv", [target_game, "2", "true", event, "Earlier active row kept for audit history."])
    run_sgfpack(sgfpack_bin, "repair", "--root", str(root))
    state = {row["game_id"]: row for row in json.loads((root / "register" / "repair_state.json").read_text(encoding="utf-8"))}
    assert state[target_game]["journal_seq"] == 10
    assert state[target_game]["journal_event"] == active_journal(root)[target_game]["journal_event"]
    before = snapshot_tree(root / "register")
    run_sgfpack(sgfpack_bin, "repair", "--root", str(root))
    assert snapshot_tree(root / "register") == before


def test_audit_rejects_late_record_divergence_and_repair_recovers(sgfpack_bin: Path, tmp_path: Path):
    """Audit must fail after durable records drift, and repair must reconstruct the coherent state."""
    root = fresh_workspace(tmp_path)
    run_sgfpack(sgfpack_bin, "repair", "--root", str(root))
    record = root / "records" / "current" / "G01.sgf"
    record.write_text(record.read_text(encoding="utf-8").replace("RE[B+1]", "RE[W+1]"), encoding="utf-8")
    failed = run_sgfpack(sgfpack_bin, "audit", "--root", str(root), check=False)
    assert failed.returncode != 0
    assert "G01" in failed.stderr
    run_sgfpack(sgfpack_bin, "repair", "--root", str(root))
    run_sgfpack(sgfpack_bin, "audit", "--root", str(root))
    assert_repaired_archive(root)
