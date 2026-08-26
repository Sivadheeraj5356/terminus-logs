#!/usr/bin/env python3
"""Generate claim docket shards and checkpoint sidecars for fixture corpora."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import crc32c

ENV = Path(__file__).resolve().parents[1]
FIX = ENV / "fixtures"


def canonical_payload(payload: dict) -> str:
    kind = payload["kind"]
    if kind == "tombstone":
        slim = {
            "account": payload["account"],
            "kind": kind,
            "region": payload["region"],
            "seq": payload["seq"],
        }
        return json.dumps(slim, separators=(",", ":"), sort_keys=True)
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def link_step(prev: str, seq: int, payload: dict) -> str:
    token = f"{seq:016d}:{canonical_payload(payload)}"
    return hashlib.sha256((prev + ":" + token).encode()).hexdigest()


def encode_frame(epoch: int, seq: int, payload: dict, *, corrupt_crc: bool = False) -> bytes:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    header = bytearray()
    header += b"CDKT"
    header += bytes([1])
    header += bytes([1 if payload["kind"] != "void" else 2])
    header += struct.pack("<I", epoch)
    header += struct.pack("<Q", seq)
    header += struct.pack("<I", len(body))
    frame = bytes(header) + body
    csum = crc32c.crc32c(frame)
    if corrupt_crc:
        csum ^= 0x00FF00FF
    return frame + struct.pack("<I", csum)


def write_shard(path: Path, frames: list[bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(frames))


def docket_fingerprint(names: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(names)).encode()).hexdigest()


def walk(
    docket_dir: Path,
    epoch: int,
    *,
    seed_prev: str | None = None,
    skip_through_seq: int = 0,
    region_allow: set[str] | None = None,
) -> dict:
    prev = seed_prev or ("0" * 64)
    files = sorted(p.name for p in docket_dir.glob("*.cdk"))
    frame_count = 0
    record_count = 0
    retract_count = 0
    accounts: set[str] = set()
    crc_failures = 0
    active_records: dict[tuple[str, int], dict] = {}

    for name in files:
        blob = (docket_dir / name).read_bytes()
        off = 0
        while off + 26 <= len(blob):
            if blob[off : off + 4] != b"CDKT":
                break
            ep = int.from_bytes(blob[off + 6 : off + 10], "little")
            seq = int.from_bytes(blob[off + 10 : off + 18], "little")
            plen = int.from_bytes(blob[off + 18 : off + 22], "little")
            end = off + 22 + plen
            if end + 4 > len(blob):
                crc_failures += 1
                break
            want = int.from_bytes(blob[end : end + 4], "little")
            got = crc32c.crc32c(blob[off:end])
            if got != want:
                crc_failures += 1
                off = end + 4
                continue
            payload = json.loads(blob[off + 22 : end].decode("utf-8"))
            off = end + 4
            if ep != epoch:
                continue
            if seq <= skip_through_seq:
                continue
            frame_count += 1
            prev = link_step(prev, seq, payload)
            kind = payload["kind"]
            if kind in ("upsert", "transfer"):
                region = payload.get("region", "")
                gated = region_allow is not None and region not in region_allow
                if not gated:
                    replaces = int(payload.get("replaces_seq") or 0)
                    if replaces:
                        active_records.pop((payload["account"], replaces), None)
                    active_records[(payload["account"], int(payload["seq"]))] = payload
            elif kind == "void":
                retract_count += 1
            elif kind == "tombstone":
                acct = payload["account"]
                for key in list(active_records):
                    if key[0] == acct:
                        del active_records[key]

    record_count = sum(
        1 for p in active_records.values() if p["kind"] in ("upsert", "transfer")
    )
    accounts = {
        p["account"] for p in active_records.values() if p["kind"] in ("upsert", "transfer")
    }

    return {
        "docket_files": files,
        "chain_root_sha256": prev,
        "frame_count": frame_count,
        "record_count": record_count,
        "retract_count": retract_count,
        "distinct_account_count": len(accounts),
        "crc_failure_count": crc_failures,
    }


def write_checkpoint(
    docket_dir: Path,
    epoch: int,
    skip_through_seq: int,
    chain_tail: str,
) -> None:
    names = sorted(p.name for p in docket_dir.glob("*.cdk"))
    doc = {
        "epoch": epoch,
        "docket_fingerprint": docket_fingerprint(names),
        "skip_through_seq": skip_through_seq,
        "chain_tail_sha256": chain_tail,
    }
    mark_name = docket_dir.name + ".cdkmark"
    (docket_dir / mark_name).write_text(
        json.dumps(doc, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_practice() -> None:
    d = FIX / "practice"
    frames = [
        encode_frame(7, 1, {"account": "A1", "amount": 10, "kind": "upsert", "region": "west", "seq": 1}),
        encode_frame(7, 2, {"account": "A2", "amount": 20, "kind": "upsert", "region": "east", "seq": 2}),
        encode_frame(7, 3, {"account": "A3", "amount": 30, "kind": "upsert", "region": "west", "seq": 3}),
    ]
    write_shard(d / "alpha.cdk", frames)
    frames2 = [
        encode_frame(7, 4, {"account": "A4", "amount": 40, "kind": "upsert", "region": "east", "seq": 4}),
        encode_frame(7, 5, {"account": "A5", "amount": 50, "kind": "upsert", "region": "west", "seq": 5}),
        encode_frame(7, 6, {"kind": "void", "account": "A2", "region": "east", "seq": 6}),
    ]
    write_shard(d / "beta.cdk", frames2)


def build_regression() -> str:
    d = FIX / "regression" / "epoch_mismatch"
    write_shard(
        d / "epoch_mismatch.cdk",
        [
            encode_frame(7, 1, {"account": "Z1", "amount": 1, "kind": "upsert", "region": "west", "seq": 1}),
            encode_frame(8, 2, {"account": "Z9", "amount": 9, "kind": "upsert", "region": "west", "seq": 2}),
        ],
    )

    d = FIX / "regression" / "crc_noise"
    write_shard(
        d / "crc_noise.cdk",
        [
            encode_frame(7, 1, {"account": "C1", "amount": 1, "kind": "upsert", "region": "west", "seq": 1}),
            encode_frame(7, 2, {"account": "C2", "amount": 2, "kind": "upsert", "region": "west", "seq": 2}, corrupt_crc=True),
        ],
    )

    d = FIX / "regression" / "transfer_void"
    write_shard(
        d / "transfer_void.cdk",
        [
            encode_frame(9, 1, {"account": "T1", "amount": 100, "kind": "transfer", "region": "west", "seq": 1}),
            encode_frame(9, 2, {"kind": "void", "account": "T1", "region": "west", "seq": 2}),
        ],
    )

    d = FIX / "regression" / "checkpoint_seed"
    shard_frames = [
        encode_frame(7, 1, {"account": "K1", "amount": 1, "kind": "upsert", "region": "west", "seq": 1}),
        encode_frame(7, 2, {"account": "K2", "amount": 2, "kind": "upsert", "region": "west", "seq": 2}),
        encode_frame(7, 3, {"account": "K3", "amount": 3, "kind": "upsert", "region": "west", "seq": 3}),
        encode_frame(7, 4, {"account": "K4", "amount": 4, "kind": "upsert", "region": "west", "seq": 4}),
    ]
    write_shard(d / "seed.cdk", shard_frames)
    prev = "0" * 64
    payloads = [
        {"account": "K1", "amount": 1, "kind": "upsert", "region": "west", "seq": 1},
        {"account": "K2", "amount": 2, "kind": "upsert", "region": "west", "seq": 2},
    ]
    for p in payloads:
        prev = link_step(prev, int(p["seq"]), p)
    write_checkpoint(d, 7, 2, prev)
    checkpoint_tail = prev

    d = FIX / "regression" / "tombstone_retract"
    write_shard(
        d / "tombstone.cdk",
        [
            encode_frame(7, 1, {"account": "R1", "amount": 1, "kind": "upsert", "region": "west", "seq": 1}),
            encode_frame(7, 2, {"account": "R2", "amount": 2, "kind": "upsert", "region": "west", "seq": 2}),
            encode_frame(7, 3, {"account": "R2", "kind": "tombstone", "region": "west", "seq": 3}),
        ],
    )

    d = FIX / "regression" / "region_excluded"
    write_shard(
        d / "region.cdk",
        [
            encode_frame(7, 1, {"account": "X1", "amount": 1, "kind": "upsert", "region": "pole", "seq": 1}),
            encode_frame(7, 2, {"account": "X2", "amount": 2, "kind": "upsert", "region": "west", "seq": 2}),
        ],
    )

    d = FIX / "regression" / "supersede_slot"
    write_shard(
        d / "supersede.cdk",
        [
            encode_frame(7, 1, {"account": "S1", "amount": 10, "kind": "upsert", "region": "west", "seq": 1}),
            encode_frame(
                7,
                2,
                {
                    "account": "S1",
                    "amount": 99,
                    "kind": "upsert",
                    "region": "west",
                    "seq": 2,
                    "replaces_seq": 1,
                },
            ),
        ],
    )

    d = FIX / "regression" / "stale_checkpoint"
    write_shard(
        d / "lane.cdk",
        [
            encode_frame(7, 1, {"account": "P1", "amount": 1, "kind": "upsert", "region": "west", "seq": 1}),
            encode_frame(7, 2, {"account": "P2", "amount": 2, "kind": "upsert", "region": "east", "seq": 2}),
        ],
    )
    stale_doc = {
        "epoch": 7,
        "docket_fingerprint": "0" * 64,
        "skip_through_seq": 1,
        "chain_tail_sha256": "f" * 64,
    }
    (d / "stale_checkpoint.cdkmark").write_text(
        json.dumps(stale_doc, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )

    d = FIX / "regression" / "shard_order"
    write_shard(
        d / "alpha.cdk",
        [encode_frame(7, 20, {"account": "O1", "amount": 20, "kind": "upsert", "region": "west", "seq": 20})],
    )
    write_shard(
        d / "beta.cdk",
        [encode_frame(7, 5, {"account": "O2", "amount": 5, "kind": "upsert", "region": "east", "seq": 5})],
    )

    d = FIX / "regression" / "truncated_tail"
    good = encode_frame(7, 1, {"account": "T1", "amount": 1, "kind": "upsert", "region": "west", "seq": 1})
    truncated = bytearray(b"CDKT")
    truncated += bytes([1, 1])
    truncated += struct.pack("<I", 7)
    truncated += struct.pack("<Q", 99)
    truncated += struct.pack("<I", 500)
    truncated += bytes(4)
    write_shard(d / "tail.cdk", [good, bytes(truncated)])

    d = FIX / "regression" / "void_after_supersede"
    write_shard(
        d / "mix.cdk",
        [
            encode_frame(7, 1, {"account": "V1", "amount": 10, "kind": "upsert", "region": "west", "seq": 1}),
            encode_frame(
                7,
                2,
                {
                    "account": "V1",
                    "amount": 50,
                    "kind": "upsert",
                    "region": "west",
                    "seq": 2,
                    "replaces_seq": 1,
                },
            ),
            encode_frame(7, 3, {"kind": "void", "account": "V1", "region": "west", "seq": 3}),
        ],
    )
    return checkpoint_tail


def main() -> None:
    build_practice()
    checkpoint_tail = build_regression()
    allow = {
        line.strip()
        for line in (ENV / "data" / "region_codes.txt").read_text().splitlines()
        if line.strip()
    }
    summaries = {
        "practice/7": walk(FIX / "practice", 7, region_allow=allow),
        "checkpoint_tail_after_seq2": checkpoint_tail,
        "regression/epoch_mismatch/7": walk(FIX / "regression" / "epoch_mismatch", 7, region_allow=allow),
        "regression/crc_noise/7": walk(FIX / "regression" / "crc_noise", 7, region_allow=allow),
        "regression/transfer_void/9": walk(FIX / "regression" / "transfer_void", 9, region_allow=allow),
        "regression/checkpoint_seed/7": walk(
            FIX / "regression" / "checkpoint_seed",
            7,
            seed_prev=checkpoint_tail,
            skip_through_seq=2,
            region_allow=allow,
        ),
        "regression/tombstone_retract/7": walk(FIX / "regression" / "tombstone_retract", 7, region_allow=allow),
        "regression/region_excluded/7": walk(FIX / "regression" / "region_excluded", 7, region_allow=allow),
        "regression/supersede_slot/7": walk(FIX / "regression" / "supersede_slot", 7, region_allow=allow),
        "regression/stale_checkpoint/7": walk(FIX / "regression" / "stale_checkpoint", 7, region_allow=allow),
        "regression/shard_order/7": walk(FIX / "regression" / "shard_order", 7, region_allow=allow),
        "regression/truncated_tail/7": walk(FIX / "regression" / "truncated_tail", 7, region_allow=allow),
        "regression/void_after_supersede/7": walk(FIX / "regression" / "void_after_supersede", 7, region_allow=allow),
    }
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
