"""Verifier for chamber escape route manifest."""

import json
import os
import subprocess
from pathlib import Path

import pytest

MANIFEST = Path("/app/output/route_manifest.json")
PID_FILE = Path("/tmp/chamberd.pid")


def _run_pipeline() -> None:
    proc = subprocess.run(
        ["bash", "/app/environment/scripts/run_escape.sh"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"run_escape failed ({proc.returncode}):\n{proc.stdout}\n{proc.stderr}"
        )


def _load_manifest() -> dict:
    assert MANIFEST.exists(), f"missing manifest at {MANIFEST}"
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def reference_digest16(text: str) -> str:
    digest_tool = "sha256sum"
    proc = subprocess.run(
        [digest_tool],
        input=text.encode("utf-8"),
        check=True,
        capture_output=True,
    )
    return proc.stdout.decode("ascii").split()[0][:16]


def _pids_with_title(title: str) -> list[int]:
    pids: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmdline = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        raw = cmdline.split(b"\0", 1)[0]
        try:
            first = raw.decode("utf-8")
        except UnicodeDecodeError:
            first = raw.decode("latin-1")
        base = first.rsplit("/", 1)[-1]
        if base == title or first == title:
            pids.append(int(entry.name))
    return pids


def _listen_port_for_pid(pid: int) -> int | None:
    try:
        out = subprocess.check_output(
            ["lsof", "-nP", "-a", "-p", str(pid), "-iTCP", "-sTCP:LISTEN"],
            text=True,
        )
    except subprocess.CalledProcessError:
        return None
    for line in out.splitlines():
        cols = line.split()
        if len(cols) < 9:
            continue
        addr = cols[8]
        if ":" not in addr:
            continue
        return int(addr.rsplit(":", 1)[1])
    return None


def reference_live_port() -> int:
    if PID_FILE.exists():
        pid_text = PID_FILE.read_text(encoding="utf-8").strip()
        if pid_text.isdigit():
            port = _listen_port_for_pid(int(pid_text))
            if port is not None:
                return port
    for pid in _pids_with_title("chamberd"):
        port = _listen_port_for_pid(pid)
        if port is not None:
            return port
    raise AssertionError("chamberd listener not found")


def reference_live_graph_path() -> str:
    pid = PID_FILE.read_text(encoding="utf-8").strip()
    fd_dir = Path(f"/proc/{pid}/fd")
    if fd_dir.is_dir():
        for entry in fd_dir.iterdir():
            try:
                target = os.readlink(entry)
            except OSError:
                continue
            if "/vault/graphs/" in target and target.endswith(".json"):
                return target
    trace = Path("/tmp/chamberd.trace")
    if trace.exists():
        for line in trace.read_bytes().decode("latin-1").splitlines():
            if "/vault/graphs/" not in line or ".json" not in line:
                continue
            start = line.find('"')
            while start != -1:
                end = line.find('"', start + 1)
                if end == -1:
                    break
                candidate = line[start + 1 : end]
                if "/vault/graphs/" in candidate and candidate.endswith(".json"):
                    return candidate
                start = line.find('"', end + 1)
    raise AssertionError("live graph path not found")


def reference_load_graph(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


@pytest.fixture(scope="module", autouse=True)
def _pipeline_once():
    if MANIFEST.exists():
        MANIFEST.unlink()
    _run_pipeline()
    yield


def test_manifest_top_level_keys():
    """Manifest exposes every required top-level field from the public contract."""
    manifest = _load_manifest()
    for key in (
        "schema_tag",
        "rooms",
        "moves",
        "api_evidence",
        "rooms_checksum",
        "moves_checksum",
        "evidence_checksum",
        "manifest_checksum",
    ):
        assert key in manifest


def test_schema_tag_value():
    """schema_tag must be the route_manifest_v1 identifier."""
    manifest = _load_manifest()
    assert manifest["schema_tag"] == "route_manifest_v1"


def test_api_evidence_object_keys():
    """api_evidence carries listener, graph, endpoint, and status fields."""
    manifest = _load_manifest()
    for key in ("listen_port", "graph_path", "endpoint", "status_code"):
        assert key in manifest["api_evidence"]


def test_rooms_and_moves_are_lists():
    """rooms and moves are ordered lists with at least one transition."""
    manifest = _load_manifest()
    assert isinstance(manifest["rooms"], list)
    assert isinstance(manifest["moves"], list)
    assert len(manifest["rooms"]) >= 2
    assert len(manifest["moves"]) >= 1


def test_checksum_fields_are_lowercase_hex16():
    """Each checksum field is a 16-character lowercase hex digest."""
    manifest = _load_manifest()
    for digest_key in (
        "rooms_checksum",
        "moves_checksum",
        "evidence_checksum",
        "manifest_checksum",
    ):
        assert len(manifest[digest_key]) == 16
        assert manifest[digest_key] == manifest[digest_key].lower()


def test_moves_length_matches_room_transitions():
    """moves.len equals rooms.len minus one per manifest_contract.md."""
    manifest = _load_manifest()
    assert len(manifest["moves"]) == len(manifest["rooms"]) - 1


def test_move_tokens_are_cardinal():
    """Every move token is one of the legal compass labels."""
    manifest = _load_manifest()
    for move in manifest["moves"]:
        assert move in ("N", "S", "E", "W")


def test_graph_path_points_at_vault_graph():
    """api_evidence.graph_path references a live vault graph JSON file."""
    manifest = _load_manifest()
    path = manifest["api_evidence"]["graph_path"]
    assert "/vault/graphs/" in path
    assert path.endswith(".json")
    assert Path(path).is_file()


def test_listen_port_is_positive_integer():
    """api_evidence.listen_port is a positive TCP port number."""
    manifest = _load_manifest()
    port = manifest["api_evidence"]["listen_port"]
    assert isinstance(port, int)
    assert 1 <= port <= 65535


def test_rooms_checksum_recomputes():
    """rooms_checksum matches the pipe-joined room digest formula."""
    manifest = _load_manifest()
    expected = reference_digest16("|".join(manifest["rooms"]))
    assert manifest["rooms_checksum"] == expected


def test_moves_checksum_recomputes():
    """moves_checksum matches the concatenated move digest formula."""
    manifest = _load_manifest()
    expected = reference_digest16("".join(manifest["moves"]))
    assert manifest["moves_checksum"] == expected


def test_evidence_checksum_recomputes():
    """evidence_checksum matches port, graph_path, and endpoint joined with pipes."""
    manifest = _load_manifest()
    ev = manifest["api_evidence"]
    expected = reference_digest16(
        f"{ev['listen_port']}|{ev['graph_path']}|{ev['endpoint']}"
    )
    assert manifest["evidence_checksum"] == expected


def test_manifest_checksum_recomputes():
    """manifest_checksum chains the three component checksum fields."""
    manifest = _load_manifest()
    expected = reference_digest16(
        f"{manifest['rooms_checksum']}|{manifest['moves_checksum']}|{manifest['evidence_checksum']}"
    )
    assert manifest["manifest_checksum"] == expected


def test_regenerated_listen_port_matches_live_service():
    """After delete-and-rerun, api_evidence still tracks the live listener."""
    MANIFEST.unlink()
    _run_pipeline()
    manifest = _load_manifest()
    assert manifest["api_evidence"]["listen_port"] == reference_live_port()


def test_rooms_reach_exit_on_live_graph():
    """Rooms form a start-to-exit walk on the graph file the live service has open."""
    manifest = _load_manifest()
    graph = reference_load_graph(reference_live_graph_path())
    rooms = manifest["rooms"]
    assert rooms[0] == graph["start"]
    assert rooms[-1] == graph["exit"]
    for cur, nxt in zip(rooms, rooms[1:]):
        edges = graph["rooms"][cur]
        assert nxt in edges.values()


def test_moves_match_room_edges():
    """Each move token is the labeled edge between consecutive rooms on the live graph."""
    manifest = _load_manifest()
    graph = reference_load_graph(reference_live_graph_path())
    rooms = manifest["rooms"]
    moves = manifest["moves"]
    assert len(moves) == len(rooms) - 1
    for i, move in enumerate(moves):
        assert move in ("N", "S", "E", "W")
        assert graph["rooms"][rooms[i]].get(move) == rooms[i + 1]


def test_api_evidence_listen_port_live():
    """api_evidence.listen_port matches the live chamberd TCP listener."""
    manifest = _load_manifest()
    assert manifest["api_evidence"]["listen_port"] == reference_live_port()


def test_api_evidence_graph_path_open():
    """api_evidence.graph_path matches the graph file opened by the live service."""
    manifest = _load_manifest()
    assert manifest["api_evidence"]["graph_path"] == reference_live_graph_path()


def test_endpoint_and_status_evidence():
    """api_evidence records a successful /v1/topology fetch."""
    manifest = _load_manifest()
    ev = manifest["api_evidence"]
    assert ev["endpoint"] == "/v1/topology"
    assert ev["status_code"] == 200


def test_pipeline_regenerates_manifest():
    """Deleting the manifest and rerunning the entrypoint regenerates a valid document."""
    assert MANIFEST.exists()
    MANIFEST.unlink()
    if MANIFEST.exists():
        raise AssertionError("manifest still present after delete")
    _run_pipeline()
    manifest = _load_manifest()
    assert manifest["schema_tag"] == "route_manifest_v1"
    assert len(manifest["rooms"]) >= 2
