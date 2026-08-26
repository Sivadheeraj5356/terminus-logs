"""Verifier tests for the Portfall TypeScript adjudicator.

The system under test is a TypeScript library that exports
``adjudicatePortfall(containerSpec, transcript): AdjudicationResult``. There is
no CLI, so these pytest tests drive the library directly: a tiny Node driver
imports the module via ts-node and prints the emitted JSON, which the tests
deep-compare against golden files and check against structural invariants.

Each test maps to a functional_criteria[] entry. Run via tests/test.sh, which
writes /logs/verifier/reward.txt from pytest's exit code.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

# Workdir the Dockerfile builds; fixtures are COPYed here (NOT under environment/).
APP = Path("/app")
SPEC = APP / "portfall" / "container-spec.example.json"
PUBLIC_TRANSCRIPTS = APP / "transcripts"
PUBLIC_GOLDEN = APP / "golden" / "adjudications"
PACKAGE_JSON = APP / "package.json"

# Hidden anti-hardcoding fixtures ship under tests/ and are copied into the
# verifier only at grade time (absent during the agent run). They mirror the
# public layout: <hidden>/transcripts/<name>.txt + <hidden>/golden/adjudications/<name>.json.
HIDDEN_DIR = Path(__file__).resolve().parent / "hidden"
HIDDEN_TRANSCRIPTS = HIDDEN_DIR / "transcripts"
HIDDEN_GOLDEN = HIDDEN_DIR / "golden" / "adjudications"

# Every AdjudicationResult must carry these keys (see src/types.ts).
REQUIRED_RESULT_KEYS = {
    "finalRoom",
    "visitedRooms",
    "transitions",
    "brokenSeals",
    "rejectedActions",
    "hazardsTriggered",
    "score",
    "scoreBreakdown",
}

# Node driver: import the library and print adjudicatePortfall(spec, transcript)
# as JSON. transpileOnly keeps grading focused on runtime behaviour rather than
# strict type-cleanliness (which no criterion asks for).
DRIVER_JS = """const fs = require("fs");
require("ts-node").register({ transpileOnly: true, project: "/app/tsconfig.json" });
const mod = require("/app/src/index.ts");
const fn = mod.adjudicatePortfall;
if (typeof fn !== "function") {
  console.error("adjudicatePortfall is not exported as a function");
  process.exit(3);
}
const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const transcript = fs.readFileSync(process.argv[3], "utf8");
const result = fn(spec, transcript);
process.stdout.write(JSON.stringify(result));
"""


@pytest.fixture(scope="session")
def driver(tmp_path_factory) -> Path:
    """Write the Node driver once per session and return its path."""
    path = tmp_path_factory.mktemp("adjudicator") / "driver.js"
    path.write_text(DRIVER_JS, encoding="utf-8")
    return path


def _run(driver: Path, spec_path: Path, transcript_path: Path) -> dict:
    """Invoke the agent's library on (spec, transcript) and return parsed JSON."""
    env = {**os.environ, "NODE_PATH": "/app/node_modules"}
    proc = subprocess.run(
        ["node", str(driver), str(spec_path), str(transcript_path)],
        cwd="/app",
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    assert proc.returncode == 0, (
        f"adjudicator driver failed (exit {proc.returncode}) for "
        f"{transcript_path.name}:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
    return json.loads(proc.stdout)


def _run_league(spec_path: Path, transcripts: dict[str, str]) -> dict:
    """Invoke summarizePortfallLeague on a generated transcript map."""
    driver_js = Path("/tmp/portfall-league-driver.js")
    input_path = Path("/tmp/portfall-league-input.json")
    driver_js.write_text(
        """const fs = require("fs");
require("ts-node").register({ transpileOnly: true, project: "/app/tsconfig.json" });
const mod = require("/app/src/index.ts");
const fn = mod.summarizePortfallLeague;
if (typeof fn !== "function") {
  console.error("summarizePortfallLeague is not exported as a function");
  process.exit(3);
}
const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const transcripts = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
process.stdout.write(JSON.stringify(fn(spec, transcripts)));
""",
        encoding="utf-8",
    )
    input_path.write_text(json.dumps(transcripts), encoding="utf-8")
    proc = subprocess.run(
        ["node", str(driver_js), str(spec_path), str(input_path)],
        cwd="/app",
        capture_output=True,
        text=True,
        timeout=180,
        env={**os.environ, "NODE_PATH": "/app/node_modules"},
    )
    assert proc.returncode == 0, (
        f"league driver failed (exit {proc.returncode}):\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
    return json.loads(proc.stdout)


def _run_audit_pack(spec_path: Path, transcript_files: dict[str, str], output_dir: Path) -> dict:
    """Invoke writePortfallAuditPack and return the manifest it emits."""
    driver_js = Path("/tmp/portfall-audit-driver.js")
    input_path = Path("/tmp/portfall-audit-input.json")
    driver_js.write_text(
        """const fs = require("fs");
require("ts-node").register({ transpileOnly: true, project: "/app/tsconfig.json" });
const mod = require("/app/src/index.ts");
const fn = mod.writePortfallAuditPack;
if (typeof fn !== "function") {
  console.error("writePortfallAuditPack is not exported as a function");
  process.exit(3);
}
const spec = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const transcriptFiles = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
process.stdout.write(JSON.stringify(fn(spec, transcriptFiles, process.argv[4])));
""",
        encoding="utf-8",
    )
    input_path.write_text(json.dumps(transcript_files), encoding="utf-8")
    proc = subprocess.run(
        ["node", str(driver_js), str(spec_path), str(input_path), str(output_dir)],
        cwd="/app",
        capture_output=True,
        text=True,
        timeout=180,
        env={**os.environ, "NODE_PATH": "/app/node_modules"},
    )
    assert proc.returncode == 0, (
        f"audit driver failed (exit {proc.returncode}):\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
    return json.loads(proc.stdout)


def _public_cases() -> list[tuple[str, Path, Path]]:
    """Discover (name, transcript_path, golden_path) triples for public fixtures."""
    cases = []
    for golden in sorted(PUBLIC_GOLDEN.glob("*.json")):
        transcript = PUBLIC_TRANSCRIPTS / f"{golden.stem}.txt"
        cases.append((golden.stem, transcript, golden))
    return cases


def _hidden_cases() -> list[tuple[str, Path, Path]]:
    """Discover (name, transcript_path, golden_path) triples for hidden fixtures."""
    cases = []
    if not HIDDEN_GOLDEN.is_dir():
        return cases
    for golden in sorted(HIDDEN_GOLDEN.glob("*.json")):
        transcript = HIDDEN_TRANSCRIPTS / f"{golden.stem}.txt"
        cases.append((golden.stem, transcript, golden))
    return cases


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical(obj) -> str:
    """Canonical-normalized-exact form: keys sorted recursively, no spacing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _spec() -> dict:
    return _load_json(SPEC)


def _all_seals(spec: dict) -> set[str]:
    seals: set[str] = set()
    for container in spec["containers"]:
        seals.update(container.get("seals", []))
    return seals


def _connections(spec: dict) -> dict[str, set[str]]:
    return {c["id"]: set(c.get("connectsTo", [])) for c in spec["containers"]}


def _hazards_by_room(spec: dict) -> dict[str, set[str]]:
    return {c["id"]: set(c.get("hazards", [])) for c in spec["containers"]}


def test_typescript_package_builds():
    """The submitted library should compile with the package build script."""
    proc = subprocess.run(
        ["npm", "run", "build"],
        cwd="/app",
        capture_output=True,
        text=True,
        timeout=180,
        env={**os.environ, "NODE_PATH": "/app/node_modules"},
    )
    assert proc.returncode == 0, (
        "npm run build failed; the adjudicator should remain a compileable "
        "TypeScript library.\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )


@pytest.fixture(scope="session")
def public_results(driver) -> dict[str, dict]:
    """Run every public transcript once and cache the emitted results by name."""
    results: dict[str, dict] = {}
    cases = _public_cases()
    assert cases, "no public golden fixtures found under /app/golden/adjudications"
    for name, transcript_path, _golden in cases:
        results[name] = _run(driver, SPEC, transcript_path)
    return results


# --------------------------------------------------------------------------- #
# Criterion tests
# --------------------------------------------------------------------------- #


def test_matches_public_golden_adjudications(public_results):
    """functional_criteria[id=matches_public_golden_adjudications]: each public
    transcript's emitted JSON is deep-equal to its golden adjudication file."""
    cases = _public_cases()
    assert cases, "no public golden fixtures discovered"
    for name, _transcript, golden_path in cases:
        expected = _load_json(golden_path)
        produced = public_results[name]
        assert _canonical(produced) == _canonical(expected), (
            f"public case {name!r} does not match its golden file.\n"
            f"expected: {_canonical(expected)}\nproduced: {_canonical(produced)}"
        )


def test_matches_hidden_golden_adjudications(driver):
    """functional_criteria[id=matches_hidden_golden_adjudications]: every hidden
    transcript (shipped under tests/, absent during the agent run) produces JSON
    deep-equal to its golden file. Anti-hardcoding check."""
    cases = _hidden_cases()
    assert cases, (
        "no hidden fixtures found under tests/hidden/ — a human must author at "
        "least one hidden transcript + golden pair (tests/hidden/transcripts/*.txt "
        "and tests/hidden/golden/adjudications/*.json) for the anti-hardcoding check"
    )
    for name, transcript_path, golden_path in cases:
        assert transcript_path.is_file(), f"missing hidden transcript for {name!r}"
        expected = _load_json(golden_path)
        produced = _run(driver, SPEC, transcript_path)
        assert _canonical(produced) == _canonical(expected), (
            f"hidden case {name!r} does not match its golden file.\n"
            f"expected: {_canonical(expected)}\nproduced: {_canonical(produced)}"
        )


def test_room_transitions_applied(public_results):
    """functional_criteria[id=room_transitions_applied]: movement commands produce
    the room/location state and transition records the manual documents."""
    spec = _spec()
    start = spec["startContainer"]
    connections = _connections(spec)

    for name, _transcript, golden_path in _public_cases():
        produced = public_results[name]
        expected = _load_json(golden_path)

        # Match the golden transition-related fields exactly.
        for field in ("finalRoom", "visitedRooms", "transitions"):
            assert _canonical(produced[field]) == _canonical(expected[field]), (
                f"case {name!r} field {field!r} mismatch: "
                f"expected {expected[field]!r}, got {produced[field]!r}"
            )

        # Decision-independent structural invariants any correct replay satisfies.
        transitions = produced["transitions"]
        prev = start
        for idx, transition in enumerate(transitions):
            assert transition["from"] == prev, (
                f"case {name!r}: transition {idx} starts at {transition['from']!r}, "
                f"expected contiguous from {prev!r}"
            )
            assert transition["to"] in connections.get(transition["from"], set()), (
                f"case {name!r}: move {transition['from']!r} -> {transition['to']!r} "
                f"is not a declared connection"
            )
            prev = transition["to"]

        expected_final = transitions[-1]["to"] if transitions else start
        assert produced["finalRoom"] == expected_final, (
            f"case {name!r}: finalRoom {produced['finalRoom']!r} is not the last "
            f"room reached ({expected_final!r})"
        )

        # visitedRooms is the ordered, de-duplicated path starting at the origin.
        path = [start] + [t["to"] for t in transitions]
        seen: list[str] = []
        for room in path:
            if room not in seen:
                seen.append(room)
        assert produced["visitedRooms"] == seen, (
            f"case {name!r}: visitedRooms {produced['visitedRooms']!r} is not the "
            f"ordered unique path {seen!r}"
        )


def test_seal_breaking_rules_enforced(public_results):
    """functional_criteria[id=seal_breaking_rules_enforced]: legal seal breaks
    succeed and update state; illegal breaks are rejected/flagged."""
    spec = _spec()
    all_seals = _all_seals(spec)

    for name, _transcript, golden_path in _public_cases():
        produced = public_results[name]
        expected = _load_json(golden_path)

        assert _canonical(produced["brokenSeals"]) == _canonical(expected["brokenSeals"]), (
            f"case {name!r}: brokenSeals mismatch — expected "
            f"{expected['brokenSeals']!r}, got {produced['brokenSeals']!r}"
        )
        assert _canonical(produced["rejectedActions"]) == _canonical(expected["rejectedActions"]), (
            f"case {name!r}: rejectedActions mismatch — expected "
            f"{expected['rejectedActions']!r}, got {produced['rejectedActions']!r}"
        )

        # Structural invariants: broken seals are real seals, with no duplicates,
        # and each rejected action carries a non-empty reason.
        broken = produced["brokenSeals"]
        assert len(broken) == len(set(broken)), (
            f"case {name!r}: brokenSeals contains duplicates: {broken!r}"
        )
        assert set(broken) <= all_seals, (
            f"case {name!r}: brokenSeals {broken!r} includes ids absent from the "
            f"spec seals {sorted(all_seals)!r}"
        )
        for rejected in produced["rejectedActions"]:
            assert rejected.get("command"), f"case {name!r}: rejected action missing command"
            assert rejected.get("reason"), (
                f"case {name!r}: rejected action {rejected!r} missing a reason"
            )


def test_hazard_exceptions_handled(public_results):
    """functional_criteria[id=hazard_exceptions_handled]: hazard exception cases
    resolve per the manual's exception rules rather than the default path."""
    spec = _spec()
    hazards_by_room = _hazards_by_room(spec)

    for name, _transcript, golden_path in _public_cases():
        produced = public_results[name]
        expected = _load_json(golden_path)

        assert _canonical(produced["hazardsTriggered"]) == _canonical(expected["hazardsTriggered"]), (
            f"case {name!r}: hazardsTriggered mismatch — expected "
            f"{expected['hazardsTriggered']!r}, got {produced['hazardsTriggered']!r}"
        )

        # Structural invariant: a triggered hazard must exist in a visited room.
        reachable_hazards: set[str] = set()
        for room in produced["visitedRooms"]:
            reachable_hazards |= hazards_by_room.get(room, set())
        assert set(produced["hazardsTriggered"]) <= reachable_hazards, (
            f"case {name!r}: hazardsTriggered {produced['hazardsTriggered']!r} "
            f"includes hazards not present in any visited room {reachable_hazards!r}"
        )


def test_scoring_matches_manual_examples(public_results):
    """functional_criteria[id=scoring_matches_manual_examples]: score and
    scoreBreakdown match the manual's worked scoring examples."""
    for name, _transcript, golden_path in _public_cases():
        produced = public_results[name]
        expected = _load_json(golden_path)

        assert produced["score"] == expected["score"], (
            f"case {name!r}: score {produced['score']!r} != golden {expected['score']!r}"
        )
        assert _canonical(produced["scoreBreakdown"]) == _canonical(expected["scoreBreakdown"]), (
            f"case {name!r}: scoreBreakdown mismatch — expected "
            f"{expected['scoreBreakdown']!r}, got {produced['scoreBreakdown']!r}"
        )

        # Decision-independent invariant: the total equals the sum of its parts.
        breakdown_total = sum(produced["scoreBreakdown"].values())
        assert produced["score"] == breakdown_total, (
            f"case {name!r}: score {produced['score']!r} != sum of scoreBreakdown "
            f"{breakdown_total!r}"
        )


def test_alternate_layout_pathfind_secure_and_scoring(driver, tmp_path):
    """A correct adjudicator must generalize to a different container layout."""
    spec = {
        "startContainer": "dock",
        "containers": [
            {"id": "dock", "stackedOn": None, "seals": [], "hazards": [], "connectsTo": ["crane", "hold"]},
            {"id": "crane", "stackedOn": "dock", "seals": ["seal-c"], "hazards": ["wind"], "connectsTo": ["dock", "tower"]},
            {"id": "hold", "stackedOn": None, "seals": ["seal-h"], "hazards": ["corrosive"], "connectsTo": ["dock", "engine"]},
            {"id": "tower", "stackedOn": "crane", "seals": [], "hazards": ["electric"], "connectsTo": ["crane"]},
            {"id": "engine", "stackedOn": "hold", "seals": ["seal-e"], "hazards": ["heat", "ventilated"], "connectsTo": ["hold"]},
        ],
    }
    transcript = """scan wind
pathfind tower
pathfind dock
secure hold
pathfind engine
unlock seal-e
break-seal seal-e
"""
    expected = {
        "finalRoom": "engine",
        "visitedRooms": ["dock", "crane", "tower", "hold", "engine"],
        "transitions": [
            {"from": "dock", "to": "crane", "command": "pathfind tower"},
            {"from": "crane", "to": "tower", "command": "pathfind tower"},
            {"from": "tower", "to": "crane", "command": "pathfind dock"},
            {"from": "crane", "to": "dock", "command": "pathfind dock"},
            {"from": "dock", "to": "hold", "command": "pathfind engine"},
            {"from": "hold", "to": "engine", "command": "pathfind engine"},
        ],
        "brokenSeals": ["seal-e"],
        "rejectedActions": [],
        "hazardsTriggered": ["electric", "wind"],
        "score": 27,
        "scoreBreakdown": {
            "roomsVisited": 50,
            "sealsBroken": 25,
            "hazardPenalty": -30,
            "stackMovePenalty": -25,
            "securedRooms": 7,
        },
    }
    spec_path = tmp_path / "alt-spec.json"
    transcript_path = tmp_path / "alt-transcript.txt"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    transcript_path.write_text(transcript, encoding="utf-8")
    produced = _run(driver, spec_path, transcript_path)
    assert _canonical(produced) == _canonical(expected)


def test_temporary_routes_are_directed_and_consumed(driver, tmp_path):
    """Temporary routes are one-use directed edges during pathfinding and moves."""
    spec = {
        "startContainer": "a",
        "containers": [
            {"id": "a", "stackedOn": None, "seals": [], "hazards": [], "connectsTo": ["b"]},
            {"id": "b", "stackedOn": None, "seals": [], "hazards": [], "connectsTo": ["a"]},
            {"id": "c", "stackedOn": None, "seals": [], "hazards": [], "connectsTo": ["d"]},
            {"id": "d", "stackedOn": None, "seals": [], "hazards": [], "connectsTo": ["c"]},
        ],
    }
    transcript = """reroute a c
pathfind d
move c
move a
reroute c a
move a
"""
    expected = {
        "finalRoom": "a",
        "visitedRooms": ["a", "c", "d"],
        "transitions": [
            {"from": "a", "to": "c", "command": "pathfind d"},
            {"from": "c", "to": "d", "command": "pathfind d"},
            {"from": "d", "to": "c", "command": "move c"},
            {"from": "c", "to": "a", "command": "move a"},
        ],
        "brokenSeals": [],
        "rejectedActions": [
            {"command": "move a", "reason": "no connection"},
        ],
        "hazardsTriggered": [],
        "score": 38,
        "scoreBreakdown": {
            "roomsVisited": 30,
            "temporaryRoutesUsed": 8,
        },
    }
    spec_path = tmp_path / "route-spec.json"
    transcript_path = tmp_path / "route-transcript.txt"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    transcript_path.write_text(transcript, encoding="utf-8")
    produced = _run(driver, spec_path, transcript_path)
    assert _canonical(produced) == _canonical(expected)


def test_pathfinding_tie_breaks_and_scan_replacement(driver, tmp_path):
    """Shortest-path ties use lexicographic next rooms and scan replacement."""
    spec = {
        "startContainer": "s",
        "containers": [
            {"id": "s", "stackedOn": None, "seals": [], "hazards": [], "connectsTo": ["b", "a"]},
            {"id": "a", "stackedOn": None, "seals": [], "hazards": ["spark", "smoke"], "connectsTo": ["z"]},
            {"id": "b", "stackedOn": None, "seals": [], "hazards": ["wrong"], "connectsTo": ["z"]},
            {"id": "z", "stackedOn": None, "seals": [], "hazards": [], "connectsTo": []},
        ],
    }
    transcript = """scan wrong
scan spark
pathfind z
"""
    expected = {
        "finalRoom": "z",
        "visitedRooms": ["s", "a", "z"],
        "transitions": [
            {"from": "s", "to": "a", "command": "pathfind z"},
            {"from": "a", "to": "z", "command": "pathfind z"},
        ],
        "brokenSeals": [],
        "rejectedActions": [],
        "hazardsTriggered": ["smoke"],
        "score": 15,
        "scoreBreakdown": {
            "roomsVisited": 30,
            "hazardPenalty": -15,
        },
    }
    spec_path = tmp_path / "tie-spec.json"
    transcript_path = tmp_path / "tie-transcript.txt"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    transcript_path.write_text(transcript, encoding="utf-8")
    produced = _run(driver, spec_path, transcript_path)
    assert _canonical(produced) == _canonical(expected)


def test_recall_beacons_cross_gaps_and_consume_once(driver, tmp_path):
    """Recall beacons are reachable-only when placed, then one-use direct moves."""
    spec = {
        "startContainer": "hub",
        "containers": [
            {"id": "hub", "stackedOn": None, "seals": [], "hazards": [], "connectsTo": ["east", "west"]},
            {"id": "east", "stackedOn": "hub", "seals": [], "hazards": ["spark"], "connectsTo": ["hub"]},
            {"id": "west", "stackedOn": "hub", "seals": [], "hazards": ["mist"], "connectsTo": ["hub"]},
            {"id": "far", "stackedOn": None, "seals": [], "hazards": [], "connectsTo": []},
        ],
    }
    transcript = """beacon far
scan spark
beacon east
move west
recall east
recall east
"""
    expected = {
        "finalRoom": "east",
        "visitedRooms": ["hub", "west", "east"],
        "transitions": [
            {"from": "hub", "to": "west", "command": "move west"},
            {"from": "west", "to": "east", "command": "recall east"},
        ],
        "brokenSeals": [],
        "rejectedActions": [
            {"command": "beacon far", "reason": "not reachable"},
            {"command": "recall east", "reason": "beacon absent"},
        ],
        "hazardsTriggered": ["mist"],
        "score": 16,
        "scoreBreakdown": {
            "roomsVisited": 30,
            "hazardPenalty": -15,
            "stackMovePenalty": -5,
            "beaconsUsed": 6,
        },
    }
    spec_path = tmp_path / "beacon-spec.json"
    transcript_path = tmp_path / "beacon-transcript.txt"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    transcript_path.write_text(transcript, encoding="utf-8")
    produced = _run(driver, spec_path, transcript_path)
    assert _canonical(produced) == _canonical(expected)


def test_aliases_resolve_to_canonical_state_without_rewriting_commands(driver, tmp_path):
    """Command aliases resolve for rules, while output ids stay canonical."""
    spec = {
        "startContainer": "hub",
        "aliases": {
            "containers": {"fore": "east", "aft": "west", "base": "hub"},
            "seals": {"gold": "seal-g"},
            "hazards": {"flash": "spark"},
        },
        "containers": [
            {"id": "hub", "stackedOn": None, "seals": [], "hazards": [], "connectsTo": ["east", "west"]},
            {"id": "east", "stackedOn": "hub", "seals": ["seal-g"], "hazards": ["spark"], "connectsTo": ["hub", "vault"]},
            {"id": "west", "stackedOn": "hub", "seals": [], "hazards": ["mist"], "connectsTo": ["hub"]},
        ],
    }
    transcript = """scan flash
beacon fore
move aft
recall fore
unlock gold
break-seal gold
move base
"""
    expected = {
        "finalRoom": "hub",
        "visitedRooms": ["hub", "west", "east"],
        "transitions": [
            {"from": "hub", "to": "west", "command": "move aft"},
            {"from": "west", "to": "east", "command": "recall fore"},
            {"from": "east", "to": "hub", "command": "move base"},
        ],
        "brokenSeals": ["seal-g"],
        "rejectedActions": [],
        "hazardsTriggered": ["mist"],
        "score": 36,
        "scoreBreakdown": {
            "roomsVisited": 30,
            "sealsBroken": 25,
            "hazardPenalty": -15,
            "stackMovePenalty": -10,
            "beaconsUsed": 6,
        },
    }
    spec_path = tmp_path / "alias-spec.json"
    transcript_path = tmp_path / "alias-transcript.txt"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    transcript_path.write_text(transcript, encoding="utf-8")
    produced = _run(driver, spec_path, transcript_path)
    assert _canonical(produced) == _canonical(expected)


def test_entry_requirements_affect_moves_recalls_and_pathfinding(driver, tmp_path):
    """Entry requirements depend on accumulated canonical game state."""
    spec = {
        "startContainer": "start",
        "aliases": {
            "containers": {"gate": "lock", "treasure": "vault", "home": "start"},
            "seals": {"key": "seal-key"},
            "hazards": {"dust": "spore"},
        },
        "containers": [
            {"id": "start", "stackedOn": None, "seals": [], "hazards": [], "connectsTo": ["lock", "side"]},
            {"id": "lock", "stackedOn": "start", "seals": ["seal-key"], "hazards": ["spore"], "connectsTo": ["start", "vault"]},
            {"id": "side", "stackedOn": None, "seals": [], "hazards": [], "connectsTo": ["start", "vault"]},
            {"id": "vault", "stackedOn": "lock", "seals": [], "hazards": ["glare"], "connectsTo": ["lock", "side"], "requires": {"visited": ["lock"], "brokenSeals": ["seal-key"]}},
        ],
    }
    transcript = """scan dust
move treasure
pathfind treasure
move gate
unlock key
break-seal key
beacon treasure
pathfind treasure
recall treasure
move side
pathfind home
"""
    expected = {
        "finalRoom": "start",
        "visitedRooms": ["start", "lock", "vault", "side"],
        "transitions": [
            {"from": "start", "to": "lock", "command": "move gate"},
            {"from": "lock", "to": "vault", "command": "pathfind treasure"},
            {"from": "vault", "to": "vault", "command": "recall treasure"},
            {"from": "vault", "to": "side", "command": "move side"},
            {"from": "side", "to": "start", "command": "pathfind home"},
        ],
        "brokenSeals": ["seal-key"],
        "rejectedActions": [
            {"command": "move treasure", "reason": "no connection"},
            {"command": "pathfind treasure", "reason": "no path"},
        ],
        "hazardsTriggered": ["glare"],
        "score": 46,
        "scoreBreakdown": {
            "roomsVisited": 40,
            "sealsBroken": 25,
            "hazardPenalty": -15,
            "stackMovePenalty": -10,
            "beaconsUsed": 6,
        },
    }
    spec_path = tmp_path / "requirements-spec.json"
    transcript_path = tmp_path / "requirements-transcript.txt"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    transcript_path.write_text(transcript, encoding="utf-8")
    produced = _run(driver, spec_path, transcript_path)
    assert _canonical(produced) == _canonical(expected)


def test_league_summary_ranks_and_aggregates_independent_runs(tmp_path):
    """League summaries rank independent adjudications and aggregate canonical state."""
    spec = {
        "startContainer": "hub",
        "aliases": {
            "containers": {"fore": "east", "aft": "west", "base": "hub"},
            "seals": {"gold": "seal-g"},
            "hazards": {"flash": "spark"},
        },
        "containers": [
            {"id": "hub", "stackedOn": None, "seals": [], "hazards": [], "connectsTo": ["east", "west"]},
            {"id": "east", "stackedOn": "hub", "seals": ["seal-g"], "hazards": ["spark"], "connectsTo": ["hub", "vault"]},
            {"id": "west", "stackedOn": "hub", "seals": [], "hazards": ["mist"], "connectsTo": ["hub"]},
            {"id": "vault", "stackedOn": "east", "seals": [], "hazards": ["glare"], "connectsTo": ["east"], "requires": {"brokenSeals": ["seal-g"]}},
        ],
    }
    transcripts = {
        "Ada": """scan flash
move fore
unlock gold
break-seal gold
pathfind vault
""",
        "Bo": """move aft
move base
move fore
""",
        "Cy": """move vault
inspect hub
""",
        "Di": """scan flash
move fore
move base
move aft
""",
    }
    expected = {
        "leaderboard": [
            {"player": "Ada", "rank": 1, "score": 30, "finalRoom": "vault", "brokenSeals": 1, "rejectedActions": 0},
            {"player": "Cy", "rank": 2, "score": 10, "finalRoom": "hub", "brokenSeals": 0, "rejectedActions": 1},
            {"player": "Di", "rank": 3, "score": 0, "finalRoom": "west", "brokenSeals": 0, "rejectedActions": 0},
            {"player": "Bo", "rank": 4, "score": -15, "finalRoom": "east", "brokenSeals": 0, "rejectedActions": 0},
        ],
        "aggregate": {
            "playerCount": 4,
            "topScore": 30,
            "totalBrokenSeals": 1,
            "uniqueHazardsTriggered": ["glare", "mist", "spark"],
            "roomVisitCounts": {"east": 3, "hub": 4, "vault": 1, "west": 2},
        },
    }
    spec_path = tmp_path / "league-spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    produced = _run_league(spec_path, transcripts)
    assert set(produced) == {"cases", "leaderboard", "aggregate"}
    assert _canonical(produced["leaderboard"]) == _canonical(expected["leaderboard"])
    assert _canonical(produced["aggregate"]) == _canonical(expected["aggregate"])
    assert set(produced["cases"]) == set(transcripts)
    assert produced["cases"]["Ada"]["brokenSeals"] == ["seal-g"]
    assert produced["cases"]["Cy"]["rejectedActions"] == [
        {"command": "move vault", "reason": "no connection"}
    ]


def test_nested_repeat_blocks_expand_before_adjudication(driver, tmp_path):
    """Nested repeat blocks expand into ordinary commands before replay."""
    spec = {
        "startContainer": "hub",
        "aliases": {
            "containers": {"fore": "east", "base": "hub"},
            "seals": {"gold": "seal-g"},
            "hazards": {"flash": "spark"},
        },
        "containers": [
            {"id": "hub", "stackedOn": None, "seals": [], "hazards": [], "connectsTo": ["east"]},
            {"id": "east", "stackedOn": "hub", "seals": ["seal-g"], "hazards": ["spark"], "connectsTo": ["hub", "vault"]},
            {"id": "vault", "stackedOn": "east", "seals": [], "hazards": ["glare"], "connectsTo": ["east"], "requires": {"brokenSeals": ["seal-g"]}},
        ],
    }
    transcript = """scan flash
repeat 2 {
  repeat 1 {
    move fore
  }
  move base
}
move fore
unlock gold
break-seal gold
pathfind vault
"""
    expected = {
        "finalRoom": "vault",
        "visitedRooms": ["hub", "east", "vault"],
        "transitions": [
            {"from": "hub", "to": "east", "command": "move fore"},
            {"from": "east", "to": "hub", "command": "move base"},
            {"from": "hub", "to": "east", "command": "move fore"},
            {"from": "east", "to": "hub", "command": "move base"},
            {"from": "hub", "to": "east", "command": "move fore"},
            {"from": "east", "to": "vault", "command": "pathfind vault"},
        ],
        "brokenSeals": ["seal-g"],
        "rejectedActions": [],
        "hazardsTriggered": ["spark", "glare"],
        "score": -5,
        "scoreBreakdown": {
            "roomsVisited": 30,
            "sealsBroken": 25,
            "hazardPenalty": -30,
            "stackMovePenalty": -30,
        },
    }
    spec_path = tmp_path / "repeat-spec.json"
    transcript_path = tmp_path / "repeat-transcript.txt"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    transcript_path.write_text(transcript, encoding="utf-8")
    produced = _run(driver, spec_path, transcript_path)
    assert _canonical(produced) == _canonical(expected)


def test_audit_pack_writes_deterministic_artifacts_and_digests(tmp_path):
    """Audit packs write canonical per-player JSON, CSV, hazards, and manifest."""
    spec = {
        "startContainer": "hub",
        "aliases": {"containers": {"fore": "east", "aft": "west", "base": "hub"}, "seals": {"gold": "seal-g"}, "hazards": {"flash": "spark"}},
        "containers": [
            {"id": "hub", "stackedOn": None, "seals": [], "hazards": [], "connectsTo": ["east", "west"]},
            {"id": "east", "stackedOn": "hub", "seals": ["seal-g"], "hazards": ["spark"], "connectsTo": ["hub", "vault"]},
            {"id": "west", "stackedOn": "hub", "seals": [], "hazards": ["mist"], "connectsTo": ["hub"]},
            {"id": "vault", "stackedOn": "east", "seals": [], "hazards": ["glare"], "connectsTo": ["east"], "requires": {"brokenSeals": ["seal-g"]}},
        ],
    }
    transcript_dir = tmp_path / "transcripts"
    transcript_dir.mkdir()
    transcripts = {
        "Ada": """scan flash
move fore
unlock gold
break-seal gold
pathfind vault
""",
        "Bo": """move aft
move base
move fore
""",
        "Cy": """move vault
inspect hub
""",
    }
    transcript_files = {}
    for player, body in transcripts.items():
        path = transcript_dir / f"{player}.txt"
        path.write_text(body, encoding="utf-8")
        transcript_files[player] = str(path)
    spec_path = tmp_path / "audit-spec.json"
    out_dir = tmp_path / "audit-out"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    manifest = _run_audit_pack(spec_path, transcript_files, out_dir)

    expected_artifacts = [
        "cases/Ada.json",
        "cases/Bo.json",
        "cases/Cy.json",
        "hazards.json",
        "leaderboard.csv",
        "manifest.json",
    ]
    assert manifest["artifacts"] == expected_artifacts
    assert manifest == _load_json(out_dir / "manifest.json")
    assert manifest["playerCount"] == 3
    assert manifest["topScore"] == 30

    leaderboard = (out_dir / "leaderboard.csv").read_text(encoding="utf-8")
    assert leaderboard == (
        "rank,player,score,finalRoom,brokenSeals,rejectedActions\n"
        "1,Ada,30,vault,1,0\n"
        "2,Cy,10,hub,0,1\n"
        "3,Bo,-15,east,0,0\n"
    )
    assert manifest["leaderboardDigest"] == hashlib.sha256(leaderboard.encode("utf-8")).hexdigest()

    ada_case = json.loads((out_dir / "cases" / "Ada.json").read_text(encoding="utf-8"))
    assert ada_case["finalRoom"] == "vault"
    assert ada_case["brokenSeals"] == ["seal-g"]
    ada_bytes = (out_dir / "cases" / "Ada.json").read_bytes()
    assert manifest["caseDigests"]["Ada"] == hashlib.sha256(ada_bytes).hexdigest()

    hazards = _load_json(out_dir / "hazards.json")
    assert hazards == {
        "byPlayer": {"Ada": ["glare"], "Bo": ["mist", "spark"], "Cy": []},
        "uniqueHazardsTriggered": ["glare", "mist", "spark"],
    }


def test_output_is_deterministic(driver):
    """functional_criteria[id=output_is_deterministic]: two calls on identical
    inputs yield byte-identical normalized JSON (no timestamps/randomness/order
    reliance)."""
    cases = _public_cases()
    assert cases, "no public fixtures to exercise determinism against"
    for name, transcript_path, _golden in cases:
        first = _canonical(_run(driver, SPEC, transcript_path))
        second = _canonical(_run(driver, SPEC, transcript_path))
        assert first == second, (
            f"case {name!r} produced different normalized JSON across two runs:\n"
            f"run1: {first}\nrun2: {second}"
        )


def test_library_import_no_cli_no_network(public_results):
    """functional_criteria[id=library_import_no_cli_no_network]: the package
    exposes adjudicatePortfall as an importable library export (no CLI/bin) and
    completes adjudication without network access."""
    manifest = _load_json(PACKAGE_JSON)
    assert "bin" not in manifest, (
        "package.json declares a 'bin' entry — the package must stay "
        "library-oriented with no CLI"
    )
    assert manifest.get("main"), "package.json must declare a library 'main' entry point"

    # The library is importable and callable: it ran offline (allow_internet=false)
    # and returned a well-formed AdjudicationResult for at least one case.
    assert public_results, "library produced no results — not importable/callable"
    for name, result in public_results.items():
        missing = REQUIRED_RESULT_KEYS - set(result)
        assert not missing, f"case {name!r}: AdjudicationResult missing keys {sorted(missing)}"
        assert isinstance(result["finalRoom"], str)
        assert isinstance(result["visitedRooms"], list)
        assert isinstance(result["transitions"], list)
        assert isinstance(result["brokenSeals"], list)
        assert isinstance(result["rejectedActions"], list)
        assert isinstance(result["hazardsTriggered"], list)
        assert isinstance(result["score"], (int, float)) and not isinstance(result["score"], bool)
        assert isinstance(result["scoreBreakdown"], dict)
