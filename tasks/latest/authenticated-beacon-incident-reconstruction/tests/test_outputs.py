import hashlib
import os
import shutil
import struct
import subprocess
import textwrap
from pathlib import Path

import pytest


APP = Path(os.environ.get("APP_DIR", "/app"))
PUBLIC_BIN = APP / "input_data" / "public_frames.bin"
PUBLIC_SHA = APP / "input_data" / "public_frames.sha256"
SRC = APP / "src" / "beacon_replay.c"
BIN = APP / "beacon_replay"
TMP = Path("/tmp/beacon_cases")

REJECT_KEYS = [
    "bad_length",
    "bad_magic",
    "bad_crc",
    "bad_version",
    "bad_flags",
    "bad_type",
    "bad_layout",
    "stale",
    "dependency",
]

GENERATED_CASE_NAMES = [
    "wrap_and_calibration",
    "reject_matrix",
    "delete_and_empty",
    "trailing_fragment",
    "multi_key_sorting",
    "calibration_after_data",
    "calibration_and_data_sequences_are_separate",
    "version2_flag_is_allowed",
    "sealed_calibration_dependencies",
    "encoded_station_dependencies",
    "beacon_layout_and_station_stale",
    "invalid_type_after_valid_crc",
    "tight_sequence_horizon",
    "delete_without_prior_state",
    "negative_truncation",
    "mixed_rejections_keep_replaying",
    "carry_auth_dependency_chain",
    "calibration_and_chain_dependencies",
    "epoch_anchor_full_auth_stack",
    "relay_auth_cross_station_dependency",
    "relay_with_full_auth_stack",
    "anchor_rejections_and_tighter_horizon",
    "carry_layout_and_beacon_auth",
    "checkpoint_auth_and_precedence",
    "hierarchical_invalidation_preserves_histories",
    "quorum_certificate_full_chain",
    "quorum_reverse_invalidation_and_precedence",
    "quorum_all_auth_layers",
    "exact_257_horizon_and_wrap",
]


def crc32_ieee(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
            crc &= 0xFFFFFFFF
    return crc ^ 0xFFFFFFFF


def beacon_x_payload(data: bytes, version: int, typ: int, station: int) -> bytes:
    buf = bytearray(data)
    state = (0xA5 ^ station ^ ((typ * 17) & 0xFF) ^ version) & 0xFF
    for off in range(6, 32):
        state = (((state << 1) & 0xFF) | (state >> 7)) & 0xFF
        state ^= (0x3D + off * 11) & 0xFF
        buf[off] ^= state
    return bytes(buf)


def u32(value):
    return value & 0xFFFFFFFF


def s32(value):
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def s64(value):
    value &= 0xFFFFFFFFFFFFFFFF
    return value - 0x10000000000000000 if value & 0x8000000000000000 else value


SEQ_FORWARD_LIMIT = 257


def rotl16(value, shift):
    value &= 0xFFFF
    shift &= 15
    return ((value << shift) | (value >> (16 - shift))) & 0xFFFF


def beacon_auth_word(station, seq, base, time):
    auth = 0x5F3759DF ^ (time & 0xFFFFFFFF)
    auth = u32(auth + seq * 1103515245)
    auth = u32(auth ^ u32(station * 2654435761))
    auth = u32(auth + base * 40503)
    return auth


def beacon_auth_key(station, seq, base, time):
    return (rotl16(seq, 5) ^ (time & 0xFFFF) ^ base ^ ((station & 0xFF) << 8)) & 0xFFFF


def anchor_auth_word(station, seq, base, time, station_key):
    auth = 0xC2B2AE35 ^ (time & 0xFFFFFFFF)
    auth = u32(auth + seq * 747796405)
    auth = u32(auth ^ u32(station_key * 2891336453))
    auth = u32(auth + station * 40503)
    auth = u32(auth + base * 97)
    return auth


def anchor_epoch_key(station, seq, base, time, station_key):
    return (
        rotl16(seq, 9)
        ^ station_key
        ^ (time & 0xFFFF)
        ^ base
        ^ ((station & 0xFF) << 8)
    ) & 0xFFFF


def relay_auth_word(station, source_station, seq, base, time, epoch_key, source_key):
    auth = 0x85EBCA6B ^ (time & 0xFFFFFFFF)
    auth = u32(auth + seq * 1597334677)
    auth = u32(auth ^ u32(epoch_key * 2246822519))
    auth = u32(auth + source_key * 3266489917)
    auth = u32(auth ^ u32(station * 40503))
    auth = u32(auth + source_station * 97)
    auth = u32(auth + base * 31)
    return auth


def relay_key(station, source_station, seq, time, epoch_key, source_key):
    return (
        rotl16(seq, 2)
        ^ epoch_key
        ^ source_key
        ^ (time & 0xFFFF)
        ^ ((station & 0xFF) << 8)
        ^ source_station
    ) & 0xFFFF


def checkpoint_auth_word(station, seq, base, time, station_key, epoch_key):
    auth = 0x27D4EB2F ^ (time & 0xFFFFFFFF)
    auth = u32(auth + seq * 2654435761)
    auth = u32(auth ^ u32(station_key * 2246822519))
    auth = u32(auth + epoch_key * 3266489917)
    auth = u32(auth ^ u32(station * 668265263))
    auth = u32(auth + base * 40503)
    return auth


def checkpoint_key(station, seq, base, time, station_key, epoch_key):
    return (
        rotl16(seq, 13)
        ^ station_key
        ^ rotl16(epoch_key, 3)
        ^ (time & 0xFFFF)
        ^ base
        ^ ((station & 0xFF) << 8)
    ) & 0xFFFF


def quorum_auth_word(station, witnesses, seq, base, time, station_key, epoch_key,
                     checkpoint_key_value, witness_a_key, witness_b_key):
    auth = 0x165667B1 ^ (time & 0xFFFFFFFF)
    auth = u32(auth + seq * 374761393)
    auth = u32(auth ^ u32(checkpoint_key_value * 668265263))
    auth = u32(auth + station_key * 2246822519)
    auth = u32(auth ^ u32(epoch_key * 3266489917))
    auth = u32(auth + witness_a_key * 40503)
    auth = u32(auth ^ u32(witness_b_key * 2654435761))
    auth = u32(auth + witnesses * 97)
    auth = u32(auth + base * 31)
    auth = u32(auth ^ u32(station * 1597334677))
    return auth


def quorum_key(station, witnesses, seq, time, station_key, epoch_key,
               checkpoint_key_value, witness_a_key, witness_b_key):
    return (
        rotl16(seq, 7) ^ station_key ^ epoch_key ^ checkpoint_key_value
        ^ rotl16(witness_a_key, 3) ^ rotl16(witness_b_key, 11)
        ^ (time & 0xFFFF) ^ witnesses ^ ((station & 0xFF) << 8)
    ) & 0xFFFF


def quorum_time(quorum_key_value, seq, sensor, upper_time=0):
    tag = quorum_key_value ^ rotl16(seq, 15) ^ sensor
    return s64((upper_time & 0xFFFFFFFFFFFF0000) | (tag & 0xFFFF))


def quorum_dependency_ok(stations, station, seq, sensor, time):
    stn = stations.get(station)
    if (
        not stn or not stn.get("quorum_current") or not stn.get("has")
        or not stn.get("anchor_current") or not stn.get("checkpoint_current")
        or stn["seq"] != stn["quorum_beacon_seq"]
        or stn["anchor_seq"] != stn["quorum_anchor_seq"]
        or stn["checkpoint_seq"] != stn["quorum_checkpoint_seq"]
    ):
        return False
    a = stations.get(stn["quorum_witness_a"])
    b = stations.get(stn["quorum_witness_b"])
    if (
        not a or not a.get("has") or not b or not b.get("has")
        or a["seq"] != stn["witness_a_seq"]
        or b["seq"] != stn["witness_b_seq"]
    ):
        return False
    tag = time & 0xFFFF
    want = stn["quorum_key"] ^ rotl16(seq, 15) ^ sensor
    return tag == want


def calibration_auth_word(station, sensor, seq, base, scale, offset, time, station_key):
    auth = 0x9E3779B9 ^ (time & 0xFFFFFFFF)
    auth = u32(auth + seq * 2246822519)
    auth = u32(auth ^ u32(station_key * 3266489917))
    auth = u32(auth + sensor * 668265263)
    auth = u32(auth ^ u32(scale * 40503))
    auth = u32(auth + u32(offset ^ rotl16(base, 7)))
    auth = u32(auth ^ u32(station * 2654435761))
    return auth


def epoch_time(epoch_key, seq, sensor, low_time):
    tag = epoch_key ^ rotl16(seq, 6) ^ sensor
    return s64(((tag & 0xFFFF) << 48) | (low_time & 0x0000FFFFFFFFFFFF))


def relay_time(relay_key_value, seq, sensor, low_time, epoch_key=None):
    relay_tag = relay_key_value ^ rotl16(seq, 9) ^ sensor
    base = low_time & 0x00000000FFFFFFFF
    if epoch_key is not None:
        epoch_tag = epoch_key ^ rotl16(seq, 6) ^ sensor
        return s64(((epoch_tag & 0xFFFF) << 48) | ((relay_tag & 0xFFFF) << 32) | base)
    return s64(((relay_tag & 0xFFFF) << 32) | base)


def checkpoint_time(checkpoint_key_value, seq, sensor, low_time, relay_key_value=None, epoch_key=None):
    value = low_time & 0xFFFF
    value |= ((checkpoint_key_value ^ rotl16(seq, 12) ^ sensor) & 0xFFFF) << 16
    if relay_key_value is not None:
        value |= ((relay_key_value ^ rotl16(seq, 9) ^ sensor) & 0xFFFF) << 32
    if epoch_key is not None:
        value |= ((epoch_key ^ rotl16(seq, 6) ^ sensor) & 0xFFFF) << 48
    return s64(value)


def carry_offset(station_key, seq, sensor, low=0):
    tag = station_key ^ rotl16(seq, 3) ^ sensor
    return s32((tag << 16) | (low & 0xFFFF))


def calibration_key(station, sensor, seq, scale, offset):
    scale &= 0xFFFFFFFF
    offset &= 0xFFFFFFFF
    return (
        rotl16(seq, 7)
        ^ (scale & 0xFFFF)
        ^ ((scale >> 16) & 0xFFFF)
        ^ rotl16(offset & 0xFFFF, 3)
        ^ ((offset >> 16) & 0xFFFF)
        ^ ((station & 0xFF) << 8)
        ^ sensor
    ) & 0xFFFF


def calibration_tag(cal_key, seq):
    return (cal_key ^ rotl16(seq, 1)) & 0xFFFF


def chain_tag(data_key, base, sensor):
    return (data_key ^ rotl16(base, 5) ^ sensor) & 0xFFFF


def scale_tags(beacon_seq, cal_tag=0):
    return s32(((cal_tag & 0xFFFF) << 16) | (beacon_seq & 0xFFFF))


def snapshot_data_key(station_key, cal_key, station, sensor, seq, raw, time):
    return (
        station_key
        ^ cal_key
        ^ (raw & 0xFFFF)
        ^ rotl16(seq, 4)
        ^ (time & 0xFFFF)
        ^ ((station & 0xFF) << 8)
        ^ sensor
    ) & 0xFFFF


def delta_data_key(old_key, seq, raw_delta, time):
    return (rotl16(old_key, 3) ^ (raw_delta & 0xFFFF) ^ seq ^ (time & 0xFFFF)) & 0xFFFF


def delete_data_key(old_key, seq, time):
    return (rotl16(old_key, 11) ^ seq ^ (time & 0xFFFF) ^ 0xD1E7) & 0xFFFF


def frame(
    typ,
    station,
    seq,
    sensor,
    *,
    version=1,
    flags=0,
    base=65535,
    raw=None,
    scale=1000000,
    offset=0,
    time=0,
    corrupt_crc=False,
    magic=b"HB",
):
    if raw is None:
        if typ == 5 and version == 2 and flags == 1 and sensor == 0:
            raw = s32(beacon_auth_word(station, seq, base, time))
        elif typ == 6 and version == 2 and flags == 1 and sensor == 0:
            raise ValueError("type 6 anchor frames need explicit raw auth")
        elif typ in (7, 8) and version == 2 and flags == 1:
            raise ValueError("type 7 relay frames need explicit raw auth")
        else:
            raw = 0
    head = struct.pack(
        "<2sBBBBHHHiiiq",
        magic,
        version,
        typ,
        flags,
        station,
        seq,
        sensor,
        base,
        raw,
        scale,
        offset,
        time,
    )
    assert len(head) == 32
    if version == 2 and flags & 1:
        head = beacon_x_payload(head, version, typ, station)
    crc = crc32_ieee(head)
    if corrupt_crc:
        crc ^= 0x01020304
    return head + struct.pack("<I", crc)


def newer(candidate, current):
    d = (candidate - current) & 0xFFFF
    return 1 <= d <= SEQ_FORWARD_LIMIT


def trunc_div_1000(value):
    sign = -1 if value < 0 else 1
    return sign * (abs(value) // 1000)


def replay(blob: bytes) -> str:
    states = {}
    stations = {}
    counts = {"accepted": 0, **{k: 0 for k in REJECT_KEYS}}
    pos = 0
    while pos + 36 <= len(blob):
        rec = blob[pos : pos + 36]
        pos += 36
        magic, version, typ, flags, station, seq, sensor, base, raw, scale, offset, time = struct.unpack(
            "<2sBBBBHHHiiiq", rec[:32]
        )
        got_crc = struct.unpack("<I", rec[32:])[0]
        if magic != b"HB":
            counts["bad_magic"] += 1
            continue
        if got_crc != crc32_ieee(rec[:32]):
            counts["bad_crc"] += 1
            continue
        if version not in (1, 2):
            counts["bad_version"] += 1
            continue
        if (version == 1 and flags != 0) or (
            version == 2 and ((flags & 0x80) or ((flags & 0x7E) and not (flags & 0x01)))
        ):
            counts["bad_flags"] += 1
            continue
        if typ not in (1, 2, 3, 4, 5, 6, 7, 8, 9):
            counts["bad_type"] += 1
            continue

        if flags & 1:
            rec = beacon_x_payload(rec[:32], version, typ, station) + rec[32:]
            magic, version, typ, flags, station, seq, sensor, base, raw, scale, offset, time = struct.unpack(
                "<2sBBBBHHHiiiq", rec[:32]
            )

        if typ == 5:
            if (
                version != 2
                or flags != 1
                or sensor != 0
                or (raw & 0xFFFFFFFF) != beacon_auth_word(station, seq, base, time)
            ):
                counts["bad_layout"] += 1
                continue
            stn = stations.setdefault(
                station,
                {
                    "has": False,
                    "seq": 0,
                    "time": 0,
                    "key": 0,
                    "has_anchor": False,
                    "anchor_current": False,
                    "anchor_seq": 0,
                    "epoch_key": 0,
                    "has_relay": False,
                    "relay_current": False,
                    "relay_seq": 0,
                    "relay_key": 0,
                    "has_checkpoint": False,
                    "checkpoint_current": False,
                    "checkpoint_seq": 0,
                    "checkpoint_key": 0,
                },
            )
            if stn["has"] and not newer(seq, stn["seq"]):
                counts["stale"] += 1
                continue
            stn["has"] = True
            stn["seq"] = seq
            stn["time"] = time
            stn["key"] = beacon_auth_key(station, seq, base, time)
            stn["anchor_current"] = False
            stn["relay_current"] = False
            stn["checkpoint_current"] = False
            stn["quorum_current"] = False
            counts["accepted"] += 1
            continue

        if typ == 6:
            if version != 2 or flags != 1 or sensor != 0:
                counts["bad_layout"] += 1
                continue
            stn = stations.setdefault(
                station,
                {
                    "has": False,
                    "seq": 0,
                    "time": 0,
                    "key": 0,
                    "has_anchor": False,
                    "anchor_current": False,
                    "anchor_seq": 0,
                    "epoch_key": 0,
                    "has_relay": False,
                    "relay_current": False,
                    "relay_seq": 0,
                    "relay_key": 0,
                    "has_checkpoint": False,
                    "checkpoint_current": False,
                    "checkpoint_seq": 0,
                    "checkpoint_key": 0,
                },
            )
            if stn.get("has_anchor") and not newer(seq, stn["anchor_seq"]):
                counts["stale"] += 1
                continue
            if (
                not stn["has"]
                or stn["seq"] != base
                or (raw & 0xFFFFFFFF) != anchor_auth_word(station, seq, base, time, stn["key"])
            ):
                counts["dependency"] += 1
                continue
            stn["has_anchor"] = True
            stn["anchor_current"] = True
            stn["anchor_seq"] = seq
            stn["time"] = time
            stn["epoch_key"] = anchor_epoch_key(station, seq, base, time, stn["key"])
            stn["relay_current"] = False
            stn["checkpoint_current"] = False
            stn["quorum_current"] = False
            counts["accepted"] += 1
            continue

        if typ == 7:
            if version != 2 or flags != 1 or sensor > 255:
                counts["bad_layout"] += 1
                continue
            source_station = sensor
            stn = stations.setdefault(
                station,
                {
                    "has": False,
                    "seq": 0,
                    "time": 0,
                    "key": 0,
                    "has_anchor": False,
                    "anchor_current": False,
                    "anchor_seq": 0,
                    "epoch_key": 0,
                    "has_relay": False,
                    "relay_current": False,
                    "relay_seq": 0,
                    "relay_key": 0,
                    "has_checkpoint": False,
                    "checkpoint_current": False,
                    "checkpoint_seq": 0,
                    "checkpoint_key": 0,
                },
            )
            source = stations.get(source_station)
            if stn.get("has_relay") and not newer(seq, stn["relay_seq"]):
                counts["stale"] += 1
                continue
            if (
                not stn.get("anchor_current")
                or stn["anchor_seq"] != base
                or not source
                or not source["has"]
                or (raw & 0xFFFFFFFF)
                != relay_auth_word(station, source_station, seq, base, time, stn["epoch_key"], source["key"])
            ):
                counts["dependency"] += 1
                continue
            stn["has_relay"] = True
            stn["relay_current"] = True
            stn["relay_seq"] = seq
            stn["time"] = time
            stn["relay_key"] = relay_key(station, source_station, seq, time, stn["epoch_key"], source["key"])
            stn["checkpoint_current"] = False
            stn["quorum_current"] = False
            counts["accepted"] += 1
            continue

        if typ == 8:
            if version != 2 or flags != 1 or sensor != 0:
                counts["bad_layout"] += 1
                continue
            stn = stations.setdefault(station, {})
            if stn.get("has_checkpoint") and not newer(seq, stn["checkpoint_seq"]):
                counts["stale"] += 1
                continue
            if (
                not stn.get("has")
                or not stn.get("anchor_current")
                or stn["anchor_seq"] != base
                or (raw & 0xFFFFFFFF)
                != checkpoint_auth_word(station, seq, base, time, stn["key"], stn["epoch_key"])
            ):
                counts["dependency"] += 1
                continue
            stn["has_checkpoint"] = True
            stn["checkpoint_current"] = True
            stn["checkpoint_seq"] = seq
            stn["checkpoint_key"] = checkpoint_key(
                station, seq, base, time, stn["key"], stn["epoch_key"]
            )
            stn["quorum_current"] = False
            counts["accepted"] += 1
            continue

        if typ == 9:
            witness_a = sensor & 0xFF
            witness_b = (sensor >> 8) & 0xFF
            if (
                version != 2
                or flags != 1
                or witness_a >= witness_b
                or witness_a == station
                or witness_b == station
            ):
                counts["bad_layout"] += 1
                continue
            stn = stations.setdefault(station, {})
            a = stations.get(witness_a)
            b = stations.get(witness_b)
            if stn.get("has_quorum") and not newer(seq, stn["quorum_seq"]):
                counts["stale"] += 1
                continue
            tagged_a_seq = scale & 0xFFFF
            tagged_b_seq = (scale >> 16) & 0xFFFF
            tagged_anchor = offset & 0xFFFF
            tagged_beacon = (offset >> 16) & 0xFFFF
            if (
                not stn.get("has")
                or not stn.get("anchor_current")
                or not stn.get("checkpoint_current")
                or stn["checkpoint_seq"] != base
                or stn["anchor_seq"] != tagged_anchor
                or stn["seq"] != tagged_beacon
                or not a or not a.get("has") or a["seq"] != tagged_a_seq
                or not b or not b.get("has") or b["seq"] != tagged_b_seq
                or (raw & 0xFFFFFFFF) != quorum_auth_word(
                    station, sensor, seq, base, time, stn["key"], stn["epoch_key"],
                    stn["checkpoint_key"], a["key"], b["key"]
                )
            ):
                counts["dependency"] += 1
                continue
            stn["has_quorum"] = True
            stn["quorum_current"] = True
            stn["quorum_seq"] = seq
            stn["quorum_key"] = quorum_key(
                station, sensor, seq, time, stn["key"], stn["epoch_key"],
                stn["checkpoint_key"], a["key"], b["key"]
            )
            stn["quorum_witness_a"] = witness_a
            stn["quorum_witness_b"] = witness_b
            stn["quorum_beacon_seq"] = stn["seq"]
            stn["quorum_anchor_seq"] = stn["anchor_seq"]
            stn["quorum_checkpoint_seq"] = stn["checkpoint_seq"]
            stn["witness_a_seq"] = a["seq"]
            stn["witness_b_seq"] = b["seq"]
            counts["accepted"] += 1
            continue

        if (flags & 0x7E) and typ == 1:
            counts["bad_layout"] += 1
            continue

        key = (station, sensor)
        st = states.setdefault(
            key,
            {
                "has_data": False,
                "data_seq": 0,
                "has_cal": False,
                "cal_seq": 0,
                "active": False,
                "raw": 0,
                "time": 0,
                "scale": 1000000,
                "offset": 0,
                "cal_key": 0,
                "data_key": 0,
            },
        )
        if typ == 1:
            if st["has_cal"] and not newer(seq, st["cal_seq"]):
                counts["stale"] += 1
                continue
            if flags & 1:
                stn = stations.get(station)
                if (
                    not stn
                    or not stn["has"]
                    or stn["seq"] != base
                    or (raw & 0xFFFFFFFF)
                    != calibration_auth_word(station, sensor, seq, base, scale, offset, time, stn["key"])
                ):
                    counts["dependency"] += 1
                    continue
            st["has_cal"] = True
            st["cal_seq"] = seq
            st["scale"] = scale
            st["offset"] = offset
            st["cal_key"] = calibration_key(station, sensor, seq, scale, offset)
            counts["accepted"] += 1
        elif typ == 2:
            if st["has_data"] and not newer(seq, st["data_seq"]):
                counts["stale"] += 1
                continue
            if flags & 1:
                tag = scale & 0xFFFF
                stn = stations.get(station)
                if not stn or not stn["has"] or stn["seq"] != tag:
                    counts["dependency"] += 1
                    continue
            if flags & 4:
                tag = (scale >> 16) & 0xFFFF
                if not st["has_cal"] or tag != calibration_tag(st["cal_key"], seq):
                    counts["dependency"] += 1
                    continue
            if flags & 2:
                stn = stations.get(station)
                tag = (offset >> 16) & 0xFFFF
                if not stn or tag != (stn["key"] ^ rotl16(seq, 3) ^ sensor):
                    counts["dependency"] += 1
                    continue
            if flags & 8:
                stn = stations.get(station)
                tag = (time >> 48) & 0xFFFF
                if not stn or not stn.get("anchor_current") or tag != (stn["epoch_key"] ^ rotl16(seq, 6) ^ sensor):
                    counts["dependency"] += 1
                    continue
            if flags & 16:
                stn = stations.get(station)
                tag = (time >> 32) & 0xFFFF
                if not stn or not stn.get("relay_current") or tag != (stn["relay_key"] ^ rotl16(seq, 9) ^ sensor):
                    counts["dependency"] += 1
                    continue
            if flags & 32:
                stn = stations.get(station)
                tag = (time >> 16) & 0xFFFF
                if not stn or not stn.get("checkpoint_current") or tag != (stn["checkpoint_key"] ^ rotl16(seq, 12) ^ sensor):
                    counts["dependency"] += 1
                    continue
            if flags & 64 and not quorum_dependency_ok(stations, station, seq, sensor, time):
                counts["dependency"] += 1
                continue
            st["has_data"] = True
            st["data_seq"] = seq
            st["active"] = True
            st["raw"] = raw
            st["time"] = time
            stn = stations.get(station)
            stn_key = stn["key"] if stn and stn["has"] else 0
            st["data_key"] = snapshot_data_key(stn_key, st["cal_key"], station, sensor, seq, raw, time)
            counts["accepted"] += 1
        elif typ == 3:
            if st["has_data"] and not newer(seq, st["data_seq"]):
                counts["stale"] += 1
                continue
            if not st["active"] or not st["has_data"] or base != st["data_seq"]:
                counts["dependency"] += 1
                continue
            if flags & 1:
                tag = scale & 0xFFFF
                stn = stations.get(station)
                if not stn or not stn["has"] or stn["seq"] != tag:
                    counts["dependency"] += 1
                    continue
            if flags & 4:
                tag = (scale >> 16) & 0xFFFF
                if not st["has_cal"] or tag != calibration_tag(st["cal_key"], seq):
                    counts["dependency"] += 1
                    continue
            if flags & 2:
                stn = stations.get(station)
                tag = (offset >> 16) & 0xFFFF
                if not stn or tag != (stn["key"] ^ rotl16(seq, 3) ^ sensor):
                    counts["dependency"] += 1
                    continue
            if flags & 4:
                tag = offset & 0xFFFF
                if tag != chain_tag(st["data_key"], base, sensor):
                    counts["dependency"] += 1
                    continue
            if flags & 8:
                stn = stations.get(station)
                tag = (time >> 48) & 0xFFFF
                if not stn or not stn.get("anchor_current") or tag != (stn["epoch_key"] ^ rotl16(seq, 6) ^ sensor):
                    counts["dependency"] += 1
                    continue
            if flags & 16:
                stn = stations.get(station)
                tag = (time >> 32) & 0xFFFF
                if not stn or not stn.get("relay_current") or tag != (stn["relay_key"] ^ rotl16(seq, 9) ^ sensor):
                    counts["dependency"] += 1
                    continue
            if flags & 32:
                stn = stations.get(station)
                tag = (time >> 16) & 0xFFFF
                if not stn or not stn.get("checkpoint_current") or tag != (stn["checkpoint_key"] ^ rotl16(seq, 12) ^ sensor):
                    counts["dependency"] += 1
                    continue
            if flags & 64 and not quorum_dependency_ok(stations, station, seq, sensor, time):
                counts["dependency"] += 1
                continue
            old_key = st["data_key"]
            st["raw"] += raw
            st["data_seq"] = seq
            st["time"] = time
            st["data_key"] = delta_data_key(old_key, seq, raw, time)
            counts["accepted"] += 1
        else:
            if st["has_data"] and not newer(seq, st["data_seq"]):
                counts["stale"] += 1
                continue
            if base != 65535 and (not st["has_data"] or base != st["data_seq"]):
                counts["dependency"] += 1
                continue
            if flags & 1:
                tag = scale & 0xFFFF
                stn = stations.get(station)
                if not stn or not stn["has"] or stn["seq"] != tag:
                    counts["dependency"] += 1
                    continue
            if flags & 4:
                tag = (scale >> 16) & 0xFFFF
                if not st["has_cal"] or tag != calibration_tag(st["cal_key"], seq):
                    counts["dependency"] += 1
                    continue
            if flags & 2:
                stn = stations.get(station)
                tag = (offset >> 16) & 0xFFFF
                if not stn or tag != (stn["key"] ^ rotl16(seq, 3) ^ sensor):
                    counts["dependency"] += 1
                    continue
            if flags & 4 and base != 65535:
                tag = offset & 0xFFFF
                if tag != chain_tag(st["data_key"], base, sensor):
                    counts["dependency"] += 1
                    continue
            if flags & 8:
                stn = stations.get(station)
                tag = (time >> 48) & 0xFFFF
                if not stn or not stn.get("anchor_current") or tag != (stn["epoch_key"] ^ rotl16(seq, 6) ^ sensor):
                    counts["dependency"] += 1
                    continue
            if flags & 16:
                stn = stations.get(station)
                tag = (time >> 32) & 0xFFFF
                if not stn or not stn.get("relay_current") or tag != (stn["relay_key"] ^ rotl16(seq, 9) ^ sensor):
                    counts["dependency"] += 1
                    continue
            if flags & 32:
                stn = stations.get(station)
                tag = (time >> 16) & 0xFFFF
                if not stn or not stn.get("checkpoint_current") or tag != (stn["checkpoint_key"] ^ rotl16(seq, 12) ^ sensor):
                    counts["dependency"] += 1
                    continue
            if flags & 64 and not quorum_dependency_ok(stations, station, seq, sensor, time):
                counts["dependency"] += 1
                continue
            old_key = st["data_key"]
            st["has_data"] = True
            st["data_seq"] = seq
            st["active"] = False
            st["time"] = time
            st["data_key"] = delete_data_key(old_key, seq, time)
            counts["accepted"] += 1

    if pos != len(blob):
        counts["bad_length"] += 1

    rejected = sum(counts[k] for k in REJECT_KEYS)
    lines = [f"summary accepted={counts['accepted']} rejected={rejected}"]
    lines.extend(f"reject {k}={counts[k]}" for k in REJECT_KEYS)
    for station, sensor in sorted(states):
        st = states[(station, sensor)]
        if st["active"]:
            calibrated = trunc_div_1000(st["raw"] * st["scale"]) + st["offset"]
            lines.append(
                f"sensor station={station} sensor={sensor} seq={st['data_seq']} "
                f"time={st['time']} raw={st['raw']} calibrated_milli={calibrated}"
            )
    return "\n".join(lines) + "\n"


def compile_program():
    assert SRC.exists(), "/app/src/beacon_replay.c is missing"
    text = SRC.read_text(errors="ignore")
    forbidden = ["system(", "popen(", "fork(", "execv", "/solution", "python"]
    for token in forbidden:
        assert token not in text, f"source must not shell out or depend on forbidden token {token!r}"
    result = subprocess.run(
        ["gcc", "-O2", "-std=c11", str(SRC), "-o", str(BIN)],
        cwd=APP,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert result.returncode == 0, (
        "gcc failed\n"
        f"command: gcc -O2 -std=c11 {SRC} -o {BIN}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )


def run_case(path: Path) -> str:
    result = subprocess.run(
        [str(BIN), str(path)],
        cwd=APP,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, (
        f"program exited with {result.returncode} for {path.name}\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    lines = [line for line in result.stdout.splitlines() if not line.startswith("#")]
    return "\n".join(lines) + ("\n" if lines else "")


def assert_output_matches(name: str, actual: str, expected: str):
    assert actual == expected, textwrap.dedent(
        f"""
        output mismatch for case {name}

        expected:
        {expected}

        actual:
        {actual}
        """
    )


def build_cases():
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir()

    cases = {}

    cases["public"] = PUBLIC_BIN.read_bytes()

    cases["wrap_and_calibration"] = b"".join(
        [
            frame(1, 2, 65000, 10, scale=1500000, offset=-25, time=1),
            frame(2, 2, 65001, 10, raw=200, time=10),
            frame(3, 2, 65002, 10, base=65001, raw=-20, time=11),
            frame(1, 2, 65000, 10, scale=1700000, offset=0, time=12),
            frame(1, 2, 65003, 10, scale=1200000, offset=5, time=13),
            frame(5, 2, 65002, 0, time=19, version=2, flags=1),
            frame(3, 2, 3, 10, base=65002, raw=30, scale=65002, time=20, version=2, flags=1),
            frame(2, 2, 32771, 10, raw=999, time=21),
            frame(2, 1, 4, 2, raw=-40, time=4),
            frame(1, 1, 5, 2, scale=-500000, offset=9, time=5),
        ]
    )

    cases["reject_matrix"] = b"".join(
        [
            frame(2, 7, 1, 1, raw=10, time=1),
            frame(3, 7, 2, 1, base=0, raw=5, time=2),
            frame(3, 7, 1, 1, base=1, raw=5, time=3),
            frame(4, 7, 3, 1, base=1, time=4),
            frame(3, 7, 4, 1, base=3, raw=99, time=5),
            frame(2, 7, 5, 1, raw=15, time=6, corrupt_crc=True),
            frame(2, 7, 6, 1, raw=20, time=7, magic=b"XB"),
            frame(2, 7, 7, 1, raw=25, time=8, version=3),
            frame(2, 7, 8, 1, raw=30, time=9, version=1, flags=1),
            frame(9, 7, 9, 1, raw=35, time=10),
            frame(2, 8, 1, 4, raw=100, time=11),
        ]
    )

    cases["delete_and_empty"] = b"".join(
        [
            frame(2, 3, 10, 1, raw=77, time=10),
            frame(4, 3, 11, 1, base=65535, time=11),
            frame(3, 3, 12, 1, base=11, raw=5, time=12),
            frame(2, 3, 13, 1, raw=88, time=13),
            frame(4, 3, 14, 1, base=13, time=14),
            frame(1, 3, 15, 1, scale=1100000, offset=0, time=15),
        ]
    )

    cases["trailing_fragment"] = (
        frame(1, 4, 100, 9, scale=900000, offset=30, time=100)
        + frame(2, 4, 101, 9, raw=123, time=101)
        + frame(3, 4, 102, 9, base=101, raw=7, time=102)
        + b"\x48\x42\x01"
    )

    cases["multi_key_sorting"] = b"".join(
        [
            frame(2, 9, 1, 30, raw=1, time=1),
            frame(2, 2, 1, 400, raw=2, time=2),
            frame(2, 2, 2, 3, raw=3, time=3),
            frame(1, 2, 3, 3, scale=2000000, offset=1, time=4),
            frame(2, 1, 1, 999, raw=4, time=5),
        ]
    )

    cases["calibration_after_data"] = b"".join(
        [
            frame(2, 5, 10, 10, raw=64, time=10),
            frame(3, 5, 11, 10, base=10, raw=6, time=11),
            frame(1, 5, 1, 10, scale=1750000, offset=-2, time=12),
            frame(1, 5, 0, 10, scale=3000000, offset=0, time=13),
        ]
    )

    cases["calibration_and_data_sequences_are_separate"] = b"".join(
        [
            frame(1, 6, 50, 1, scale=1100000, offset=4, time=1),
            frame(2, 6, 50, 1, raw=10, time=2),
            frame(3, 6, 51, 1, base=50, raw=10, time=3),
            frame(1, 6, 51, 1, scale=1200000, offset=5, time=4),
        ]
    )

    key_8 = beacon_auth_key(8, 100, 65535, 0)
    cal_8_raw = s32(calibration_auth_word(8, 8, 1, 100, 1000000, 8, 1, key_8))
    cases["version2_flag_is_allowed"] = b"".join(
        [
            frame(5, 8, 100, 0, time=0, version=2, flags=1),
            frame(1, 8, 1, 8, base=100, raw=cal_8_raw, scale=1000000, offset=8, time=1, version=2, flags=1),
            frame(2, 8, 2, 8, raw=8, scale=100, time=2, version=2, flags=1),
            frame(3, 8, 3, 8, base=2, raw=8, scale=100, time=3, version=2, flags=1),
            frame(4, 8, 4, 8, base=3, scale=100, time=4, version=2, flags=1),
        ]
    )

    key_18 = beacon_auth_key(18, 70, 2, 10)
    good_cal_18 = s32(calibration_auth_word(18, 4, 6, 70, 1400000, -17, 15, key_18))
    cases["sealed_calibration_dependencies"] = b"".join(
        [
            frame(1, 18, 1, 4, base=70, raw=0, scale=1300000, offset=3, time=1, version=2, flags=1),
            frame(5, 18, 70, 0, base=2, time=10, version=2, flags=1),
            frame(1, 18, 5, 4, base=69, raw=good_cal_18, scale=1400000, offset=-17, time=11, version=2, flags=1),
            frame(1, 18, 5, 4, base=70, raw=good_cal_18 ^ 1, scale=1400000, offset=-17, time=12, version=2, flags=1),
            frame(1, 18, 6, 4, base=70, raw=good_cal_18, scale=1400000, offset=-17, time=15, version=2, flags=1),
            frame(2, 18, 7, 4, raw=100, scale=70, time=16, version=2, flags=1),
            frame(1, 18, 5, 4, base=70, raw=good_cal_18, scale=1800000, offset=0, time=17, version=2, flags=1),
        ]
    )

    cases["encoded_station_dependencies"] = b"".join(
        [
            frame(2, 15, 1, 7, raw=10, scale=77, time=1, version=2, flags=1),
            frame(5, 15, 77, 0, time=2, version=2, flags=1),
            frame(2, 15, 2, 7, raw=20, scale=77, time=3, version=2, flags=1),
            frame(3, 15, 3, 7, base=2, raw=5, scale=76, time=4, version=2, flags=1),
            frame(3, 15, 2, 7, base=999, raw=5, scale=76, time=5, version=2, flags=1),
            frame(5, 15, 90, 0, time=6, version=2, flags=1),
            frame(3, 15, 4, 7, base=2, raw=7, scale=77, time=7, version=2, flags=1),
            frame(3, 15, 5, 7, base=2, raw=9, scale=90, time=8, version=2, flags=1),
            frame(4, 15, 6, 7, base=5, scale=90, time=9, version=2, flags=1),
        ]
    )

    cases["beacon_layout_and_station_stale"] = b"".join(
        [
            frame(5, 16, 10, 0, time=1),
            frame(5, 16, 11, 2, time=2, version=2, flags=1),
            frame(5, 16, 12, 0, time=3, version=2, flags=1),
            frame(5, 16, 12, 0, time=4, version=2, flags=1),
            frame(5, 16, 32780, 0, time=5, version=2, flags=1),
            frame(2, 16, 1, 1, raw=33, scale=12, time=6, version=2, flags=1),
        ]
    )

    cases["invalid_type_after_valid_crc"] = b"".join(
        [
            frame(2, 10, 1, 1, raw=5, time=1),
            frame(0, 10, 2, 1, raw=6, time=2),
            frame(5, 10, 3, 1, raw=7, time=3),
        ]
    )

    cases["tight_sequence_horizon"] = b"".join(
        [
            frame(2, 11, 1000, 1, raw=100, time=1),
            frame(3, 11, 31001, 1, base=1000, raw=7, time=2),
            frame(3, 11, 31000, 1, base=1000, raw=8, time=3),
        ]
    )

    cases["delete_without_prior_state"] = b"".join(
        [
            frame(4, 12, 10, 1, base=65535, time=1),
            frame(2, 12, 11, 1, raw=44, time=2),
            frame(4, 12, 12, 1, base=11, time=3),
        ]
    )

    cases["negative_truncation"] = b"".join(
        [
            frame(1, 13, 1, 1, scale=333333, offset=-7, time=1),
            frame(2, 13, 2, 1, raw=-10, time=2),
            frame(3, 13, 3, 1, base=2, raw=-1, time=3),
        ]
    )

    cases["mixed_rejections_keep_replaying"] = b"".join(
        [
            frame(2, 14, 1, 1, raw=1, time=1),
            frame(2, 14, 2, 1, raw=2, time=2, corrupt_crc=True),
            frame(3, 14, 2, 1, base=1, raw=3, time=3),
            frame(3, 14, 3, 1, base=2, raw=4, time=4, magic=b"ZZ"),
            frame(3, 14, 3, 1, base=2, raw=5, time=5),
        ]
    )

    key_21_a = beacon_auth_key(21, 400, 9, 100)
    key_21_b = beacon_auth_key(21, 500, 3, 200)
    cases["carry_auth_dependency_chain"] = b"".join(
        [
            frame(5, 21, 400, 0, base=9, time=100, version=2, flags=1),
            frame(2, 21, 1, 5, raw=10, scale=400, offset=carry_offset(key_21_a, 1, 5), time=101, version=2, flags=3),
            frame(3, 21, 2, 5, base=1, raw=3, scale=400, offset=carry_offset(key_21_a, 2, 4), time=102, version=2, flags=3),
            frame(3, 21, 2, 5, base=1, raw=4, scale=401, offset=carry_offset(key_21_a, 2, 5), time=103, version=2, flags=3),
            frame(3, 21, 2, 5, base=1, raw=5, scale=400, offset=carry_offset(key_21_a, 2, 5), time=104, version=2, flags=3),
            frame(5, 21, 500, 0, base=3, time=200, version=2, flags=1),
            frame(3, 21, 3, 5, base=2, raw=6, scale=400, offset=carry_offset(key_21_b, 3, 5), time=201, version=2, flags=3),
            frame(3, 21, 3, 5, base=2, raw=7, scale=500, offset=carry_offset(key_21_a, 3, 5), time=202, version=2, flags=3),
            frame(3, 21, 3, 5, base=2, raw=8, scale=500, offset=carry_offset(key_21_b, 3, 5), time=203, version=2, flags=3),
        ]
    )

    key_31 = beacon_auth_key(31, 200, 4, 30)
    cal_31 = calibration_key(31, 9, 10, 1234000, -12)
    data_31_a = snapshot_data_key(key_31, cal_31, 31, 9, 11, 50, 31)
    data_31_b = delta_data_key(data_31_a, 12, 5, 32)
    data_31_c = delta_data_key(data_31_b, 13, 7, 35)
    cases["calibration_and_chain_dependencies"] = b"".join(
        [
            frame(5, 31, 200, 0, base=4, time=30, version=2, flags=1),
            frame(1, 31, 10, 9, scale=1234000, offset=-12, time=30),
            frame(
                2,
                31,
                11,
                9,
                raw=50,
                scale=scale_tags(200, calibration_tag(cal_31, 11)),
                offset=carry_offset(key_31, 11, 9, low=0x2222),
                time=31,
                version=2,
                flags=7,
            ),
            frame(
                3,
                31,
                12,
                9,
                base=11,
                raw=5,
                scale=scale_tags(200, calibration_tag(cal_31, 12)),
                offset=carry_offset(key_31, 12, 9, low=chain_tag(data_31_a, 11, 9)),
                time=32,
                version=2,
                flags=7,
            ),
            frame(
                3,
                31,
                13,
                9,
                base=12,
                raw=6,
                scale=scale_tags(200, calibration_tag(cal_31, 13) ^ 1),
                offset=carry_offset(key_31, 13, 9, low=chain_tag(data_31_b, 12, 9)),
                time=33,
                version=2,
                flags=7,
            ),
            frame(
                3,
                31,
                13,
                9,
                base=12,
                raw=6,
                scale=scale_tags(200, calibration_tag(cal_31, 13)),
                offset=carry_offset(key_31, 13, 9, low=chain_tag(data_31_b, 12, 9) ^ 7),
                time=34,
                version=2,
                flags=7,
            ),
            frame(
                3,
                31,
                13,
                9,
                base=12,
                raw=7,
                scale=scale_tags(200, calibration_tag(cal_31, 13)),
                offset=carry_offset(key_31, 13, 9, low=chain_tag(data_31_b, 12, 9)),
                time=35,
                version=2,
                flags=7,
            ),
            frame(
                4,
                31,
                14,
                9,
                base=13,
                scale=scale_tags(200, calibration_tag(cal_31, 14)),
                offset=carry_offset(key_31, 14, 9, low=chain_tag(data_31_c, 13, 9)),
                time=36,
                version=2,
                flags=7,
            ),
            frame(5, 32, 201, 0, base=4, time=40, version=2, flags=1),
            frame(
                2,
                32,
                1,
                2,
                raw=9,
                scale=scale_tags(201, 0),
                time=41,
                version=2,
                flags=5,
            ),
            frame(1, 32, 2, 2, scale=1200000, offset=0, time=42, version=2, flags=5),
        ]
    )

    key_40 = beacon_auth_key(40, 100, 3, 10)
    anchor_40_raw = s32(anchor_auth_word(40, 101, 100, 11, key_40))
    epoch_40 = anchor_epoch_key(40, 101, 100, 11, key_40)
    cal_40 = calibration_key(40, 12, 5, 1300000, -4)
    data_40_a = snapshot_data_key(key_40, cal_40, 40, 12, 6, 30, epoch_time(epoch_40, 6, 12, 12))
    data_40_b = delta_data_key(data_40_a, 7, 4, epoch_time(epoch_40, 7, 12, 13))
    cases["epoch_anchor_full_auth_stack"] = b"".join(
        [
            frame(5, 40, 100, 0, base=3, time=10, version=2, flags=1),
            frame(6, 40, 101, 0, base=100, raw=anchor_40_raw, time=11, version=2, flags=1),
            frame(1, 40, 5, 12, scale=1300000, offset=-4, time=11),
            frame(
                2,
                40,
                6,
                12,
                raw=30,
                scale=scale_tags(100, calibration_tag(cal_40, 6)),
                offset=carry_offset(key_40, 6, 12, low=0x4444),
                time=epoch_time(epoch_40, 6, 12, 12),
                version=2,
                flags=15,
            ),
            frame(
                3,
                40,
                7,
                12,
                base=6,
                raw=4,
                scale=scale_tags(100, calibration_tag(cal_40, 7)),
                offset=carry_offset(key_40, 7, 12, low=chain_tag(data_40_a, 6, 12)),
                time=epoch_time(epoch_40, 7, 12, 13),
                version=2,
                flags=15,
            ),
            frame(
                4,
                40,
                8,
                12,
                base=7,
                scale=scale_tags(100, calibration_tag(cal_40, 8)),
                offset=carry_offset(key_40, 8, 12, low=chain_tag(data_40_b, 7, 12)),
                time=epoch_time(epoch_40, 8, 12, 14),
                version=2,
                flags=15,
            ),
        ]
    )

    source_50_key = beacon_auth_key(50, 20, 1, 100)
    local_51_key = beacon_auth_key(51, 30, 2, 101)
    anchor_51_raw = s32(anchor_auth_word(51, 31, 30, 102, local_51_key))
    epoch_51 = anchor_epoch_key(51, 31, 30, 102, local_51_key)
    relay_51_raw = s32(relay_auth_word(51, 50, 32, 31, 103, epoch_51, source_50_key))
    relay_51 = relay_key(51, 50, 32, 103, epoch_51, source_50_key)
    cases["relay_auth_cross_station_dependency"] = b"".join(
        [
            frame(5, 50, 20, 0, base=1, time=100, version=2, flags=1),
            frame(5, 51, 30, 0, base=2, time=101, version=2, flags=1),
            frame(2, 51, 1, 9, raw=1, scale=30, time=relay_time(relay_51, 1, 9, 104), version=2, flags=17),
            frame(6, 51, 31, 0, base=30, raw=anchor_51_raw, time=102, version=2, flags=1),
            frame(7, 51, 32, 49, base=31, raw=relay_51_raw, time=103, version=2, flags=1),
            frame(7, 51, 32, 50, base=31, raw=relay_51_raw, time=103, version=2, flags=1),
            frame(7, 51, 1057, 50, base=31, raw=relay_51_raw, time=104, version=2, flags=1),
            frame(7, 51, 33, 50, base=31, raw=relay_51_raw ^ 3, time=105, version=2, flags=1),
            frame(7, 51, 33, 50, base=31, raw=relay_51_raw, time=103, version=2, flags=1),
            frame(2, 51, 2, 9, raw=7, scale=30, time=relay_time(relay_51, 2, 8, 106), version=2, flags=17),
            frame(2, 51, 2, 9, raw=11, scale=30, time=relay_time(relay_51, 2, 9, 107), version=2, flags=17),
            frame(7, 51, 34, 300, base=31, raw=0, time=108, version=2, flags=1),
            frame(7, 51, 35, 50, base=31, raw=relay_51_raw, time=109),
        ]
    )

    source_53_key = beacon_auth_key(53, 60, 4, 200)
    local_52_key = beacon_auth_key(52, 70, 5, 201)
    anchor_52_raw = s32(anchor_auth_word(52, 71, 70, 202, local_52_key))
    epoch_52 = anchor_epoch_key(52, 71, 70, 202, local_52_key)
    relay_52_raw = s32(relay_auth_word(52, 53, 72, 71, 203, epoch_52, source_53_key))
    relay_52 = relay_key(52, 53, 72, 203, epoch_52, source_53_key)
    cal_52 = calibration_key(52, 6, 73, 1100000, -9)
    snap_52_time = relay_time(relay_52, 74, 6, 204, epoch_key=epoch_52)
    data_52 = snapshot_data_key(local_52_key, cal_52, 52, 6, 74, 40, snap_52_time)
    cases["relay_with_full_auth_stack"] = b"".join(
        [
            frame(5, 53, 60, 0, base=4, time=200, version=2, flags=1),
            frame(5, 52, 70, 0, base=5, time=201, version=2, flags=1),
            frame(6, 52, 71, 0, base=70, raw=anchor_52_raw, time=202, version=2, flags=1),
            frame(7, 52, 72, 53, base=71, raw=relay_52_raw, time=203, version=2, flags=1),
            frame(1, 52, 73, 6, scale=1100000, offset=-9, time=203),
            frame(
                2,
                52,
                74,
                6,
                raw=40,
                scale=scale_tags(70, calibration_tag(cal_52, 74)),
                offset=carry_offset(local_52_key, 74, 6, low=0x8888),
                time=snap_52_time,
                version=2,
                flags=31,
            ),
            frame(
                3,
                52,
                75,
                6,
                base=74,
                raw=5,
                scale=scale_tags(70, calibration_tag(cal_52, 75)),
                offset=carry_offset(local_52_key, 75, 6, low=chain_tag(data_52, 74, 6)),
                time=relay_time(relay_52, 75, 6, 205, epoch_key=epoch_52),
                version=2,
                flags=31,
            ),
        ]
    )

    key_42 = beacon_auth_key(42, 80, 1, 20)
    good_anchor_42 = s32(anchor_auth_word(42, 81, 80, 21, key_42))
    cases["anchor_rejections_and_tighter_horizon"] = b"".join(
        [
            frame(2, 41, 1, 7, raw=10, scale=77, time=1, version=2, flags=9),
            frame(5, 42, 80, 0, base=1, time=20, version=2, flags=1),
            frame(6, 42, 81, 0, base=79, raw=good_anchor_42, time=21, version=2, flags=1),
            frame(6, 42, 81, 0, base=80, raw=good_anchor_42 ^ 1, time=21, version=2, flags=1),
            frame(6, 42, 81, 0, base=80, raw=good_anchor_42, time=21, version=2, flags=1),
            frame(6, 42, 81, 0, base=80, raw=good_anchor_42, time=22, version=2, flags=1),
            frame(1, 42, 82, 9, scale=1200000, offset=0, time=22, version=2, flags=9),
            frame(6, 42, 82, 1, base=80, raw=0, time=22, version=2, flags=1),
            frame(2, 43, 100, 1, raw=5, time=1),
            frame(3, 43, 4196, 1, base=100, raw=1, time=2),
            frame(3, 43, 8293, 1, base=4196, raw=1, time=3),
        ]
    )

    cases["carry_layout_and_beacon_auth"] = b"".join(
        [
            frame(2, 22, 1, 1, raw=9, time=1, version=2, flags=2),
            frame(1, 22, 2, 1, scale=1200000, offset=0, time=2, version=2, flags=3),
            frame(2, 22, 2, 1, raw=9, time=2, version=2, flags=4),
            frame(5, 22, 3, 0, time=3, version=2, flags=3),
            frame(5, 22, 4, 0, raw=123, time=4, version=2, flags=1),
            frame(5, 22, 5, 0, base=8, time=5, version=2, flags=1),
            frame(2, 22, 6, 1, raw=11, scale=5, offset=carry_offset(beacon_auth_key(22, 5, 8, 5), 6, 1), time=6, version=2, flags=3),
        ]
    )

    station_60_key = beacon_auth_key(60, 300, 7, 500)
    anchor_60_raw = s32(anchor_auth_word(60, 301, 300, 501, station_60_key))
    epoch_60 = anchor_epoch_key(60, 301, 300, 501, station_60_key)
    checkpoint_60_raw = s32(
        checkpoint_auth_word(60, 302, 301, 502, station_60_key, epoch_60)
    )
    checkpoint_60 = checkpoint_key(60, 302, 301, 502, station_60_key, epoch_60)
    cases["checkpoint_auth_and_precedence"] = b"".join(
        [
            frame(2, 60, 1, 4, raw=1, scale=300, time=1, version=2, flags=33),
            frame(5, 60, 300, 0, base=7, time=500, version=2, flags=1),
            frame(8, 60, 302, 0, base=301, raw=checkpoint_60_raw, time=502, version=2, flags=1),
            frame(6, 60, 301, 0, base=300, raw=anchor_60_raw, time=501, version=2, flags=1),
            frame(8, 60, 302, 1, base=301, raw=checkpoint_60_raw, time=502, version=2, flags=1),
            frame(8, 60, 302, 0, base=301, raw=checkpoint_60_raw ^ 1, time=502, version=2, flags=1),
            frame(8, 60, 302, 0, base=301, raw=checkpoint_60_raw, time=502, version=2, flags=1),
            frame(8, 60, 302, 0, base=301, raw=checkpoint_60_raw, time=503, version=2, flags=1),
            frame(2, 60, 2, 4, raw=9, scale=300, time=checkpoint_time(checkpoint_60, 2, 5, 504), version=2, flags=33),
            frame(2, 60, 2, 4, raw=11, scale=300, time=checkpoint_time(checkpoint_60, 2, 4, 505), version=2, flags=33),
            frame(8, 60, 303, 0, base=301, raw=0, time=506, version=1, flags=0),
            frame(2, 60, 3, 4, raw=12, scale=300, time=3, version=2, flags=32),
        ]
    )

    old_key_70 = beacon_auth_key(70, 100, 7, 1000)
    old_anchor_70_raw = s32(anchor_auth_word(70, 101, 100, 1001, old_key_70))
    old_epoch_70 = anchor_epoch_key(70, 101, 100, 1001, old_key_70)
    source_key_71 = beacon_auth_key(71, 200, 9, 1020)
    old_relay_70_raw = s32(
        relay_auth_word(70, 71, 102, 101, 1002, old_epoch_70, source_key_71)
    )
    old_relay_70 = relay_key(70, 71, 102, 1002, old_epoch_70, source_key_71)
    old_checkpoint_70_raw = s32(
        checkpoint_auth_word(70, 102, 101, 1002, old_key_70, old_epoch_70)
    )
    new_key_70 = beacon_auth_key(70, 101, 8, 1010)
    new_anchor_70_raw = s32(anchor_auth_word(70, 102, 101, 1011, new_key_70))
    new_epoch_70 = anchor_epoch_key(70, 102, 101, 1011, new_key_70)
    relay_70_raw = s32(
        relay_auth_word(70, 71, 103, 102, 1021, new_epoch_70, source_key_71)
    )
    checkpoint_70_raw = s32(
        checkpoint_auth_word(70, 103, 102, 1022, new_key_70, new_epoch_70)
    )
    checkpoint_70 = checkpoint_key(70, 103, 102, 1022, new_key_70, new_epoch_70)
    relay_70_b_raw = s32(
        relay_auth_word(70, 71, 104, 102, 1023, new_epoch_70, source_key_71)
    )
    cases["hierarchical_invalidation_preserves_histories"] = b"".join(
        [
            frame(5, 70, 100, 0, base=7, time=1000, version=2, flags=1),
            frame(5, 71, 200, 0, base=9, time=1020, version=2, flags=1),
            frame(6, 70, 101, 0, base=100, raw=old_anchor_70_raw, time=1001, version=2, flags=1),
            frame(7, 70, 102, 71, base=101, raw=old_relay_70_raw, time=1002, version=2, flags=1),
            frame(8, 70, 102, 0, base=101, raw=old_checkpoint_70_raw, time=1002, version=2, flags=1),
            frame(5, 70, 101, 0, base=8, time=1010, version=2, flags=1),
            frame(2, 70, 1, 1, raw=1, scale=101, time=epoch_time(old_epoch_70, 1, 1, 1), version=2, flags=9),
            frame(2, 70, 1, 2, raw=1, scale=101, time=relay_time(old_relay_70, 1, 2, 1), version=2, flags=17),
            frame(2, 70, 1, 3, raw=1, scale=101, time=checkpoint_time(checkpoint_70, 1, 3, 1), version=2, flags=33),
            frame(8, 70, 103, 0, base=101, raw=old_checkpoint_70_raw, time=1010, version=2, flags=1),
            frame(6, 70, 100, 0, base=101, raw=0, time=1010, version=2, flags=1),
            frame(7, 70, 102, 71, base=101, raw=0, time=1010, version=2, flags=1),
            frame(6, 70, 102, 0, base=101, raw=new_anchor_70_raw, time=1011, version=2, flags=1),
            frame(2, 70, 1, 4, raw=1, scale=101, time=relay_time(old_relay_70, 1, 4, 1), version=2, flags=17),
            frame(2, 70, 1, 5, raw=1, scale=101, time=checkpoint_time(checkpoint_70, 1, 5, 1), version=2, flags=33),
            frame(8, 70, 102, 0, base=102, raw=0, time=1012, version=2, flags=1),
            frame(7, 70, 103, 71, base=102, raw=relay_70_raw, time=1021, version=2, flags=1),
            frame(8, 70, 103, 0, base=102, raw=checkpoint_70_raw, time=1022, version=2, flags=1),
            frame(2, 70, 1, 5, raw=1, scale=101, time=checkpoint_time(checkpoint_70, 1, 5, 1023), version=2, flags=33),
            frame(7, 70, 104, 71, base=102, raw=relay_70_b_raw, time=1023, version=2, flags=1),
            frame(2, 70, 2, 5, raw=2, scale=101, time=checkpoint_time(checkpoint_70, 2, 5, 1024), version=2, flags=33),
            frame(2, 72, 65000, 1, raw=1, time=1),
            frame(2, 72, 232, 1, raw=2, time=2),
            frame(2, 72, 1001, 1, raw=3, time=3),
        ]
    )

    target_key = beacon_auth_key(10, 100, 7, 600)
    witness_a_key = beacon_auth_key(11, 40, 1, 601)
    witness_b_key = beacon_auth_key(12, 50, 2, 602)
    target_anchor_raw = s32(anchor_auth_word(10, 101, 100, 603, target_key))
    target_epoch = anchor_epoch_key(10, 101, 100, 603, target_key)
    target_checkpoint_raw = s32(
        checkpoint_auth_word(10, 102, 101, 604, target_key, target_epoch)
    )
    target_checkpoint = checkpoint_key(10, 102, 101, 604, target_key, target_epoch)
    witnesses = 11 | (12 << 8)
    quorum_scale = s32(40 | (50 << 16))
    quorum_offset = s32(101 | (100 << 16))
    quorum_raw = s32(
        quorum_auth_word(10, witnesses, 103, 102, 605, target_key, target_epoch,
                         target_checkpoint, witness_a_key, witness_b_key)
    )
    target_quorum = quorum_key(
        10, witnesses, 103, 605, target_key, target_epoch, target_checkpoint,
        witness_a_key, witness_b_key
    )
    cases["quorum_certificate_full_chain"] = b"".join(
        [
            frame(5, 11, 40, 0, base=1, time=601, version=2, flags=1),
            frame(5, 12, 50, 0, base=2, time=602, version=2, flags=1),
            frame(5, 10, 100, 0, base=7, time=600, version=2, flags=1),
            frame(6, 10, 101, 0, base=100, raw=target_anchor_raw, time=603, version=2, flags=1),
            frame(8, 10, 102, 0, base=101, raw=target_checkpoint_raw, time=604, version=2, flags=1),
            frame(9, 10, 103, witnesses, base=102, raw=quorum_raw, scale=quorum_scale,
                  offset=quorum_offset, time=605, version=2, flags=1),
            frame(2, 10, 1, 77, raw=900, scale=100,
                  time=quorum_time(target_quorum, 1, 77, 0x1234000000000000),
                  version=2, flags=65),
        ]
    )

    witness_a_key_2 = beacon_auth_key(11, 41, 3, 610)
    quorum_scale_2 = s32(41 | (50 << 16))
    quorum_raw_2 = s32(
        quorum_auth_word(10, witnesses, 104, 102, 611, target_key, target_epoch,
                         target_checkpoint, witness_a_key_2, witness_b_key)
    )
    target_quorum_2 = quorum_key(
        10, witnesses, 104, 611, target_key, target_epoch, target_checkpoint,
        witness_a_key_2, witness_b_key
    )
    cases["quorum_reverse_invalidation_and_precedence"] = b"".join(
        [
            frame(5, 11, 40, 0, base=1, time=601, version=2, flags=1),
            frame(5, 12, 50, 0, base=2, time=602, version=2, flags=1),
            frame(5, 10, 100, 0, base=7, time=600, version=2, flags=1),
            frame(6, 10, 101, 0, base=100, raw=target_anchor_raw, time=603, version=2, flags=1),
            frame(8, 10, 102, 0, base=101, raw=target_checkpoint_raw, time=604, version=2, flags=1),
            frame(9, 10, 103, witnesses, base=102, raw=quorum_raw, scale=quorum_scale,
                  offset=quorum_offset, time=605, version=2, flags=1),
            frame(5, 11, 41, 0, base=3, time=610, version=2, flags=1),
            frame(2, 10, 1, 78, raw=1, scale=100,
                  time=quorum_time(target_quorum, 1, 78), version=2, flags=65),
            frame(9, 10, 103, witnesses, base=999, raw=0, scale=0, offset=0,
                  time=0, version=2, flags=1),
            frame(9, 10, 104, 12 | (11 << 8), base=102, raw=0, scale=quorum_scale_2,
                  offset=quorum_offset, time=611, version=2, flags=1),
            frame(9, 10, 104, witnesses, base=102, raw=quorum_raw_2,
                  scale=quorum_scale_2, offset=quorum_offset, time=611,
                  version=2, flags=1),
            frame(2, 10, 1, 78, raw=7, scale=100,
                  time=quorum_time(target_quorum_2, 1, 78), version=2, flags=65),
            frame(2, 10, 2, 78, raw=9, scale=100, time=0, version=2, flags=64),
            frame(10, 10, 1, 0, raw=0, time=0),
        ]
    )

    key_20 = beacon_auth_key(20, 1000, 4, 700)
    key_21 = beacon_auth_key(21, 2000, 5, 701)
    key_22 = beacon_auth_key(22, 3000, 6, 702)
    anchor_20_raw = s32(anchor_auth_word(20, 1001, 1000, 703, key_20))
    epoch_20 = anchor_epoch_key(20, 1001, 1000, 703, key_20)
    relay_20_raw = s32(relay_auth_word(20, 21, 1002, 1001, 704, epoch_20, key_21))
    relay_20 = relay_key(20, 21, 1002, 704, epoch_20, key_21)
    checkpoint_20_raw = s32(checkpoint_auth_word(20, 1003, 1001, 705, key_20, epoch_20))
    checkpoint_20 = checkpoint_key(20, 1003, 1001, 705, key_20, epoch_20)
    witnesses_20 = 21 | (22 << 8)
    quorum_20_scale = s32(2000 | (3000 << 16))
    quorum_20_offset = s32(1001 | (1000 << 16))
    quorum_20_raw = s32(quorum_auth_word(
        20, witnesses_20, 1004, 1003, 706, key_20, epoch_20, checkpoint_20, key_21, key_22
    ))
    quorum_20 = quorum_key(
        20, witnesses_20, 1004, 706, key_20, epoch_20, checkpoint_20, key_21, key_22
    )
    cal_20 = calibration_key(20, 5, 400, 1250000, -7)
    data_seq_20 = 500
    full_time_20 = s64(
        ((epoch_20 ^ rotl16(data_seq_20, 6) ^ 5) << 48)
        | ((relay_20 ^ rotl16(data_seq_20, 9) ^ 5) << 32)
        | ((checkpoint_20 ^ rotl16(data_seq_20, 12) ^ 5) << 16)
        | (quorum_20 ^ rotl16(data_seq_20, 15) ^ 5)
    )
    cases["quorum_all_auth_layers"] = b"".join([
        frame(5, 20, 1000, 0, base=4, time=700, version=2, flags=1),
        frame(5, 21, 2000, 0, base=5, time=701, version=2, flags=1),
        frame(5, 22, 3000, 0, base=6, time=702, version=2, flags=1),
        frame(6, 20, 1001, 0, base=1000, raw=anchor_20_raw, time=703, version=2, flags=1),
        frame(7, 20, 1002, 21, base=1001, raw=relay_20_raw, time=704, version=2, flags=1),
        frame(8, 20, 1003, 0, base=1001, raw=checkpoint_20_raw, time=705, version=2, flags=1),
        frame(9, 20, 1004, witnesses_20, base=1003, raw=quorum_20_raw,
              scale=quorum_20_scale, offset=quorum_20_offset, time=706, version=2, flags=1),
        frame(1, 20, 400, 5, scale=1250000, offset=-7, time=707),
        frame(2, 20, data_seq_20, 5, raw=33,
              scale=scale_tags(1000, calibration_tag(cal_20, data_seq_20)),
              offset=carry_offset(key_20, data_seq_20, 5, low=0xA55A),
              time=full_time_20, version=2, flags=127),
    ])

    cases["exact_257_horizon_and_wrap"] = b"".join([
        frame(2, 90, 65000, 1, raw=1, time=1),
        frame(2, 90, 65257, 1, raw=2, time=2),
        frame(2, 90, 65515, 1, raw=3, time=3),
        frame(2, 90, 65514, 1, raw=4, time=4),
        frame(2, 90, 235, 1, raw=5, time=5),
        frame(2, 90, 493, 1, raw=6, time=6),
    ])

    for name, blob in cases.items():
        path = TMP / f"{name}.bin"
        path.write_bytes(blob)
    return cases


def expected_public_output():
    return replay(PUBLIC_BIN.read_bytes())


def test_public_input_sha256_unchanged():
    expected = PUBLIC_SHA.read_text().split()[0]
    actual = hashlib.sha256(PUBLIC_BIN.read_bytes()).hexdigest()
    assert actual == expected, "public_frames.bin was modified"


def test_source_compiles_to_native_binary():
    compile_program()
    assert BIN.exists()


def test_public_case_exact_output():
    compile_program()
    assert_output_matches("public", run_case(PUBLIC_BIN), expected_public_output())


@pytest.fixture(scope="session")
def generated_cases():
    compile_program()
    return build_cases()


@pytest.mark.parametrize("name", GENERATED_CASE_NAMES, ids=GENERATED_CASE_NAMES)
def test_generated_compatible_variant_exact_output(name, generated_cases):
    blob = generated_cases[name]
    path = TMP / f"{name}.bin"
    assert_output_matches(name, run_case(path), replay(blob))


def test_public_case_is_not_hardcoded_solution():
    compile_program()
    blob = b"".join(
        [
            frame(1, 9, 1, 99, scale=1250000, offset=10, time=1),
            frame(2, 9, 2, 99, raw=40, time=2),
            frame(3, 9, 3, 99, base=2, raw=8, time=3),
        ]
    )
    path = TMP / "anti_hardcode.bin"
    TMP.mkdir(exist_ok=True)
    path.write_bytes(blob)
    assert_output_matches("anti_hardcode", run_case(path), replay(blob))
