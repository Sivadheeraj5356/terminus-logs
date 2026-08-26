"""Behavioral checks for the rebuilt Clockwork Crypt world and clue atlas."""

from __future__ import annotations

import hashlib
import sqlite3
import subprocess
from collections import deque
from pathlib import Path

import pytest


APP = Path("/app")
DB = APP / "state/world.db"
ARTIFACTS = APP / "artifacts"
EXPECTED_WORLD_SHA256 = "3826888f2fad0603751e5d9f49105f04231fc417c63ac8e8457402a174c0bdb9"
EXPECTED_ATLAS_RGBA_SHA256 = "534c977c31a1f0b5aa6c3740ca16b2decc762047d87f5481a3c4ff85cca93761"
EXPECTED_CIRCUIT = (
    "steps=10\n"
    "shortest_walks=1\n"
    "moves=east,north,east,north,east,south,east,north,north,east\n"
    "rooms=vestibule,gearwell,boiler,choir,ossuary,archive,gallery,"
    "observatory,mirror,clockheart,keeper\n"
)


@pytest.fixture(scope="session", autouse=True)
def rebuild_from_migrations() -> None:
    """Rebuild from source so stale or hand-written artifacts cannot satisfy the verifier."""
    subprocess.run(["/app/bin/rebuild-world"], check=True, text=True, capture_output=True)


def query(sql: str) -> list[tuple]:
    """Return rows from the generated SQLite world database."""
    with sqlite3.connect(DB) as connection:
        return connection.execute(sql).fetchall()


def test_all_migrations_are_applied_once() -> None:
    """Verify the migration runner produced the complete four-step schema history."""
    assert query("SELECT version, name FROM migration_log ORDER BY version") == [
        (1, "schema"),
        (2, "legacy_seed"),
        (3, "gallery_refit"),
        (4, "keeper_audit"),
    ]


def test_canonical_world_checksum_matches_keeper_record() -> None:
    """Verify all room, item, lock, NPC, and clue fields through a canonical database digest."""
    dump = subprocess.run(
        ["/app/tools/canonical_dump.sh", str(DB)],
        check=True,
        text=False,
        capture_output=True,
    ).stdout
    digest = hashlib.sha256(dump).hexdigest()
    assert digest == EXPECTED_WORLD_SHA256
    assert (ARTIFACTS / "world.dump").read_bytes() == dump
    assert (ARTIFACTS / "world.sha256").read_text().strip() == digest


def test_room_graph_is_reciprocal_and_connected() -> None:
    """Verify every playable exit has a reverse edge and every room is reachable."""
    directions = {"north": "south", "east": "west", "south": "north", "west": "east"}
    rows = query("SELECT id, north, east, south, west FROM rooms ORDER BY id")
    graph = {row[0]: dict(zip(directions, row[1:])) for row in rows}
    assert len(graph) == 11
    for source, exits in graph.items():
        for direction, destination in exits.items():
            if destination is not None:
                assert destination in graph
                assert graph[destination][directions[direction]] == source

    visited = {"vestibule"}
    queue = deque(visited)
    while queue:
        current = queue.popleft()
        for destination in graph[current].values():
            if destination is not None and destination not in visited:
                visited.add(destination)
                queue.append(destination)
    assert visited == set(graph)


def test_item_lock_chain_is_structurally_usable() -> None:
    """Verify each canonical item targets one lock and every lock consumes that exact relation."""
    items = query("SELECT id, room_id, unlocks, reusable FROM items ORDER BY id")
    locks = query("SELECT id, room_id, requires_item, opens_flag FROM locks ORDER BY id")
    assert len(items) == len(locks) == 8
    item_by_id = {row[0]: row for row in items}
    lock_by_id = {row[0]: row for row in locks}
    assert set(item_by_id) == {row[2] for row in locks}
    for item_id, _, unlocks, reusable in items:
        assert unlocks in lock_by_id
        assert lock_by_id[unlocks][2] == item_id
        assert reusable in (0, 1)


def test_npc_gates_reference_real_lock_outcomes() -> None:
    """Verify encounter gates are produced by locks and dialogue state symbols are unique."""
    open_flags = {row[0] for row in query("SELECT opens_flag FROM locks")}
    npcs = query("SELECT id, gate_flag, dialogue_flag, grants_flag FROM npcs ORDER BY id")
    assert len(npcs) == 7
    assert {row[1] for row in npcs} <= open_flags
    assert len({row[2] for row in npcs}) == len(npcs)
    assert len({row[3] for row in npcs}) == len(npcs)


def test_performance_beats_form_a_complete_dependency_chain() -> None:
    """Verify all twelve endgame beats use real subjects and only available state flags."""
    rows = query(
        "SELECT position, room_id, action, subject_id, requires_flag, emits_flag "
        "FROM beats ORDER BY position"
    )
    assert len(rows) == 12
    assert [row[0] for row in rows] == list(range(1, 13))
    room_ids = {row[0] for row in query("SELECT id FROM rooms")}
    subject_ids = (
        {row[0] for row in query("SELECT id FROM items")}
        | {row[0] for row in query("SELECT id FROM npcs")}
        | {row[0] for row in query("SELECT id FROM clues")}
    )
    available_flags = (
        {row[0] for row in query("SELECT opens_flag FROM locks")}
        | {row[0] for row in query("SELECT grants_flag FROM npcs")}
    )
    emitted_flags = set()
    for _, room_id, action, subject_id, requires_flag, emits_flag in rows:
        assert room_id in room_ids
        assert action and action.replace("_", "").isalpha()
        assert subject_id in subject_ids
        assert requires_flag in available_flags | emitted_flags
        assert emits_flag not in available_flags | emitted_flags
        emitted_flags.add(emits_flag)
    assert rows[-1][-1] == "crypt_open"


def test_clue_records_form_a_complete_atlas_contract() -> None:
    """Verify clue slots, rotations, mattes, and source references are well-formed."""
    rows = query("SELECT source, position, rotation, matte FROM clues ORDER BY position")
    assert len(rows) == 9
    assert [row[1] for row in rows] == list(range(1, 10))
    assert {row[2] for row in rows} <= {0, 90, 180, 270}
    for source, _, _, matte in rows:
        assert (APP / "assets/clues" / source).is_file()
        assert len(matte) == 7 and matte.startswith("#")
        int(matte[1:], 16)


def test_image_pipeline_emits_nine_normalized_tiles() -> None:
    """Verify ImageMagick created a gapless 3x3 atlas and nine distinct 64px thumbnails."""
    atlas = ARTIFACTS / "clue_atlas.png"
    assert subprocess.run(
        ["identify", "-format", "%wx%h", str(atlas)],
        check=True,
        text=True,
        capture_output=True,
    ).stdout == "192x192"
    thumbnails = sorted((ARTIFACTS / "thumbnails").glob("*.png"))
    assert len(thumbnails) == 9
    pixel_digests = set()
    for thumbnail in thumbnails:
        assert subprocess.run(
            ["identify", "-format", "%wx%h", str(thumbnail)],
            check=True,
            text=True,
            capture_output=True,
        ).stdout == "64x64"
        rgba = subprocess.run(
            ["convert", str(thumbnail), "rgba:-"],
            check=True,
            capture_output=True,
        ).stdout
        pixel_digests.add(hashlib.sha256(rgba).hexdigest())
    assert len(pixel_digests) == 9


def test_normalized_atlas_checksum_matches_keeper_record() -> None:
    """Verify clue order and visual treatment through the normalized RGBA pixel digest."""
    rgba = subprocess.run(
        ["convert", str(ARTIFACTS / "clue_atlas.png"), "rgba:-"],
        check=True,
        capture_output=True,
    ).stdout
    digest = hashlib.sha256(rgba).hexdigest()
    assert digest == EXPECTED_ATLAS_RGBA_SHA256
    assert (ARTIFACTS / "atlas.rgba.sha256").read_text().strip() == digest


def test_terminal_query_interface_uses_the_rebuilt_database() -> None:
    """Verify the public CLI reads canonical generated state and can traverse to the ending."""
    summary = subprocess.run(
        ["/app/bin/clockwork-crypt", "summary"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    assert summary == "rooms=11|items=8|locks=8|npcs=7|clues=9|beats=12"
    route = subprocess.run(
        [
            "/app/bin/clockwork-crypt",
            "route",
            "vestibule",
            "east",
            "north",
            "east",
            "north",
            "east",
            "east",
            "north",
            "east",
        ],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    assert route == "keeper"
    beat = subprocess.run(
        ["/app/bin/clockwork-crypt", "beat", "12"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    assert beat == (
        "12|room=clockheart|action=chime|subject=heart|"
        "requires=keeper_seal_set|emits=crypt_open"
    )


def test_keeper_circuit_is_the_shortest_canonical_all_room_walk() -> None:
    """Verify the release circuit is computed, persisted, and exposed by the public CLI."""
    result = subprocess.run(
        ["/app/bin/clockwork-crypt", "circuit"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    assert result == EXPECTED_CIRCUIT
    assert (ARTIFACTS / "keeper.circuit").read_text() == EXPECTED_CIRCUIT
    digest = hashlib.sha256(EXPECTED_CIRCUIT.encode()).hexdigest()
    assert (ARTIFACTS / "keeper.circuit.sha256").read_text().strip() == digest


def test_keeper_circuit_tracks_visited_sets_and_direction_ties(tmp_path: Path) -> None:
    """Verify the planner handles revisits and north-first ties on a different room graph."""
    database = tmp_path / "fork.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE rooms (id TEXT PRIMARY KEY, north TEXT, east TEXT, south TEXT, west TEXT)"
        )
        connection.executemany(
            "INSERT INTO rooms VALUES (?, ?, ?, ?, ?)",
            [
                ("center", "north_leaf", "goal", "south_leaf", None),
                ("north_leaf", None, None, "center", None),
                ("south_leaf", "center", None, None, None),
                ("goal", None, None, None, "center"),
            ],
        )
    result = subprocess.run(
        ["lua5.4", "/app/game/keeper_circuit.lua", str(database), "center", "goal"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    assert result == (
        "steps=5\n"
        "shortest_walks=2\n"
        "moves=north,south,south,north,east\n"
        "rooms=center,north_leaf,center,south_leaf,center,goal\n"
    )


def test_keeper_circuit_rejects_an_unreachable_goal(tmp_path: Path) -> None:
    """Verify an alternate disconnected graph fails instead of printing a partial route."""
    database = tmp_path / "disconnected.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE rooms (id TEXT PRIMARY KEY, north TEXT, east TEXT, south TEXT, west TEXT)"
        )
        connection.executemany(
            "INSERT INTO rooms VALUES (?, ?, ?, ?, ?)",
            [("start", None, None, None, None), ("goal", None, None, None, None)],
        )
    result = subprocess.run(
        ["lua5.4", "/app/game/keeper_circuit.lua", str(database), "start", "goal"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode != 0
    assert result.stdout == ""


def test_keeper_audit_recomputes_both_checksum_families() -> None:
    """Verify the audit independently recomputes world, visual, and circuit artifacts."""
    result = subprocess.run(
        ["/app/bin/keeper-audit"],
        check=False,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "keeper audit passed"
