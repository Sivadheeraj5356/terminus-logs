#!/usr/bin/env python3
import hashlib
import json
import subprocess
from pathlib import Path

import crc32c

ENV = Path("/app/environment")
PRACTICE = ENV / "fixtures" / "practice"
PROFILE = ENV / "configs" / "audit_profile.json"


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


def link_step(prev: str, seq: int, payload: dict, width: int) -> str:
    token = f"{seq:0{width}d}:{canonical_payload(payload)}"
    return hashlib.sha256((prev + ":" + token).encode()).hexdigest()


def recompute(docket_dir: Path, epoch: int) -> dict:
    width = int(json.loads(PROFILE.read_text()).get("chain_seq_width", 16))
    files = sorted(p.name for p in docket_dir.glob("*.cdk"))
    prev = "0" * 64
    frame_count = 0
    kept_seq = []
    for name in files:
        blob = (docket_dir / name).read_bytes()
        off = 0
        while off + 26 <= len(blob):
            if blob[off : off + 4] != b"CDKT":
                break
            hdr_seq = int.from_bytes(blob[off + 10 : off + 18], "little")
            ep = int.from_bytes(blob[off + 6 : off + 10], "little")
            plen = int.from_bytes(blob[off + 18 : off + 22], "little")
            end = off + 22 + plen
            if end + 4 > len(blob):
                break
            want = int.from_bytes(blob[end : end + 4], "little")
            got = crc32c.crc32c(blob[off:end])
            if got != want:
                off = end + 4
                continue
            payload = json.loads(blob[off + 22 : end].decode())
            off = end + 4
            if ep != epoch:
                continue
            frame_count += 1
            kept_seq.append(hdr_seq)
            prev = link_step(prev, hdr_seq, payload, width)
    return {
        "frame_count": frame_count,
        "chain_root_sha256": prev,
        "min_seq": min(kept_seq) if kept_seq else 0,
        "max_seq": max(kept_seq) if kept_seq else 0,
    }


subprocess.run(
    [
        "/app/bin/claimdocketaudit",
        "audit",
        "--docket-dir",
        str(PRACTICE),
        "--epoch",
        "7",
        "--json-out",
        "/app/out/r.json",
    ],
    check=True,
)
rep = json.loads(Path("/app/out/r.json").read_text())
ref = recompute(PRACTICE, 7)
for key in ("frame_count", "chain_root_sha256", "min_seq", "max_seq", "record_count", "retract_count"):
    if rep.get(key) != ref.get(key):
        print(f"MISMATCH {key}: report={rep.get(key)!r} ref={ref.get(key)!r}")
