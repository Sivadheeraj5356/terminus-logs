#!/usr/bin/env python3
"""Build-time fixture generator for the link ledger registry.

Emits the packed LKR1 ledger blobs, the Redis seed file consumed by
redis-cli --pipe, and the private documents behind the interface API. Once
the fixture is generated it re-proves every documented rule against the
actual bytes, so the docker build aborts if any stated behavior stops firing.
"""

import json
import os
import random
import struct

BASE = os.environ.get("GEN_BASE", "")
BUILD_DIR = BASE + "/tmp/build"
PRIVATE_DIR = BASE + "/opt/api-private"

MASK64 = (1 << 64) - 1
FNV_OFFSET = 0xCBF29CE484222325
FNV_PRIME = 0x100000001B3

UNIT = 1500
BURST_DIVISOR = 5500
BURST_MIN = 24
RATE_DIVISOR = 40000
TIER_BASE = {"background": 2000, "general": 5000, "express": 12000}
TIER_CEIL = {"background": 3500, "general": 8000, "express": 18000}

# Registry order: the link:index order the seal chains over. Deliberately
# neither alphabetical nor the API (provisioning) order.
REGISTRY_ORDER = [
    "vx-tenant7", "wan-east0", "lan-core2", "gre-hub1", "wg-branch4",
    "wan-west1", "vx-tenant2", "lan-acc5", "wg-branch9", "gre-spoke3",
    "wan-mpls0", "vx-tenant4", "lan-core0", "wg-mesh6", "gre-spoke8",
    "wan-lte2", "vx-storage1", "lan-dmz3", "wg-branch2", "wan-sat0",
    "vx-tenant9", "lan-acc1", "gre-hub0", "wg-mesh3", "wan-fiber1",
    "vx-backup5",
]

# The API interface list order, a different shuffle of the same fleet.
API_ORDER = [
    "lan-core0", "wan-sat0", "vx-tenant2", "wg-branch9", "wan-east0",
    "gre-hub0", "lan-dmz3", "vx-backup5", "wan-mpls0", "wg-mesh3",
    "lan-acc5", "vx-tenant7", "gre-spoke8", "wan-fiber1", "wg-branch4",
    "lan-core2", "vx-tenant9", "wan-west1", "gre-spoke3", "wg-branch2",
    "lan-acc1", "vx-storage1", "wan-lte2", "gre-hub1", "wg-mesh6",
    "vx-tenant4",
]

DETACHED = {"gre-spoke3", "wan-lte2", "lan-acc1", "vx-tenant2", "wg-mesh3"}

UIDS = {iface: 6101 + pos for pos, iface in enumerate(REGISTRY_ORDER)}

TIERS = {
    "vx-tenant7": "express", "wan-east0": "express", "lan-core2": "background",
    "gre-hub1": "express", "wg-branch4": "background", "wan-west1": "general",
    "vx-tenant2": "general", "lan-acc5": "general", "wg-branch9": "general",
    "gre-spoke3": "background", "wan-mpls0": "express", "vx-tenant4": "general",
    "lan-core0": "general", "wg-mesh6": "background", "gre-spoke8": "general",
    "wan-lte2": "express", "vx-storage1": "background", "lan-dmz3": "background",
    "wg-branch2": "background", "wan-sat0": "general", "vx-tenant9": "background",
    "lan-acc1": "background", "gre-hub0": "general", "wg-mesh3": "background",
    "wan-fiber1": "express", "vx-backup5": "background",
}

DISPLAY = {
    "vx-tenant7": "Tenant Overlay 7", "wan-east0": "East Uplink",
    "lan-core2": "Core Switch Lane 2", "gre-hub1": "GRE Hub 1",
    "wg-branch4": "Branch Tunnel 4", "wan-west1": "West Uplink",
    "vx-tenant2": "Tenant Overlay 2", "lan-acc5": "Access Lane 5",
    "wg-branch9": "Branch Tunnel 9", "gre-spoke3": "GRE Spoke 3",
    "wan-mpls0": "MPLS Uplink", "vx-tenant4": "Tenant Overlay 4",
    "lan-core0": "Core Switch Lane 0", "wg-mesh6": "Mesh Tunnel 6",
    "gre-spoke8": "GRE Spoke 8", "wan-lte2": "LTE Backup Uplink",
    "vx-storage1": "Storage Overlay 1", "lan-dmz3": "DMZ Lane 3",
    "wg-branch2": "Branch Tunnel 2", "wan-sat0": "Satellite Uplink",
    "vx-tenant9": "Tenant Overlay 9", "lan-acc1": "Access Lane 1",
    "gre-hub0": "GRE Hub 0", "wg-mesh3": "Mesh Tunnel 3",
    "wan-fiber1": "Fiber Uplink", "vx-backup5": "Backup Overlay 5",
}

# The volume class drives raw daily egress figures so rate_kbit sweeps the
# whole formula (zero add, mid-band add, ceiling-capped) and burst_kib both
# spreads and hits its raise-to-24 floor.
VOLUME = {
    "vx-tenant7": "medium", "wan-east0": "huge", "lan-core2": "small",
    "gre-hub1": "medium", "wg-branch4": "medium", "wan-west1": "medium",
    "vx-tenant2": "large", "lan-acc5": "tiny", "wg-branch9": "large",
    "gre-spoke3": "medium", "wan-mpls0": "large", "vx-tenant4": "large",
    "lan-core0": "medium", "wg-mesh6": "tiny", "gre-spoke8": "large",
    "wan-lte2": "huge", "vx-storage1": "huge", "lan-dmz3": "medium",
    "wg-branch2": "small", "wan-sat0": "tiny", "vx-tenant9": "small",
    "lan-acc1": "large", "gre-hub0": "small", "wg-mesh3": "medium",
    "wan-fiber1": "huge", "vx-backup5": "huge",
}

VOL_RANGE = {
    "tiny": (1800, 110000),
    "small": (200000, 2600000),
    "medium": (6000000, 90000000),
    "large": (150000000, 900000000),
    "huge": (1100000000, 3200000000),
}

OPS = {
    "vx-tenant7": [{"op": "add", "k": 147456}, {"op": "scale", "num": 9, "den": 10}],
    "wan-east0": [{"op": "scale", "num": 7, "den": 6}, {"op": "add", "k": 262144}],
    "lan-core2": [],
    "gre-hub1": [{"op": "scale", "num": 4, "den": 5}, {"op": "add", "k": 61440}],
    "wg-branch4": [{"op": "add", "k": 98304}, {"op": "scale", "num": 7, "den": 8}],
    "wan-west1": [{"op": "scale", "num": 6, "den": 5}, {"op": "add", "k": 40960}],
    "vx-tenant2": [{"op": "scale", "num": 8, "den": 9}, {"op": "add", "k": 24576}],
    "lan-acc5": [{"op": "scale", "num": 9, "den": 10}],
    "wg-branch9": [{"op": "floor", "k": 8000000}, {"op": "add", "k": 65536}],
    "gre-spoke3": [{"op": "add", "k": 30720}],
    "wan-mpls0": [{"op": "scale", "num": 5, "den": 4}, {"op": "add", "k": 131072}],
    "vx-tenant4": [{"op": "add", "k": 204800}, {"op": "scale", "num": 3, "den": 4}],
    "lan-core0": [{"op": "floor", "k": 90000}, {"op": "scale", "num": 10, "den": 9}],
    "wg-mesh6": [{"op": "add", "k": 512}, {"op": "scale", "num": 5, "den": 6}],
    "gre-spoke8": [{"op": "scale", "num": 9, "den": 8}, {"op": "floor", "k": 500000}],
    "wan-lte2": [{"op": "add", "k": 786432}, {"op": "scale", "num": 7, "den": 8}],
    "vx-storage1": [{"op": "add", "k": 524288}, {"op": "scale", "num": 5, "den": 6}],
    "lan-dmz3": [{"op": "scale", "num": 3, "den": 5}, {"op": "add", "k": 20480}],
    "wg-branch2": [{"op": "add", "k": 5120}, {"op": "scale", "num": 3, "den": 4}],
    "wan-sat0": [{"op": "floor", "k": 20000}, {"op": "add", "k": 256}],
    "vx-tenant9": [{"op": "scale", "num": 7, "den": 10}],
    "lan-acc1": [{"op": "scale", "num": 2, "den": 3}, {"op": "add", "k": 327680}],
    "gre-hub0": [],
    "wg-mesh3": [{"op": "scale", "num": 5, "den": 8}, {"op": "add", "k": 12288}],
    "wan-fiber1": [{"op": "scale", "num": 11, "den": 10}, {"op": "floor", "k": 2000000}],
    "vx-backup5": [{"op": "scale", "num": 13, "den": 12}],
}


def encode_varint(value):
    """Unsigned MSB-first base-128 varint, high bit set on all but the last byte."""
    groups = []
    v = value
    while True:
        groups.append(v & 0x7F)
        v >>= 7
        if v == 0:
            break
    groups.reverse()
    out = bytearray()
    for i, g in enumerate(groups):
        out.append(g | (0x80 if i < len(groups) - 1 else 0))
    return bytes(out)


def decode_varints(payload, count):
    """Decode exactly count MSB-first base-128 varints from payload."""
    values, v = [], 0
    for b in payload:
        v = (v << 7) | (b & 0x7F)
        if not (b & 0x80):
            values.append(v)
            v = 0
    if len(values) != count:
        raise ValueError("varint count mismatch")
    return values


def payload_checksum(payload):
    """Big-endian u16, the sum of the payload bytes modulo 65521."""
    return struct.pack(">H", sum(payload) % 65521)


def pack_ledger(detached, raws):
    payload = b"".join(encode_varint(v) for v in raws)
    return (
        b"LKR1"
        + bytes([1, 1 if detached else 0])
        + struct.pack("<H", len(raws))
        + payload
        + payload_checksum(payload)
    )


def apply_ops(value, ops):
    v = value
    for op in ops:
        if op["op"] == "scale":
            v = (v * op["num"]) // op["den"]
        elif op["op"] == "add":
            v = v + op["k"]
        elif op["op"] == "floor":
            v = max(v, op["k"])
        else:
            raise ValueError("unknown op")
    return v


def smooth_series(adjusted, drop_carry=False):
    s = [adjusted[0]]
    carry = 0
    for d in range(1, len(adjusted)):
        t = 5 * s[-1] + adjusted[d] + (0 if drop_carry else carry)
        s.append(t // 6)
        carry = t % 6
    return s


def day_weight(s_value):
    return (s_value + UNIT - 1) // UNIT


def le(value, width):
    return int(value).to_bytes(width, "little")


def fold(acc, data):
    for b in data:
        acc = ((acc ^ b) * FNV_PRIME) & MASK64
    return acc


def seal_chain(rows, mode="pre"):
    """rows = [(pos, day, smoothed, weight)] in fold order.

    mode 'pre' snapshots the accumulator before any of the row's bytes are
    folded (the correct reading). mode 'mid' folds the row's four leading
    fields and then folds the accumulator value as it stands at that point
    (the natural wrong reading of 'the current accumulator value itself').
    """
    acc = FNV_OFFSET
    sub = 0
    for pos, day, s_val, w_val in rows:
        sub = (sub + s_val + w_val) & MASK64
        snap = acc
        body = le(pos, 2) + le(day, 2) + le(s_val, 8) + le(sub, 8)
        if mode == "pre":
            acc = fold(acc, body + le(snap, 8))
        elif mode == "mid":
            acc = fold(acc, body)
            acc = fold(acc, le(acc, 8))
        else:
            raise ValueError("unknown mode")
    return acc


def shaping_values(smoothed, weights, tier):
    peak = max(smoothed)
    total_units = sum(weights)
    rate = min(TIER_BASE[tier] + total_units // RATE_DIVISOR, TIER_CEIL[tier])
    burst = max((peak + BURST_DIVISOR - 1) // BURST_DIVISOR, BURST_MIN)
    return {
        "peak": peak,
        "total_units": total_units,
        "rate_kbit": rate,
        "burst_kib": burst,
    }


def resp(*args):
    out = bytearray()
    out += b"*%d\r\n" % len(args)
    for a in args:
        if isinstance(a, str):
            a = a.encode()
        out += b"$%d\r\n" % len(a)
        out += a
        out += b"\r\n"
    return bytes(out)


def main():
    rng = random.Random(20260719)

    day_counts = {}
    raws = {}
    for iface in REGISTRY_ORDER:
        n = rng.randrange(140, 211)
        day_counts[iface] = n
        lo, hi = VOL_RANGE[VOLUME[iface]]
        series = []
        for d in range(n):
            if d % 31 == 11:
                series.append(rng.randrange(90, 45000))
            else:
                series.append(rng.randrange(lo, hi))
        raws[iface] = series

    adjusted = {
        iface: [apply_ops(v, OPS[iface]) for v in raws[iface]]
        for iface in REGISTRY_ORDER
    }
    smoothed = {iface: smooth_series(adjusted[iface]) for iface in REGISTRY_ORDER}
    weights = {
        iface: [day_weight(s) for s in smoothed[iface]] for iface in REGISTRY_ORDER
    }

    values = {
        iface: shaping_values(smoothed[iface], weights[iface], TIERS[iface])
        for iface in REGISTRY_ORDER
    }

    rows = []
    for pos, iface in enumerate(REGISTRY_ORDER):
        for day in range(day_counts[iface]):
            rows.append((pos, day, smoothed[iface][day], weights[iface][day]))
    seal = seal_chain(rows, "pre")

    # ---- self-asserts: every documented rule must fire in this fixture ----

    # 1. Round-trip and trailer integrity for every ledger blob.
    ledgers = {
        iface: pack_ledger(iface in DETACHED, raws[iface]) for iface in REGISTRY_ORDER
    }
    for iface, blob in ledgers.items():
        assert blob[:4] == b"LKR1" and blob[4] == 1
        n = struct.unpack("<H", blob[6:8])[0]
        payload = blob[8:-2]
        assert decode_varints(payload, n) == raws[iface]
        assert blob[-2:] == payload_checksum(payload)
        assert (blob[5] & 1) == (1 if iface in DETACHED else 0)

    # 2. Varint widths genuinely spread, single-byte through five-plus bytes.
    lengths = set()
    for iface in REGISTRY_ORDER:
        for v in raws[iface]:
            lengths.add(len(encode_varint(v)))
    assert min(lengths) <= 2 and max(lengths) >= 5, lengths

    # 3. Op order is load-bearing on >= 8 interfaces.
    order_sensitive = 0
    for iface in REGISTRY_ORDER:
        if len(OPS[iface]) >= 2:
            rev = [apply_ops(v, list(reversed(OPS[iface]))) for v in raws[iface]]
            if rev != adjusted[iface]:
                order_sensitive += 1
    assert order_sensitive >= 8, order_sensitive

    # 4. At least 2 interfaces carry an empty op list, and floor fires on >= 3.
    assert sum(1 for iface in REGISTRY_ORDER if not OPS[iface]) >= 2
    floor_fired = 0
    for iface in REGISTRY_ORDER:
        pre = raws[iface]
        for op in OPS[iface]:
            if op["op"] == "floor" and any(v < op["k"] for v in pre):
                floor_fired += 1
                break
            pre = [apply_ops(v, [op]) for v in pre]
    assert floor_fired >= 3, floor_fired

    # 5. The smoothing carry is load-bearing on every interface.
    for iface in REGISTRY_ORDER:
        assert smooth_series(adjusted[iface], drop_carry=True) != smoothed[iface], iface

    # 6. The two seal readings diverge, and order/coverage are load-bearing.
    assert seal_chain(rows, "mid") != seal
    sorted_rows = []
    for iface in sorted(REGISTRY_ORDER):
        real_pos = REGISTRY_ORDER.index(iface)
        for day in range(day_counts[iface]):
            sorted_rows.append((real_pos, day, smoothed[iface][day], weights[iface][day]))
    assert seal_chain(sorted_rows, "pre") != seal
    active_rows = [r for r in rows if REGISTRY_ORDER[r[0]] not in DETACHED]
    assert seal_chain(active_rows, "pre") != seal
    nocarry_rows = []
    for pos, iface in enumerate(REGISTRY_ORDER):
        s_naive = smooth_series(adjusted[iface], drop_carry=True)
        for day in range(day_counts[iface]):
            nocarry_rows.append((pos, day, s_naive[day], day_weight(s_naive[day])))
    assert seal_chain(nocarry_rows, "pre") != seal

    # 7. Both naive pipelines move the delivered shaping values on >= 4
    #    active interfaces each, so the verifier's divergence gate has teeth.
    for naive in ("nocarry", "revops"):
        moved = 0
        for iface in REGISTRY_ORDER:
            if iface in DETACHED:
                continue
            if naive == "nocarry":
                s_alt = smooth_series(adjusted[iface], drop_carry=True)
            else:
                adj_rev = [
                    apply_ops(v, list(reversed(OPS[iface]))) for v in raws[iface]
                ]
                s_alt = smooth_series(adj_rev)
            alt = shaping_values(s_alt, [day_weight(s) for s in s_alt], TIERS[iface])
            if alt != values[iface]:
                moved += 1
        assert moved >= 4, (naive, moved)

    # 8. The three interface orderings are pairwise different.
    assert REGISTRY_ORDER != API_ORDER
    assert REGISTRY_ORDER != sorted(REGISTRY_ORDER)
    assert API_ORDER != sorted(API_ORDER)
    assert sorted(REGISTRY_ORDER) == sorted(API_ORDER)

    # 9. Day counts genuinely vary and the chain is deep.
    assert min(day_counts.values()) != max(day_counts.values())
    assert len(rows) >= 4300, len(rows)

    # 10. The rate_kbit formula exercises its whole range on active interfaces.
    capped = midband = zero_add = 0
    for iface in REGISTRY_ORDER:
        if iface in DETACHED:
            continue
        tier = TIERS[iface]
        add = values[iface]["total_units"] // RATE_DIVISOR
        if TIER_BASE[tier] + add > TIER_CEIL[tier]:
            capped += 1
        elif add > 0:
            midband += 1
        else:
            zero_add += 1
    assert capped >= 2 and midband >= 2 and zero_add >= 2, (capped, midband, zero_add)

    # 11. Values stay positive through the whole pipeline, and burst_kib both
    #     spreads and hits its raise-to-24 floor.
    for iface in REGISTRY_ORDER:
        assert min(adjusted[iface]) > 0 and min(smoothed[iface]) > 0
    active_bursts = [
        values[iface]["burst_kib"] for iface in REGISTRY_ORDER if iface not in DETACHED
    ]
    assert len(set(active_bursts)) >= 8, sorted(set(active_bursts))
    assert sum(1 for b in active_bursts if b == BURST_MIN) >= 2
    assert max(active_bursts) > BURST_MIN

    # ---- outputs ----

    os.makedirs(BUILD_DIR, exist_ok=True)
    os.makedirs(PRIVATE_DIR, exist_ok=True)

    with open(BUILD_DIR + "/seed.resp", "wb") as f:
        f.write(resp("DEL", "link:index"))
        f.write(resp("RPUSH", "link:index", *REGISTRY_ORDER))
        for iface in REGISTRY_ORDER:
            f.write(resp("SET", "link:ledger:" + iface, ledgers[iface]))

    links_doc = {
        "links": [
            {
                "iface_id": iface,
                "display_name": DISPLAY[iface],
                "uid": UIDS[iface],
                "tier": TIERS[iface],
            }
            for iface in API_ORDER
        ]
    }
    with open(PRIVATE_DIR + "/links.json", "w") as f:
        json.dump(links_doc, f, indent=2)
        f.write("\n")
    with open(PRIVATE_DIR + "/shaping.json", "w") as f:
        json.dump({iface: {"ops": OPS[iface]} for iface in REGISTRY_ORDER}, f, indent=2)
        f.write("\n")

    print("rows=%d seal=%016x" % (len(rows), seal))
    print(
        "order_sensitive=%d floor_fired=%d capped=%d midband=%d zero_add=%d"
        % (order_sensitive, floor_fired, capped, midband, zero_add)
    )
    for iface in REGISTRY_ORDER:
        pv = values[iface]
        print(
            "%s tier=%s days=%d peak=%d units=%d rate=%d burst=%d%s"
            % (
                iface, TIERS[iface], day_counts[iface], pv["peak"],
                pv["total_units"], pv["rate_kbit"], pv["burst_kib"],
                " DETACHED" if iface in DETACHED else "",
            )
        )


if __name__ == "__main__":
    main()
