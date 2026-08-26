"""Digest helpers for tl.json construction (hashlib/struct).

tag_of(pid, scp, role, gen):
  UTF-8 concat pid|scp|role|decimal_gen; first 8 bytes of SHA-256 as big-endian uint64.
  At material bind, pass the bound material role as `role`, not the issue-row role.

hex_lane(pack, arm, wins):
  payload starts with UTF-8 pack, 0x00, UTF-8 arm, 0x00.
  Then for each win sorted by pid ascending:
    UTF-8 pid, gen as uint32 little-endian, UTF-8 role (bound material role),
    tag as uint64 big-endian (tag_of at bind time with bound role), then 0x01 if revoked else 0x00,
    then 0x01 if hs_fail else 0x00.
  Return lowercase hex of SHA-256 over that payload (64 hex characters).

seal_hex(lanes, total_viol):
  Concatenate every hex_lane as UTF-8, then uint32 little-endian total_viol.
  Return lowercase hex of SHA-256 over that material.

closed_ok predicate (ledger level):
  Every row has viol_n == 0, every row has seal_ok == 1, and seal_hex matches
  seal_hex(lanes, sum(viol_n)).
"""
from __future__ import annotations

import hashlib
import struct


def tag_of(pid: str, scp: str, role: str, gen: int) -> int:
    raw = f"{pid}|{scp}|{role}|{gen}".encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def hex_lane(pack: str, arm: str, wins: list[dict]) -> str:
    payload = pack.encode() + b"\x00" + arm.encode() + b"\x00"
    for w in sorted(wins, key=lambda x: x["pid"]):
        payload += w["pid"].encode()
        payload += struct.pack("<I", int(w["gen"]))
        payload += w["role"].encode()
        payload += struct.pack(">Q", int(w["tag"]))
        payload += b"\x01" if w["revoked"] else b"\x00"
        payload += b"\x01" if w.get("hs_fail") else b"\x00"
    return hashlib.sha256(payload).hexdigest()


def seal_hex(lanes: list[str], total_viol: int) -> str:
    material = b"".join(lane.encode() for lane in lanes) + struct.pack("<I", total_viol)
    return hashlib.sha256(material).hexdigest()
