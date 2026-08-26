import json
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import lmdb
import yaml

TOOL = Path("/app/recovered/glyph_tool.py")
ROOT = Path("/app/glyph-mill")

# The submitted tool is graded running as this unprivileged uid, never as
# root: it cannot read the verifier's test/solution files, cannot attach a
# debugger to the runtime daemon, and cannot read the daemon's root-only
# audit log. Set up in the Dockerfile.
RESTRICTED_UID = 4001

# Trusted, absolute executable paths. The agent's own shell runs as
# RESTRICTED_UID for its entire session (never root), so it cannot tamper
# with these binaries in the first place - but resolve them by fixed path
# regardless of PATH or `sys.executable`, rather than trusting whatever a
# name lookup would find.
SETPRIV_BIN = "/usr/bin/setpriv"
PYTHON_BIN = "/usr/local/bin/python3.13"

# The runtime's own trace facility tags each openat() line it emits with a
# fresh, unguessable nonce and records the same nonce (bound to root, room,
# and the files actually opened) in a root-only audit log. Genuine runtime
# evidence therefore carries a nonce that shows up in that log; a statically
# fabricated trace line does not.
AUDIT_PATH = Path("/run/glyph-mill.d/audit.jsonl")
NONCE_RE = re.compile(r"<nonce:([0-9a-f]{32})>")

# A trace_excerpt line must look like genuine tracer output: an strace-style
# syscall line (e.g. `openat(AT_FDCWD, "...core.yaml", O_RDONLY) = 3`) or an
# lsof-style table row (with a REG file-type column).
TRACER_LINE = re.compile(
    r"(?:\b\w*(?:open|openat|read|stat)\w*\s*\(.*\)\s*=\s*-?\d+)|(?:\bREG\b)"
)


def _grant_restricted_access(path):
    """Make `path` and its ancestors reachable/usable by the restricted uid
    that the tool runs as (pytest's tmp dirs are created mode 700 by root)."""
    current = Path(path)
    for node in [current, *current.parents]:
        try:
            os.chmod(node, 0o777)
        except OSError:
            pass
        if str(node) in ("/tmp", "/"):
            break


def run_tool(cmd, root, out):
    assert TOOL.exists(), f"missing {TOOL}"
    _grant_restricted_access(root)
    _grant_restricted_access(Path(out).parent)
    result = subprocess.run(
        [
            SETPRIV_BIN,
            "--reuid",
            str(RESTRICTED_UID),
            "--regid",
            str(RESTRICTED_UID),
            "--clear-groups",
            PYTHON_BIN,
            str(TOOL),
            cmd,
            "--root",
            str(root),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"{cmd} failed: stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    return json.loads(Path(out).read_text())


def audit_records():
    """Every runtime resolution the daemon has recorded, keyed by nonce. Only
    the verifier (root) can read this; the restricted tool cannot."""
    records = {}
    if AUDIT_PATH.exists():
        for line in AUDIT_PATH.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            records[rec["nonce"]] = rec
    return records


def assert_trace_is_runtime_observed(item, root, room_id):
    """The room's trace_excerpt must carry at least one nonce that the daemon
    actually minted for this (root, room) with these exact loaded_files -
    proving the evidence came from observing the runtime, not from static path
    computation plus a hand-written trace line."""
    nonces = set()
    for line in item["trace_excerpt"]:
        nonces.update(NONCE_RE.findall(line))
    assert nonces, (
        f"room {room_id}: trace_excerpt carries no runtime-minted nonce; "
        f"evidence must come from the runtime's own trace facility"
    )
    records = audit_records()
    matched = [records[n] for n in nonces if n in records]
    assert matched, (
        f"room {room_id}: no trace nonce is present in the runtime audit log; "
        f"the evidence was not produced by observing the runtime"
    )
    assert any(
        rec["room"] == room_id
        and rec["root"] == str(Path(root).resolve())
        and sorted(rec["loaded_files"]) == item["loaded_files"]
        for rec in matched
    ), (
        f"room {room_id}: trace nonce does not bind to the reported "
        f"loaded_files for this root in the runtime audit log"
    )


def rooms(root):
    env = lmdb.open(str(root / "hints.lmdb"), readonly=False, lock=False, max_dbs=1)
    with env.begin() as txn:
        ids = json.loads(txn.get(b"rooms").decode())
        data = {
            room: json.loads(txn.get(f"room:{room}".encode()).decode()) for room in ids
        }
    env.close()
    return data


def load_pack(root, room):
    with (root / "rules" / "packs" / f"{room['pack']}.toml").open("rb") as file:
        return tomllib.load(file)


def overlay_path(root, room):
    pack = load_pack(root, room)
    names = sorted(p.name for p in (root / "rules" / "overlays").glob("*.yaml"))
    idx = (room["salt"] * pack["walk"]["stride"] + len(room["id"])) % len(names)
    return root / "rules" / "overlays" / names[idx]


def expected_files(root, room):
    return sorted(
        str(path.resolve())
        for path in [
            root / "rules" / "core.yaml",
            root / "rules" / "palettes" / f"{room['palette']}.yaml",
            root / "rules" / "packs" / f"{room['pack']}.toml",
            overlay_path(root, room),
        ]
    )


def copy_fixture(tmp_path):
    dst = tmp_path / "glyph-copy"
    shutil.copytree(ROOT, dst)
    return dst


def mutate_room(root, room_id="anvil", **updates):
    env = lmdb.open(str(root / "hints.lmdb"), readonly=False, lock=False, max_dbs=1)
    with env.begin(write=True) as txn:
        key = f"room:{room_id}".encode()
        room = json.loads(txn.get(key).decode())
        room.update(updates)
        txn.put(key, json.dumps(room, sort_keys=True).encode())
    env.sync()
    env.close()
    return room


def expected_rulebook(root):
    hints = rooms(root)
    core = yaml.safe_load((root / "rules" / "core.yaml").read_text())
    out = []
    for room_id in sorted(hints):
        hint = hints[room_id]
        palette = yaml.safe_load(
            (root / "rules" / "palettes" / f"{hint['palette']}.yaml").read_text()
        )
        pack = load_pack(root, hint)
        opath = overlay_path(root, hint)
        overlay = yaml.safe_load(opath.read_text())
        pivot = pack["walk"]["pivot"]
        out.append(
            {
                "room": room_id,
                "title": hint["title"],
                "start": hint["start"],
                "target": hint["target"],
                "beacons": {
                    str(key): int(value)
                    for key, value in hint.get("beacons", {}).items()
                },
                "salt": hint["salt"],
                "palette": hint["palette"],
                "pack": hint["pack"],
                "glyphs": hint["glyphs"],
                "glyph_values": {
                    key: int(value) for key, value in sorted(palette["symbols"].items())
                },
                "mask": int(palette["mask"]),
                "max_moves": hint["max_moves"],
                "cycle": pack["walk"]["cycle"],
                "stride": hint.get("stride_override", pack["walk"]["stride"]),
                "pivot": pivot,
                "turn_bias": core["turns"][pivot],
                "overlay": opath.stem,
                "mask_shift": int(overlay["mask_shift"]),
                "rotation": int(overlay["rotation"]),
                "loaded_files": expected_files(root, hint),
            }
        )
    return {
        "schema_version": 1,
        "grid": {
            "width": core["grid"]["width"],
            "height": core["grid"]["height"],
            "directions": core["directions"],
        },
        "rooms": out,
    }


def replay(root, route_path):
    result = subprocess.run(
        ["glyph-mill", "--root", str(root), "replay", str(route_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.returncode, json.loads(result.stdout)


def simulate(root, hint, seq):
    """Reference transition model (mirrors the game runtime); returns the
    full path, indexed from 0 (the start cell)."""
    core = yaml.safe_load((root / "rules" / "core.yaml").read_text())
    palette = yaml.safe_load(
        (root / "rules" / "palettes" / f"{hint['palette']}.yaml").read_text()
    )
    pack = load_pack(root, hint)
    overlay = yaml.safe_load(overlay_path(root, hint).read_text())
    width = core["grid"]["width"]
    height = core["grid"]["height"]
    cycle = pack["walk"]["cycle"]
    pivot = core["turns"][pack["walk"]["pivot"]]
    state = hint["start"]
    prev = None
    path = [state]
    for index, glyph in enumerate(seq):
        prev_term = pivot if prev is None else prev
        dindex = (
            palette["symbols"][glyph]
            + palette["mask"]
            + overlay["mask_shift"]
            + hint["salt"]
            + state
            + index * pack["walk"]["stride"]
            + pivot
            + prev_term * overlay["rotation"]
        ) % len(cycle)
        direction = cycle[dindex]
        dx, dy = core["directions"][direction]
        state = ((state // width + dy) % height) * width + (
            (state % width + dx) % width
        )
        path.append(state)
        prev = dindex
    return path


class TestDiscover:
    def test_discovery_base_fixture_has_runtime_loaded_files(self, tmp_path):
        """Verify discover reports correct schema, per-room LMDB hint fields,
        the runtime-traced loaded_files list, and genuine tracer-style
        trace_excerpt evidence for every room in the base fixture."""
        data = run_tool("discover", ROOT, tmp_path / "discovery.json")
        assert data["schema_version"] == 1
        by_room = {room["room"]: room for room in data["rooms"]}
        assert list(by_room) == sorted(rooms(ROOT))
        for room_id, hint in rooms(ROOT).items():
            item = by_room[room_id]
            assert item["title"] == hint["title"]
            assert item["lmdb_key"] == f"room:{room_id}"
            assert item["glyphs"] == hint["glyphs"]
            assert item["max_moves"] == hint["max_moves"]
            assert item["loaded_files"] == expected_files(ROOT, hint)
            assert item["trace_excerpt"], "trace evidence must not be empty"
            for line in item["trace_excerpt"]:
                assert TRACER_LINE.search(line), (
                    f"trace_excerpt line is not tracer-style evidence: {line!r}"
                )
                assert any(Path(path).name in line for path in item["loaded_files"]), (
                    f"trace_excerpt line does not mention a loaded file: {line!r}"
                )
            excerpt_text = " ".join(item["trace_excerpt"])
            for path in item["loaded_files"]:
                assert Path(path).name in excerpt_text, (
                    f"trace_excerpt must show evidence for every loaded file; "
                    f"missing {Path(path).name} for room {room_id}"
                )
            assert_trace_is_runtime_observed(item, ROOT, room_id)

    def test_discovery_overlay_follows_runtime_not_directory_layout(self, tmp_path):
        """The overlay rule file a room loads is picked by runtime logic; adding a
        new candidate overlay to a copied fixture changes the selection, which
        only genuine runtime observation reports correctly."""
        root = copy_fixture(tmp_path)
        extra = root / "rules" / "overlays" / "zenith.yaml"
        extra.write_text("mask_shift: 2\nrotation: 3\n")
        hint = mutate_room(
            root,
            "anvil",
            palette="lumen",
            pack="prism",
            salt=6,
            glyphs=["prism", "glint", "halo", "shard", "lens"],
        )
        data = run_tool("discover", root, tmp_path / "mutated-discovery.json")
        anvil = next(room for room in data["rooms"] if room["room"] == "anvil")
        assert anvil["glyphs"] == hint["glyphs"]
        assert anvil["loaded_files"] == expected_files(root, hint)
        assert str(root.resolve()) in anvil["loaded_files"][0]
        assert "/app/glyph-mill" not in json.dumps(anvil["loaded_files"])
        # The evidence must come from THIS copy of the fixture, not a canned
        # trace of the original: every line must reference the copied root, and
        # the runtime-selected overlay file must appear in the evidence.
        assert "/app/glyph-mill" not in json.dumps(anvil["trace_excerpt"])
        for line in anvil["trace_excerpt"]:
            assert str(root) in line or str(root.resolve()) in line, (
                f"trace_excerpt line does not reference the mutated copy: {line!r}"
            )
        overlay_name = overlay_path(root, hint).name
        assert any(overlay_name in line for line in anvil["trace_excerpt"]), (
            f"trace_excerpt must show the runtime-selected overlay {overlay_name}"
        )
        # And it must be genuine runtime evidence for THIS copy, not a
        # fabricated line: the nonce has to trace back to the daemon's audit
        # log bound to the mutated root and the reported loaded_files.
        assert_trace_is_runtime_observed(anvil, root, "anvil")


class TestNormalize:
    def test_normalized_rulebook_matches_runtime_sources(self, tmp_path):
        """Verify normalize's full output, field for field, against an
        independent reconstruction from the same LMDB hints and rule files."""
        actual = run_tool("normalize", ROOT, tmp_path / "rulebook.json")
        assert actual == expected_rulebook(ROOT)

    def test_glyph_values_covers_all_palette_symbols_not_just_room_glyphs(self, tmp_path):
        """Every palette carries at least one symbol that is not a legal glyph in
        any room; glyph_values must include it, so an implementation that maps
        only the room's own glyphs cannot pass."""
        actual = run_tool("normalize", ROOT, tmp_path / "rulebook.json")
        for room in actual["rooms"]:
            extras = set(room["glyph_values"]) - set(room["glyphs"])
            assert extras, (
                f"{room['room']}: glyph_values must cover every palette symbol, "
                f"including those absent from the room's glyphs; got only "
                f"{sorted(room['glyph_values'])}"
            )

    def test_normalize_recomputes_after_lmdb_yaml_and_overlay_mutation(self, tmp_path):
        """Mutating the LMDB salt changes which overlay the runtime picks; the
        normalized rulebook must follow both that switch and edited YAML values,
        including a brand-new palette symbol outside the room's glyph list."""
        root = copy_fixture(tmp_path)
        hint = mutate_room(root, "prism", salt=12)
        palette_path = root / "rules" / "palettes" / f"{hint['palette']}.yaml"
        palette = yaml.safe_load(palette_path.read_text())
        palette["symbols"]["halo"] = 14
        palette["symbols"]["quartz"] = 99
        palette_path.write_text(yaml.safe_dump(palette, sort_keys=False))
        opath = overlay_path(root, hint)
        overlay = yaml.safe_load(opath.read_text())
        overlay["mask_shift"] = int(overlay["mask_shift"]) + 5
        opath.write_text(yaml.safe_dump(overlay, sort_keys=False))
        actual = run_tool("normalize", root, tmp_path / "mutated-rulebook.json")
        assert actual == expected_rulebook(root)
        prism = next(room for room in actual["rooms"] if room["room"] == "prism")
        assert prism["salt"] == 12
        assert prism["glyph_values"]["halo"] == 14
        assert "quartz" not in prism["glyphs"]
        assert prism["glyph_values"]["quartz"] == 99, (
            "glyph_values must include palette symbols that are not room glyphs"
        )
        assert prism["overlay"] == opath.stem
        assert prism["mask_shift"] == overlay["mask_shift"]

    def test_stride_override_in_hint_takes_precedence_over_pack(self, tmp_path):
        """A room's own LMDB hint can carry a stride_override that overrides
        its pack's stride; normalize must report the hint's value, not the
        pack's, and must go back to the pack's value once the override is
        removed."""
        root = copy_fixture(tmp_path)
        hint = mutate_room(root, "estuary", stride_override=11)
        pack = load_pack(root, hint)
        assert pack["walk"]["stride"] != 11
        actual = run_tool("normalize", root, tmp_path / "override-rulebook.json")
        assert actual == expected_rulebook(root)
        estuary = next(room for room in actual["rooms"] if room["room"] == "estuary")
        assert estuary["stride"] == 11

        env = lmdb.open(str(root / "hints.lmdb"), readonly=False, lock=False, max_dbs=1)
        with env.begin(write=True) as txn:
            key = b"room:estuary"
            room = json.loads(txn.get(key).decode())
            del room["stride_override"]
            txn.put(key, json.dumps(room, sort_keys=True).encode())
        env.sync()
        env.close()
        reverted = run_tool("normalize", root, tmp_path / "reverted-rulebook.json")
        assert reverted == expected_rulebook(root)
        estuary_reverted = next(
            room for room in reverted["rooms"] if room["room"] == "estuary"
        )
        assert estuary_reverted["stride"] == pack["walk"]["stride"]


class TestSolve:
    def test_solve_route_passes_replay_and_respects_room_contract(self, tmp_path):
        """Verify solve's output schema, per-room glyph-count/subset
        constraints, and that the produced route is independently accepted by
        the compiled replay harness for every room."""
        route_path = tmp_path / "route.json"
        data = run_tool("solve", ROOT, route_path)
        assert data["schema_version"] == 1
        hint_map = rooms(ROOT)
        assert [room["room"] for room in data["rooms"]] == sorted(hint_map)
        for item in data["rooms"]:
            hint = hint_map[item["room"]]
            assert len(item["glyphs"]) == hint["max_moves"]
            assert set(item["glyphs"]).issubset(set(hint["glyphs"]))
        code, replay_data = replay(ROOT, route_path)
        assert code == 0, replay_data
        assert replay_data["accepted"] is True
        assert all(room["accepted"] for room in replay_data["rooms"])

    def test_solve_recomputes_for_mutated_copy(self, tmp_path):
        """Mutating the salt changes the overlay selection and the walk formula;
        the solver must recompute a genuinely new route for the new target."""
        root = copy_fixture(tmp_path)
        mutate_room(root, "estuary", salt=9)
        hint = rooms(root)["estuary"]
        probe = [hint["glyphs"][i % len(hint["glyphs"])] for i in range(hint["max_moves"])]
        path = simulate(root, hint, probe)
        mutate_room(
            root,
            "estuary",
            target=path[-1],
            beacons={"5": path[5], "11": path[11], "16": path[16]},
        )
        route_path = tmp_path / "mutated-route.json"
        data = run_tool("solve", root, route_path)
        estuary = next(room for room in data["rooms"] if room["room"] == "estuary")
        assert len(estuary["glyphs"]) == hint["max_moves"]
        assert set(estuary["glyphs"]).issubset(set(hint["glyphs"]))
        code, replay_data = replay(root, route_path)
        assert code == 0, replay_data
        assert replay_data["accepted"] is True

    def test_earlier_commands_still_work_after_solver(self, tmp_path):
        """Verify discover and normalize still run correctly after solve has
        been added, i.e. adding the solver didn't regress earlier commands."""
        run_tool("solve", ROOT, tmp_path / "route.json")
        disc = run_tool("discover", ROOT, tmp_path / "discovery.json")
        rb = run_tool("normalize", ROOT, tmp_path / "rulebook.json")
        assert len(disc["rooms"]) == len(rb["rooms"]) == len(rooms(ROOT))
