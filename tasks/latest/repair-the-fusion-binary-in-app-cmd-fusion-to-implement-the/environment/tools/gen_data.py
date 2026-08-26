from __future__ import annotations

import json
import struct
from pathlib import Path


ROOT = Path("/app")
CAL = ROOT / "calibration"
TEL = ROOT / "telemetry"


def zz_encode(value: int) -> int:
    return (value << 1) ^ (value >> 31)


def stored_values(values: list[int], zone: int, flags: int) -> list[int]:
    if not flags & 0x02:
        return list(values)
    predictor = zone - 3
    out = []
    for value in values:
        delta = value - predictor
        out.append(delta)
        predictor = value
    return out


def packed_width(width: int) -> int:
    return width & 0x0F if width & 0xC0 else width


def pack_values(values: list[int], width: int) -> bytearray:
    bits_width = packed_width(width)
    mask = (1 << bits_width) - 1
    acc = 0
    bits = 0
    out = bytearray()
    for value in values:
        raw = zz_encode(value) if width & 0x80 else (value & mask)
        acc |= (raw & mask) << bits
        bits += bits_width
        while bits >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            bits -= 8
    if bits:
        out.append(acc & 0xFF)
    return out


def lane_order(dim: int, zone: int) -> list[int]:
    start = zone % dim
    step = dim - 1
    return [(start + k * step) % dim for k in range(dim)]


def rotation(frame_id: int, zone: int, dim: int, n: int) -> int:
    if n <= 1:
        return 0
    return (frame_id + (frame_id >> 8) + zone * 13 + dim * 5) % n


def rotate_left(data: bytearray, amount: int) -> bytearray:
    if not data:
        return data
    amount %= len(data)
    return bytearray(data[amount:] + data[:amount])


def nibble_swap(data: bytearray) -> bytearray:
    return bytearray(((b & 0x0F) << 4) | (b >> 4) for b in data)


def effective_mask(mask: int, flags: int, frame_id: int, zone: int, dim: int, seed: int) -> int:
    if not flags & 0x20:
        return mask
    return (mask ^ seed ^ ((frame_id >> 7) & 0xFF) ^ ((zone & 7) * 29) ^ dim) & 0xFF


def lane_seed(frame_id: int, zone: int, dim: int, mask: int, flags: int) -> int:
    return (frame_id ^ (frame_id >> 11) ^ (zone * 31) ^ (dim * 13) ^ mask ^ flags) & 0xFF


def encode_lane(values: list[int], frame_id: int, zone: int, flags: int, width: int, mask: int) -> tuple[bytearray, int | None]:
    dim = len(values)
    stored = stored_values(values, zone, flags)
    if flags & 0x10:
        order = lane_order(dim, zone)
        serialized = [stored[i] for i in order]
    else:
        serialized = stored
    descriptor = bytearray()
    payload_values = serialized
    if flags & 0x08:
        present = [idx for idx in (lane_order(dim, zone) if flags & 0x10 else range(dim)) if stored[idx] != 0]
        payload_values = [stored[idx] for idx in present]
        if flags & 0x80:
            descriptor.append(len(present))
            descriptor.extend(present)
        else:
            bitmap = bytearray((dim + 7) // 8)
            for idx in present:
                bitmap[idx // 8] |= 1 << (idx & 7)
            descriptor.extend(bitmap)
    if flags & 0x04:
        payload = pack_values(payload_values, width)
        if width & 0x40:
            payload = nibble_swap(payload)
    else:
        payload = bytearray((v & 0xFF) for v in payload_values)
    if flags & 0x40:
        payload = rotate_left(payload, rotation(frame_id, zone, dim, len(payload)))
    lane = descriptor + payload
    seed = lane_seed(frame_id, zone, dim, mask, flags) if flags & 0x20 else None
    lane_mask = effective_mask(mask, flags, frame_id, zone, dim, seed or 0)
    if flags & 0x01:
        lane = bytearray(b ^ lane_mask for b in lane)
    return lane, seed


def write_cfr(path: Path, rows: list[tuple], flags: int, width: int, mask: int, mix: int) -> None:
    dim = len(rows[0][3])
    data = bytearray(b"ALT1")
    data.extend([1, dim, flags, width])
    data.extend(struct.pack("<H", len(rows)))
    data.append(mask)
    data.append((dim * 19 + len(rows) + mask + flags + width) & 0xFF)
    prev_minute = 0
    for row in rows:
        frame_id, zone, minute, values = row[:4]
        quality = row[4] if len(row) > 4 else 0
        if width & 0x20 and quality >> dim:
            raise ValueError("quality mask references sensors outside dimension")
        rec = bytearray(struct.pack("<IBH", frame_id, zone, zz_encode(minute - prev_minute) & 0xFFFF))
        prev_minute = minute
        lane, seed = encode_lane(values, frame_id, zone, flags, width, mask)
        if seed is not None:
            rec.append(seed)
        rec.extend(lane)
        if width & 0x20:
            rec.append(quality)
        rec.append((sum(rec) + mask) & 0xFF)
        data.extend(rec)
    footer = bytearray(b"AL")
    footer.extend(struct.pack("<H", mix))
    footer.append((sum(footer) + mask + len(rows)) & 0xFF)
    data.extend(footer)
    path.write_bytes(data)


def main() -> None:
    CAL.mkdir(parents=True, exist_ok=True)
    TEL.mkdir(parents=True, exist_ok=True)
    manifests = {
        "north.json": {
            "name": "aurora-north",
            "probe_rank": 14,
            "probe_drift": -5,
            "probe_anchor": 0x1A2B5C4D,
            "labels": ["ok", "watch", "alarm"],
            "scale_den": 100,
            "scale_num": [8, 7, 9, 6, 5, 10],
            "zero": [2, -1, 3, 0, -2, 1],
            "clip_min": [-30, -30, -30, -30, -30, -30],
            "clip_max": [35, 35, 35, 35, 35, 35],
            "sensor_order": [2, 0, 5, 1, 4, 3],
            "zone_shift": [0, 1, 2, 3, 1, 4, 2, 5],
            "bias_milli": [20, -15, -40],
            "weights_milli": [[-2, -1, 1, 2, 1, 0], [1, 2, -1, 0, 2, 1], [3, -2, 2, -1, 1, 3]],
            "zone_bias_milli": [[0, 2, -1], [1, -1, 3], [2, 1, 0], [-1, 3, 2], [0, 0, 2], [2, -2, 1], [1, 1, -1], [-2, 2, 3]],
            "load_bias_milli": [[1, -1, 2], [0, 2, -1], [2, 1, 0], [-1, 1, 2], [1, 0, -2], [2, -1, 1], [0, 1, 1], [-2, 2, 0]],
            "anchor_bias_milli": [2, -1, 3],
            "shard_bias_milli": [[0, 1, -1], [2, -1, 1], [1, 0, 2], [-1, 2, 0], [2, 1, -2], [0, -2, 1], [1, 2, 1], [-2, 0, 2]],
            "quality_bias_milli": [-3, 4, 7],
            "quality_weights_milli": [[-1, 0, 2, -2, 1, 3], [2, -1, 1, 0, 3, -2], [4, 1, -2, 3, -1, 2]],
            "drift_bias_milli": [1, -2, 3],
            "mix_bias_milli": [2, -1, 1],
            "median_milli": [[1, 0, 1, 0, -1, 1], [0, 2, -1, 1, 1, 0], [2, -1, 1, 1, 0, -2]],
            "pair_terms": [[[0, 2, 1], [3, 5, -1]], [[1, 4, 2]], [[0, 5, 2], [2, 3, -1]]],
        },
        "east.json": {
            "name": "aurora-east",
            "probe_rank": 6,
            "probe_drift": 3,
            "probe_anchor": 0x0BADC0DE,
            "labels": ["ok", "watch", "alarm"],
            "scale_den": 100,
            "scale_num": [7, 8, 5, 9, 6, 10],
            "zero": [0, 1, -2, 2, -1, 3],
            "clip_min": [-28, -28, -28, -28, -28, -28],
            "clip_max": [32, 32, 32, 32, 32, 32],
            "sensor_order": [1, 3, 0, 5, 2, 4],
            "zone_shift": [1, 0, 3, 2, 4, 1, 5, 2],
            "bias_milli": [-10, 15, -25],
            "weights_milli": [[-1, 1, 2, -1, 0, 2], [2, 1, -2, 1, 3, -1], [1, -3, 2, 3, -1, 2]],
            "zone_bias_milli": [[1, 0, 2], [0, 2, -1], [3, -1, 1], [1, 2, 0], [-1, 1, 2], [2, 0, 1], [0, -2, 3], [1, 3, -1]],
            "load_bias_milli": [[0, 1, -1], [2, -1, 1], [1, 1, 0], [-2, 2, 1], [1, 0, 2], [0, -2, 1], [2, 1, -1], [1, -1, 2]],
            "anchor_bias_milli": [-1, 2, 1],
            "shard_bias_milli": [[1, 0, 2], [0, 2, -1], [2, -1, 1], [1, 1, 0], [-1, 2, 1], [2, 0, -2], [0, -1, 2], [1, 2, -1]],
            "quality_bias_milli": [2, -4, 5],
            "quality_weights_milli": [[1, -2, 0, 3, -1, 2], [-3, 1, 2, -1, 4, 0], [2, 3, -2, 1, 0, -1]],
            "drift_bias_milli": [-1, 1, 2],
            "mix_bias_milli": [1, 2, -1],
            "median_milli": [[0, 1, -1, 2, 0, 1], [1, -1, 2, 0, 1, -2], [2, 0, 1, -1, 2, 1]],
            "pair_terms": [[[0, 1, 1]], [[2, 5, -1], [3, 4, 1]], [[1, 5, 2]]],
        },
        "west.json": {
            "name": "aurora-west",
            "probe_rank": 19,
            "probe_drift": 2,
            "probe_anchor": 0x11224455,
            "labels": ["ok", "watch", "alarm"],
            "scale_den": 100,
            "scale_num": [6, 8, 7, 9, 5, 10],
            "zero": [1, 0, 2, -1, 3, -2],
            "clip_min": [-35, -35, -35, -35, -35, -35],
            "clip_max": [36, 36, 36, 36, 36, 36],
            "sensor_order": [0, 2, 4, 1, 3, 5],
            "zone_shift": [0, 2, 1, 4, 3, 5, 2, 1],
            "bias_milli": [5, -5, 10],
            "weights_milli": [[1, -1, 0, 2, -2, 1], [2, 2, -1, 1, 1, 0], [-2, 1, 3, -1, 2, 2]],
            "zone_bias_milli": [[0, 1, 2], [1, 0, 1], [2, -1, 0], [0, 2, -1], [1, 1, 1], [-1, 2, 0], [2, 0, -2], [1, -1, 2]],
            "load_bias_milli": [[1, 0, 1], [-1, 2, 0], [2, -1, 1], [0, 1, 2], [1, -2, 1], [2, 0, -1], [-1, 1, 2], [0, 2, -2]],
            "anchor_bias_milli": [1, 1, -2],
            "shard_bias_milli": [[2, -1, 0], [1, 1, 2], [0, 2, -1], [-2, 1, 1], [1, 0, -2], [2, -2, 0], [0, 1, 2], [-1, 2, 1]],
            "quality_bias_milli": [1, -3, 4],
            "quality_weights_milli": [[0, 2, -1, 1, -2, 3], [2, 0, 1, -3, 2, -1], [-1, 3, 2, 0, 1, -2]],
            "drift_bias_milli": [2, -1, 1],
            "mix_bias_milli": [-1, 1, 2],
            "median_milli": [[1, 1, 0, -1, 2, 0], [0, 2, 1, 1, -1, 2], [2, -1, 2, 0, 1, -1]],
            "pair_terms": [[[1, 3, 1]], [[0, 4, 1]], [[2, 5, -2]]],
        },
    }
    for manifest_index, manifest in enumerate(manifests.values()):
        classes = len(manifest["labels"])
        features = len(manifest["scale_num"])
        manifest["time_bias_milli"] = [
            [((phase + 1) * (klass + 2) + manifest_index * 3) % 11 - 5 for klass in range(classes)]
            for phase in range(16)
        ]
        manifest["span_bias_milli"] = [
            [((bucket + 2) * (klass + 1) + manifest_index) % 9 - 4 for klass in range(classes)]
            for bucket in range(8)
        ]
        manifest["trend_weights_milli"] = [
            [((klass + 1) * (feature + 3) + manifest_index * 2) % 7 - 3 for feature in range(features)]
            for klass in range(classes)
        ]
    for name, manifest in manifests.items():
        (CAL / name).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    rows = [
        (0x10000004, 2, 8, [14, -5, 9, 21, -8, 5], 0b001001),
        (0x10000001, 5, 15, [-7, 13, -2, 8, 19, -11], 0b010000),
        (0x10000009, 1, 19, [22, -10, 7, -5, 13, 2], 0b000010),
        (0x10000002, 6, 26, [-15, 9, 20, -4, 6, -13], 0b100100),
        (0x1000000D, 3, 31, [7, -19, 10, 15, -8, 21], 0b000000),
    ]
    write_cfr(TEL / "public.cfr", rows, flags=0x01 | 0x02 | 0x04 | 0x10 | 0x20 | 0x40, width=0xA4, mask=0x5A, mix=0x2D91)


if __name__ == "__main__":
    main()
