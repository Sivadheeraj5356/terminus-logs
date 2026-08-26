"""Balance archives rebuilt from the Go workspace under /app/environment."""

import hashlib
import json
import math
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
OUT = APP / "output" / "balance_archive.json"
TOOL = Path("/opt/simbin/balancectl")
ENV = Path("/app/environment")
SCEN_DIR = ENV / "data" / "scenarios"
SCHEMA_VERSION = 2

POLICY = {
    "era_gap_seq": 3,
    "wilson_z": 1.96,
    "js_turn_threshold": 0.24
}
CHRONOLOGY = [
    {
        "seq": 10,
        "patch_id": "0.9.0",
        "iso_week": "2020-W10"
    },
    {
        "seq": 11,
        "patch_id": "1.0.0",
        "iso_week": "2020-W11"
    },
    {
        "seq": 12,
        "patch_id": "1.0.1",
        "iso_week": "2020-W11"
    },
    {
        "seq": 16,
        "patch_id": "1.1.0",
        "iso_week": "2020-W15"
    },
    {
        "seq": 17,
        "patch_id": "1.1.1",
        "iso_week": "2020-W16"
    },
    {
        "seq": 21,
        "patch_id": "1.2.0",
        "iso_week": "2020-W20"
    }
]
CHRONOLOGY_DELTA = [
    {
        "seq": 10,
        "patch_id": "0.9.0",
        "iso_week": "2020-W10"
    },
    {
        "seq": 11,
        "patch_id": "1.0.0",
        "iso_week": "2020-W11"
    },
    {
        "seq": 12,
        "patch_id": "1.0.1",
        "iso_week": "2020-W11"
    },
    {
        "seq": 16,
        "patch_id": "1.1.0",
        "iso_week": "2020-W15"
    },
    {
        "seq": 17,
        "patch_id": "1.1.1",
        "iso_week": "2020-W16"
    },
    {
        "seq": 21,
        "patch_id": "1.2.0",
        "iso_week": "2020-W20"
    },
    {
        "seq": 22,
        "patch_id": "1.2.1",
        "iso_week": "2020-W21"
    }
]
MATCHES = {
    "alpha_rift": [
        {
            "patch_id": "0.9.0",
            "actor": "striker",
            "picks": 40,
            "wins": 22
        },
        {
            "patch_id": "0.9.0",
            "actor": "warden",
            "picks": 35,
            "wins": 20
        },
        {
            "patch_id": "0.9.0",
            "actor": "skirmisher",
            "picks": 30,
            "wins": 14
        },
        {
            "patch_id": "0.9.0",
            "actor": "medic",
            "picks": 25,
            "wins": 13
        },
        {
            "patch_id": "1.0.0",
            "actor": "striker",
            "picks": 45,
            "wins": 24
        },
        {
            "patch_id": "1.0.0",
            "actor": "warden",
            "picks": 30,
            "wins": 16
        },
        {
            "patch_id": "1.0.0",
            "actor": "skirmisher",
            "picks": 28,
            "wins": 15
        },
        {
            "patch_id": "1.0.0",
            "actor": "medic",
            "picks": 27,
            "wins": 14
        },
        {
            "patch_id": "1.0.1",
            "actor": "striker",
            "picks": 42,
            "wins": 23
        },
        {
            "patch_id": "1.0.1",
            "actor": "warden",
            "picks": 33,
            "wins": 18
        },
        {
            "patch_id": "1.0.1",
            "actor": "skirmisher",
            "picks": 30,
            "wins": 14
        },
        {
            "patch_id": "1.0.1",
            "actor": "medic",
            "picks": 25,
            "wins": 12
        },
        {
            "patch_id": "1.1.0",
            "actor": "striker",
            "picks": 55,
            "wins": 26
        },
        {
            "patch_id": "1.1.0",
            "actor": "warden",
            "picks": 28,
            "wins": 16
        },
        {
            "patch_id": "1.1.0",
            "actor": "skirmisher",
            "picks": 22,
            "wins": 12
        },
        {
            "patch_id": "1.1.0",
            "actor": "medic",
            "picks": 20,
            "wins": 11
        },
        {
            "patch_id": "1.1.1",
            "actor": "striker",
            "picks": 50,
            "wins": 24
        },
        {
            "patch_id": "1.1.1",
            "actor": "warden",
            "picks": 32,
            "wins": 18
        },
        {
            "patch_id": "1.1.1",
            "actor": "skirmisher",
            "picks": 26,
            "wins": 13
        },
        {
            "patch_id": "1.1.1",
            "actor": "medic",
            "picks": 22,
            "wins": 12
        },
        {
            "patch_id": "1.2.0",
            "actor": "striker",
            "picks": 48,
            "wins": 22
        },
        {
            "patch_id": "1.2.0",
            "actor": "warden",
            "picks": 34,
            "wins": 19
        },
        {
            "patch_id": "1.2.0",
            "actor": "skirmisher",
            "picks": 30,
            "wins": 16
        },
        {
            "patch_id": "1.2.0",
            "actor": "medic",
            "picks": 28,
            "wins": 15
        }
    ],
    "beta_collapse": [
        {
            "patch_id": "0.9.0",
            "actor": "striker",
            "picks": 60,
            "wins": 28
        },
        {
            "patch_id": "0.9.0",
            "actor": "warden",
            "picks": 25,
            "wins": 14
        },
        {
            "patch_id": "0.9.0",
            "actor": "skirmisher",
            "picks": 25,
            "wins": 13
        },
        {
            "patch_id": "0.9.0",
            "actor": "medic",
            "picks": 20,
            "wins": 11
        },
        {
            "patch_id": "1.0.0",
            "actor": "striker",
            "picks": 70,
            "wins": 30
        },
        {
            "patch_id": "1.0.0",
            "actor": "warden",
            "picks": 22,
            "wins": 12
        },
        {
            "patch_id": "1.0.0",
            "actor": "skirmisher",
            "picks": 20,
            "wins": 11
        },
        {
            "patch_id": "1.0.0",
            "actor": "medic",
            "picks": 18,
            "wins": 10
        },
        {
            "patch_id": "1.0.1",
            "actor": "striker",
            "picks": 72,
            "wins": 31
        },
        {
            "patch_id": "1.0.1",
            "actor": "warden",
            "picks": 20,
            "wins": 11
        },
        {
            "patch_id": "1.0.1",
            "actor": "skirmisher",
            "picks": 18,
            "wins": 9
        },
        {
            "patch_id": "1.0.1",
            "actor": "medic",
            "picks": 16,
            "wins": 8
        },
        {
            "patch_id": "1.1.0",
            "actor": "striker",
            "picks": 80,
            "wins": 32
        },
        {
            "patch_id": "1.1.0",
            "actor": "warden",
            "picks": 18,
            "wins": 10
        },
        {
            "patch_id": "1.1.0",
            "actor": "skirmisher",
            "picks": 16,
            "wins": 8
        },
        {
            "patch_id": "1.1.0",
            "actor": "medic",
            "picks": 14,
            "wins": 7
        },
        {
            "patch_id": "1.1.1",
            "actor": "striker",
            "picks": 85,
            "wins": 33
        },
        {
            "patch_id": "1.1.1",
            "actor": "warden",
            "picks": 16,
            "wins": 9
        },
        {
            "patch_id": "1.1.1",
            "actor": "skirmisher",
            "picks": 14,
            "wins": 7
        },
        {
            "patch_id": "1.1.1",
            "actor": "medic",
            "picks": 12,
            "wins": 6
        },
        {
            "patch_id": "1.2.0",
            "actor": "striker",
            "picks": 90,
            "wins": 34
        },
        {
            "patch_id": "1.2.0",
            "actor": "warden",
            "picks": 14,
            "wins": 8
        },
        {
            "patch_id": "1.2.0",
            "actor": "skirmisher",
            "picks": 12,
            "wins": 6
        },
        {
            "patch_id": "1.2.0",
            "actor": "medic",
            "picks": 10,
            "wins": 5
        }
    ],
    "gamma_notes": [
        {
            "patch_id": "0.9.0",
            "actor": "striker",
            "picks": 30,
            "wins": 16
        },
        {
            "patch_id": "0.9.0",
            "actor": "warden",
            "picks": 30,
            "wins": 15
        },
        {
            "patch_id": "0.9.0",
            "actor": "skirmisher",
            "picks": 30,
            "wins": 14
        },
        {
            "patch_id": "0.9.0",
            "actor": "medic",
            "picks": 30,
            "wins": 15
        },
        {
            "patch_id": "1.0.0",
            "actor": "striker",
            "picks": 80,
            "wins": 38
        },
        {
            "patch_id": "1.0.0",
            "actor": "warden",
            "picks": 10,
            "wins": 5
        },
        {
            "patch_id": "1.0.0",
            "actor": "skirmisher",
            "picks": 10,
            "wins": 5
        },
        {
            "patch_id": "1.0.0",
            "actor": "medic",
            "picks": 10,
            "wins": 5
        },
        {
            "patch_id": "1.0.1",
            "actor": "striker",
            "picks": 78,
            "wins": 37
        },
        {
            "patch_id": "1.0.1",
            "actor": "warden",
            "picks": 12,
            "wins": 6
        },
        {
            "patch_id": "1.0.1",
            "actor": "skirmisher",
            "picks": 11,
            "wins": 5
        },
        {
            "patch_id": "1.0.1",
            "actor": "medic",
            "picks": 11,
            "wins": 5
        },
        {
            "patch_id": "1.1.0",
            "actor": "striker",
            "picks": 12,
            "wins": 6
        },
        {
            "patch_id": "1.1.0",
            "actor": "warden",
            "picks": 82,
            "wins": 40
        },
        {
            "patch_id": "1.1.0",
            "actor": "skirmisher",
            "picks": 10,
            "wins": 5
        },
        {
            "patch_id": "1.1.0",
            "actor": "medic",
            "picks": 10,
            "wins": 5
        },
        {
            "patch_id": "1.1.1",
            "actor": "striker",
            "picks": 14,
            "wins": 7
        },
        {
            "patch_id": "1.1.1",
            "actor": "warden",
            "picks": 80,
            "wins": 39
        },
        {
            "patch_id": "1.1.1",
            "actor": "skirmisher",
            "picks": 10,
            "wins": 5
        },
        {
            "patch_id": "1.1.1",
            "actor": "medic",
            "picks": 10,
            "wins": 5
        },
        {
            "patch_id": "1.2.0",
            "actor": "striker",
            "picks": 35,
            "wins": 17
        },
        {
            "patch_id": "1.2.0",
            "actor": "warden",
            "picks": 35,
            "wins": 18
        },
        {
            "patch_id": "1.2.0",
            "actor": "skirmisher",
            "picks": 30,
            "wins": 14
        },
        {
            "patch_id": "1.2.0",
            "actor": "medic",
            "picks": 30,
            "wins": 15
        }
    ],
    "delta_digest": [
        {
            "patch_id": "0.9.0",
            "actor": "striker",
            "picks": 25,
            "wins": 13
        },
        {
            "patch_id": "0.9.0",
            "actor": "warden",
            "picks": 25,
            "wins": 12
        },
        {
            "patch_id": "0.9.0",
            "actor": "skirmisher",
            "picks": 25,
            "wins": 12
        },
        {
            "patch_id": "0.9.0",
            "actor": "medic",
            "picks": 25,
            "wins": 13
        },
        {
            "patch_id": "1.0.0",
            "actor": "striker",
            "picks": 30,
            "wins": 16
        },
        {
            "patch_id": "1.0.0",
            "actor": "warden",
            "picks": 28,
            "wins": 14
        },
        {
            "patch_id": "1.0.0",
            "actor": "skirmisher",
            "picks": 26,
            "wins": 13
        },
        {
            "patch_id": "1.0.0",
            "actor": "medic",
            "picks": 24,
            "wins": 12
        },
        {
            "patch_id": "1.0.1",
            "actor": "striker",
            "picks": 32,
            "wins": 17
        },
        {
            "patch_id": "1.0.1",
            "actor": "warden",
            "picks": 27,
            "wins": 14
        },
        {
            "patch_id": "1.0.1",
            "actor": "skirmisher",
            "picks": 25,
            "wins": 12
        },
        {
            "patch_id": "1.0.1",
            "actor": "medic",
            "picks": 24,
            "wins": 12
        },
        {
            "patch_id": "1.1.0",
            "actor": "striker",
            "picks": 34,
            "wins": 17
        },
        {
            "patch_id": "1.1.0",
            "actor": "warden",
            "picks": 30,
            "wins": 16
        },
        {
            "patch_id": "1.1.0",
            "actor": "skirmisher",
            "picks": 28,
            "wins": 14
        },
        {
            "patch_id": "1.1.0",
            "actor": "medic",
            "picks": 26,
            "wins": 13
        },
        {
            "patch_id": "1.1.1",
            "actor": "striker",
            "picks": 33,
            "wins": 17
        },
        {
            "patch_id": "1.1.1",
            "actor": "warden",
            "picks": 31,
            "wins": 16
        },
        {
            "patch_id": "1.1.1",
            "actor": "skirmisher",
            "picks": 28,
            "wins": 14
        },
        {
            "patch_id": "1.1.1",
            "actor": "medic",
            "picks": 26,
            "wins": 13
        },
        {
            "patch_id": "1.2.0",
            "actor": "striker",
            "picks": 36,
            "wins": 18
        },
        {
            "patch_id": "1.2.0",
            "actor": "warden",
            "picks": 32,
            "wins": 17
        },
        {
            "patch_id": "1.2.0",
            "actor": "skirmisher",
            "picks": 30,
            "wins": 15
        },
        {
            "patch_id": "1.2.0",
            "actor": "medic",
            "picks": 28,
            "wins": 14
        },
        {
            "patch_id": "1.2.1",
            "actor": "striker",
            "picks": 38,
            "wins": 19
        },
        {
            "patch_id": "1.2.1",
            "actor": "warden",
            "picks": 33,
            "wins": 17
        },
        {
            "patch_id": "1.2.1",
            "actor": "skirmisher",
            "picks": 31,
            "wins": 15
        },
        {
            "patch_id": "1.2.1",
            "actor": "medic",
            "picks": 29,
            "wins": 14
        }
    ]
}
NOTES = {
    "alpha_rift": [
        {
            "patch_id": "1.0.0",
            "headline": "Striker damage tune",
            "stat_delta": 0
        },
        {
            "patch_id": "1.1.0",
            "headline": "Warden shield nerf headline",
            "stat_delta": -1
        }
    ],
    "beta_collapse": [
        {
            "patch_id": "1.1.0",
            "headline": "Striker dominance buff note",
            "stat_delta": 1
        },
        {
            "patch_id": "1.2.0",
            "headline": "Striker overpick nerf",
            "stat_delta": -1
        }
    ],
    "gamma_notes": [
        {
            "patch_id": "1.0.0",
            "headline": "Striker spike buff",
            "stat_delta": 1
        },
        {
            "patch_id": "1.1.0",
            "headline": "Warden pivot buff",
            "stat_delta": 1
        },
        {
            "patch_id": "1.2.0",
            "headline": "Flat skirmisher tune",
            "stat_delta": 0
        }
    ],
    "delta_digest": [
        {
            "patch_id": "1.2.1",
            "headline": "Medic sustain tune",
            "stat_delta": 0
        }
    ]
}


def _slice_eras(chronology: list[dict], era_gap_seq: int) -> list[dict]:
    ordered = sorted(chronology, key=lambda row: row["seq"])
    if not ordered:
        return []
    eras: list[dict] = []
    era_id = 0
    start_patch = ordered[0]["patch_id"]
    end_patch = ordered[0]["patch_id"]
    prev_seq = ordered[0]["seq"]
    for row in ordered[1:]:
        if row["seq"] - prev_seq > era_gap_seq:
            eras.append({"id": era_id, "start_patch": start_patch, "end_patch": end_patch})
            era_id += 1
            start_patch = row["patch_id"]
        end_patch = row["patch_id"]
        prev_seq = row["seq"]
    eras.append({"id": era_id, "start_patch": start_patch, "end_patch": end_patch})
    return eras


def _patches_in_era(era: dict, chronology: list[dict]) -> list[str]:
    ordered = sorted(chronology, key=lambda row: row["seq"])
    patches: list[str] = []
    in_span = False
    for row in ordered:
        if row["patch_id"] == era["start_patch"]:
            in_span = True
        if in_span:
            patches.append(row["patch_id"])
        if row["patch_id"] == era["end_patch"]:
            break
    return patches


def _era_totals(era: dict, chronology: list[dict], matches: list[dict]) -> dict[str, dict[str, int]]:
    patch_set = set(_patches_in_era(era, chronology))
    totals: dict[str, dict[str, int]] = {}
    for row in matches:
        if row["patch_id"] not in patch_set:
            continue
        bucket = totals.setdefault(row["actor"], {"picks": 0, "wins": 0})
        bucket["picks"] += row["picks"]
        bucket["wins"] += row["wins"]
    return totals


def _pick_share(picks: int, total_picks: int) -> float:
    if total_picks <= 0:
        return 0.0
    return picks / total_picks


def _norm_entropy(shares: list[float]) -> float:
    positive = [s for s in shares if s > 0]
    n = len(positive)
    if n <= 1:
        return 0.0
    h = 0.0
    for s in positive:
        h -= s * math.log(s)
    return h / math.log(n)


def _kl(p: float, m: float) -> float:
    if p <= 0.0:
        return 0.0
    return p * math.log(p / m)


def _js(vec_a: dict[str, float], vec_b: dict[str, float], roster: list[str]) -> float:
    js = 0.0
    for actor in roster:
        pa = vec_a.get(actor, 0.0)
        pb = vec_b.get(actor, 0.0)
        pm = 0.5 * (pa + pb)
        if pm <= 0.0:
            continue
        js += 0.5 * _kl(pa, pm) + 0.5 * _kl(pb, pm)
    return js


def _win_lower(wins: int, picks: int, z: float) -> float:
    if picks <= 0:
        return 0.0
    p = wins / picks
    z2 = z * z
    denom = 1.0 + z2 / picks
    center = p + z2 / (2.0 * picks)
    rad = z * math.sqrt((p * (1.0 - p) / picks) + (z2 / (4.0 * picks * picks)))
    return (center - rad) / denom


def _patch_vector(patch_id: str, matches: list[dict], roster: list[str]) -> dict[str, float]:
    totals = {actor: 0 for actor in roster}
    for row in matches:
        if row["patch_id"] != patch_id:
            continue
        totals[row["actor"]] += row["picks"]
    total = sum(totals.values())
    if total <= 0:
        return {actor: 0.0 for actor in roster}
    return {actor: totals[actor] / total for actor in roster}


def _note_tag(stat_delta: int) -> str:
    if stat_delta < 0:
        return "nerf_pressure"
    if stat_delta > 0:
        return "buff_pressure"
    return "tune_flat"


def _actor_rationale(actor: str, notes: list[dict], chronology: list[dict]) -> str:
    seq_by_patch = {row["patch_id"]: row["seq"] for row in chronology}
    candidates = []
    for note in notes:
        if actor.lower() in note["headline"].lower():
            candidates.append((seq_by_patch.get(note["patch_id"], 0), note))
    if not candidates:
        return "tune_flat"
    candidates.sort(key=lambda item: item[0], reverse=True)
    return _note_tag(int(candidates[0][1]["stat_delta"]))


def _archive_digest(env_root: Path, manifest: dict) -> str:
    parts = [
        f"{manifest['chronology']}:{(env_root / manifest['chronology']).read_text()}",
        f"{manifest['matches']}:{(env_root / manifest['matches']).read_text()}",
        f"{manifest['notes']}:{(env_root / manifest['notes']).read_text()}",
        f"policy/balance_policy.json:{(env_root / 'policy' / 'balance_policy.json').read_text()}",
    ]
    parts.sort()
    joined = "\n".join(parts)
    return hashlib.sha256(joined.encode()).hexdigest()[:16]


def _expected_archive(name: str) -> dict:
    manifest = json.loads((SCEN_DIR / f"{name}.json").read_text())
    chronology_path = manifest["chronology"]
    if chronology_path.endswith("delta.json"):
        chronology = CHRONOLOGY_DELTA
    else:
        chronology = CHRONOLOGY
    matches = MATCHES[name]
    notes = NOTES[name]
    roster = manifest["roster"]
    era_gap_seq = int(POLICY["era_gap_seq"])
    wilson_z = float(POLICY["wilson_z"])
    threshold = float(POLICY["js_turn_threshold"])

    era_defs = _slice_eras(chronology, era_gap_seq)
    eras_out: list[dict] = []
    for era in era_defs:
        totals = _era_totals(era, chronology, matches)
        total_picks = sum(v["picks"] for v in totals.values())
        shares: list[float] = []
        dominant = roster[0]
        best_share = -1.0
        for actor in roster:
            picks = totals.get(actor, {"picks": 0})["picks"]
            share = _pick_share(picks, total_picks)
            if picks > 0:
                shares.append(share)
            if share > best_share:
                best_share = share
                dominant = actor
        dom_totals = totals.get(dominant, {"picks": 0, "wins": 0})
        eras_out.append(
            {
                "id": era["id"],
                "start_patch": era["start_patch"],
                "end_patch": era["end_patch"],
                "dominant_actor": dominant,
                "diversity_index": round(_norm_entropy(shares), 4),
                "dominant_win_lower": round(
                    _win_lower(dom_totals["wins"], dom_totals["picks"], wilson_z), 4
                ),
            }
        )

    last_era = era_defs[-1]
    last_totals = _era_totals(last_era, chronology, matches)
    last_total_picks = sum(v["picks"] for v in last_totals.values())
    positive: list[float] = []
    shares_map: dict[str, float] = {}
    for actor in roster:
        picks = last_totals.get(actor, {"picks": 0})["picks"]
        share = _pick_share(picks, last_total_picks)
        shares_map[actor] = share
        if picks > 0:
            positive.append(share)
    diversity = _norm_entropy(positive)
    ranked = sorted(
        roster,
        key=lambda actor: (-shares_map[actor] * (1.0 - diversity), actor),
    )
    recommendations = [
        {
            "actor": actor,
            "priority": idx,
            "rationale_tag": _actor_rationale(actor, notes, chronology),
        }
        for idx, actor in enumerate(ranked, start=1)
    ]

    ordered = sorted(chronology, key=lambda row: row["seq"])
    turning_points: list[dict] = []
    for prev, cur in zip(ordered, ordered[1:]):
        score = _js(
            _patch_vector(prev["patch_id"], matches, roster),
            _patch_vector(cur["patch_id"], matches, roster),
            roster,
        )
        if score >= threshold:
            turning_points.append(
                {"patch_id": cur["patch_id"], "shift_score": round(score, 4)}
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "scenario": manifest["name"],
        "eras": eras_out,
        "turning_points": turning_points,
        "recommendations": recommendations,
        "archive_digest": _archive_digest(ENV, manifest),
    }


@pytest.fixture(scope="session", autouse=True)
def rebuild_toolchain() -> None:
    """Verifier rebuilds balancectl before exercising scenarios."""
    subprocess.run(["make", "-C", "/app/environment", "all"], check=True)


@pytest.mark.parametrize("path", sorted(SCEN_DIR.glob("*.json")))
def test_scenario_balance_archive(path: Path) -> None:
    """Each scenario export must match independent contract recomputation."""
    manifest = json.loads(path.read_text())
    name = manifest["name"]
    subprocess.run(
        [str(TOOL), "--scenario", name, "--out", str(OUT)],
        check=True,
    )
    arch = json.loads(OUT.read_text())
    exp = _expected_archive(name)
    assert arch["schema_version"] == SCHEMA_VERSION
    assert arch == exp


def test_stale_json_replaced_by_emitter() -> None:
    """Static balance JSON cannot satisfy era count after rebuild."""
    exp = _expected_archive("alpha_rift")
    stale = {
        "schema_version": SCHEMA_VERSION,
        "scenario": "alpha_rift",
        "eras": [],
        "turning_points": [],
        "recommendations": [],
        "archive_digest": exp["archive_digest"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(stale))
    subprocess.run(
        [str(TOOL), "--scenario", "alpha_rift", "--out", str(OUT)],
        check=True,
    )
    arch = json.loads(OUT.read_text())
    assert len(arch["eras"]) == len(exp["eras"])


def test_era_dominant_actor_reflects_telemetry() -> None:
    """Dominant actor reflects highest era rate denominator."""
    subprocess.run(
        [str(TOOL), "--scenario", "beta_collapse", "--out", str(OUT)],
        check=True,
    )
    arch = json.loads(OUT.read_text())
    exp = _expected_archive("beta_collapse")
    assert all(
        a["dominant_actor"] == b["dominant_actor"]
        for a, b in zip(arch["eras"], exp["eras"])
    )


def test_era_dominant_win_lower_wilson() -> None:
    """Dominant era row carries Wilson lower bound for the top actor."""
    subprocess.run(
        [str(TOOL), "--scenario", "alpha_rift", "--out", str(OUT)],
        check=True,
    )
    arch = json.loads(OUT.read_text())
    exp = _expected_archive("alpha_rift")
    for actual, expected in zip(arch["eras"], exp["eras"]):
        assert actual["dominant_win_lower"] == expected["dominant_win_lower"]


def test_era_diversity_index_normalized() -> None:
    """Diversity index uses normalized Shannon entropy."""
    subprocess.run(
        [str(TOOL), "--scenario", "alpha_rift", "--out", str(OUT)],
        check=True,
    )
    arch = json.loads(OUT.read_text())
    exp = _expected_archive("alpha_rift")
    assert arch["eras"][0]["diversity_index"] == exp["eras"][0]["diversity_index"]


def test_inflection_points_threshold_met() -> None:
    """Inflection points follow Jensen-Shannon thresholding."""
    subprocess.run(
        [str(TOOL), "--scenario", "gamma_notes", "--out", str(OUT)],
        check=True,
    )
    arch = json.loads(OUT.read_text())
    exp = _expected_archive("gamma_notes")
    assert arch["turning_points"] == exp["turning_points"]


def test_recommendation_rationale_tags() -> None:
    """Recommendation tags map stat_delta rather than headline keywords."""
    subprocess.run(
        [str(TOOL), "--scenario", "beta_collapse", "--out", str(OUT)],
        check=True,
    )
    arch = json.loads(OUT.read_text())
    exp = _expected_archive("beta_collapse")
    assert arch["recommendations"] == exp["recommendations"]


def test_recommendation_priority_sequence() -> None:
    """Recommendation priority follows diversity deficit ranking."""
    subprocess.run(
        [str(TOOL), "--scenario", "beta_collapse", "--out", str(OUT)],
        check=True,
    )
    arch = json.loads(OUT.read_text())
    exp = _expected_archive("beta_collapse")
    priorities = [row["priority"] for row in arch["recommendations"]]
    exp_priorities = [row["priority"] for row in exp["recommendations"]]
    assert priorities == exp_priorities
    assert priorities == sorted(priorities)


def test_archive_stamp_includes_chronology() -> None:
    """Archive digest folds chronology bytes into the hash."""
    subprocess.run(
        [str(TOOL), "--scenario", "delta_digest", "--out", str(OUT)],
        check=True,
    )
    arch = json.loads(OUT.read_text())
    exp = _expected_archive("delta_digest")
    assert arch["archive_digest"] == exp["archive_digest"]
    assert len(arch["archive_digest"]) == 16
