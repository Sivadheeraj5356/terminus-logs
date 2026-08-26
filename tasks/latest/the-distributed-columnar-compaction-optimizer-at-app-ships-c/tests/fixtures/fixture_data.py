"""Catalog builders and independent reference for columnarctl verifier tests."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

Fragment = dict[str, Any]


def write_clfc(path: Path, fragments: list[Fragment]) -> None:
    """Write a CLFC catalog file from fragment dicts."""
    buf = bytearray(b"CLFC")
    buf.extend(struct.pack("<H", 1))
    buf.extend(struct.pack("<H", len(fragments)))
    buf.extend(struct.pack("<I", 0))
    for f in fragments:
        col = f["column_name"].encode("utf-8")
        buf.extend(struct.pack("<H", f["id"]))
        buf.extend(struct.pack("<H", f["partition_id"]))
        buf.extend(struct.pack("<H", f["seq"]))
        buf.extend(struct.pack("<H", f["flags"]))
        buf.extend(struct.pack("<I", f["row_start"]))
        buf.extend(struct.pack("<I", f["row_end"]))
        buf.extend(struct.pack("<I", f["byte_size"]))
        buf.extend(struct.pack("<H", f["replica_mask"]))
        buf.extend(struct.pack("<H", len(col)))
        buf.extend(col)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(buf))


def normalize_column_name(raw: str, case_fold_ascii: bool = True) -> str:
    s = raw.replace("\x00", "")
    if s.startswith("\ufeff"):
        s = s[1:]
    start = 0
    while start < len(s) and s[start] in " \t\n\r":
        start += 1
    end = len(s)
    while end > start and s[end - 1] in " \t\n\r":
        end -= 1
    out: list[str] = []
    in_ws = False
    for ch in s[start:end]:
        if ch in " \t\n\r":
            if not in_ws:
                out.append(" ")
                in_ws = True
        else:
            if case_fold_ascii and ord(ch) < 128 and ch.isalpha():
                out.append(ch.lower())
            else:
                out.append(ch)
            in_ws = False
    return "".join(out)


def same_partition_column(a: Fragment, b: Fragment, case_fold: bool) -> bool:
    if a["partition_id"] != b["partition_id"]:
        return False
    return normalize_column_name(a["column_name"], case_fold) == normalize_column_name(
        b["column_name"], case_fold
    )


def row_junction_peak(left: Fragment, right: Fragment, case_fold: bool) -> int:
    if not same_partition_column(left, right, case_fold):
        return 0
    overlap = min(left["row_end"], right["row_end"]) - max(left["row_start"], right["row_start"]) + 1
    return overlap if overlap > 0 else 0


def row_junction_overlap(left: Fragment, right: Fragment, min_overlap: int, case_fold: bool) -> int:
    if not same_partition_column(left, right, case_fold):
        return 0
    overlap = min(left["row_end"], right["row_end"]) - max(left["row_start"], right["row_start"]) + 1
    if overlap < min_overlap:
        return 0
    return overlap if overlap > 0 else 0


def row_span(f: Fragment) -> int:
    if f["row_end"] < f["row_start"]:
        return 0
    return f["row_end"] - f["row_start"] + 1


def select_outgoing_edge(
    from_id: int, fragments: list[Fragment], policy: dict[str, Any]
) -> tuple[int, int] | None:
    by_id = {f["id"]: f for f in fragments}
    src = by_id[from_id]
    best: tuple[int, int, int] | None = None
    for cand in fragments:
        if cand["id"] == from_id:
            continue
        ov = row_junction_overlap(src, cand, policy["min_row_overlap"], policy["case_fold_ascii"])
        if ov == 0:
            continue
        edge = (ov, cand["seq"], cand["id"])
        if best is None or edge[0] > best[0] or (
            edge[0] == best[0] and (edge[1], edge[2]) < (best[1], best[2])
        ):
            best = edge
    if best is None:
        return None
    return best[2], best[0]


def resolve_open_fragment(fragments: list[Fragment], policy: dict[str, Any]) -> int:
    has_incoming: set[int] = set()
    for a in fragments:
        for b in fragments:
            if a["id"] == b["id"]:
                continue
            if row_junction_overlap(a, b, policy["min_row_overlap"], policy["case_fold_ascii"]) > 0:
                has_incoming.add(b["id"])

    def pick(cands: list[Fragment]) -> int:
        best = min(cands, key=lambda f: (f["seq"], f["id"]))
        return best["id"]

    anchors = [f for f in fragments if f["flags"] & 1]
    if anchors:
        return pick(anchors)
    no_in = [f for f in fragments if f["id"] not in has_incoming]
    if no_in:
        return pick(no_in)
    return pick(fragments)


def compute_fragmentation_index(plan: dict[str, Any], fragments: list[Fragment]) -> int:
    ids = plan["fragment_ids"]
    if len(ids) < 2:
        return 0
    by_id = {f["id"]: f for f in fragments}
    gaps = 0
    for i in range(len(ids) - 1):
        a = by_id[ids[i]]
        b = by_id[ids[i + 1]]
        if b["row_start"] > a["row_end"] + 1:
            gaps += b["row_start"] - a["row_end"] - 1
    total = plan["total_rows"]
    if total == 0:
        return gaps
    return (gaps * 1000) // total


def check_replica_consistency(fragments: list[Fragment], policy: dict[str, Any]) -> bool:
    mask = policy["required_replica_mask"]
    for f in fragments:
        if (f["replica_mask"] & mask) != mask:
            return False
    return True


def compute_scan_cost_units(plan: dict[str, Any], fragments: list[Fragment], policy: dict[str, Any]) -> int:
    by_id = {f["id"]: f for f in fragments}
    cost = 0
    for fid in plan["fragment_ids"]:
        cost += by_id[fid]["byte_size"] * policy["scan_cost_per_byte"]
    cost += plan["fragmentation_index"] * policy["scan_penalty_per_gap"]
    return cost


def fnv1a64(text: str) -> int:
    h = 1469598103934665603
    for c in text.encode("utf-8"):
        h ^= c
        h = (h * 1099511628211) & ((1 << 64) - 1)
    return h


def tag_scramble_u64(x: int) -> int:
    x &= (1 << 64) - 1
    x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9 & ((1 << 64) - 1)
    x = (x ^ (x >> 27)) * 0x94D049BB133111EB & ((1 << 64) - 1)
    return x ^ (x >> 31)


def plan_signature(plan: dict[str, Any]) -> str:
    frag = ",".join(str(i) for i in plan["fragment_ids"])
    rep = "1" if plan["replica_consistent"] else "0"
    return f"rows:{plan['total_rows']};cost:{plan['scan_cost_units']};frag:{frag};rep:{rep}"


def fingerprint_hex(text: str) -> str:
    h = tag_scramble_u64(fnv1a64(text))
    return f"{h:016x}"


def plan_expected(fragments: list[Fragment], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """Independent reference compaction plan matching fixed columnarctl logic."""
    if policy is None:
        policy = {
            "min_row_overlap": 3,
            "case_fold_ascii": True,
            "required_replica_mask": 0x0007,
            "scan_cost_per_byte": 1,
            "scan_penalty_per_gap": 10,
        }
    by_id = {f["id"]: f for f in fragments}
    start = resolve_open_fragment(fragments, policy)
    order = [start]
    overlaps: list[int] = []
    used = {start}
    cur = start
    while True:
        nxt = select_outgoing_edge(cur, fragments, policy)
        if nxt is None or nxt[0] in used:
            break
        overlaps.append(nxt[1])
        order.append(nxt[0])
        used.add(nxt[0])
        cur = nxt[0]

    total = row_span(by_id[order[0]])
    for i in range(1, len(order)):
        total += row_span(by_id[order[i]]) - overlaps[i - 1]

    plan: dict[str, Any] = {
        "fragment_ids": order,
        "row_overlap_lengths": overlaps,
        "total_rows": total,
        "fragmentation_index": 0,
        "replica_consistent": check_replica_consistency(fragments, policy),
        "scan_cost_units": 0,
        "fingerprint": "",
    }
    plan["fragmentation_index"] = compute_fragmentation_index(plan, fragments)
    plan["scan_cost_units"] = compute_scan_cost_units(plan, fragments, policy)
    plan["fingerprint"] = fingerprint_hex(plan_signature(plan))
    return plan


DEFAULT_POLICY = {
    "min_row_overlap": 3,
    "case_fold_ascii": True,
    "max_ambiguity": 0,
    "required_replica_mask": 0x0007,
    "scan_cost_per_byte": 1,
    "scan_penalty_per_gap": 10,
}

ALPHA_FRAGMENTS = [
    {
        "id": 1,
        "partition_id": 1,
        "seq": 1,
        "flags": 1,
        "row_start": 0,
        "row_end": 9,
        "byte_size": 100,
        "replica_mask": 0x0007,
        "column_name": "metrics",
    },
    {
        "id": 2,
        "partition_id": 1,
        "seq": 2,
        "flags": 0,
        "row_start": 5,
        "row_end": 19,
        "byte_size": 120,
        "replica_mask": 0x0007,
        "column_name": "metrics",
    },
    {
        "id": 3,
        "partition_id": 1,
        "seq": 3,
        "flags": 0,
        "row_start": 11,
        "row_end": 29,
        "byte_size": 130,
        "replica_mask": 0x0007,
        "column_name": "metrics",
    },
]

BETA_FRAGMENTS = [
    {
        "id": 10,
        "partition_id": 2,
        "seq": 1,
        "flags": 1,
        "row_start": 100,
        "row_end": 109,
        "byte_size": 200,
        "replica_mask": 0x0007,
        "column_name": "events",
    },
    {
        "id": 11,
        "partition_id": 2,
        "seq": 2,
        "flags": 0,
        "row_start": 107,
        "row_end": 119,
        "byte_size": 210,
        "replica_mask": 0x0007,
        "column_name": "events",
    },
    {
        "id": 12,
        "partition_id": 2,
        "seq": 3,
        "flags": 0,
        "row_start": 115,
        "row_end": 129,
        "byte_size": 220,
        "replica_mask": 0x0007,
        "column_name": "events",
    },
]

CASE_COLUMN_FRAGMENTS = [
    {
        "id": 1,
        "partition_id": 4,
        "seq": 1,
        "flags": 1,
        "row_start": 0,
        "row_end": 5,
        "byte_size": 40,
        "replica_mask": 0x0007,
        "column_name": "Metrics",
    },
    {
        "id": 2,
        "partition_id": 4,
        "seq": 2,
        "flags": 0,
        "row_start": 3,
        "row_end": 10,
        "byte_size": 45,
        "replica_mask": 0x0007,
        "column_name": "metrics",
    },
]

REPLICA_EDGE_FRAGMENTS = [
    {
        "id": 1,
        "partition_id": 3,
        "seq": 1,
        "flags": 1,
        "row_start": 0,
        "row_end": 5,
        "byte_size": 50,
        "replica_mask": 0x0007,
        "column_name": "dims",
    },
    {
        "id": 2,
        "partition_id": 3,
        "seq": 2,
        "flags": 0,
        "row_start": 3,
        "row_end": 10,
        "byte_size": 55,
        "replica_mask": 0x0003,
        "column_name": "dims",
    },
]

HIDDEN_CATALOGS: dict[str, list[Fragment]] = {
    "gap_chain": [
        {
            "id": 1,
            "partition_id": 10,
            "seq": 1,
            "flags": 1,
            "row_start": 0,
            "row_end": 9,
            "byte_size": 80,
            "replica_mask": 0x0007,
            "column_name": "payload",
        },
        {
            "id": 2,
            "partition_id": 10,
            "seq": 2,
            "flags": 0,
            "row_start": 7,
            "row_end": 19,
            "byte_size": 90,
            "replica_mask": 0x0007,
            "column_name": "payload",
        },
    ],
    "tie_break": [
        {
            "id": 5,
            "partition_id": 20,
            "seq": 1,
            "flags": 1,
            "row_start": 0,
            "row_end": 20,
            "byte_size": 60,
            "replica_mask": 0x0007,
            "column_name": "col",
        },
        {
            "id": 6,
            "partition_id": 20,
            "seq": 2,
            "flags": 0,
            "row_start": 15,
            "row_end": 25,
            "byte_size": 70,
            "replica_mask": 0x0007,
            "column_name": "col",
        },
        {
            "id": 7,
            "partition_id": 20,
            "seq": 3,
            "flags": 0,
            "row_start": 15,
            "row_end": 25,
            "byte_size": 65,
            "replica_mask": 0x0007,
            "column_name": "col",
        },
    ],
    "strict_overlap": [
        {
            "id": 1,
            "partition_id": 30,
            "seq": 1,
            "flags": 1,
            "row_start": 0,
            "row_end": 8,
            "byte_size": 50,
            "replica_mask": 0x0007,
            "column_name": "wide",
        },
        {
            "id": 2,
            "partition_id": 30,
            "seq": 2,
            "flags": 0,
            "row_start": 4,
            "row_end": 12,
            "byte_size": 55,
            "replica_mask": 0x0007,
            "column_name": "wide",
        },
    ],
    "row_wrap": [
        {
            "id": 1,
            "partition_id": 40,
            "seq": 1,
            "flags": 1,
            "row_start": 0,
            "row_end": 50,
            "byte_size": 100,
            "replica_mask": 0x0007,
            "column_name": "wrap",
        },
        {
            "id": 2,
            "partition_id": 40,
            "seq": 2,
            "flags": 0,
            "row_start": 45,
            "row_end": 60,
            "byte_size": 110,
            "replica_mask": 0x0007,
            "column_name": "wrap",
        },
        {
            "id": 3,
            "partition_id": 40,
            "seq": 3,
            "flags": 0,
            "row_start": 54,
            "row_end": 70,
            "byte_size": 90,
            "replica_mask": 0x0007,
            "column_name": "wrap",
        },
    ],
    "null_byte_col": [
        {
            "id": 1,
            "partition_id": 50,
            "seq": 1,
            "flags": 1,
            "row_start": 0,
            "row_end": 8,
            "byte_size": 40,
            "replica_mask": 0x0007,
            "column_name": "met\x00rics",
        },
        {
            "id": 2,
            "partition_id": 50,
            "seq": 2,
            "flags": 0,
            "row_start": 5,
            "row_end": 15,
            "byte_size": 45,
            "replica_mask": 0x0007,
            "column_name": "metrics",
        },
    ],
    "replica_strict_fail": [
        {
            "id": 1,
            "partition_id": 60,
            "seq": 1,
            "flags": 1,
            "row_start": 0,
            "row_end": 6,
            "byte_size": 30,
            "replica_mask": 0x000F,
            "column_name": "shard",
        },
        {
            "id": 2,
            "partition_id": 60,
            "seq": 2,
            "flags": 0,
            "row_start": 4,
            "row_end": 12,
            "byte_size": 35,
            "replica_mask": 0x0007,
            "column_name": "shard",
        },
    ],
    "export_shadow": [
        {
            "id": 1,
            "partition_id": 70,
            "seq": 1,
            "flags": 1,
            "row_start": 0,
            "row_end": 9,
            "byte_size": 100,
            "replica_mask": 0x0007,
            "column_name": "shadow",
        },
        {
            "id": 2,
            "partition_id": 70,
            "seq": 2,
            "flags": 0,
            "row_start": 5,
            "row_end": 19,
            "byte_size": 120,
            "replica_mask": 0x0007,
            "column_name": "shadow",
        },
    ],
    "poison_norm_tie": [
        {
            "id": 5,
            "partition_id": 80,
            "seq": 1,
            "flags": 1,
            "row_start": 0,
            "row_end": 20,
            "byte_size": 60,
            "replica_mask": 0x0007,
            "column_name": "c\x00ol",
        },
        {
            "id": 6,
            "partition_id": 80,
            "seq": 2,
            "flags": 0,
            "row_start": 15,
            "row_end": 25,
            "byte_size": 70,
            "replica_mask": 0x0007,
            "column_name": "col",
        },
        {
            "id": 7,
            "partition_id": 80,
            "seq": 3,
            "flags": 0,
            "row_start": 15,
            "row_end": 25,
            "byte_size": 65,
            "replica_mask": 0x0007,
            "column_name": "col",
        },
    ],
}

REPLICA_STRICT_POLICY = {
    "min_row_overlap": 3,
    "case_fold_ascii": True,
    "max_ambiguity": 0,
    "required_replica_mask": 0x000F,
    "scan_cost_per_byte": 1,
    "scan_penalty_per_gap": 10,
}


def ingest_chain_reference(fragments: list[Fragment], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """Independent ingest chain matching fixed columnarctl ingest stage."""
    if policy is None:
        policy = DEFAULT_POLICY
    start = resolve_open_fragment(fragments, policy)
    order = [start]
    overlaps: list[int] = []
    used = {start}
    cur = start
    while True:
        nxt = select_outgoing_edge(cur, fragments, policy)
        if nxt is None or nxt[0] in used:
            break
        overlaps.append(nxt[1])
        order.append(nxt[0])
        used.add(nxt[0])
        cur = nxt[0]
    digest_parts = [f"{f['id']}:{f['seq']}:{f['partition_id']};" for f in fragments]
    digest = fingerprint_hex("".join(digest_parts))
    rep_ok = check_replica_consistency(fragments, policy)
    return {
        "open_fragment_id": start,
        "chain_fragment_ids": order,
        "chain_overlaps": overlaps,
        "replica_summary": rep_ok,
        "catalog_digest": digest,
    }


def staging_snapshot_reference(
    fragments: list[Fragment], policy: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Reference staging snapshot body for ingest contract tests."""
    body = ingest_chain_reference(fragments, policy)
    body["version"] = 1
    return body


ALPHA_EXPECT = plan_expected(ALPHA_FRAGMENTS)
BETA_EXPECT = plan_expected(BETA_FRAGMENTS)
CASE_COLUMN_EXPECT = plan_expected(CASE_COLUMN_FRAGMENTS)
REPLICA_EDGE_EXPECT = plan_expected(REPLICA_EDGE_FRAGMENTS)

# Aliases for verifier anti-synthetic gate (independent reference naming).
reference_plan_expected = plan_expected
reference_row_junction_overlap = row_junction_overlap
reference_fingerprint_hex = fingerprint_hex
