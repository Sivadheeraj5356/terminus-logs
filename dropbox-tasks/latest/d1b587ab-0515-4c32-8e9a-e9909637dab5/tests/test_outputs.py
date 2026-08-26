import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
from collections import deque
from pathlib import Path

import pytest

APP = Path("/app")
GO = Path("/usr/local/go/bin/go")
GOROOT = Path("/usr/local/go")
PUBLIC_BOARD = APP / "boards" / "public.json"
PUBLIC_EXPECTED = Path("/tests/fixtures/public_expected.json")
PUBLIC_BOARD_SHA256 = "24adaf30cd28c5d00930d8fa04e742fd7f3837eddf226e6846fb820f54dbf9ba"
PUBLIC_EXPECTED_SHA256 = "978cb21d20391932d361e0c1a4f35d5fcb1680a59d1e46d34fcdb7d66e041aea"
CHROOT = Path("/usr/sbin/chroot")
JAIL_UID_GID = "65534:65534"
JAIL_GROUPS = "65534"
MAX_SOURCE_FILE_BYTES = 8 * 1024 * 1024
MAX_SOURCE_TREE_BYTES = 64 * 1024 * 1024

ROOT_KEYS = [
    "schema_version",
    "board_id",
    "status",
    "worst_turns",
    "worst_boosts",
    "worst_energy",
    "total_turns",
    "policy_nodes",
    "root",
    "nodes",
]
NODE_KEYS = [
    "id",
    "tick",
    "amber",
    "cobalt",
    "charges_left",
    "boosts_used",
    "energy",
    "belief",
    "terminal",
    "action",
    "branches",
]
ACTION_KEYS = ["amber", "cobalt"]
BRANCH_KEYS = ["observation", "next"]


def file_sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def go_build_env():
    env = os.environ.copy()
    env["CGO_ENABLED"] = "0"
    env["GOTOOLCHAIN"] = "local"
    return env


def _link_or_copy(source, destination):
    try:
        os.link(source, destination, follow_symlinks=False)
    except OSError:
        shutil.copy2(source, destination, follow_symlinks=False)


def _install_trusted_go_toolchain(build_root):
    destination = build_root / "usr" / "local" / "go"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        GOROOT,
        destination,
        symlinks=True,
        copy_function=_link_or_copy,
    )


def _copy_regular_source_tree(source_root, destination_root):
    """Copy agent files without following or preserving any agent-controlled link."""
    source_stat = os.lstat(source_root)
    if not stat.S_ISDIR(source_stat.st_mode):
        raise AssertionError("agent source root is not a regular directory")
    total_bytes = 0

    def copy_directory(source, destination, relative):
        nonlocal total_bytes
        destination.mkdir(mode=0o755)
        with os.scandir(source) as entries:
            for entry in sorted(entries, key=lambda item: item.name):
                item_relative = relative / entry.name
                item_stat = entry.stat(follow_symlinks=False)
                if stat.S_ISLNK(item_stat.st_mode):
                    raise AssertionError(f"agent source contains link: {item_relative}")
                if stat.S_ISDIR(item_stat.st_mode):
                    copy_directory(Path(entry.path), destination / entry.name, item_relative)
                    continue
                if not stat.S_ISREG(item_stat.st_mode):
                    raise AssertionError(
                        f"agent source contains non-regular file: {item_relative}"
                    )
                if item_stat.st_nlink != 1:
                    raise AssertionError(
                        f"agent source contains hard-linked file: {item_relative}"
                    )
                if item_stat.st_size > MAX_SOURCE_FILE_BYTES:
                    raise AssertionError(f"agent source file is too large: {item_relative}")
                total_bytes += item_stat.st_size
                if total_bytes > MAX_SOURCE_TREE_BYTES:
                    raise AssertionError("agent source tree is too large")

                flags = os.O_RDONLY | os.O_CLOEXEC
                flags |= getattr(os, "O_NOFOLLOW", 0)
                descriptor = os.open(entry.path, flags)
                try:
                    opened_stat = os.fstat(descriptor)
                    if (
                        not stat.S_ISREG(opened_stat.st_mode)
                        or opened_stat.st_nlink != 1
                        or opened_stat.st_dev != item_stat.st_dev
                        or opened_stat.st_ino != item_stat.st_ino
                    ):
                        raise AssertionError(
                            f"agent source changed during copy: {item_relative}"
                        )
                    target = destination / entry.name
                    with os.fdopen(os.dup(descriptor), "rb", closefd=True) as source_file:
                        with target.open("xb") as target_file:
                            shutil.copyfileobj(source_file, target_file, 1024 * 1024)
                    target.chmod(0o444)
                finally:
                    os.close(descriptor)

    copy_directory(source_root, destination_root, Path("."))


def _make_build_jail(tmp_path_factory):
    build_root = tmp_path_factory.mktemp("phaseglass-build-jail")
    build_root.chmod(0o755)
    _install_trusted_go_toolchain(build_root)
    for relative, mode in (
        ("dev", 0o755),
        ("output", 0o777),
        ("probe", 0o755),
        ("tmp", 0o777),
        ("tmp/gocache", 0o777),
        ("tmp/gotmp", 0o777),
        ("tmp/home", 0o777),
    ):
        directory = build_root / relative
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(mode)
    null_path = build_root / "dev" / "null"
    try:
        os.mknod(null_path, stat.S_IFCHR | 0o666, os.makedev(1, 3))
    except PermissionError:
        null_path.touch(mode=0o666)
    null_path.chmod(0o666)
    return build_root


def _run_in_build_jail(build_root, command, timeout=180):
    env = {
        "CGO_ENABLED": "0",
        "GOCACHE": "/tmp/gocache",
        "GOROOT": "/usr/local/go",
        "GOTELEMETRY": "off",
        "GOTOOLCHAIN": "local",
        "GOTMPDIR": "/tmp/gotmp",
        "HOME": "/tmp/home",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/local/go/bin",
        "TMPDIR": "/tmp/gotmp",
    }
    return subprocess.run(
        [
            str(CHROOT),
            f"--userspec={JAIL_UID_GID}",
            f"--groups={JAIL_GROUPS}",
            str(build_root),
            *command,
        ],
        text=True,
        capture_output=True,
        close_fds=True,
        start_new_session=True,
        timeout=timeout,
        env=env,
    )


@pytest.fixture(scope="session")
def secure_agent_build(tmp_path_factory, verifier_jail_probe):
    assert GO.exists(), "canonical Go toolchain is missing"
    assert GOROOT.is_dir(), "canonical Go root is missing"
    assert CHROOT.exists(), "verifier chroot helper is missing"
    version = subprocess.run(
        [str(GO), "version"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    assert "go version go1.24" in version

    build_root = _make_build_jail(tmp_path_factory)
    build_probe = build_root / "probe" / "check"
    shutil.copyfile(verifier_jail_probe, build_probe)
    build_probe.chmod(0o555)
    probe_proc = _run_in_build_jail(build_root, ["/probe/check"], timeout=30)
    assert probe_proc.returncode == 0, probe_proc.stderr
    assert probe_proc.stdout == ""

    workspace = build_root / "workspace"
    _copy_regular_source_tree(APP, workspace)
    build_proc = _run_in_build_jail(
        build_root,
        [
            "/usr/local/go/bin/go",
            "-C",
            "/workspace",
            "build",
            "-trimpath",
            "-buildvcs=false",
            "-o",
            "/output/phaseglass-duet",
            "./cmd/phaseglass-duet",
        ],
    )
    assert build_proc.returncode == 0, build_proc.stderr
    jailed_output = build_root / "output" / "phaseglass-duet"
    output_stat = os.lstat(jailed_output)
    assert stat.S_ISREG(output_stat.st_mode)
    assert output_stat.st_nlink == 1

    output = tmp_path_factory.mktemp("phaseglass-v3-bin") / "phaseglass-duet"
    shutil.copyfile(jailed_output, output)
    output.chmod(0o555)
    return {"binary": output, "build_probe_ok": True}


@pytest.fixture(scope="session")
def phaseglass_binary(secure_agent_build):
    return secure_agent_build["binary"]


@pytest.fixture(scope="session")
def verifier_jail_probe(tmp_path_factory):
    root = tmp_path_factory.mktemp("phaseglass-jail-probe")
    source = root / "main.go"
    source.write_text(
        r'''package main

import (
    "fmt"
    "os"
    "os/exec"
)

func blocked(path string) bool {
    file, err := os.Open(path)
    if err != nil {
        return true
    }
    file.Close()
    return false
}

func check() error {
    for _, path := range []string{
        "/tests",
        "/solution",
        "/proc/self/root/tests",
        "/proc/self/root/solution",
    } {
        if !blocked(path) {
            return fmt.Errorf("jail exposed %s", path)
        }
    }
    return nil
}

func main() {
    if err := check(); err != nil {
        fmt.Fprintln(os.Stderr, err)
        os.Exit(2)
    }
    if os.Getenv("PHASEGLASS_JAIL_CHILD") == "1" {
        return
    }
    child := exec.Command(os.Args[0])
    child.Stdin = os.Stdin
    child.Env = []string{"PHASEGLASS_JAIL_CHILD=1"}
    output, err := child.CombinedOutput()
    if err != nil {
        fmt.Fprintf(os.Stderr, "child jail check failed: %v: %s", err, output)
        os.Exit(3)
    }
}
'''
        + "\n",
        encoding="utf-8",
    )
    output = root / "jail-probe"
    subprocess.run(
        [str(GO), "build", "-o", str(output), str(source)],
        cwd=root,
        env=go_build_env(),
        check=True,
        text=True,
        capture_output=True,
    )
    output.chmod(0o555)
    return output


def make_jail(binary, tmp_path):
    jail = Path(tempfile.mkdtemp(prefix="phaseglass-verifier-jail-", dir=tmp_path))
    jail.chmod(0o755)
    for relative, mode in (("bin", 0o755), ("input", 0o755), ("output", 0o777)):
        directory = jail / relative
        directory.mkdir()
        directory.chmod(mode)
    jailed_binary = jail / "bin" / "phaseglass-duet"
    shutil.copyfile(binary, jailed_binary)
    jailed_binary.chmod(0o555)
    return jail


def run_in_jail(jail, arguments):
    env = {
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/bin",
    }
    return subprocess.run(
        [
            str(CHROOT),
            f"--userspec={JAIL_UID_GID}",
            f"--groups={JAIL_GROUPS}",
            str(jail),
            "/bin/phaseglass-duet",
            *arguments,
        ],
        text=True,
        capture_output=True,
        close_fds=True,
        start_new_session=True,
        timeout=120,
        env=env,
    )


def ensure_world_writable(directory, stop):
    current = directory
    while current != stop:
        current.chmod(0o777)
        current = current.parent


def run_board_path(binary, tmp_path, board_path, output_name="out/policy.json"):
    relative_output = Path(output_name)
    assert not relative_output.is_absolute()
    assert ".." not in relative_output.parts
    output_path = tmp_path / relative_output
    board_before = board_path.read_bytes()

    jail = make_jail(binary, tmp_path)
    jailed_board = jail / "input" / "board.json"
    jailed_board.write_bytes(board_before)
    jailed_board.chmod(0o444)
    jailed_output = jail / "output" / relative_output

    if output_path.exists():
        jailed_output.parent.mkdir(parents=True, exist_ok=True)
        ensure_world_writable(jailed_output.parent, jail / "output")
        jailed_output.write_bytes(output_path.read_bytes())
        jailed_output.chmod(0o666)

    proc = run_in_jail(
        jail,
        [
            "--board",
            "/input/board.json",
            "--output",
            f"/output/{relative_output.as_posix()}",
        ],
    )

    assert jailed_board.read_bytes() == board_before, "submitted binary modified its input"
    if jailed_output.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(jailed_output, output_path)
    return proc, board_path, output_path


def run_board(binary, tmp_path, board, output_name="out/policy.json"):
    board_path = tmp_path / "board.json"
    board_path.write_text(json.dumps(board, indent=2) + "\n", encoding="utf-8")
    return run_board_path(binary, tmp_path, board_path, output_name)


def read_result(path):
    raw = path.read_bytes()
    assert raw.endswith(b"\n")
    assert not raw.endswith(b"\n\n")
    parsed = json.loads(raw)
    canonical = json.dumps(parsed, indent=2, ensure_ascii=False) + "\n"
    assert raw.decode("utf-8") == canonical
    return parsed


def edge(
    edge_id,
    actor,
    source,
    target,
    *,
    cost=1,
    phase_mask="1",
    boostable=False,
    gate="",
    tone=0,
):
    return {
        "id": edge_id,
        "actor": actor,
        "from": source,
        "to": target,
        "cost": cost,
        "phase_mask": phase_mask,
        "boostable": boostable,
        "gate": gate,
        "tone": tone,
    }


def hidden(
    state_id,
    world,
    *,
    open_gates=None,
    accepting=True,
    signals=None,
    next_by_tone=None,
):
    raw_transitions = dict(next_by_tone or {"0": state_id, "1": state_id})
    transitions = {
        key: list(value) if isinstance(value, list) else [value]
        for key, value in raw_transitions.items()
    }
    return {
        "id": state_id,
        "world": world,
        "open_gates": list(open_gates or []),
        "accepting": accepting,
        "signals": dict(signals or {}),
        "next_by_tone": transitions,
    }


def make_board(
    board_id,
    *,
    rooms,
    start,
    goals,
    edges,
    hidden_states,
    initial_states,
    tether_links,
    beacons=None,
    period=2,
    max_turns=4,
    phase_charges=0,
    charge_cap=0,
    boost_surcharge=0,
    blocked_cost=1,
    tether_limit=1,
    tone_modulus=2,
):
    return {
        "schema_version": "phaseglass.board.v3",
        "board_id": board_id,
        "period": period,
        "max_turns": max_turns,
        "phase_charges": phase_charges,
        "charge_cap": charge_cap,
        "boost_surcharge": boost_surcharge,
        "blocked_cost": blocked_cost,
        "tether_limit": tether_limit,
        "tone_modulus": tone_modulus,
        "rooms": rooms,
        "start": start,
        "goals": goals,
        "edges": edges,
        "tether_links": tether_links,
        "beacons": [
            {**item, "tone": item.get("tone", 0)} for item in (beacons or [])
        ],
        "hidden_states": hidden_states,
        "initial_states": initial_states,
    }


def physical_distances(board):
    adjacency = {room: set() for room in board["rooms"]}
    for item in board["edges"]:
        adjacency[item["from"]].add(item["to"])
        adjacency[item["to"]].add(item["from"])
    for left, right in board["tether_links"]:
        adjacency[left].add(right)
        adjacency[right].add(left)
    result = {}
    for source in board["rooms"]:
        queue = deque([(source, 0)])
        seen = {source}
        while queue:
            room, distance = queue.popleft()
            result[(source, room)] = distance
            for neighbor in adjacency[room]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append((neighbor, distance + 1))
    return result


def parse_action(board, actor, room, tick, label, charges):
    phase = tick % board["period"]
    if label == "wait":
        return {"kind": "wait", "tone": 0, "boosts": 0}
    kind, item_id = label.split(":", 1)
    if kind == "listen":
        beacon = next(item for item in board["beacons"] if item["id"] == item_id)
        assert beacon["room"] == room
        return {
            "kind": "listen",
            "beacon": beacon,
            "tone": beacon["tone"],
            "boosts": 0,
        }
    assert kind in {"move", "boost"}
    item = next(edge_item for edge_item in board["edges"] if edge_item["id"] == item_id)
    assert item["actor"] in {actor, "either"}
    assert item["from"] == room
    is_open = item["phase_mask"][phase] == "1"
    if kind == "move":
        assert is_open
        boost_count = 0
    else:
        assert not is_open
        assert item["boostable"] is True
        assert charges > 0
        boost_count = 1
    return {
        "kind": kind,
        "edge": item,
        "tone": item["tone"],
        "boosts": boost_count,
    }


def apply_piece(board, hidden_state, parsed, room):
    kind = parsed["kind"]
    if kind == "wait":
        return room, "wait", 0, 0, 0
    if kind == "listen":
        beacon = parsed["beacon"]
        symbol = hidden_state["signals"][beacon["id"]]
        return (
            room,
            f"signal:{beacon['id']}={symbol}",
            beacon["listen_cost"],
            beacon["tone"],
            0,
        )
    item = parsed["edge"]
    gate_open = item["gate"] == "" or item["gate"] in hidden_state["open_gates"]
    surcharge = board["boost_surcharge"] if kind == "boost" else 0
    if gate_open:
        return (
            item["to"],
            f"moved:{item['id']}",
            item["cost"] + surcharge,
            item["tone"],
            parsed["boosts"],
        )
    return (
        room,
        f"blocked:{item['id']}",
        board["blocked_cost"] + surcharge,
        item["tone"],
        parsed["boosts"],
    )


def simulate_node(board, node):
    hidden_by_id = {item["id"]: item for item in board["hidden_states"]}
    distances = physical_distances(board)
    amber_action = parse_action(
        board,
        "amber",
        node["amber"],
        node["tick"],
        node["action"]["amber"],
        node["charges_left"],
    )
    cobalt_action = parse_action(
        board,
        "cobalt",
        node["cobalt"],
        node["tick"],
        node["action"]["cobalt"],
        node["charges_left"],
    )
    boost_attempts = amber_action["boosts"] + cobalt_action["boosts"]
    assert boost_attempts <= node["charges_left"]
    groups = {}
    for hidden_id in node["belief"]:
        current = hidden_by_id[hidden_id]
        a_room, a_component, a_energy, a_tone, a_boost = apply_piece(
            board, current, amber_action, node["amber"]
        )
        c_room, c_component, c_energy, c_tone, c_boost = apply_piece(
            board, current, cobalt_action, node["cobalt"]
        )
        assert a_room != c_room
        assert not (a_room == node["cobalt"] and c_room == node["amber"])
        assert distances.get((a_room, c_room), 10**9) <= board["tether_limit"]
        tone = (a_tone + c_tone) % board["tone_modulus"]
        next_hidden_set = current["next_by_tone"][str(tone)]
        observation = f"amber={a_component};cobalt={c_component}"
        successor = {
            "tick": node["tick"] + 1,
            "amber": a_room,
            "cobalt": c_room,
            "charges_left": node["charges_left"] - a_boost - c_boost,
            "boosts_used": node["boosts_used"] + a_boost + c_boost,
            "energy": node["energy"] + a_energy + c_energy,
        }
        if observation not in groups:
            groups[observation] = {**successor, "belief": []}
        else:
            for name, value in successor.items():
                assert groups[observation][name] == value
        groups[observation]["belief"].extend(next_hidden_set)
    for successor in groups.values():
        successor["belief"] = sorted(set(successor["belief"]))
    return groups


def replay_and_check(board, result):
    assert list(result.keys()) == ROOT_KEYS
    assert result["schema_version"] == "phaseglass.policy.v3"
    assert result["board_id"] == board["board_id"]
    for name in [
        "worst_turns",
        "worst_boosts",
        "worst_energy",
        "total_turns",
        "policy_nodes",
    ]:
        assert type(result[name]) is int
    assert isinstance(result["nodes"], list)

    if result["status"] == "unsolved":
        assert result["worst_turns"] == 0
        assert result["worst_boosts"] == 0
        assert result["worst_energy"] == 0
        assert result["total_turns"] == 0
        assert result["policy_nodes"] == 0
        assert result["root"] == ""
        assert result["nodes"] == []
        return

    assert result["status"] == "solved"
    assert result["root"] == "N0"
    assert result["policy_nodes"] == len(result["nodes"])
    assert result["policy_nodes"] > 0
    nodes = result["nodes"]
    node_by_id = {}
    state_to_id = {}
    for index, node in enumerate(nodes):
        assert list(node.keys()) == NODE_KEYS
        assert node["id"] == f"N{index}"
        assert node["id"] not in node_by_id
        node_by_id[node["id"]] = node
        for name in ["tick", "charges_left", "boosts_used", "energy"]:
            assert type(node[name]) is int
        assert type(node["terminal"]) is bool
        assert isinstance(node["belief"], list)
        assert node["belief"] == sorted(node["belief"])
        assert len(node["belief"]) == len(set(node["belief"]))
        state_key = (
            node["tick"],
            node["amber"],
            node["cobalt"],
            node["charges_left"],
            node["boosts_used"],
            node["energy"],
            tuple(node["belief"]),
        )
        assert state_key not in state_to_id
        state_to_id[state_key] = node["id"]
        assert isinstance(node["branches"], list)
        observations = [branch["observation"] for branch in node["branches"]]
        assert observations == sorted(observations)
        assert len(observations) == len(set(observations))
        for branch in node["branches"]:
            assert list(branch.keys()) == BRANCH_KEYS
            assert isinstance(branch["observation"], str)
            assert isinstance(branch["next"], str)
        if node["terminal"]:
            assert node["action"] is None
            assert node["branches"] == []
        else:
            assert list(node["action"].keys()) == ACTION_KEYS
            assert isinstance(node["action"]["amber"], str)
            assert isinstance(node["action"]["cobalt"], str)
            assert node["branches"]

    # Canonical breadth-first numbering.
    queue = deque(["N0"])
    seen = {"N0"}
    expected_next = 1
    while queue:
        node_id = queue.popleft()
        for branch in node_by_id[node_id]["branches"]:
            child_id = branch["next"]
            assert child_id in node_by_id
            if child_id not in seen:
                assert child_id == f"N{expected_next}"
                expected_next += 1
                seen.add(child_id)
                queue.append(child_id)
    assert len(seen) == len(nodes)

    # Every node's complete branch partition and child snapshot is replayed.
    hidden_by_id = {item["id"]: item for item in board["hidden_states"]}
    for node in nodes:
        for hidden_id in node["belief"]:
            assert hidden_id in hidden_by_id
        if node["terminal"]:
            assert node["amber"] == board["goals"]["amber"]
            assert node["cobalt"] == board["goals"]["cobalt"]
            assert all(hidden_by_id[item]["accepting"] for item in node["belief"])
            continue
        expected_groups = simulate_node(board, node)
        assert [branch["observation"] for branch in node["branches"]] == sorted(
            expected_groups
        )
        for branch in node["branches"]:
            expected = expected_groups[branch["observation"]]
            child = node_by_id[branch["next"]]
            for name in [
                "tick",
                "amber",
                "cobalt",
                "charges_left",
                "boosts_used",
                "energy",
                "belief",
            ]:
                assert child[name] == expected[name]

    # Explore every initial world and every adversarial hidden successor.
    initial_node = node_by_id["N0"]
    assert initial_node["belief"] == sorted(board["initial_states"])
    terminal_metrics = []
    world_worst_turn = {}
    reached_beliefs = {node_id: set() for node_id in node_by_id}
    pending = deque(("N0", hidden_id) for hidden_id in board["initial_states"])
    visited = set()
    while pending:
        node_id, hidden_id = pending.popleft()
        visit_key = (node_id, hidden_id)
        if visit_key in visited:
            continue
        visited.add(visit_key)
        node = node_by_id[node_id]
        reached_beliefs[node_id].add(hidden_id)
        assert hidden_id in node["belief"]
        world = hidden_by_id[hidden_id]["world"]
        if node["terminal"]:
            terminal_metrics.append(
                (node["tick"], node["boosts_used"], node["energy"])
            )
            world_worst_turn[world] = max(
                world_worst_turn.get(world, 0), node["tick"]
            )
            continue
        groups = simulate_node(board, {**node, "belief": [hidden_id]})
        assert len(groups) == 1
        observation, successor = next(iter(groups.items()))
        branch = next(
            item for item in node["branches"] if item["observation"] == observation
        )
        child_id = branch["next"]
        assert node_by_id[child_id]["tick"] <= board["max_turns"]
        for next_hidden in successor["belief"]:
            pending.append((child_id, next_hidden))
    for node_id, reached in reached_beliefs.items():
        assert reached
        assert node_by_id[node_id]["belief"] == sorted(reached)
    initial_worlds = {
        hidden_by_id[hidden_id]["world"] for hidden_id in board["initial_states"]
    }
    assert set(world_worst_turn) == initial_worlds
    assert result["worst_turns"] == max(item[0] for item in terminal_metrics)
    assert result["worst_boosts"] == max(item[1] for item in terminal_metrics)
    assert result["worst_energy"] == max(item[2] for item in terminal_metrics)
    assert result["total_turns"] == sum(world_worst_turn.values())


def single_world_state(
    *, state_id="s0", world="w", accepting=True, gates=None, beacons=None, nexts=None
):
    signals = {item["id"]: "same" for item in beacons or []}
    return hidden(
        state_id,
        world,
        open_gates=gates,
        accepting=accepting,
        signals=signals,
        next_by_tone=nexts or {"0": state_id, "1": state_id},
    )


def test_verifier_build_and_runtime_jails_hide_private_mounts(
    secure_agent_build, verifier_jail_probe, tmp_path
):
    """Build and runtime process trees cannot see tests, solution, or proc escapes."""
    assert secure_agent_build["build_probe_ok"] is True
    jail = make_jail(verifier_jail_probe, tmp_path)
    proc = run_in_jail(jail, [])
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == ""


@pytest.mark.parametrize("link_kind", ["file_symlink", "directory_symlink", "hardlink"])
def test_verifier_source_copy_rejects_agent_links(tmp_path, link_kind):
    """No agent-controlled file or directory link can enter the build workspace."""
    source = tmp_path / "source"
    source.mkdir()
    (source / "go.mod").write_text("module example\n\ngo 1.24\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    target = outside / "oracle.go"
    target.write_text("package main\n", encoding="utf-8")
    if link_kind == "file_symlink":
        (source / "main.go").symlink_to(target)
    elif link_kind == "directory_symlink":
        (source / "cmd").symlink_to(outside, target_is_directory=True)
    else:
        os.link(target, source / "main.go")
    with pytest.raises(AssertionError, match="link"):
        _copy_regular_source_tree(source, tmp_path / "copy")



def test_public_policy_exact_and_fixture_integrity(phaseglass_binary, tmp_path):
    assert file_sha256(PUBLIC_BOARD) == PUBLIC_BOARD_SHA256
    assert file_sha256(PUBLIC_EXPECTED) == PUBLIC_EXPECTED_SHA256
    board_before = PUBLIC_BOARD.read_bytes()
    expected_before = PUBLIC_EXPECTED.read_bytes()
    proc, _, output = run_board_path(
        phaseglass_binary, tmp_path, PUBLIC_BOARD, "public/policy.json"
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == ""
    assert output.read_bytes() == expected_before
    result = read_result(output)
    board = json.loads(board_before)
    replay_and_check(board, result)
    assert result["worst_turns"] == 3
    assert result["policy_nodes"] == 13
    assert len(result["nodes"][0]["branches"]) == 4
    assert result["nodes"][5]["belief"] == ["w3-a", "w3-b"]
    assert PUBLIC_BOARD.read_bytes() == board_before
    assert PUBLIC_EXPECTED.read_bytes() == expected_before
    assert file_sha256(PUBLIC_BOARD) == PUBLIC_BOARD_SHA256
    assert file_sha256(PUBLIC_EXPECTED) == PUBLIC_EXPECTED_SHA256


def test_mutated_runtime_ids_still_build_four_world_policy(phaseglass_binary, tmp_path):
    board = json.loads(PUBLIC_BOARD.read_text(encoding="utf-8"))
    suffix = "-q9"
    room_map = {item: item + suffix for item in board["rooms"]}
    edge_map = {item["id"]: item["id"] + suffix for item in board["edges"]}
    beacon_map = {item["id"]: item["id"] + suffix for item in board["beacons"]}
    state_map = {item["id"]: item["id"] + suffix for item in board["hidden_states"]}
    gate_values = {item["gate"] for item in board["edges"] if item["gate"]}
    gate_map = {item: item + suffix for item in gate_values}
    board["board_id"] = "mutated-quadrants-q9"
    board["rooms"] = [room_map[item] for item in board["rooms"]]
    for pair_name in ["start", "goals"]:
        for actor in ["amber", "cobalt"]:
            board[pair_name][actor] = room_map[board[pair_name][actor]]
    for item in board["edges"]:
        item["id"] = edge_map[item["id"]]
        item["from"] = room_map[item["from"]]
        item["to"] = room_map[item["to"]]
        if item["gate"]:
            item["gate"] = gate_map[item["gate"]]
    board["tether_links"] = [
        [room_map[left], room_map[right]] for left, right in board["tether_links"]
    ]
    for item in board["beacons"]:
        old = item["id"]
        item["id"] = beacon_map[old]
        item["room"] = room_map[item["room"]]
    for item in board["hidden_states"]:
        old_signals = item["signals"]
        item["id"] = state_map[item["id"]]
        item["open_gates"] = [gate_map[value] for value in item["open_gates"]]
        item["signals"] = {
            beacon_map[key]: value + suffix for key, value in old_signals.items()
        }
        item["next_by_tone"] = {
            key: [state_map[value] for value in values]
            for key, values in item["next_by_tone"].items()
        }
    board["initial_states"] = [state_map[item] for item in board["initial_states"]]
    proc, _, output = run_board(phaseglass_binary, tmp_path, board)
    assert proc.returncode == 0, proc.stderr
    result = read_result(output)
    replay_and_check(board, result)
    assert result["worst_turns"] == 3
    root = result["nodes"][0]
    assert root["action"] == {
        "amber": "listen:alpha-q9",
        "cobalt": "listen:beta-q9",
    }
    assert len(root["branches"]) == 4


def test_adversarial_drift_expands_one_world_belief(phaseglass_binary, tmp_path):
    beacons = [{"id": "fork", "room": "A0", "listen_cost": 1}]
    states = [
        hidden(
            "seed",
            "w",
            accepting=False,
            signals={"fork": "blind"},
            next_by_tone={"0": ["left", "right"], "1": ["seed"]},
        ),
        hidden(
            "left",
            "w",
            open_gates=["gl"],
            accepting=True,
            signals={"fork": "left"},
            next_by_tone={"0": ["left"], "1": ["left"]},
        ),
        hidden(
            "right",
            "w",
            open_gates=["gr"],
            accepting=True,
            signals={"fork": "right"},
            next_by_tone={"0": ["right"], "1": ["right"]},
        ),
    ]
    board = make_board(
        "adversarial-drift",
        rooms=["A0", "AG", "C0", "CG"],
        start={"amber": "A0", "cobalt": "C0"},
        goals={"amber": "AG", "cobalt": "CG"},
        edges=[
            edge("a-left", "amber", "A0", "AG", gate="gl", phase_mask="111"),
            edge("c-left", "cobalt", "C0", "CG", gate="gl", phase_mask="111"),
            edge("a-right", "amber", "A0", "AG", gate="gr", phase_mask="111"),
            edge("c-right", "cobalt", "C0", "CG", gate="gr", phase_mask="111"),
        ],
        hidden_states=states,
        initial_states=["seed"],
        tether_links=[["A0", "C0"], ["AG", "CG"]],
        beacons=beacons,
        max_turns=3,
        period=3,
    )
    proc, _, output = run_board(phaseglass_binary, tmp_path, board)
    assert proc.returncode == 0, proc.stderr
    result = read_result(output)
    replay_and_check(board, result)
    assert result["worst_turns"] == 3
    root = result["nodes"][0]
    assert root["action"] == {"amber": "wait", "cobalt": "wait"}
    drift_node = result["nodes"][1]
    assert drift_node["belief"] == ["left", "right"]
    assert drift_node["action"] == {"amber": "listen:fork", "cobalt": "wait"}
    assert len(drift_node["branches"]) == 2


def test_canonical_dag_reuses_reconverged_information_state(phaseglass_binary, tmp_path):
    beacons = [{"id": "merge", "room": "CG", "listen_cost": 1, "tone": 1}]
    states = [
        hidden(
            "seed",
            "w",
            accepting=False,
            signals={"merge": "blind"},
            next_by_tone={"0": ["left", "right"], "1": ["seed"]},
        ),
        hidden(
            "left",
            "w",
            accepting=False,
            signals={"merge": "left"},
            next_by_tone={"0": ["left"], "1": ["merged"]},
        ),
        hidden(
            "right",
            "w",
            accepting=False,
            signals={"merge": "right"},
            next_by_tone={"0": ["right"], "1": ["merged"]},
        ),
        hidden(
            "merged",
            "w",
            accepting=True,
            signals={"merge": "done"},
            next_by_tone={"0": ["merged"], "1": ["merged"]},
        ),
    ]
    board = make_board(
        "reconverged-dag",
        rooms=["AG", "AX", "CG"],
        start={"amber": "AG", "cobalt": "CG"},
        goals={"amber": "AG", "cobalt": "CG"},
        edges=[
            edge(
                "sealed-tone",
                "amber",
                "AG",
                "AX",
                gate="sealed",
                tone=1,
                phase_mask="11",
            )
        ],
        hidden_states=states,
        initial_states=["seed"],
        tether_links=[["AG", "CG"], ["AX", "CG"]],
        beacons=beacons,
        max_turns=2,
    )
    proc, _, output = run_board(phaseglass_binary, tmp_path, board)
    assert proc.returncode == 0, proc.stderr
    result = read_result(output)
    replay_and_check(board, result)
    assert result["policy_nodes"] == 3
    fork = result["nodes"][1]
    assert fork["belief"] == ["left", "right"]
    assert fork["action"] == {
        "amber": "wait",
        "cobalt": "listen:merge",
    }
    assert len(fork["branches"]) == 2
    assert {branch["next"] for branch in fork["branches"]} == {"N2"}
    assert result["nodes"][2]["belief"] == ["merged"]


def test_signal_is_read_before_hidden_tone_transition(phaseglass_binary, tmp_path):
    beacons = [{"id": "eye", "room": "C0", "listen_cost": 1}]
    states = [
        hidden(
            "w1-old",
            "w1",
            accepting=False,
            signals={"eye": "left"},
            next_by_tone={"0": "w1-old", "1": "w1-new"},
        ),
        hidden(
            "w1-new",
            "w1",
            open_gates=["g1"],
            accepting=True,
            signals={"eye": "same"},
            next_by_tone={"0": "w1-new", "1": "w1-new"},
        ),
        hidden(
            "w2-old",
            "w2",
            accepting=False,
            signals={"eye": "right"},
            next_by_tone={"0": "w2-old", "1": "w2-new"},
        ),
        hidden(
            "w2-new",
            "w2",
            open_gates=["g2"],
            accepting=True,
            signals={"eye": "same"},
            next_by_tone={"0": "w2-new", "1": "w2-new"},
        ),
    ]
    board = make_board(
        "pretransition-signal",
        rooms=["A0", "A1", "AG", "C0"],
        start={"amber": "A0", "cobalt": "C0"},
        goals={"amber": "AG", "cobalt": "C0"},
        edges=[
            edge("tone-step", "amber", "A0", "A1", phase_mask="11", tone=1),
            edge("exit-left", "amber", "A1", "AG", gate="g1", phase_mask="11"),
            edge("exit-right", "amber", "A1", "AG", gate="g2", phase_mask="11"),
        ],
        hidden_states=states,
        initial_states=["w1-old", "w2-old"],
        tether_links=[["A0", "C0"], ["A1", "C0"], ["AG", "C0"]],
        beacons=beacons,
        max_turns=2,
    )
    proc, _, output = run_board(phaseglass_binary, tmp_path, board)
    assert proc.returncode == 0, proc.stderr
    result = read_result(output)
    replay_and_check(board, result)
    root = result["nodes"][0]
    assert root["action"] == {"amber": "move:tone-step", "cobalt": "listen:eye"}
    observations = [branch["observation"] for branch in root["branches"]]
    assert observations == [
        "amber=moved:tone-step;cobalt=signal:eye=left",
        "amber=moved:tone-step;cobalt=signal:eye=right",
    ]
    beliefs = [result["nodes"][int(branch["next"][1:])]["belief"] for branch in root["branches"]]
    assert beliefs == [["w1-new"], ["w2-new"]]

def test_goal_positions_do_not_count_until_hidden_state_accepts(phaseglass_binary, tmp_path):
    states = [
        hidden(
            "locked",
            "w",
            accepting=False,
            next_by_tone={"0": "locked", "1": "accepted"},
        ),
        hidden(
            "accepted",
            "w",
            accepting=True,
            next_by_tone={"0": "accepted", "1": "accepted"},
        ),
    ]
    board = make_board(
        "accepting-required",
        rooms=["AG", "AX", "CG"],
        start={"amber": "AG", "cobalt": "CG"},
        goals={"amber": "AG", "cobalt": "CG"},
        edges=[edge("closed-tone", "amber", "AG", "AX", gate="sealed", tone=1, phase_mask="11")],
        hidden_states=states,
        initial_states=["locked"],
        tether_links=[["AG", "CG"], ["AX", "CG"]],
        max_turns=1,
    )
    proc, _, output = run_board(phaseglass_binary, tmp_path, board)
    assert proc.returncode == 0, proc.stderr
    result = read_result(output)
    replay_and_check(board, result)
    assert result["worst_turns"] == 1
    assert result["nodes"][0]["action"] == {
        "amber": "move:closed-tone",
        "cobalt": "wait",
    }
    assert result["nodes"][0]["branches"][0]["observation"].startswith(
        "amber=blocked:closed-tone"
    )


def test_blocked_boost_consumes_charge_and_still_drives_tone(phaseglass_binary, tmp_path):
    states = [
        hidden(
            "sleep",
            "w",
            accepting=False,
            next_by_tone={"0": "sleep", "1": "awake"},
        ),
        hidden(
            "awake",
            "w",
            accepting=True,
            next_by_tone={"0": "awake", "1": "awake"},
        ),
    ]
    board = make_board(
        "blocked-boost-tone",
        rooms=["AG", "AX", "CG"],
        start={"amber": "AG", "cobalt": "CG"},
        goals={"amber": "AG", "cobalt": "CG"},
        edges=[
            edge(
                "closed-boost",
                "amber",
                "AG",
                "AX",
                gate="sealed",
                tone=1,
                phase_mask="01",
                boostable=True,
            )
        ],
        hidden_states=states,
        initial_states=["sleep"],
        tether_links=[["AG", "CG"], ["AX", "CG"]],
        max_turns=1,
        phase_charges=1,
        charge_cap=1,
        boost_surcharge=3,
        blocked_cost=2,
    )
    proc, _, output = run_board(phaseglass_binary, tmp_path, board)
    assert proc.returncode == 0, proc.stderr
    result = read_result(output)
    replay_and_check(board, result)
    terminal = result["nodes"][1]
    assert terminal["charges_left"] == 0
    assert terminal["boosts_used"] == 1
    assert terminal["energy"] == 5


def test_zero_turn_accepting_belief_is_one_terminal_node(phaseglass_binary, tmp_path):
    state = single_world_state(accepting=True)
    board = make_board(
        "zero-turn-accepting",
        rooms=["AG", "CG"],
        start={"amber": "AG", "cobalt": "CG"},
        goals={"amber": "AG", "cobalt": "CG"},
        edges=[],
        hidden_states=[state],
        initial_states=["s0"],
        tether_links=[["AG", "CG"]],
        max_turns=0,
    )
    proc, _, output = run_board(phaseglass_binary, tmp_path, board)
    assert proc.returncode == 0, proc.stderr
    result = read_result(output)
    replay_and_check(board, result)
    assert result["worst_turns"] == 0
    assert result["total_turns"] == 0
    assert result["policy_nodes"] == 1
    assert result["nodes"][0]["terminal"] is True


def test_indistinguishable_conflicting_worlds_are_unsolved(phaseglass_binary, tmp_path):
    states = [
        hidden(
            "w1-start",
            "w1",
            accepting=False,
            next_by_tone={"0": "w1-start", "1": "w1-ok", "2": "w1-dead"},
        ),
        hidden(
            "w1-ok",
            "w1",
            accepting=True,
            next_by_tone={"0": "w1-ok", "1": "w1-ok", "2": "w1-ok"},
        ),
        hidden(
            "w1-dead",
            "w1",
            accepting=False,
            next_by_tone={"0": "w1-dead", "1": "w1-dead", "2": "w1-dead"},
        ),
        hidden(
            "w2-start",
            "w2",
            accepting=False,
            next_by_tone={"0": "w2-start", "1": "w2-dead", "2": "w2-ok"},
        ),
        hidden(
            "w2-ok",
            "w2",
            accepting=True,
            next_by_tone={"0": "w2-ok", "1": "w2-ok", "2": "w2-ok"},
        ),
        hidden(
            "w2-dead",
            "w2",
            accepting=False,
            next_by_tone={"0": "w2-dead", "1": "w2-dead", "2": "w2-dead"},
        ),
    ]
    board = make_board(
        "conflicting-hidden-tones",
        rooms=["AG", "AX", "AY", "CG"],
        start={"amber": "AG", "cobalt": "CG"},
        goals={"amber": "AG", "cobalt": "CG"},
        edges=[
            edge("tone-one", "amber", "AG", "AX", gate="closed1", tone=1, phase_mask="111"),
            edge("tone-two", "amber", "AG", "AY", gate="closed2", tone=2, phase_mask="111"),
        ],
        hidden_states=states,
        initial_states=["w1-start", "w2-start"],
        tether_links=[["AG", "CG"], ["AX", "CG"], ["AY", "CG"]],
        max_turns=1,
        period=3,
        tone_modulus=3,
    )
    proc, _, output = run_board(phaseglass_binary, tmp_path, board)
    assert proc.returncode == 0, proc.stderr
    result = read_result(output)
    assert result["status"] == "unsolved"
    replay_and_check(board, result)


def test_universal_safety_rejects_informative_mixed_gate_attempt(phaseglass_binary, tmp_path):
    beacons = [{"id": "which", "room": "A0", "listen_cost": 5}]
    states = [
        hidden(
            "left",
            "w1",
            open_gates=["a1", "c1", "c2"],
            signals={"which": "left"},
        ),
        hidden(
            "right",
            "w2",
            open_gates=["c1", "a2", "c2"],
            signals={"which": "right"},
        ),
    ]
    board = make_board(
        "unsafe-information",
        rooms=["A0", "AG", "C0", "CG"],
        start={"amber": "A0", "cobalt": "C0"},
        goals={"amber": "AG", "cobalt": "CG"},
        edges=[
            edge("a-pair1", "amber", "A0", "AG", gate="a1", phase_mask="11"),
            edge("c-pair1", "cobalt", "C0", "CG", gate="c1", phase_mask="11"),
            edge("a-pair2", "amber", "A0", "AG", gate="a2", phase_mask="11"),
            edge("c-pair2", "cobalt", "C0", "CG", gate="c2", phase_mask="11"),
        ],
        hidden_states=states,
        initial_states=["left", "right"],
        tether_links=[["A0", "C0"], ["AG", "CG"]],
        beacons=beacons,
        max_turns=2,
    )
    proc, _, output = run_board(phaseglass_binary, tmp_path, board)
    assert proc.returncode == 0, proc.stderr
    result = read_result(output)
    replay_and_check(board, result)
    root = result["nodes"][0]
    assert root["action"] == {"amber": "listen:which", "cobalt": "wait"}

def test_worst_turns_precedes_boost_count(phaseglass_binary, tmp_path):
    state = single_world_state(accepting=True)
    board = make_board(
        "turns-before-boosts",
        rooms=["A0", "AG", "C0", "CG"],
        start={"amber": "A0", "cobalt": "C0"},
        goals={"amber": "AG", "cobalt": "CG"},
        edges=[
            edge("a-direct", "amber", "A0", "AG", phase_mask="01", boostable=True),
            edge("c-direct", "cobalt", "C0", "CG", phase_mask="01", boostable=True),
        ],
        hidden_states=[state],
        initial_states=["s0"],
        tether_links=[["A0", "C0"], ["AG", "CG"]],
        max_turns=2,
        phase_charges=2,
        charge_cap=2,
    )
    proc, _, output = run_board(phaseglass_binary, tmp_path, board)
    assert proc.returncode == 0, proc.stderr
    result = read_result(output)
    replay_and_check(board, result)
    assert result["worst_turns"] == 1
    assert result["worst_boosts"] == 2
    assert result["nodes"][0]["action"] == {
        "amber": "boost:a-direct",
        "cobalt": "boost:c-direct",
    }


def test_worst_boosts_precede_lower_energy(phaseglass_binary, tmp_path):
    state = single_world_state(accepting=True)
    board = make_board(
        "boosts-before-energy",
        rooms=["A0", "AG", "C0", "CG"],
        start={"amber": "A0", "cobalt": "C0"},
        goals={"amber": "AG", "cobalt": "CG"},
        edges=[
            edge("a-high", "amber", "A0", "AG", cost=9, phase_mask="10"),
            edge("c-high", "cobalt", "C0", "CG", cost=9, phase_mask="10"),
            edge("a-low", "amber", "A0", "AG", cost=1, phase_mask="01", boostable=True),
            edge("c-low", "cobalt", "C0", "CG", cost=1, phase_mask="01", boostable=True),
        ],
        hidden_states=[state],
        initial_states=["s0"],
        tether_links=[["A0", "C0"], ["AG", "CG"]],
        max_turns=1,
        phase_charges=2,
        charge_cap=2,
    )
    proc, _, output = run_board(phaseglass_binary, tmp_path, board)
    assert proc.returncode == 0, proc.stderr
    result = read_result(output)
    replay_and_check(board, result)
    assert result["worst_boosts"] == 0
    assert result["worst_energy"] == 18
    assert result["nodes"][0]["action"] == {
        "amber": "move:a-high",
        "cobalt": "move:c-high",
    }


def test_worst_energy_precedes_total_terminal_turns(phaseglass_binary, tmp_path):
    beacons = [{"id": "sense", "room": "A0", "listen_cost": 0}]
    states = [
        hidden("w1", "one", open_gates=["g1", "fast"], signals={"sense": "one"}),
        hidden("w2", "two", open_gates=["g2"], signals={"sense": "two"}),
    ]
    board = make_board(
        "energy-before-total",
        rooms=["A0", "AG", "C0", "CG"],
        start={"amber": "A0", "cobalt": "C0"},
        goals={"amber": "AG", "cobalt": "CG"},
        edges=[
            edge("a-fast", "amber", "A0", "AG", cost=3, gate="fast", phase_mask="11"),
            edge("c-fast", "cobalt", "C0", "CG", cost=3, gate="fast", phase_mask="11"),
            edge("a-g1", "amber", "A0", "AG", cost=1, gate="g1", phase_mask="11"),
            edge("c-g1", "cobalt", "C0", "CG", cost=1, gate="g1", phase_mask="11"),
            edge("a-g2", "amber", "A0", "AG", cost=1, gate="g2", phase_mask="11"),
            edge("c-g2", "cobalt", "C0", "CG", cost=1, gate="g2", phase_mask="11"),
        ],
        hidden_states=states,
        initial_states=["w1", "w2"],
        tether_links=[["A0", "C0"], ["AG", "CG"]],
        beacons=beacons,
        max_turns=2,
        blocked_cost=1,
    )
    proc, _, output = run_board(phaseglass_binary, tmp_path, board)
    assert proc.returncode == 0, proc.stderr
    result = read_result(output)
    replay_and_check(board, result)
    assert result["worst_turns"] == 2
    assert result["worst_energy"] == 2
    assert result["total_turns"] == 4
    assert result["nodes"][0]["action"] == {"amber": "listen:sense", "cobalt": "wait"}


def test_total_turns_precede_lexicographically_smaller_policy(phaseglass_binary, tmp_path):
    states = [
        hidden(
            "open-0",
            "one",
            open_gates=["gz"],
            next_by_tone={"0": "open-0", "1": "open-1"},
        ),
        hidden(
            "open-1",
            "one",
            open_gates=["gz"],
            next_by_tone={"0": "open-1", "1": "open-1"},
        ),
        hidden(
            "closed-0",
            "two",
            next_by_tone={"0": "closed-0", "1": "closed-1"},
        ),
        hidden(
            "closed-1",
            "two",
            open_gates=["gf"],
            next_by_tone={"0": "closed-1", "1": "closed-1"},
        ),
    ]
    board = make_board(
        "total-before-lex",
        rooms=["A0", "AM", "AG", "C0", "CM", "CG"],
        start={"amber": "A0", "cobalt": "C0"},
        goals={"amber": "AG", "cobalt": "CG"},
        edges=[
            edge("a-slow", "amber", "A0", "AM", cost=1, phase_mask="10"),
            edge("c-slow", "cobalt", "C0", "CM", cost=1, phase_mask="10"),
            edge("a-zfast", "amber", "A0", "AG", cost=2, gate="gz", tone=1, phase_mask="10"),
            edge("c-zfast", "cobalt", "C0", "CG", cost=2, gate="gz", tone=0, phase_mask="10"),
            edge("a-slow-exit", "amber", "AM", "AG", cost=1, phase_mask="01"),
            edge("c-slow-exit", "cobalt", "CM", "CG", cost=1, phase_mask="01"),
            edge("a-fallback", "amber", "A0", "AG", cost=1, gate="gf", phase_mask="01"),
            edge("c-fallback", "cobalt", "C0", "CG", cost=1, gate="gf", phase_mask="01"),
        ],
        hidden_states=states,
        initial_states=["open-0", "closed-0"],
        tether_links=[["A0", "C0"], ["AM", "CM"], ["AG", "CG"]],
        max_turns=2,
        blocked_cost=1,
    )
    proc, _, output = run_board(phaseglass_binary, tmp_path, board)
    assert proc.returncode == 0, proc.stderr
    result = read_result(output)
    replay_and_check(board, result)
    assert result["worst_turns"] == 2
    assert result["worst_energy"] == 4
    assert result["total_turns"] == 3
    assert result["nodes"][0]["action"] == {
        "amber": "move:a-zfast",
        "cobalt": "move:c-zfast",
    }


def test_split_branch_tradeoff_is_optimized_at_complete_root(phaseglass_binary, tmp_path):
    """A child may spend an extra turn when another branch already fixes the root limit."""
    beacons = [{"id": "sense", "room": "A0", "listen_cost": 0, "tone": 1}]
    states = [
        hidden(
            "w1-start",
            "w1",
            accepting=False,
            signals={"sense": "one"},
            next_by_tone={"0": "w1-dead", "1": "w1-route", "2": "w1-dead"},
        ),
        hidden(
            "w1-dead",
            "w1",
            accepting=False,
            signals={"sense": "dead"},
            next_by_tone={"0": "w1-dead", "1": "w1-dead", "2": "w1-dead"},
        ),
        hidden(
            "w1-route",
            "w1",
            open_gates=["fast", "slow1"],
            accepting=True,
            signals={"sense": "one"},
            next_by_tone={"0": "w1-route", "1": "w1-route", "2": "w1-route"},
        ),
        hidden(
            "w2-start",
            "w2",
            accepting=False,
            signals={"sense": "two"},
            next_by_tone={"0": "w2-dead", "1": "w2-route", "2": "w2-dead"},
        ),
        hidden(
            "w2-dead",
            "w2",
            accepting=False,
            signals={"sense": "dead"},
            next_by_tone={"0": "w2-dead", "1": "w2-dead", "2": "w2-dead"},
        ),
        hidden(
            "w2-route",
            "w2",
            open_gates=["slow2"],
            accepting=True,
            signals={"sense": "two"},
            next_by_tone={"0": "w2-route", "1": "w2-route", "2": "w2-route"},
        ),
    ]
    board = make_board(
        "split-root-tradeoff",
        rooms=["A0", "A1", "AG", "C0", "C1", "CG"],
        start={"amber": "A0", "cobalt": "C0"},
        goals={"amber": "AG", "cobalt": "CG"},
        edges=[
            edge(
                "a-fast",
                "amber",
                "A0",
                "AG",
                cost=1,
                phase_mask="100",
                boostable=True,
                gate="fast",
            ),
            edge(
                "c-fast",
                "cobalt",
                "C0",
                "CG",
                cost=1,
                phase_mask="100",
                boostable=True,
                gate="fast",
            ),
            edge("a-slow1", "amber", "A0", "A1", phase_mask="010", gate="slow1"),
            edge("c-slow1", "cobalt", "C0", "C1", phase_mask="010", gate="slow1"),
            edge("a-slow2", "amber", "A0", "A1", phase_mask="010", gate="slow2"),
            edge("c-slow2", "cobalt", "C0", "C1", phase_mask="010", gate="slow2"),
            edge("a-exit", "amber", "A1", "AG", phase_mask="001"),
            edge("c-exit", "cobalt", "C1", "CG", phase_mask="001"),
        ],
        hidden_states=states,
        initial_states=["w1-start", "w2-start"],
        tether_links=[["A0", "C0"], ["A1", "C1"], ["AG", "CG"]],
        beacons=beacons,
        max_turns=3,
        period=3,
        phase_charges=2,
        charge_cap=2,
        boost_surcharge=0,
        blocked_cost=1,
        tone_modulus=3,
    )
    proc, _, output = run_board(phaseglass_binary, tmp_path, board)
    assert proc.returncode == 0, proc.stderr
    result = read_result(output)
    replay_and_check(board, result)
    assert result["worst_turns"] == 3
    assert result["worst_boosts"] == 0
    assert result["worst_energy"] == 4
    assert result["total_turns"] == 6
    first_world = next(node for node in result["nodes"] if node["belief"] == ["w1-route"] and node["tick"] == 1)
    assert first_world["action"] == {
        "amber": "move:a-slow1",
        "cobalt": "move:c-slow1",
    }


def test_recursive_policy_lexicographic_tie_break(phaseglass_binary, tmp_path):
    state = single_world_state(accepting=True)
    board = make_board(
        "policy-lex",
        rooms=["A0", "AG", "C0", "CG"],
        start={"amber": "A0", "cobalt": "C0"},
        goals={"amber": "AG", "cobalt": "CG"},
        edges=[
            edge("a-alpha", "amber", "A0", "AG", phase_mask="11"),
            edge("a-beta", "amber", "A0", "AG", phase_mask="11"),
            edge("c-alpha", "cobalt", "C0", "CG", phase_mask="11"),
            edge("c-beta", "cobalt", "C0", "CG", phase_mask="11"),
        ],
        hidden_states=[state],
        initial_states=["s0"],
        tether_links=[["A0", "C0"], ["AG", "CG"]],
        max_turns=1,
    )
    proc, _, output = run_board(phaseglass_binary, tmp_path, board)
    assert proc.returncode == 0, proc.stderr
    result = read_result(output)
    replay_and_check(board, result)
    assert result["nodes"][0]["action"] == {
        "amber": "move:a-alpha",
        "cobalt": "move:c-alpha",
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "duplicate_edge",
        "missing_boolean",
        "bad_phase_mask",
        "unknown_open_gate",
        "missing_signal",
        "extra_signal",
        "cross_world_transition",
        "missing_tone_transition",
        "empty_successor_set",
        "duplicate_successor",
        "bad_beacon_tone",
        "duplicate_initial_world",
        "bad_tether_link",
        "wrong_primitive_type",
        "extra_root_member",
        "bad_schema_version",
        "bad_token",
        "unknown_room",
        "invalid_actor",
        "nonpositive_cost",
        "bad_edge_tone",
        "excess_charges",
        "unknown_successor",
        "initial_tether_violation",
        "null_max_turns",
        "null_blocked_cost",
        "null_edge_tone",
        "null_beacons",
        "null_tether_links",
        "null_open_gates",
        "null_start",
        "null_signals",
        "null_next_by_tone",
    ],
)
def test_invalid_boards_fail_without_output(phaseglass_binary, tmp_path, mutation):
    """Representative malformed boards from every documented validation group fail."""
    board = json.loads(PUBLIC_BOARD.read_text(encoding="utf-8"))
    if mutation == "duplicate_edge":
        board["edges"][1]["id"] = board["edges"][0]["id"]
    elif mutation == "missing_boolean":
        del board["edges"][0]["boostable"]
    elif mutation == "bad_phase_mask":
        board["edges"][0]["phase_mask"] = "1x"
    elif mutation == "unknown_open_gate":
        board["hidden_states"][0]["open_gates"] = ["does-not-exist"]
    elif mutation == "missing_signal":
        del board["hidden_states"][0]["signals"]["alpha"]
    elif mutation == "extra_signal":
        board["hidden_states"][0]["signals"]["extra"] = "x"
    elif mutation == "cross_world_transition":
        board["hidden_states"][0]["next_by_tone"]["1"] = ["w2-1"]
    elif mutation == "missing_tone_transition":
        del board["hidden_states"][0]["next_by_tone"]["2"]
    elif mutation == "empty_successor_set":
        board["hidden_states"][0]["next_by_tone"]["1"] = []
    elif mutation == "duplicate_successor":
        target = board["hidden_states"][0]["next_by_tone"]["1"][0]
        board["hidden_states"][0]["next_by_tone"]["1"] = [target, target]
    elif mutation == "bad_beacon_tone":
        board["beacons"][0]["tone"] = board["tone_modulus"]
    elif mutation == "duplicate_initial_world":
        board["initial_states"][1] = "w1-1"
    elif mutation == "bad_tether_link":
        board["tether_links"][0] = ["A0", "missing"]
    elif mutation == "wrong_primitive_type":
        board["period"] = "2"
    elif mutation == "extra_root_member":
        board["unexpected"] = True
    elif mutation == "bad_schema_version":
        board["schema_version"] = "phaseglass.board.v999"
    elif mutation == "bad_token":
        board["board_id"] = "bad token"
    elif mutation == "unknown_room":
        board["edges"][0]["to"] = "missing-room"
    elif mutation == "invalid_actor":
        board["edges"][0]["actor"] = "both"
    elif mutation == "nonpositive_cost":
        board["edges"][0]["cost"] = 0
    elif mutation == "bad_edge_tone":
        board["edges"][0]["tone"] = board["tone_modulus"]
    elif mutation == "excess_charges":
        board["phase_charges"] = board["charge_cap"] + 1
    elif mutation == "unknown_successor":
        board["hidden_states"][0]["next_by_tone"]["1"] = ["missing-state"]
    elif mutation == "initial_tether_violation":
        board["tether_links"] = [
            pair for pair in board["tether_links"] if pair != ["A0", "C0"]
        ]
    elif mutation == "null_max_turns":
        board["max_turns"] = None
    elif mutation == "null_blocked_cost":
        board["blocked_cost"] = None
    elif mutation == "null_edge_tone":
        board["edges"][0]["tone"] = None
    elif mutation == "null_beacons":
        board["beacons"] = None
    elif mutation == "null_tether_links":
        board["tether_links"] = None
    elif mutation == "null_open_gates":
        board["hidden_states"][0]["open_gates"] = None
    elif mutation == "null_start":
        board["start"] = None
    elif mutation == "null_signals":
        board["hidden_states"][0]["signals"] = None
    elif mutation == "null_next_by_tone":
        board["hidden_states"][0]["next_by_tone"] = None
    proc, _, output = run_board(phaseglass_binary, tmp_path, board)
    assert proc.returncode != 0
    assert "invalid board" in proc.stderr
    assert not output.exists()



@pytest.mark.parametrize("alias_kind", ["same_path", "symlink", "hardlink"])
def test_board_and_output_alias_is_rejected_without_mutation(
    phaseglass_binary, tmp_path, alias_kind
):
    """The command must reject identical, symbolic-link, and hard-link aliases."""
    jail = make_jail(phaseglass_binary, tmp_path)
    shared = jail / "shared"
    shared.mkdir(mode=0o777)
    board_path = shared / "board.json"
    original = PUBLIC_BOARD.read_bytes()
    board_path.write_bytes(original)
    board_path.chmod(0o666)
    output_path = shared / "policy.json"
    output_argument = "/shared/policy.json"
    if alias_kind == "same_path":
        output_argument = "/shared/board.json"
    elif alias_kind == "symlink":
        output_path.symlink_to("board.json")
    else:
        os.link(board_path, output_path)
    proc = run_in_jail(
        jail,
        [
            "--board",
            "/shared/board.json",
            "--output",
            output_argument,
        ],
    )
    assert proc.returncode != 0
    assert "invalid board" in proc.stderr
    assert proc.stdout == ""
    assert board_path.read_bytes() == original


def test_nested_output_overwrites_and_input_is_unchanged(phaseglass_binary, tmp_path):
    board = json.loads(PUBLIC_BOARD.read_text(encoding="utf-8"))
    board["board_id"] = "io-veil-board"
    board_path = tmp_path / "input.json"
    board_path.write_text(json.dumps(board, indent=2) + "\n", encoding="utf-8")
    original = board_path.read_bytes()
    output = tmp_path / "deep/nested/policy.json"
    output.parent.mkdir(parents=True)
    output.write_text("stale\n", encoding="utf-8")
    proc, _, output = run_board_path(
        phaseglass_binary, tmp_path, board_path, "deep/nested/policy.json"
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == ""
    result = read_result(output)
    replay_and_check(board, result)
    assert result["board_id"] == "io-veil-board"
    assert board_path.read_bytes() == original
