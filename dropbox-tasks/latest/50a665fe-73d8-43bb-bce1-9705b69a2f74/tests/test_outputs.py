from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest

ROOT = Path("/app/task_file")
SOURCE = ROOT / "main.go"
BINARY = ROOT / "conclave"
PUBLIC = ROOT / "input/public_match.json"
RULES = ROOT / "arena_rules.md"
REVIEW_OUTPUT = ROOT / "output/adjudication.json"
PUBLIC_SHA256 = "224019dd7e87e2e2071a68f7990d224e2d776093bdddb479e9af4ac50ecffefe"
RULES_SHA256 = "04794cd2faf104ab5566be1e4193f0801db4a9d1ad523015434bfc5548203243"

ATT = {"sun": 0, "moon": 1, "star": 2}
ATT_NAME = ("sun", "moon", "star")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class PMove:
    kind: str
    key: str
    card: int = -1
    site: int = -1
    a: int = -1
    b: int = -1


@dataclass(frozen=True)
class RMove:
    kind: str
    key: str
    omen: int = -1
    site: int = -1


class RefGame:
    def __init__(self, doc: dict):
        self.doc = doc
        self.rounds = doc["rounds"]
        self.energy_cap = doc["energy_cap"]
        self.strain_limit = doc["strain_limit"]
        sites = sorted(doc["sites"], key=lambda s: s["id"])
        self.site_ids = tuple(s["id"] for s in sites)
        self.thresholds = tuple(s["threshold"] for s in sites)
        self.values = tuple(s["value"] for s in sites)
        self.site_index = {v: i for i, v in enumerate(self.site_ids)}
        self.initial_sites = tuple(
            (ATT[s["attunement"]], s["power"], s["ward"], s["strain"], s["curse"])
            for s in sites
        )
        edges = []
        for raw_a, raw_b in doc["edges"]:
            a, b = self.site_index[raw_a], self.site_index[raw_b]
            edges.append((min(a, b), max(a, b)))
        self.edges = tuple(sorted(edges))
        adjacent = [[] for _ in sites]
        for a, b in self.edges:
            adjacent[a].append(b)
            adjacent[b].append(a)
        self.adjacent = tuple(tuple(sorted(x)) for x in adjacent)

        cards = sorted(doc["cards"], key=lambda c: c["id"])
        self.cards = tuple(
            (c["id"], ATT[c["school"]], c["style"], c["power"], c["cost"])
            for c in cards
        )
        omens = sorted(doc["omens"], key=lambda o: o["id"])
        self.omens = tuple(
            (
                o["id"],
                o["kind"],
                o["magnitude"],
                tuple(sorted(self.site_index[t] for t in o["targets"])),
            )
            for o in omens
        )
        self.initial = (
            0,
            doc["energy"],
            doc["channel_tokens"],
            doc["rotate_tokens"],
            doc["focus_tokens"],
            -1,
            0,
            0,
            self.initial_sites,
        )

    def controlled(self, sites: tuple[tuple[int, int, int, int, int], ...], i: int) -> bool:
        _att, power, _ward, strain, _curse = sites[i]
        return power >= self.thresholds[i] and strain < self.strain_limit

    def player_actions(self, state: tuple) -> tuple[PMove, ...]:
        _rnd, energy, channels, rotates, focuses, _prev, used_cards, _used_omens, _sites = state
        out = []
        for ci, (cid, _school, _style, _power, cost) in enumerate(self.cards):
            if used_cards & (1 << ci) or cost > energy:
                continue
            for si, sid in enumerate(self.site_ids):
                out.append(PMove("deploy", f"deploy|{cid}|{sid}", card=ci, site=si))
        if channels:
            for si, sid in enumerate(self.site_ids):
                out.append(PMove("channel", f"channel|{sid}", site=si))
        if rotates and energy >= 1:
            for a, b in self.edges:
                out.append(PMove("rotate", f"rotate|{self.site_ids[a]}|{self.site_ids[b]}", a=a, b=b))
        if focuses and energy >= 1:
            for a, b in self.edges:
                out.append(PMove("focus", f"focus|{self.site_ids[a]}|{self.site_ids[b]}", a=a, b=b))
                out.append(PMove("focus", f"focus|{self.site_ids[b]}|{self.site_ids[a]}", a=b, b=a))
        out.append(PMove("rest", "rest"))
        return tuple(sorted(out, key=lambda m: m.key))

    def apply_player(self, state: tuple, move: PMove) -> tuple:
        rnd, energy, channels, rotates, focuses, previous, used_cards, used_omens, sites_raw = state
        sites = [list(s) for s in sites_raw]
        if move.kind == "deploy":
            _cid, school, style, power, cost = self.cards[move.card]
            was_controlled = self.controlled(sites_raw, move.site)
            energy -= cost
            gain = power + (2 if school == sites[move.site][0] else 0) + (1 if previous == school else 0)
            sites[move.site][1] += gain
            if was_controlled:
                sites[move.site][3] += 1
            if style == "aegis":
                sites[move.site][2] += 2
            elif style == "link":
                for other in self.adjacent[move.site]:
                    sites[other][1] += 1
            previous = school
            used_cards |= 1 << move.card
        elif move.kind == "channel":
            channels -= 1
            energy = min(self.energy_cap, energy + 2)
            sites[move.site][2] += 1
            sites[move.site][3] += 1
            previous = -1
        elif move.kind == "rotate":
            rotates -= 1
            energy -= 1
            sites[move.a][0], sites[move.b][0] = sites[move.b][0], sites[move.a][0]
            previous = -1
        elif move.kind == "focus":
            focuses -= 1
            energy -= 1
            moved_ward = min(2, sites[move.a][2])
            sites[move.a][2] -= moved_ward
            sites[move.b][2] += moved_ward
            if sites[move.a][1] > 0:
                sites[move.a][1] -= 1
                sites[move.b][1] += 1
            sites[move.b][3] += 1
            previous = -1
        else:
            energy = min(self.energy_cap, energy + 1)
            previous = -1
        return rnd, energy, channels, rotates, focuses, previous, used_cards, used_omens, tuple(tuple(s) for s in sites)

    def rival_actions(self, state: tuple) -> tuple[RMove, ...]:
        used_omens = state[7]
        out = []
        for oi, (oid, kind, _magnitude, targets) in enumerate(self.omens):
            if used_omens & (1 << oi):
                continue
            if kind == "tax":
                out.append(RMove("omen", f"omen|{oid}|-", omen=oi))
            else:
                for site in targets:
                    out.append(RMove("omen", f"omen|{oid}|{self.site_ids[site]}", omen=oi, site=site))
        if not out:
            out.append(RMove("pass", "pass"))
        return tuple(sorted(out, key=lambda m: m.key))

    @staticmethod
    def absorb(site: list[int], magnitude: int) -> int:
        blocked = min(site[2], magnitude)
        site[2] -= blocked
        return magnitude - blocked

    def apply_rival(self, state: tuple, move: RMove) -> tuple:
        rnd, energy, channels, rotates, focuses, previous, used_cards, used_omens, sites_raw = state
        sites = [list(s) for s in sites_raw]
        if move.kind == "omen":
            _oid, kind, magnitude, _targets = self.omens[move.omen]
            used_omens |= 1 << move.omen
            if kind == "drain":
                left = self.absorb(sites[move.site], magnitude)
                sites[move.site][1] = max(0, sites[move.site][1] - left)
            elif kind == "fracture":
                left = self.absorb(sites[move.site], magnitude)
                sites[move.site][3] += left
            elif kind == "eclipse":
                if sites[move.site][2] > 0:
                    sites[move.site][2] -= 1
                else:
                    sites[move.site][0] = (sites[move.site][0] + magnitude) % 3
            elif kind == "curse":
                sites[move.site][4] += magnitude
            else:
                energy = max(0, energy - magnitude)
        for site in sites:
            if site[4] > 0:
                site[1] = max(0, site[1] - 1)
                site[4] -= 1
            if site[3] >= self.strain_limit:
                site[1] = max(0, site[1] - 1)
        sites_tuple = tuple(tuple(s) for s in sites)
        energy = min(
            self.energy_cap,
            energy + sum(self.controlled(sites_tuple, i) for i in range(len(sites))),
        )
        return rnd + 1, energy, channels, rotates, focuses, previous, used_cards, used_omens, sites_tuple

    def player_json(self, move: PMove) -> dict:
        out = {"kind": move.kind, "card": None, "site": None, "edge": None}
        if move.kind == "deploy":
            out["card"] = self.cards[move.card][0]
            out["site"] = self.site_ids[move.site]
        elif move.kind == "channel":
            out["site"] = self.site_ids[move.site]
        elif move.kind in ("rotate", "focus"):
            out["edge"] = [self.site_ids[move.a], self.site_ids[move.b]]
        return out

    def rival_json(self, move: RMove) -> dict:
        out = {"kind": move.kind, "omen": None, "site": None}
        if move.kind == "omen":
            out["omen"] = self.omens[move.omen][0]
            if move.site >= 0:
                out["site"] = self.site_ids[move.site]
        return out

    def terminal(self, state: tuple) -> tuple[int, tuple, dict]:
        _rnd, energy, _channels, _rotates, _focuses, _previous, _used_cards, _used_omens, sites = state
        controlled = []
        attunements = set()
        final_sites = []
        score = energy
        for i, (att, power, ward, strain, curse) in enumerate(sites):
            ctrl = self.controlled(sites, i)
            if ctrl:
                controlled.append(self.site_ids[i])
                attunements.add(att)
                score += self.values[i]
            score -= strain
            final_sites.append(
                {
                    "id": self.site_ids[i],
                    "attunement": ATT_NAME[att],
                    "power": power,
                    "ward": ward,
                    "strain": strain,
                    "curse": curse,
                    "controlled": ctrl,
                }
            )
        score += 2 * len(attunements)
        if len(controlled) == len(sites):
            score += 4
        final = {"energy": energy, "controlled": controlled, "sites": final_sites}
        return score, tuple(), final

    def adjudicate(self) -> dict:
        @cache
        def solve(state: tuple) -> tuple[int, tuple, dict]:
            if state[0] == self.rounds:
                return self.terminal(state)
            best = None
            best_player_key = None
            for pm in self.player_actions(state):
                after_player = self.apply_player(state, pm)
                worst = None
                worst_rival_key = None
                for rm in self.rival_actions(after_player):
                    score, tail, final = solve(self.apply_rival(after_player, rm))
                    step = {
                        "round": state[0] + 1,
                        "player": self.player_json(pm),
                        "rival": self.rival_json(rm),
                    }
                    candidate = (score, (step,) + tail, final)
                    if worst is None or score < worst[0] or (score == worst[0] and rm.key < worst_rival_key):
                        worst = candidate
                        worst_rival_key = rm.key
                if best is None or worst[0] > best[0] or (worst[0] == best[0] and pm.key < best_player_key):
                    best = worst
                    best_player_key = pm.key
            return best

        score, line, final = solve(self.initial)
        solve.cache_clear()
        return {"guaranteed_score": score, "line": list(line), "final": final}


def site(id_: str, att: str, power: int, threshold: int, value: int, ward: int = 0, strain: int = 0, curse: int = 0) -> dict:
    return {"id": id_, "attunement": att, "power": power, "ward": ward, "strain": strain, "curse": curse, "threshold": threshold, "value": value}


def card(id_: str, school: str, style: str, power: int, cost: int) -> dict:
    return {"id": id_, "school": school, "style": style, "power": power, "cost": cost}


def omen(id_: str, kind: str, magnitude: int, targets: list[str] | None = None) -> dict:
    return {"id": id_, "kind": kind, "magnitude": magnitude, "targets": targets or []}


def position(*, rounds=3, energy=3, cap=7, channels=1, rotates=1, focuses=0, limit=3, sites=None, edges=None, cards=None, omens=None) -> dict:
    return {
        "version": 1,
        "rounds": rounds,
        "energy": energy,
        "energy_cap": cap,
        "channel_tokens": channels,
        "rotate_tokens": rotates,
        "focus_tokens": focuses,
        "strain_limit": limit,
        "sites": sites,
        "edges": edges,
        "cards": cards,
        "omens": omens,
    }


BASE_SITES = [site("a", "sun", 2, 6, 5), site("b", "moon", 3, 6, 6, ward=1), site("c", "star", 1, 5, 4)]
BASE_EDGES = [["a", "b"], ["b", "c"]]
BASE_CARDS = [
    card("c1", "sun", "strike", 3, 2),
    card("c2", "moon", "aegis", 2, 1),
    card("c3", "star", "link", 3, 2),
    card("c4", "sun", "aegis", 2, 1),
]
BASE_OMENS = [
    omen("o1", "drain", 2, ["a", "b"]),
    omen("o2", "fracture", 2, ["b", "c"]),
    omen("o3", "eclipse", 1, ["a", "c"]),
]


def compatibility_cases() -> list[tuple[str, dict]]:
    cases = []
    cases.append(("basic_strike_tax", position(rounds=2, energy=2, cap=5, channels=0, rotates=0,
        sites=[site("n", "sun", 1, 5, 4), site("s", "moon", 2, 5, 5)], edges=[["n", "s"]],
        cards=[card("red", "sun", "strike", 3, 1), card("blue", "moon", "strike", 2, 1)],
        omens=[omen("cut", "drain", 2, ["n", "s"]), omen("tax", "tax", 1)])))
    cases.append(("aegis_absorption", position(sites=copy.deepcopy(BASE_SITES), edges=copy.deepcopy(BASE_EDGES),
        cards=copy.deepcopy(BASE_CARDS), omens=[omen("d", "drain", 4, ["a", "b", "c"]), omen("f", "fracture", 3, ["a", "c"]), omen("t", "tax", 2)])))
    cases.append(("fracture_overload", position(limit=2, sites=[site("a", "sun", 5, 5, 8, strain=1), site("b", "moon", 4, 5, 6), site("c", "star", 2, 4, 4)],
        edges=copy.deepcopy(BASE_EDGES), cards=copy.deepcopy(BASE_CARDS), omens=copy.deepcopy(BASE_OMENS))))
    cases.append(("link_ring", position(sites=copy.deepcopy(BASE_SITES), edges=[["a", "b"], ["b", "c"], ["a", "c"]],
        cards=[card("link1", "star", "link", 3, 2), card("link2", "moon", "link", 2, 1), card("guard", "sun", "aegis", 2, 1), card("hit", "sun", "strike", 4, 3)],
        omens=copy.deepcopy(BASE_OMENS))))
    cases.append(("rotation_eclipse", position(rotates=2, sites=copy.deepcopy(BASE_SITES), edges=copy.deepcopy(BASE_EDGES),
        cards=[card("m", "moon", "strike", 4, 2), card("s", "star", "aegis", 3, 2), card("u", "sun", "link", 2, 1)],
        omens=[omen("e1", "eclipse", 1, ["a", "b"]), omen("e2", "eclipse", 2, ["b", "c"]), omen("d", "drain", 2, ["a", "c"])])))
    cases.append(("channel_cap", position(energy=0, cap=4, channels=2, rotates=0, sites=copy.deepcopy(BASE_SITES), edges=copy.deepcopy(BASE_EDGES),
        cards=[card("costly", "sun", "strike", 6, 4), card("guard", "moon", "aegis", 3, 3), card("cheap", "star", "link", 1, 1)],
        omens=[omen("tax", "tax", 2), omen("drain", "drain", 2, ["a", "b"]), omen("break", "fracture", 2, ["b", "c"])])))
    cases.append(("resonance_choice", position(rounds=3, energy=5, cap=8, channels=0, rotates=1, sites=copy.deepcopy(BASE_SITES), edges=copy.deepcopy(BASE_EDGES),
        cards=[card("s1", "sun", "strike", 3, 1), card("s2", "sun", "aegis", 2, 1), card("m1", "moon", "link", 3, 2), card("m2", "moon", "strike", 2, 1), card("x", "star", "strike", 4, 3)],
        omens=[omen("d", "drain", 2, ["a", "b"]), omen("f", "fracture", 2, ["b", "c"]), omen("e", "eclipse", 1, ["a", "c"]), omen("t", "tax", 2)])))
    cases.append(("control_income_tax", position(rounds=3, energy=1, cap=6, channels=1, rotates=0,
        sites=[site("a", "sun", 4, 5, 7), site("b", "moon", 4, 5, 7), site("c", "star", 0, 5, 3)], edges=copy.deepcopy(BASE_EDGES),
        cards=[card("a", "sun", "strike", 2, 1), card("b", "moon", "aegis", 2, 1), card("c", "star", "link", 3, 3)],
        omens=[omen("tax1", "tax", 2), omen("tax2", "tax", 1), omen("d", "drain", 1, ["a", "b"])])))
    cases.append(("omen_target_ties", position(rounds=2, energy=3, cap=5, channels=1, rotates=1,
        sites=[site("aa", "sun", 2, 5, 5), site("ab", "sun", 2, 5, 5)], edges=[["ab", "aa"]],
        cards=[card("ca", "moon", "strike", 2, 1), card("cb", "moon", "strike", 2, 1)],
        omens=[omen("oa", "drain", 1, ["ab", "aa"]), omen("ob", "drain", 1, ["aa", "ab"])])))
    cases.append(("omens_exhaust_then_pass", position(rounds=3, energy=3, cap=7, channels=1, rotates=1,
        sites=copy.deepcopy(BASE_SITES), edges=copy.deepcopy(BASE_EDGES), cards=copy.deepcopy(BASE_CARDS),
        omens=[omen("first", "fracture", 2, ["a", "b"]), omen("second", "tax", 2)])))
    cases.append(("hard_triad", position(rounds=3, energy=4, cap=8, channels=1, rotates=1, limit=3,
        sites=[site("d", "sun", 3, 7, 7), site("g", "moon", 4, 7, 8, ward=1, strain=1), site("z", "star", 2, 6, 6)],
        edges=[["d", "g"], ["g", "z"], ["d", "z"]],
        cards=[card("a", "sun", "strike", 4, 2), card("b", "moon", "aegis", 2, 2), card("c", "star", "link", 3, 3), card("d2", "moon", "strike", 3, 1), card("e", "sun", "aegis", 2, 1)],
        omens=[omen("ash", "drain", 3, ["d", "g"]), omen("break", "fracture", 2, ["g", "z"]), omen("tithe", "tax", 2)])))
    cases.append(("hard_quadrant", position(rounds=2, energy=4, cap=8, channels=1, rotates=2, limit=3,
        sites=[site("a", "sun", 2, 6, 5), site("b", "moon", 3, 7, 7, ward=1), site("c", "star", 2, 6, 6), site("d", "sun", 4, 8, 8, strain=1)],
        edges=[["a", "b"], ["b", "c"], ["c", "d"], ["a", "d"]],
        cards=[card("a1", "sun", "link", 3, 2), card("b1", "moon", "aegis", 3, 2), card("c1", "star", "strike", 4, 3), card("d1", "sun", "strike", 2, 1), card("e1", "moon", "link", 2, 1), card("f1", "star", "aegis", 2, 1)],
        omens=[omen("o1", "drain", 3, ["a", "c"]), omen("o2", "fracture", 2, ["b", "d"]), omen("o3", "eclipse", 2, ["a", "d"]), omen("o4", "tax", 2)])))
    cases.append(("zero_cost_low_cap", position(rounds=3, energy=0, cap=2, channels=1, rotates=0,
        sites=[site("a", "sun", 0, 4, 5), site("b", "moon", 1, 4, 5)], edges=[["a", "b"]],
        cards=[card("free1", "sun", "aegis", 2, 0), card("free2", "sun", "strike", 2, 0), card("paid", "moon", "link", 3, 2)],
        omens=[omen("d", "drain", 2, ["a", "b"]), omen("f", "fracture", 1, ["a", "b"]), omen("t", "tax", 1)])))
    cases.append(("single_round_no_omens", position(rounds=1, energy=1, cap=3, channels=0, rotates=0,
        sites=[site("left", "sun", 1, 4, 3), site("right", "star", 2, 5, 4)], edges=[["right", "left"]],
        cards=[card("only", "moon", "strike", 2, 1)], omens=[])))
    cases.append(("focus_directional_transfer", position(rounds=1, energy=1, cap=3, channels=0, rotates=0, focuses=1, limit=3,
        sites=[site("vault", "sun", 6, 5, 8, ward=3), site("altar", "moon", 4, 5, 7)], edges=[["vault", "altar"]],
        cards=[card("later", "star", "strike", 2, 2)], omens=[])))
    cases.append(("curse_overload_additive", position(rounds=2, energy=1, cap=4, channels=1, rotates=0, focuses=0, limit=2,
        sites=[site("ashen", "star", 7, 6, 8, strain=2, curse=1), site("clear", "sun", 3, 5, 5, ward=1)], edges=[["ashen", "clear"]],
        cards=[card("guard", "sun", "aegis", 2, 1), card("reach", "star", "link", 2, 1)],
        omens=[omen("deep", "curse", 3, ["ashen", "clear"]), omen("split", "fracture", 2, ["ashen", "clear"])])))
    cases.append(("focus_curse_horizon", position(rounds=4, energy=3, cap=6, channels=0, rotates=1, focuses=1, limit=3,
        sites=[site("a", "sun", 5, 6, 7, ward=2), site("b", "moon", 4, 6, 6, curse=2)], edges=[["a", "b"]],
        cards=[card("a1", "sun", "strike", 2, 1), card("b1", "moon", "aegis", 2, 1), card("c1", "star", "link", 2, 2)],
        omens=[omen("c", "curse", 2, ["a", "b"]), omen("d", "drain", 2, ["a", "b"]), omen("t", "tax", 1)])))
    cases.append(("focus_direction_tie", position(rounds=1, energy=1, cap=2, channels=0, rotates=0, focuses=1, limit=4,
        sites=[site("aa", "sun", 4, 5, 4, ward=1), site("ab", "sun", 4, 5, 4, ward=1)], edges=[["ab", "aa"]],
        cards=[card("zz", "moon", "strike", 1, 2)], omens=[])))
    return cases


@pytest.fixture(scope="session", autouse=True)
def build_binary() -> None:
    assert SOURCE.is_file()
    subprocess.run(["go", "build", "-trimpath", "-o", str(BINARY), "."], cwd=ROOT, check=True, timeout=120)
    assert BINARY.is_file() and os.access(BINARY, os.X_OK)


def run_case(doc: dict, tmp_path: Path, name: str = "case") -> dict:
    input_path = tmp_path / f"{name}.json"
    output_path = tmp_path / f"{name}.out.json"
    input_path.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
    proc = subprocess.run([str(BINARY), str(input_path), str(output_path)], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == "" and proc.stderr == ""
    raw = output_path.read_bytes()
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    return json.loads(raw)


def test_public_input_and_rules_integrity() -> None:
    assert sha256(PUBLIC) == PUBLIC_SHA256
    assert sha256(RULES) == RULES_SHA256


def test_public_match_exact(tmp_path: Path) -> None:
    doc = json.loads(PUBLIC.read_text(encoding="utf-8"))
    assert run_case(doc, tmp_path, "public") == RefGame(doc).adjudicate()


def test_required_review_output() -> None:
    assert REVIEW_OUTPUT.is_file()
    raw = REVIEW_OUTPUT.read_bytes()
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    doc = json.loads(PUBLIC.read_text(encoding="utf-8"))
    assert json.loads(raw) == RefGame(doc).adjudicate()


@pytest.mark.parametrize("case_name,doc", compatibility_cases(), ids=lambda x: x if isinstance(x, str) else None)
def test_compatibility_matrix(case_name: str, doc: dict, tmp_path: Path) -> None:
    assert run_case(doc, tmp_path, case_name) == RefGame(doc).adjudicate()


def test_input_order_never_breaks_ties(tmp_path: Path) -> None:
    doc = compatibility_cases()[8][1]
    shuffled = copy.deepcopy(doc)
    shuffled["sites"].reverse()
    shuffled["cards"].reverse()
    shuffled["omens"].reverse()
    shuffled["edges"] = [list(reversed(e)) for e in reversed(shuffled["edges"])]
    for o in shuffled["omens"]:
        o["targets"].reverse()
    a = run_case(doc, tmp_path, "ordered")
    b = run_case(shuffled, tmp_path, "shuffled")
    assert a == b == RefGame(doc).adjudicate()


def test_repeat_is_deterministic(tmp_path: Path) -> None:
    doc = compatibility_cases()[6][1]
    assert run_case(doc, tmp_path, "repeat1") == run_case(doc, tmp_path, "repeat2")


@pytest.mark.parametrize(
    "mutator",
    [
        lambda d: d.update({"version": 2}),
        lambda d: d.update({"mystery": 1}),
        lambda d: d["sites"][0].pop("ward"),
        lambda d: d["sites"][0].pop("curse"),
        lambda d: d["sites"][0].update({"curse": 5}),
        lambda d: d.update({"focus_tokens": 3}),
        lambda d: d["cards"][0].update({"annotation": "invalid"}),
        lambda d: d["sites"].append(copy.deepcopy(d["sites"][0])),
        lambda d: d.update({"edges": [[d["sites"][0]["id"], d["sites"][0]["id"]]]}),
        lambda d: d["omens"][0].update({"targets": ["missing"]}),
        lambda d: d["omens"][0].update({"kind": "curse", "targets": []}),
    ],
)
def test_invalid_positions_fail_without_output(mutator, tmp_path: Path) -> None:
    doc = json.loads(PUBLIC.read_text(encoding="utf-8"))
    mutator(doc)
    inp = tmp_path / "bad.json"
    out = tmp_path / "bad.out"
    inp.write_text(json.dumps(doc), encoding="utf-8")
    proc = subprocess.run([str(BINARY), str(inp), str(out)], cwd=ROOT, capture_output=True, timeout=30)
    assert proc.returncode != 0
    assert not out.exists()


def test_command_line_contract(tmp_path: Path) -> None:
    for args in ([], [str(PUBLIC)], [str(PUBLIC), str(tmp_path / "x"), "extra"]):
        proc = subprocess.run([str(BINARY), *args], cwd=ROOT, capture_output=True, timeout=30)
        assert proc.returncode != 0
    assert not (tmp_path / "x").exists()


def test_native_go_submission_has_no_helper_processes() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    assert "os/exec" not in text
    assert "exec.Command" not in text
    assert "net/http" not in text
    assert "python" not in text.lower()
