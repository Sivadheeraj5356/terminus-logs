"""Behavioral tests for the hex skirmish adjudicator."""

from __future__ import annotations

import json
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

BIN = Path("/app/bin/skirmish")
WORKDIR = Path("/app")


def cube_distance(a: list[int], b: list[int]) -> int:
    dx = abs(a[0] - b[0])
    dy = abs(a[1] - b[1])
    dz = abs((a[0] + a[1]) - (b[0] + b[1]))
    return max(dx, dy, dz)


NEIGHBORS = (
    (1, 0),
    (-1, 0),
    (0, 1),
    (0, -1),
    (1, -1),
    (-1, 1),
)


def neighbors(x: int, y: int) -> list[list[int]]:
    return [[x + dx, y + dy] for dx, dy in NEIGHBORS]


def hex_line(a: list[int], b: list[int]) -> list[list[int]]:
    n = max(cube_distance(a, b), 1)
    out: list[list[int]] = []
    for i in range(n + 1):
        t = i / n
        x = round(a[0] + (b[0] - a[0]) * t)
        y = round(a[1] + (b[1] - a[1]) * t)
        if not out or out[-1] != [x, y]:
            out.append([x, y])
    if out[-1] != b:
        out.append(list(b))
    return out


def has_los(mp: dict[str, Any], frm: list[int], to: list[int]) -> bool:
    w, h = mp["width"], mp["height"]
    if not (0 <= frm[0] < w and 0 <= frm[1] < h and 0 <= to[0] < w and 0 <= to[1] < h):
        return False
    start_e = mp["elevation"][frm[1]][frm[0]]
    end_e = mp["elevation"][to[1]][to[0]]
    thresh = max(start_e, end_e) + 1
    line = hex_line(frm, to)
    for idx, cell in enumerate(line):
        if idx == 0 or idx + 1 == len(line):
            continue
        if not (0 <= cell[0] < w and 0 <= cell[1] < h):
            return False
        if mp["blocked"][cell[1]][cell[0]]:
            return False
        if mp["elevation"][cell[1]][cell[0]] >= thresh:
            return False
    return True


def can_see(obs: dict[str, Any], tgt: dict[str, Any], beacons: list[dict[str, Any]]) -> bool:
    if not tgt.get("alive", True):
        return False
    if obs["team"] == tgt["team"]:
        return True
    if cube_distance(obs["hex"], tgt["hex"]) <= obs["vision"]:
        return True
    return any(
        b["team"] == obs["team"] and cube_distance(b["hex"], tgt["hex"]) <= b["radius"]
        for b in beacons
    )


def strike_damage(traits: list[str], armor: int) -> int:
    if "PIERCE" in traits:
        return 4
    return max(1, 4 - armor)


def canonical_events_digest(events: list[dict[str, Any]]) -> str:
    def norm(o: Any) -> Any:
        if isinstance(o, dict):
            return {k: norm(o[k]) for k in sorted(o)}
        if isinstance(o, list):
            return [norm(x) for x in o]
        return o

    raw = json.dumps(norm(events), separators=(",", ":"), ensure_ascii=False)
    proc = subprocess.run(
        ["sha256sum"],
        input=raw.encode(),
        capture_output=True,
        check=True,
    )
    digest = proc.stdout.decode().split()[0]
    return "sha256:" + digest


def invalid_reason(scenario: dict[str, Any]) -> str | None:
    units = sorted(scenario["units"], key=lambda u: u["id"])
    mp = scenario["map"]
    for u in units:
        x, y = u["hex"]
        if not (0 <= x < mp["width"] and 0 <= y < mp["height"]):
            return "OOB"
        if mp["blocked"][y][x]:
            return "BLOCKED"
    for i, a in enumerate(units):
        for b in units[i + 1 :]:
            if a["hex"] == b["hex"]:
                return "OVERLAP"
    return None


def expect_adjudicate(scenario: dict[str, Any]) -> dict[str, Any]:
    reason = invalid_reason(scenario)
    if reason:
        return {
            "schema_version": 1,
            "status": "INVALID",
            "invalid_reason": reason,
            "initiative": [],
            "events": [],
            "survivors": [],
            "transcript_digest": canonical_events_digest([]),
        }

    units = []
    for u in scenario["units"]:
        units.append(
            {
                **deepcopy(u),
                "base_armor": u["armor"],
                "alive": True,
                "morale_broken": False,
                "actions_cancelled": False,
            }
        )
    mp = scenario["map"]
    beacons = scenario.get("beacons", [])
    order = sorted(units, key=lambda u: (-u["speed"], u["id"]))
    initiative = [u["id"] for u in order]
    events: list[dict[str, Any]] = []
    seq = 0

    def emit(kind: str, **fields: Any) -> None:
        nonlocal seq
        ev = {"seq": seq, "kind": kind}
        ev.update({k: v for k, v in fields.items() if v is not None})
        events.append(ev)
        seq += 1

    def living(uid: str) -> dict[str, Any] | None:
        for u in units:
            if u["id"] == uid and u["alive"]:
                return u
        return None

    def apply_damage(tid: str, dmg: int) -> None:
        t = living(tid)
        if not t:
            return
        t["hp"] -= dmg
        if t["hp"] <= 0:
            t["alive"] = False
            t["hp"] = 0
            emit("DOWNED", actor=tid)
            return
        if 0 < t["hp"] < 3:
            t["morale_broken"] = True
            t["actions_cancelled"] = True
            emit("MORALE_BREAK", actor=tid)

    for actor_id in initiative:
        actor = living(actor_id)
        if not actor or actor["actions_cancelled"] or actor["morale_broken"]:
            continue
        actor["armor"] = actor["base_armor"]
        emit("TURN_START", actor=actor_id)
        for action in list(actor["actions"]):
            actor = living(actor_id)
            if not actor or actor["actions_cancelled"] or actor["morale_broken"]:
                break
            if action.startswith("MOVE:"):
                spec = action.split(":", 1)[1]
                try:
                    xs, ys = spec.split(",")
                    to = [int(xs), int(ys)]
                except ValueError:
                    emit("ACTION_FAIL", actor=actor_id, detail="ILLEGAL_MOVE")
                    continue
                frm = list(actor["hex"])
                ok = to in neighbors(frm[0], frm[1])
                if ok:
                    if not (0 <= to[0] < mp["width"] and 0 <= to[1] < mp["height"]):
                        ok = False
                    elif mp["blocked"][to[1]][to[0]]:
                        ok = False
                    elif any(u["alive"] and u["hex"] == to and u["id"] != actor_id for u in units):
                        ok = False
                if not ok:
                    emit("ACTION_FAIL", actor=actor_id, detail="ILLEGAL_MOVE")
                    continue
                actor["hex"] = to
                emit("MOVE", actor=actor_id, **{"from": frm, "to": to})
                ow_ids = []
                mover = living(actor_id)
                if mover:
                    for u in units:
                        if (
                            u["alive"]
                            and u["team"] != mover["team"]
                            and "OVERWATCH" in u.get("traits", [])
                            and can_see(u, mover, beacons)
                            and has_los(mp, u["hex"], mover["hex"])
                            and cube_distance(u["hex"], mover["hex"]) <= u["range"]
                        ):
                            ow_ids.append(u["id"])
                for ow in sorted(ow_ids):
                    if not living(actor_id):
                        break
                    atk = living(ow)
                    tgt = living(actor_id)
                    if not atk or not tgt:
                        continue
                    dmg = strike_damage(atk.get("traits", []), tgt["armor"])
                    emit("OVERWATCH", actor=ow, target=actor_id, damage=dmg)
                    apply_damage(actor_id, dmg)
            elif action == "STRIKE":
                cands = []
                for u in units:
                    if (
                        u["alive"]
                        and u["team"] != actor["team"]
                        and can_see(actor, u, beacons)
                        and has_los(mp, actor["hex"], u["hex"])
                        and cube_distance(actor["hex"], u["hex"]) <= actor["range"]
                    ):
                        cands.append(u)
                cands.sort(key=lambda u: (cube_distance(actor["hex"], u["hex"]), u["id"]))
                if not cands:
                    emit("ACTION_FAIL", actor=actor_id, detail="NO_TARGET")
                    continue
                tgt = cands[0]
                dmg = strike_damage(actor.get("traits", []), tgt["armor"])
                emit("STRIKE", actor=actor_id, target=tgt["id"], damage=dmg)
                apply_damage(tgt["id"], dmg)
            elif action == "GUARD":
                actor["armor"] += 1
                emit("GUARD", actor=actor_id)
            else:
                emit("ACTION_FAIL", actor=actor_id, detail="UNKNOWN_ACTION")

    survivors = sorted(
        [
            {"id": u["id"], "hp": u["hp"], "hex": u["hex"], "armor": u["armor"]}
            for u in units
            if u["alive"]
        ],
        key=lambda s: s["id"],
    )
    return {
        "schema_version": 1,
        "status": "RESOLVED",
        "invalid_reason": None,
        "initiative": initiative,
        "events": events,
        "survivors": survivors,
        "transcript_digest": canonical_events_digest(events),
    }


def run_bin(scenario: dict[str, Any], out: Path) -> subprocess.CompletedProcess[str]:
    scen = out.parent / "scenario.json"
    scen.write_text(json.dumps(scenario), encoding="utf-8")
    return subprocess.run(
        [str(BIN), "adjudicate", "--scenario", str(scen), "--out", str(out)],
        cwd=str(WORKDIR),
        capture_output=True,
        text=True,
        check=False,
    )


def load_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_match(got: dict[str, Any], exp: dict[str, Any]) -> None:
    assert got["schema_version"] == exp["schema_version"]
    assert got["status"] == exp["status"]
    assert got["invalid_reason"] == exp["invalid_reason"]
    assert got["initiative"] == exp["initiative"]
    assert got["events"] == exp["events"]
    assert got["survivors"] == exp["survivors"]
    assert got["transcript_digest"] == exp["transcript_digest"]
    assert got["transcript_digest"].startswith("sha256:")
    assert got["transcript_digest"] == canonical_events_digest(got["events"])


def blank_map(w: int, h: int, elev: int = 0) -> dict[str, Any]:
    return {
        "width": w,
        "height": h,
        "elevation": [[elev for _ in range(w)] for _ in range(h)],
        "blocked": [[False for _ in range(w)] for _ in range(h)],
    }


def unit(
    uid: str,
    team: str,
    hex_: list[int],
    *,
    hp: int = 8,
    armor: int = 1,
    speed: int = 2,
    vision: int = 3,
    range_: int = 2,
    traits: list[str] | None = None,
    actions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": uid,
        "team": team,
        "hex": hex_,
        "hp": hp,
        "armor": armor,
        "speed": speed,
        "vision": vision,
        "range": range_,
        "traits": traits or [],
        "actions": actions or [],
    }


@pytest.fixture()
def tmp_out(tmp_path: Path) -> Path:
    return tmp_path / "report.json"


def test_binary_rebuilds_and_solo_move(tmp_out: Path) -> None:
    """Solo MOVE still resolves and emits a digest-backed transcript."""
    scen = {
        "map": blank_map(4, 3),
        "units": [unit("scout", "blue", [0, 0], actions=["MOVE:1,0"])],
        "beacons": [],
    }
    exp = expect_adjudicate(scen)
    proc = run_bin(scen, tmp_out)
    assert proc.returncode == 0, proc.stderr
    assert_match(load_report(tmp_out), exp)


def test_initiative_speed_desc_id_asc(tmp_out: Path) -> None:
    """Faster units act first; equal speed breaks on ascending id."""
    scen = {
        "map": blank_map(5, 3),
        "units": [
            unit("b", "blue", [0, 0], speed=3, actions=["GUARD"]),
            unit("a", "blue", [1, 0], speed=3, actions=["GUARD"]),
            unit("c", "red", [4, 0], speed=5, actions=["GUARD"]),
        ],
        "beacons": [],
    }
    exp = expect_adjudicate(scen)
    assert exp["initiative"] == ["c", "a", "b"]
    proc = run_bin(scen, tmp_out)
    assert proc.returncode == 0
    assert_match(load_report(tmp_out), exp)


def test_pierce_ignores_armor(tmp_out: Path) -> None:
    """PIERCE deals flat 4 even against armored targets."""
    scen = {
        "map": blank_map(4, 2),
        "units": [
            unit("blade", "blue", [0, 0], speed=4, armor=0, traits=["PIERCE"], actions=["STRIKE"]),
            unit("tank", "red", [1, 0], speed=1, armor=3, hp=10, actions=[]),
        ],
        "beacons": [],
    }
    exp = expect_adjudicate(scen)
    strike = [e for e in exp["events"] if e["kind"] == "STRIKE"][0]
    assert strike["damage"] == 4
    proc = run_bin(scen, tmp_out)
    assert proc.returncode == 0
    assert_match(load_report(tmp_out), exp)


def test_overwatch_interrupt_kind_and_order(tmp_out: Path) -> None:
    """After MOVE, OVERWATCH fires as OVERWATCH events in ascending id."""
    scen = {
        "map": blank_map(6, 3),
        "units": [
            unit("mover", "blue", [0, 1], speed=5, actions=["MOVE:1,1"]),
            unit("z_ow", "red", [3, 1], speed=1, range_=3, traits=["OVERWATCH"], actions=[]),
            unit("a_ow", "red", [2, 0], speed=1, range_=3, traits=["OVERWATCH"], actions=[]),
        ],
        "beacons": [],
    }
    exp = expect_adjudicate(scen)
    kinds = [e["kind"] for e in exp["events"]]
    assert "OVERWATCH" in kinds
    ow = [e for e in exp["events"] if e["kind"] == "OVERWATCH"]
    assert [e["actor"] for e in ow] == sorted(e["actor"] for e in ow)
    proc = run_bin(scen, tmp_out)
    assert proc.returncode == 0
    assert_match(load_report(tmp_out), exp)


def test_beacon_team_vision(tmp_out: Path) -> None:
    """Enemy beacons must not grant vision; allied beacons must."""
    mp = blank_map(8, 3)
    scen = {
        "map": mp,
        "units": [
            unit("sniper", "blue", [0, 1], speed=4, vision=1, range_=6, actions=["STRIKE"]),
            unit("spot", "red", [6, 1], speed=1, hp=8, armor=0, actions=[]),
        ],
        "beacons": [{"hex": [6, 1], "radius": 1, "team": "blue"}],
    }
    exp = expect_adjudicate(scen)
    assert any(e["kind"] == "STRIKE" for e in exp["events"])
    proc = run_bin(scen, tmp_out)
    assert proc.returncode == 0
    assert_match(load_report(tmp_out), exp)

    scen2 = deepcopy(scen)
    scen2["beacons"] = [{"hex": [6, 1], "radius": 1, "team": "red"}]
    exp2 = expect_adjudicate(scen2)
    assert any(e.get("detail") == "NO_TARGET" for e in exp2["events"])
    out2 = tmp_out.parent / "report2.json"
    proc2 = run_bin(scen2, out2)
    assert proc2.returncode == 0
    assert_match(load_report(out2), exp2)


def test_morale_break_cancels_remaining(tmp_out: Path) -> None:
    """hp after hit in {1,2} morale-breaks and cancels remaining actions."""
    scen = {
        "map": blank_map(4, 2),
        "units": [
            unit("hit", "blue", [0, 0], speed=5, armor=0, actions=["STRIKE"]),
            # armor 2 -> damage 2; hp 4 -> 2 triggers morale (<3), not the stricter <2 trap
            unit("prey", "red", [1, 0], speed=1, hp=4, armor=2, actions=["STRIKE", "GUARD"]),
        ],
        "beacons": [],
    }
    exp = expect_adjudicate(scen)
    prey_combat = [
        e for e in exp["events"] if e.get("actor") == "prey" and e["kind"] in ("STRIKE", "GUARD")
    ]
    assert prey_combat == []
    assert any(e["kind"] == "MORALE_BREAK" for e in exp["events"])
    proc = run_bin(scen, tmp_out)
    assert proc.returncode == 0
    assert_match(load_report(tmp_out), exp)


def test_invalid_reason_precedence(tmp_out: Path) -> None:
    """OOB wins over BLOCKED/OVERLAP when checked in ascending id order."""
    mp = blank_map(3, 3)
    mp["blocked"][1][1] = True
    scen = {
        "map": mp,
        "units": [
            unit("a", "blue", [9, 0], actions=[]),  # OOB
            unit("b", "red", [1, 1], actions=[]),  # blocked
            unit("c", "red", [0, 0], actions=[]),
            unit("d", "blue", [0, 0], actions=[]),  # overlap with c
        ],
        "beacons": [],
    }
    exp = expect_adjudicate(scen)
    assert exp["status"] == "INVALID"
    assert exp["invalid_reason"] == "OOB"
    proc = run_bin(scen, tmp_out)
    assert proc.returncode == 2
    assert_match(load_report(tmp_out), exp)


def test_guard_armor_persists_until_next_turn(tmp_out: Path) -> None:
    """GUARD raises armor for end-state when the unit does not take another turn."""
    scen = {
        "map": blank_map(3, 3),
        "units": [unit("keeper", "red", [1, 1], armor=2, speed=1, actions=["GUARD"])],
        "beacons": [],
    }
    exp = expect_adjudicate(scen)
    assert exp["survivors"][0]["armor"] == 3
    proc = run_bin(scen, tmp_out)
    assert proc.returncode == 0
    assert_match(load_report(tmp_out), exp)


def test_los_elevation_blocks_strike(tmp_out: Path) -> None:
    """Elevation ridge blocks LOS between otherwise in-range units."""
    mp = blank_map(5, 1)
    mp["elevation"] = [[0, 0, 3, 0, 0]]
    scen = {
        "map": mp,
        "units": [
            unit("a", "blue", [0, 0], speed=3, range_=4, actions=["STRIKE"]),
            unit("b", "red", [4, 0], speed=1, actions=[]),
        ],
        "beacons": [],
    }
    exp = expect_adjudicate(scen)
    assert any(e.get("detail") == "NO_TARGET" for e in exp["events"])
    proc = run_bin(scen, tmp_out)
    assert proc.returncode == 0
    assert_match(load_report(tmp_out), exp)


def test_dynamic_seeded_cases(tmp_out: Path) -> None:
    """Verifier-only generated scenarios must match the independent oracle."""
    cases = []
    for i in range(3):
        mp = blank_map(7, 4)
        if i == 1:
            mp["blocked"][2][3] = True
        cases.append(
            {
                "map": mp,
                "units": [
                    unit(
                        f"u{i}a",
                        "blue",
                        [0, i % 3],
                        speed=3 + i,
                        armor=i % 2,
                        traits=["PIERCE"] if i == 2 else [],
                        actions=[f"MOVE:1,{i % 3}", "STRIKE"],
                    ),
                    unit(
                        f"u{i}b",
                        "red",
                        [3, i % 3],
                        speed=2,
                        hp=9,
                        armor=2,
                        range_=3,
                        traits=["OVERWATCH"],
                        actions=["GUARD"],
                    ),
                ],
                "beacons": [{"hex": [3, i % 3], "radius": 2, "team": "blue"}] if i == 0 else [],
            }
        )
    for idx, scen in enumerate(cases):
        exp = expect_adjudicate(scen)
        out = tmp_out.parent / f"dyn_{idx}.json"
        proc = run_bin(scen, out)
        assert proc.returncode == 0, proc.stderr
        assert_match(load_report(out), exp)


def test_digest_is_canonical_sorted(tmp_out: Path) -> None:
    """transcript_digest must hash sorted-key compact JSON of events."""
    scen = {
        "map": blank_map(3, 2),
        "units": [
            unit("a", "blue", [0, 0], speed=2, actions=["MOVE:1,0", "GUARD"]),
            unit("b", "red", [2, 0], speed=1, actions=["GUARD"]),
        ],
        "beacons": [],
    }
    exp = expect_adjudicate(scen)
    proc = run_bin(scen, tmp_out)
    assert proc.returncode == 0
    got = load_report(tmp_out)
    assert_match(got, exp)
    # Mutating event key order in a re-serialized form must still match digest helper
    shuffled = []
    for e in got["events"]:
        shuffled.append({k: e[k] for k in sorted(e.keys(), reverse=True)})
    assert canonical_events_digest(shuffled) == got["transcript_digest"]


def test_cube_distance_used_for_range(tmp_out: Path) -> None:
    """Cube range admits [0,0]->[2,-1] (dist 2) where manhattan is 3."""
    scen = {
        "map": blank_map(5, 5),
        "units": [
            unit("a", "blue", [0, 2], speed=3, range_=2, vision=5, actions=["STRIKE"]),
            unit("b", "red", [2, 1], speed=1, hp=6, armor=0, actions=[]),
        ],
        "beacons": [],
    }
    assert cube_distance([0, 2], [2, 1]) == 2
    assert abs(0 - 2) + abs(2 - 1) == 3
    exp = expect_adjudicate(scen)
    assert any(e["kind"] == "STRIKE" for e in exp["events"])
    proc = run_bin(scen, tmp_out)
    assert proc.returncode == 0
    assert_match(load_report(tmp_out), exp)
