#!/usr/bin/env python3
"""Generate long-context building automation readmes for slice 759."""

from __future__ import annotations

import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs"

RNG = random.Random(7590759)

SECTION_INTROS = [
    (
        "Campus HVAC damper schedule transport",
        "Supply-air terminal units modulate damper authority through seasonal "
        "economizer logic and night-purge staging. Building automation schedules "
        "serialize ORDERS segment dumps with conditional NAD branches. Downstream "
        "enclosure witnesses reconcile segment bytes against mesh-indexed catalog "
        "rows before obligation-eight scoring.",
    ),
    (
        "Mutual-information trace alignment",
        "Greedy mutual-information selection ranks conditional segment witnesses "
        "before obligation-eight evaluation. Normalization divides arm strength "
        "bytes by their sum; ties within epsilon defer to profile-specific ladders "
        "documented in the secondary readme.",
    ),
    (
        "Interval arithmetic enclosure policy",
        "Interval witnesses overapproximate arm budgets with directed rounding. "
        "Runtime emission caps bound invariant stream length through lane_limit_runtime. "
        "Compile-time ring constants are not authoritative for graded closure.",
    ),
    (
        "Slice 759 operational context",
        "Annex slice 759 indexes campus damper schedule fixtures for the D9 formal "
        "synthesis workspace. Arm context 0759 governs profile-zero tie resolution "
        "when normalized arm weights fall within epsilon. Secondary readme documents "
        "the boundary case omitted from the primary overview.",
    ),
    (
        "Catalog mesh index binding",
        "Series rows bind mesh identifiers and class codes to slice predicates. "
        "Lookups that filter only on zone_id pull decoy rows from alternate slices "
        "and break cross-format row signatures.",
    ),
    (
        "Ring buffer emission semantics",
        "Bounded emitters drain obligation rows through a fixed-capacity ring. "
        "Runtime policy routes strict-profile limits through lane_limit_runtime. "
        "Stock scaffolds truncate streams before obligation checks without surfacing "
        "an error.",
    ),
    (
        "Label fold over segment hierarchy",
        "Parent segment nodes inherit labels from upstream ancestors during fold. "
        "Leaf-only copies pass interim stage dumps but fail terminal basis sizing "
        "when ancestor ranks contribute to obligation-eight scoring.",
    ),
    (
        "Obligation eight scoring",
        "For each graded instance the obligation-eight score sums rank weights over "
        "composed label sets minus seed label ranks. Non-negative scores on the "
        "bundled walk are required. Rank tables map mesh label ids to integer weights "
        "documented in o8_flow.md.",
    ),
]

BUILDINGS = [
    "North Annex",
    "South Atrium",
    "East Laboratory",
    "West Commons",
    "Central Plant",
    "Research Tower",
    "Library Stack",
    "Athletic Pavilion",
]

PHENOMENA = [
    "economizer lockout",
    "night purge",
    "reheat staging",
    "static pressure reset",
    "demand ventilation",
    "humidification drift",
    "mixed-air reset",
    "occupancy override",
]


def unique_sentence(seq: int, topic: str) -> str:
    """Emit one deterministic unique sentence (no comma-delimited record shape)."""
    building = BUILDINGS[seq % len(BUILDINGS)]
    phenom = PHENOMENA[(seq // 3) % len(PHENOMENA)]
    hour = (seq % 24) + 1
    sat = (seq * 13) % 97 + 55
    rat = (seq * 11) % 97 + 62
    zone = (seq % 17) + 2
    shard_kb = 128 + (seq % 9) * 32
    return (
        f"Transect {seq:05d} on {topic} at building {building} recorded SAT "
        f"{sat} F and RAT {rat} F near hour {hour} with {phenom} on zone "
        f"{zone} while shard {seq % 400} held {shard_kb} KiB of schedule lattice."
    )


def expand_section(title: str, body: str, section_idx: int, seq_start: int) -> tuple[str, int]:
    lines = [f"## {title} (segment {section_idx})", "", body, ""]
    seq = seq_start
    for _ in range(16):
        lines.append(unique_sentence(seq, title.lower()))
        seq += 1
        lines.append("")
    return "\n".join(lines), seq


def build_pack(header: str, intro: str, target_chars: int, seq_start: int = 0) -> tuple[str, int]:
    parts = [f"# {header}", "", intro, ""]
    idx = 0
    seq = seq_start
    while sum(len(p) for p in parts) < target_chars:
        title, body = SECTION_INTROS[idx % len(SECTION_INTROS)]
        block, seq = expand_section(title, body, idx + 1, seq)
        parts.append(block)
        idx += 1
    return "\n".join(parts), seq


def main() -> None:
    primary, seq = build_pack(
        "Primary building automation readme (doc_p4)",
        "This primary README summarizes campus HVAC damper schedule transport. "
        "Offline ORDERS fixture arrays. Robust arm budgets for the D9 numerical "
        "synthesis workspace. See doc_n1.md for arm 0759 tie-order boundary cases.",
        115_000,
        seq_start=1000,
    )
    secondary_intro = (
        "Arm context 0759: when profile-zero normalized arm weights tie within "
        "epsilon the resolver must apply tie order 0 then 1 then 2. Profile one "
        "uses 1 then 0 then 2. Catalog queries must bind annex slice 759 with series "
        "key set_a, not zone_id alone. These arm rules are normative for slice 759 "
        "damper schedule scoring."
    )
    secondary, _ = build_pack(
        "Secondary arm ladder readme (doc_n1)",
        secondary_intro,
        110_000,
        seq_start=seq + 5000,
    )
    (ROOT / "doc_p4.md").write_text(primary, encoding="utf-8")
    (ROOT / "doc_n1.md").write_text(secondary, encoding="utf-8")
    total = len(primary) + len(secondary)
    print(f"wrote long docs: {total} chars combined")


if __name__ == "__main__":
    main()
