from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
from pathlib import Path


def app_dir() -> Path:
    return Path("/app") if Path("/app").exists() else Path(__file__).parent.parent / "environment"


APP = app_dir()
BIN = Path("/tmp/auroral-lattice-assembler-test")
PROTECTED_INPUTS = {
    APP / "calibration" / "east.json": "4eaff9996e1f07f1d81ef3bfd6985ddd5d25f11c76d7b9a55b31f0d6669a9357",
    APP / "calibration" / "north.json": "6f66d31c2e1b1b8087ceab85ab4ee771d57044b3f547676483f382b20f1cd0d1",
    APP / "calibration" / "west.json": "f8cc8686a546d33c733d40bf2ea1b4df5d487651fb2d76067dfd6ceac8bcfe2f",
    APP / "telemetry" / "public.cfr": "22d5310c8fc36287d94c612735d66bb9f907b6d93e39c8b92692f9dc50aaeba7",
    APP / "probe" / "driftprobe": "0111a51be83c50b75458b4cf7529f34e0090fbd9d0893b84178f3bc8a39afe02",
}


def assert_protected_inputs_clean() -> None:
    if not (APP / "telemetry" / "public.cfr").exists():
        return
    for path, expected_hash in PROTECTED_INPUTS.items():
        assert path.exists(), f"protected input missing: {path}"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash, f"protected input modified: {path}"


def snapshot_path(path: Path) -> tuple[Path, dict[str, str]]:
    if path.is_file():
        return path, {".": hashlib.sha256(path.read_bytes()).hexdigest()}
    assert path.is_dir(), f"snapshot target missing: {path}"
    hashes = {}
    for item in sorted(p for p in path.rglob("*") if p.is_file()):
        hashes[str(item.relative_to(path))] = hashlib.sha256(item.read_bytes()).hexdigest()
    return path, hashes


def assert_snapshots_clean(*snapshots: tuple[Path, dict[str, str]]) -> None:
    for path, expected in snapshots:
        assert snapshot_path(path)[1] == expected, f"fixture modified: {path}"


def build_tool() -> Path:
    env = os.environ.copy()
    env["PWD"] = str(APP)
    subprocess.run(["go", "build", "-buildvcs=false", "-o", str(BIN), "./cmd/fusion"], cwd=APP, env=env, check=True)
    return BIN


def zz_encode(value: int) -> int:
    return (value << 1) ^ (value >> 31)


def zz_decode(value: int) -> int:
    return (value >> 1) ^ -(value & 1)


def packed_width(width: int) -> int:
    return width & 0x0F if width & 0xC0 else width & ~0x20


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


def rotate_right(data: bytearray, amount: int) -> bytearray:
    if not data:
        return data
    amount %= len(data)
    return bytearray(data[-amount:] + data[:-amount]) if amount else bytearray(data)


def nibble_swap(data: bytearray) -> bytearray:
    return bytearray(((b & 0x0F) << 4) | (b >> 4) for b in data)


def lane_seed(frame_id: int, zone: int, dim: int, mask: int, flags: int) -> int:
    return (frame_id ^ (frame_id >> 11) ^ (zone * 31) ^ (dim * 13) ^ mask ^ flags) & 0xFF


def effective_mask(mask: int, flags: int, frame_id: int, zone: int, dim: int, seed: int) -> int:
    if not flags & 0x20:
        return mask
    return (mask ^ seed ^ ((frame_id >> 7) & 0xFF) ^ ((zone & 7) * 29) ^ dim) & 0xFF


def stored_values(values: list[int], zone: int, flags: int) -> list[int]:
    if not flags & 0x02:
        return list(values)
    predictor = zone - 3
    out: list[int] = []
    for value in values:
        delta = value - predictor
        assert -64 <= delta <= 63
        out.append(delta)
        predictor = value
    return out


def pack_values(values: list[int], width: int) -> bytearray:
    bit_width = packed_width(width)
    mask = (1 << bit_width) - 1
    acc = 0
    bits = 0
    out = bytearray()
    for value in values:
        raw = zz_encode(value) if width & 0x80 else value & mask
        assert 0 <= raw <= mask
        acc |= (raw & mask) << bits
        bits += bit_width
        while bits >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            bits -= 8
    if bits:
        out.append(acc & 0xFF)
    return out


def unpack_values(payload: bytes | bytearray, count: int, width: int) -> list[int]:
    bit_width = packed_width(width)
    mask = (1 << bit_width) - 1
    sign = 1 << (bit_width - 1)
    acc = 0
    bits = 0
    pos = 0
    out = []
    for _ in range(count):
        while bits < bit_width:
            assert pos < len(payload)
            acc |= payload[pos] << bits
            bits += 8
            pos += 1
        raw = acc & mask
        acc >>= bit_width
        bits -= bit_width
        if width & 0x80:
            out.append(zz_decode(raw))
        elif raw & sign:
            out.append(raw - (1 << bit_width))
        else:
            out.append(raw)
    return out


def encode_lane(values: list[int], frame_id: int, zone: int, flags: int, width: int, mask: int) -> tuple[bytearray, int | None]:
    dim = len(values)
    stored = stored_values(values, zone, flags)
    serialized = [stored[i] for i in lane_order(dim, zone)] if flags & 0x10 else stored
    descriptor = bytearray()
    payload_values = serialized
    if flags & 0x08:
        order = lane_order(dim, zone) if flags & 0x10 else list(range(dim))
        present = [idx for idx in order if stored[idx] != 0]
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
        payload = bytearray(v & 0xFF for v in payload_values)
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
    previous_minute = 0
    for row in rows:
        frame_id, zone, minute, values = row[:4]
        quality = row[4] if len(row) > 4 else 0
        assert not (width & 0x20 and quality >> dim)
        rec = bytearray(struct.pack("<IBH", frame_id, zone, zz_encode(minute - previous_minute) & 0xFFFF))
        previous_minute = minute
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


def write_cfs2(path: Path, segments: list[dict], container_mask: int, mix: int) -> None:
    total = sum(len(segment["rows"]) for segment in segments)
    data = bytearray(b"ALS2")
    data.extend([2, len(segments)])
    data.extend(struct.pack("<H", total))
    data.append(container_mask)
    data.append((len(segments) * 37 + total + container_mask) & 0xFF)
    minute = 0
    for seg_index, segment in enumerate(segments):
        rows = segment["rows"]
        flags = segment["flags"]
        width = segment["width"]
        mask = segment["mask"]
        dim = len(rows[0][3])
        data.extend([flags, width, dim, mask])
        data.extend(struct.pack("<H", len(rows)))
        data.append((dim * 19 + len(rows) + mask + flags + width + seg_index) & 0xFF)
        for row in rows:
            frame_id, zone, frame_minute, values = row[:4]
            quality = row[4] if len(row) > 4 else 0
            assert not (width & 0x20 and quality >> dim)
            rec = bytearray(struct.pack("<IBH", frame_id, zone, zz_encode(frame_minute - minute) & 0xFFFF))
            minute = frame_minute
            lane, seed = encode_lane(values, frame_id, zone, flags, width, mask)
            if seed is not None:
                rec.append(seed)
            rec.extend(lane)
            if width & 0x20:
                rec.append(quality)
            rec.append((sum(rec) + mask) & 0xFF)
            data.extend(rec)
    footer = bytearray(b"AS")
    footer.extend(struct.pack("<H", mix))
    footer.append((sum(footer) + container_mask + len(segments) + total) & 0xFF)
    data.extend(footer)
    path.write_bytes(data)


def corrupt_alt1_width(path: Path, new_width: int) -> None:
    data = bytearray(path.read_bytes())
    assert data[:4] == b"ALT1"
    data[4 + 3] = new_width & 0xFF
    path.write_bytes(data)


def corrupt_als2_header(path: Path, *, segment_count: int | None = None, total_count: int | None = None) -> None:
    data = bytearray(path.read_bytes())
    assert data[:4] == b"ALS2"
    base = data.index(b"ALS2")
    if segment_count is not None:
        data[base + 5] = segment_count & 0xFF
    if total_count is not None:
        data[base + 6 : base + 8] = struct.pack("<H", total_count & 0xFFFF)
    path.write_bytes(data)


def corrupt_alt1_explicit_sparse_present_count(path: Path, present: int = 200) -> None:
    data = bytearray(path.read_bytes())
    assert data[:4] == b"ALT1"
    dim = data[5]
    flags = data[6]
    width = data[7]
    assert flags & 0x08
    assert flags & 0x80
    count = struct.unpack_from("<H", data, 8)[0]
    assert count > 0
    mask = data[10]
    pos = 12
    for i in range(count):
        frame_id = struct.unpack_from("<I", data, pos)[0]
        zone = data[pos + 4]
        seed_len = 1 if flags & 0x20 else 0
        seed = data[pos + 7] if seed_len else 0
        lane_start = pos + 7 + seed_len
        lane_mask = effective_mask(mask, flags, frame_id, zone, dim, seed)
        if flags & 0x08 and i == 0:
            data[lane_start] = present & 0xFF
            break
        quality_len = 1 if width & 0x20 else 0
        lane_len = compute_lane_len(data, lane_start, dim, flags, width, lane_mask)
        pos += 4 + 1 + 2 + seed_len + lane_len + quality_len + 1
    path.write_bytes(data)


def corrupt_alt1_first_checksum(path: Path) -> None:
    data = bytearray(path.read_bytes())
    assert data[:4] == b"ALT1"
    dim = data[5]
    flags = data[6]
    width = data[7]
    count = struct.unpack_from("<H", data, 8)[0]
    assert count > 0
    mask = data[10]
    pos = 12
    frame_id = struct.unpack_from("<I", data, pos)[0]
    zone = data[pos + 4]
    seed_len = 1 if flags & 0x20 else 0
    seed = data[pos + 7] if seed_len else 0
    lane_start = pos + 7 + seed_len
    lane_mask = effective_mask(mask, flags, frame_id, zone, dim, seed)
    quality_len = 1 if width & 0x20 else 0
    lane_len = compute_lane_len(data, lane_start, dim, flags, width, lane_mask)
    checksum_pos = pos + (4 + 1 + 2 + seed_len + lane_len + quality_len)
    data[checksum_pos] ^= 0xFF
    path.write_bytes(data)


def decode_frame_block(data: bytes, pos: int, count: int, dim: int, flags: int, width: int, mask: int, batch: str, mix: int, minute: int) -> tuple[list[dict], int, int]:
    out = []
    for _ in range(count):
        frame_id, zone, delta_raw = struct.unpack_from("<IBH", data, pos)
        seed_len = 1 if flags & 0x20 else 0
        seed = data[pos + 7] if seed_len else 0
        lane_mask = effective_mask(mask, flags, frame_id, zone, dim, seed)
        lane_start = pos + 7 + seed_len
        lane_len = compute_lane_len(data, lane_start, dim, flags, width, lane_mask)
        quality_len = 1 if width & 0x20 else 0
        rec = data[pos : pos + 7 + seed_len + lane_len + quality_len + 1]
        assert rec[-1] == (sum(rec[:-1]) + mask) & 0xFF
        lane = bytearray(rec[7 + seed_len : 7 + seed_len + lane_len])
        quality = rec[7 + seed_len + lane_len] if quality_len else 0
        assert quality >> dim == 0
        if flags & 0x01:
            lane = bytearray(b ^ lane_mask for b in lane)
        raw = decode_lane(lane, dim, frame_id, zone, flags, width)
        values = []
        predictor = zone - 3
        for value in raw:
            if flags & 0x02:
                predictor += value
                value = predictor
            values.append(value)
        minute += zz_decode(delta_raw)
        out.append({"id": frame_id, "zone": zone, "minute": minute, "values": values, "quality": quality, "mix": mix, "batch": batch})
        pos += len(rec)
    return out, pos, minute


def decode_file(path: Path) -> list[dict]:
    data = path.read_bytes()
    if data[:4] == b"ALT1":
        assert data[4] == 1
        dim, flags, width = data[5], data[6], data[7]
        count = struct.unpack_from("<H", data, 8)[0]
        mask = data[10]
        assert data[11] == (dim * 19 + count + mask + flags + width) & 0xFF
        footer_pos = len(data) - 5
        footer = data[footer_pos:]
        assert footer[:2] == b"AL"
        mix = struct.unpack_from("<H", footer, 2)[0]
        assert footer[4] == (sum(footer[:4]) + mask + count) & 0xFF
        rows, pos, _minute = decode_frame_block(data, 12, count, dim, flags, width, mask, path.stem, mix, 0)
        assert pos == footer_pos
        return rows
    assert data[:4] == b"ALS2" and data[4] == 2
    seg_count = data[5]
    total = struct.unpack_from("<H", data, 6)[0]
    container_mask = data[8]
    assert data[9] == (seg_count * 37 + total + container_mask) & 0xFF
    footer = data[-5:]
    assert footer[:2] == b"AS"
    mix = struct.unpack_from("<H", footer, 2)[0]
    assert footer[4] == (sum(footer[:4]) + container_mask + seg_count + total) & 0xFF
    pos = 10
    minute = 0
    rows = []
    for seg_index in range(seg_count):
        flags, width, dim, mask = data[pos], data[pos + 1], data[pos + 2], data[pos + 3]
        count = struct.unpack_from("<H", data, pos + 4)[0]
        assert data[pos + 6] == (dim * 19 + count + mask + flags + width + seg_index) & 0xFF
        block, pos, minute = decode_frame_block(data, pos + 7, count, dim, flags, width, mask, path.stem, mix, minute)
        rows.extend(block)
    assert len(rows) == total
    assert pos == len(data) - 5
    return rows


def compute_lane_len(data: bytes, start: int, dim: int, flags: int, width: int, mask: int) -> int:
    if not flags & 0x08:
        return (dim * packed_width(width) + 7) // 8 if flags & 0x04 else dim
    if flags & 0x80:
        present = data[start] ^ mask if flags & 0x01 else data[start]
        desc = 1 + present
    else:
        desc = (dim + 7) // 8
        bitmap = bytearray(data[start : start + desc])
        if flags & 0x01:
            bitmap = bytearray(b ^ mask for b in bitmap)
        present = sum(1 for j in range(dim) if bitmap[j // 8] & (1 << (j & 7)))
    payload = (present * packed_width(width) + 7) // 8 if flags & 0x04 else present
    return desc + payload


def decode_lane(lane: bytearray, dim: int, frame_id: int, zone: int, flags: int, width: int) -> list[int]:
    raw = [0] * dim
    if flags & 0x08:
        if flags & 0x80:
            present = lane[0]
            indexes = list(lane[1 : 1 + present])
            payload = bytearray(lane[1 + present :])
        else:
            desc = (dim + 7) // 8
            bitmap = lane[:desc]
            order = lane_order(dim, zone) if flags & 0x10 else list(range(dim))
            indexes = [idx for idx in order if bitmap[idx // 8] & (1 << (idx & 7))]
            payload = bytearray(lane[desc:])
        if flags & 0x40:
            payload = rotate_right(payload, rotation(frame_id, zone, dim, len(payload)))
        if flags & 0x04 and width & 0x40:
            payload = nibble_swap(payload)
        values = unpack_values(payload, len(indexes), width) if flags & 0x04 else [int.from_bytes(bytes([b]), "little", signed=True) for b in payload]
        for idx, value in zip(indexes, values):
            raw[idx] = value
        return raw
    if flags & 0x40:
        lane = rotate_right(lane, rotation(frame_id, zone, dim, len(lane)))
    if flags & 0x04 and width & 0x40:
        lane = nibble_swap(lane)
    values = unpack_values(lane, dim, width) if flags & 0x04 else [int.from_bytes(bytes([b]), "little", signed=True) for b in lane]
    if flags & 0x10:
        for idx, value in zip(lane_order(dim, zone), values):
            raw[idx] = value
    else:
        raw = values
    return raw


def select_manifests(cal_dir: Path, probe: Path, probe_batch: Path) -> list[dict]:
    out = []
    for manifest in sorted(cal_dir.glob("*.json")):
        proc = subprocess.run([str(probe), "--manifest", str(manifest), "--batch", str(probe_batch)], check=True, text=True, capture_output=True)
        parts = dict(part.split("=", 1) for part in proc.stdout.split() if "=" in part)
        data = json.loads(manifest.read_text())
        data["_source"] = str(manifest)
        data["_filename"] = manifest.name
        data["_rank_score"] = int(parts["rank_score"])
        data["_drift"] = int(parts["drift"])
        data["_anchor"] = int(parts["anchor"], 16)
        if not data.get("name"):
            data["name"] = manifest.stem
        out.append(data)
    out.sort(key=lambda m: (m["_rank_score"], m["_filename"]))
    selected = out[:2]
    for manifest, weight in zip(selected, [4, 2]):
        manifest["_weight"] = weight
    return selected


def quality_flags(row: dict, manifest: dict) -> list[bool]:
    zone = row["zone"] & 7
    values = row["values"]
    flags = []
    for j, _scale in enumerate(manifest["scale_num"]):
        source = (manifest["sensor_order"][j] + manifest["zone_shift"][zone]) % len(values)
        flags.append(bool(row["quality"] & (1 << source)))
    return flags


def centered(row: dict, manifest: dict) -> list[int]:
    zone = row["zone"] & 7
    values = row["values"]
    qflags = quality_flags(row, manifest)
    out = []
    for j, scale in enumerate(manifest["scale_num"]):
        source = (manifest["sensor_order"][j] + manifest["zone_shift"][zone]) % len(values)
        if qflags[j]:
            out.append(0)
        else:
            value = max(manifest["clip_min"][j], min(manifest["clip_max"][j], values[source]))
            out.append(value - manifest["zero"][j])
    return out


def batch_stats(rows: list[dict], manifest: dict) -> dict:
    stats: dict[str, dict] = {}
    values: dict[str, list[list[int]]] = {}
    minutes: dict[str, list[int]] = {}
    for row in rows:
        batch = row["batch"]
        stats.setdefault(batch, {"rows": 0, "mix": row["mix"], "zone_counts": [0] * 8})
        stats[batch]["rows"] += 1
        stats[batch]["zone_counts"][row["zone"] & 7] += 1
        values.setdefault(batch, [[] for _ in manifest["scale_num"]])
        minutes.setdefault(batch, []).append(row["minute"])
        for j, value in enumerate(centered(row, manifest)):
            values[batch][j].append(value)
    for batch, per_feature in values.items():
        meds = []
        for vals in per_feature:
            vals = sorted(vals)
            meds.append(vals[(len(vals) - 1) // 2])
        stats[batch]["medians"] = meds
        ordered_minutes = sorted(minutes[batch])
        stats[batch]["minute_median"] = ordered_minutes[(len(ordered_minutes) - 1) // 2]
        stats[batch]["minute_min"] = ordered_minutes[0]
        stats[batch]["minute_max"] = ordered_minutes[-1]
    return stats


def round_away(n: int, d: int) -> int:
    return (n + d // 2) // d if n >= 0 else -((-n + d // 2) // d)


def score_one(row: dict, manifest: dict, stat: dict) -> list[int]:
    zone = row["zone"] & 7
    shard = ((row["id"] >> 4) ^ zone ^ (manifest["_anchor"] & 7)) & 7
    cvals = centered(row, manifest)
    qflags = quality_flags(row, manifest)
    qcount = sum(1 for flag in qflags if flag)
    minute_delta = max(-64, min(64, row["minute"] - stat["minute_median"]))
    time_phase = (minute_delta + zone * 3 + (manifest["_anchor"] & 15)) & 15
    span_bucket = (stat["minute_max"] - stat["minute_min"]) & 7
    scores = []
    for c, _label in enumerate(manifest["labels"]):
        score = (manifest["bias_milli"][c] + manifest["zone_bias_milli"][zone][c] + manifest["shard_bias_milli"][shard][c]) * manifest["scale_den"]
        score += manifest["_drift"] * manifest["drift_bias_milli"][c] * manifest["scale_den"]
        anchor_term = ((manifest["_anchor"] >> ((c * 7) % 17)) & 31) - 16
        score += anchor_term * manifest["anchor_bias_milli"][c] * manifest["scale_den"]
        mix_term = ((row["mix"] >> ((zone + c) & 7)) & 15) - 8
        score += mix_term * manifest["mix_bias_milli"][c] * manifest["scale_den"]
        load_term = stat["zone_counts"][zone] * 8 - stat["rows"]
        score += load_term * manifest["load_bias_milli"][zone][c] * manifest["scale_den"]
        score += manifest["span_bias_milli"][span_bucket][c] * manifest["scale_den"]
        score += manifest["time_bias_milli"][time_phase][c] * manifest["scale_den"]
        score += qcount * manifest["quality_bias_milli"][c] * manifest["scale_den"]
        for j, value in enumerate(cvals):
            score += manifest["weights_milli"][c][j] * value * manifest["scale_num"][j]
            score += manifest["median_milli"][c][j] * (value - stat["medians"][j]) * manifest["scale_num"][j]
            score += manifest["trend_weights_milli"][c][j] * value * minute_delta
            if qflags[j]:
                score += manifest["quality_weights_milli"][c][j] * manifest["scale_den"]
        for left, right, weight in manifest["pair_terms"][c]:
            score += weight * cvals[left] * cvals[right]
        scores.append(score)
    return scores


def expected(eval_dir: Path, cal_dir: Path, probe: Path, probe_batch: Path) -> tuple[str, dict]:
    rows = []
    for file in sorted(eval_dir.glob("*.cfr")):
        rows.extend(decode_file(file))
    manifests = select_manifests(cal_dir, probe, probe_batch)
    stats = {m["_source"]: batch_stats(rows, m) for m in manifests}
    predictions = []
    for row in rows:
        combined = [0] * len(manifests[0]["labels"])
        total_weight = 0
        for manifest in manifests:
            total_weight += manifest["_weight"]
            scores = score_one(row, manifest, stats[manifest["_source"]][row["batch"]])
            for i, score in enumerate(scores):
                combined[i] += manifest["_weight"] * score
        best = max(range(len(combined)), key=lambda i: (combined[i], -i))
        second = max((i for i in range(len(combined)) if i != best), key=lambda i: (combined[i], -i))
        predictions.append((row["id"], row["batch"], row["minute"], row["zone"] & 7, manifests[0]["labels"][best], round_away(combined[best] - combined[second], manifests[0]["scale_den"] * total_weight)))
    predictions.sort(key=lambda r: (r[0], r[1]))
    lines = ["frame_id\tbatch\tminute\tzone\tevent\tmargin_milli"]
    for row in predictions:
        lines.append(f"{row[0]:08x}\t{row[1]}\t{row[2]}\t{row[3]}\t{row[4]}\t{row[5]}")
    tsv = "\n".join(lines) + "\n"
    batches = []
    for batch in sorted({row["batch"] for row in rows}):
        subset = [row for row in rows if row["batch"] == batch]
        counts = [0] * 8
        quality_counts = [0] * 8
        minutes = sorted(row["minute"] for row in subset)
        for row in subset:
            counts[row["zone"] & 7] += 1
            for sensor in range(min(8, len(row["values"]))):
                if row["quality"] & (1 << sensor):
                    quality_counts[sensor] += 1
        batches.append({
            "batch": batch,
            "rows": len(subset),
            "batch_mix": subset[0]["mix"],
            "minute_min": minutes[0],
            "minute_max": minutes[-1],
            "minute_median": minutes[(len(minutes) - 1) // 2],
            "zone_counts": counts,
            "quality_counts": quality_counts,
        })
    audit = {
        "manifests": [
            {
                "name": m["name"],
                "rank_score": m["_rank_score"],
                "drift": m["_drift"],
                "anchor": f"{m['_anchor'] & 0xFFFFFFFF:08x}",
                "weight": m["_weight"],
            }
            for m in manifests
        ],
        "rows": len(rows),
        "batches": batches,
        "events_sha256": hashlib.sha256(tsv.encode()).hexdigest(),
    }
    return tsv, audit


def run_tool(eval_dir: Path, out: Path, audit: Path, cal_dir: Path | None = None, probe: Path | None = None, probe_batch: Path | None = None) -> subprocess.CompletedProcess:
    assert_protected_inputs_clean()
    cmd = [
        str(build_tool()),
        "--telemetry-dir", str(eval_dir),
        "--calibration-dir", str(cal_dir or APP / "calibration"),
        "--probe", str(probe or APP / "probe" / "driftprobe"),
        "--probe-batch", str(probe_batch or APP / "telemetry" / "public.cfr"),
        "--out", str(out),
        "--audit-out", str(audit),
    ]
    result = subprocess.run(cmd, text=True, capture_output=True)
    assert_protected_inputs_clean()
    return result


def test_public_fixture_matches_contract(tmp_path: Path) -> None:
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    result = run_tool(APP / "telemetry", out, audit)
    assert result.returncode == 0, result.stderr
    expected_tsv, expected_audit = expected(APP / "telemetry", APP / "calibration", APP / "probe" / "driftprobe", APP / "telemetry" / "public.cfr")
    assert out.read_text() == expected_tsv
    assert json.loads(audit.read_text()) == expected_audit


def test_alternate_eval_dir_exercises_sparse_rotated_seeded_frames(tmp_path: Path) -> None:
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    write_cfr(eval_dir / "sparse.cfr", [
        (0x21000003, 4, 11, [0, 12, 0, -7, 18, 0], 0b000101),
        (0x21000001, 7, 14, [-9, 0, 0, 13, 0, -15], 0b100000),
        (0x2100000A, 2, 21, [0, -11, 8, 0, -6, 17], 0b001010),
    ], flags=0x01 | 0x02 | 0x04 | 0x08 | 0x10 | 0x20 | 0x40 | 0x80, width=0xA6, mask=0x33, mix=0x7312)
    write_cfr(eval_dir / "plain.cfr", [
        (0x20000002, 3, 5, [11, -12, 5, 17, -7, 9], 0b010001),
        (0x2000000C, 1, 9, [-6, 14, -2, 8, 19, -11], 0b000100),
    ], flags=0, width=0x20, mask=0x12, mix=0x4420)
    out = tmp_path / "nested" / "events.tsv"
    audit = tmp_path / "nested" / "audit.json"
    expected_tsv, expected_audit = expected(eval_dir, APP / "calibration", APP / "probe" / "driftprobe", APP / "telemetry" / "public.cfr")
    snapshots = [snapshot_path(eval_dir)]
    result = run_tool(eval_dir, out, audit)
    assert_snapshots_clean(*snapshots)
    assert result.returncode == 0, result.stderr
    assert out.read_text() == expected_tsv
    assert json.loads(audit.read_text()) == expected_audit


def test_zigzag_swizzled_bitmap_sparse_and_route_order(tmp_path: Path) -> None:
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    write_cfr(eval_dir / "swizzle.cfr", [
        (0x31000011, 6, 8, [12, -5, 20, -8, 3, 16, -22, 27], 0b10000001),
        (0x31000007, 3, 13, [-18, 11, -4, 9, 21, -25, 6, -2], 0b00101000),
        (0x3100001D, 5, 19, [25, -19, 8, -3, 14, -10, 29, -24], 0b01000100),
    ], flags=0x01 | 0x04 | 0x08 | 0x10 | 0x20 | 0x40, width=0xE6, mask=0x6B, mix=0x1F0A)
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    expected_tsv, expected_audit = expected(eval_dir, APP / "calibration", APP / "probe" / "driftprobe", APP / "telemetry" / "public.cfr")
    snapshots = [snapshot_path(eval_dir)]
    result = run_tool(eval_dir, out, audit)
    assert_snapshots_clean(*snapshots)
    assert result.returncode == 0, result.stderr
    assert out.read_text() == expected_tsv
    assert json.loads(audit.read_text()) == expected_audit


def test_segmented_container_mixes_dimensions_and_flag_sets(tmp_path: Path) -> None:
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    write_cfs2(
        eval_dir / "segmented.cfr",
        [
            {
                "flags": 0x01 | 0x02 | 0x04 | 0x10 | 0x20 | 0x40,
                "width": 0xA7,
                "mask": 0x44,
                "rows": [
                    (0x39000021, 4, 6, [10, -7, 5, 12, -3, 18, -21, 24], 0b00010001),
                    (0x39000025, 1, 13, [-13, 19, -8, 6, 22, -25, 4, 15], 0b01000010),
                ],
            },
            {
                "flags": 0x01 | 0x08 | 0x40 | 0x80,
                "width": 0x20,
                "mask": 0x21,
                "rows": [
                    (0x39000031, 2, 17, [0, 9, -6, 0, 15, 0], 0b001001),
                    (0x39000035, 6, 25, [-8, 0, 0, 14, 0, -17], 0b100010),
                    (0x39000039, 3, 29, [7, 0, -12, 0, 11, 0], 0b010100),
                ],
            },
        ],
        container_mask=0x5E,
        mix=0x6A31,
    )
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    expected_tsv, expected_audit = expected(eval_dir, APP / "calibration", APP / "probe" / "driftprobe", APP / "telemetry" / "public.cfr")
    snapshots = [snapshot_path(eval_dir)]
    result = run_tool(eval_dir, out, audit)
    assert_snapshots_clean(*snapshots)
    assert result.returncode == 0, result.stderr
    assert out.read_text() == expected_tsv
    assert json.loads(audit.read_text()) == expected_audit


def test_custom_probe_tie_break_and_single_manifest_fallback(tmp_path: Path) -> None:
    cal = tmp_path / "cal"
    cal.mkdir()
    base = json.loads((APP / "calibration" / "east.json").read_text())
    for filename, name, rank, drift, anchor in [
        ("b.json", "beta", 5, -7, 0x10101010),
        ("a.json", "alpha", 5, 2, 0x20202020),
    ]:
        item = dict(base)
        item.update({"name": name, "probe_rank": rank, "probe_drift": drift, "probe_anchor": anchor})
        (cal / filename).write_text(json.dumps(item))
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    write_cfr(eval_dir / "custom.cfr", [
        (0x41000001, 2, 4, [9, -7, 13, -5, 11, -3], 0b010010),
        (0x41000008, 5, 10, [-12, 16, -8, 5, 20, -15], 0b000101),
    ], flags=0x01 | 0x04 | 0x20, width=0xA6, mask=0x29, mix=0x55AA)
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    expected_tsv, expected_audit = expected(eval_dir, cal, APP / "probe" / "driftprobe", APP / "telemetry" / "public.cfr")
    snapshots = [snapshot_path(eval_dir), snapshot_path(cal)]
    result = run_tool(eval_dir, out, audit, cal_dir=cal)
    assert_snapshots_clean(*snapshots)
    assert result.returncode == 0, result.stderr
    assert json.loads(audit.read_text())["manifests"][0]["name"] == "alpha"
    assert out.read_text() == expected_tsv
    assert json.loads(audit.read_text()) == expected_audit


def test_custom_probe_and_probe_batch_flags_are_honored(tmp_path: Path) -> None:
    cal = tmp_path / "cal"
    cal.mkdir()
    base = json.loads((APP / "calibration" / "east.json").read_text())
    for filename, rank, drift, anchor in [
        ("first.json", 3, -5, 0x30303030),
        ("second.json", 9, 6, 0x40404040),
    ]:
        item = dict(base)
        item.update({"name": filename.removesuffix(".json"), "probe_rank": rank, "probe_drift": drift, "probe_anchor": anchor})
        (cal / filename).write_text(json.dumps(item))
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    probe_batch = eval_dir / "custom.cfr"
    write_cfr(probe_batch, [
        (0x51000001, 3, 7, [13, -8, 11, -6, 17, -2], 0b000101),
        (0x51000004, 4, 16, [-10, 15, -5, 9, -14, 20], 0b010010),
    ], flags=0x01 | 0x04 | 0x20 | 0x40, width=0xA6, mask=0x4C, mix=0x31AF)
    probe = tmp_path / "custom-probe"
    probe.write_text(
        "#!/usr/bin/env python3\n"
        "import argparse, json\n"
        "from pathlib import Path\n"
        f"expected = {str(probe_batch)!r}\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--manifest', required=True)\n"
        "parser.add_argument('--batch', required=True)\n"
        "args = parser.parse_args()\n"
        "if args.batch != expected:\n"
        "    raise SystemExit('wrong probe batch')\n"
        "data = json.loads(Path(args.manifest).read_text())\n"
        "print(f\"rank_score={data['probe_rank']} drift={data['probe_drift']} anchor={data['probe_anchor']:08x}\")\n"
    )
    probe.chmod(0o755)
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    expected_tsv, expected_audit = expected(eval_dir, cal, probe, probe_batch)
    snapshots = [snapshot_path(eval_dir), snapshot_path(cal), snapshot_path(probe)]
    result = run_tool(eval_dir, out, audit, cal_dir=cal, probe=probe, probe_batch=probe_batch)
    assert_snapshots_clean(*snapshots)
    assert result.returncode == 0, result.stderr
    assert out.read_text() == expected_tsv
    assert json.loads(audit.read_text()) == expected_audit


def test_probe_returns_nonzero_and_preserves_outputs(tmp_path: Path) -> None:
    cal = tmp_path / "cal"
    cal.mkdir()
    base = json.loads((APP / "calibration" / "east.json").read_text())
    (cal / "x.json").write_text(json.dumps(dict(base, name="x", probe_rank=1, probe_drift=2, probe_anchor=0x1010)))
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    write_cfr(eval_dir / "custom.cfr", [
        (0x63000001, 4, 11, [2, -3, 5, -1, 7, -2], 0b001001),
    ], flags=0, width=0x20, mask=0x11, mix=0x22)
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    out.write_text("old events\n")
    audit.write_text('{"old": true}\n')
    probe = tmp_path / "bad-probe"
    probe.write_text("#!/usr/bin/env python3\nimport sys\nprint('rank_score=1 drift=2 anchor=00000002')\nsys.exit(5)\n")
    probe.chmod(0o755)
    result = run_tool(eval_dir, out, audit, cal_dir=cal, probe=probe, probe_batch=eval_dir / "custom.cfr")
    assert result.returncode != 0
    assert out.read_text() == "old events\n"
    assert audit.read_text() == '{"old": true}\n'


def test_probe_bad_output_fails_without_overwriting_outputs(tmp_path: Path) -> None:
    cal = tmp_path / "cal"
    cal.mkdir()
    base = json.loads((APP / "calibration" / "east.json").read_text())
    (cal / "x.json").write_text(json.dumps(dict(base, name="x", probe_rank=1, probe_drift=2, probe_anchor=0x1010)))
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    write_cfr(eval_dir / "custom.cfr", [
        (0x62000001, 4, 11, [2, -3, 5, -1, 7, -2], 0b001001),
    ], flags=0, width=0x20, mask=0x11, mix=0x22)
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    out.write_text("old events\n")
    audit.write_text('{"old": true}\n')
    probe = tmp_path / "bad-probe"
    probe.write_text("#!/usr/bin/env python3\nprint('rank_score=1 drift=2')\n")
    probe.chmod(0o755)
    result = run_tool(eval_dir, out, audit, cal_dir=cal, probe=probe, probe_batch=eval_dir / "custom.cfr")
    assert result.returncode != 0
    assert out.read_text() == "old events\n"
    assert audit.read_text() == '{"old": true}\n'


def test_probe_short_anchor_rejected_without_mutating_outputs(tmp_path: Path) -> None:
    cal = tmp_path / "cal"
    cal.mkdir()
    base = json.loads((APP / "calibration" / "east.json").read_text())
    (cal / "x.json").write_text(json.dumps(dict(base, name="x", probe_rank=1, probe_drift=2, probe_anchor=0x1010)))
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    write_cfr(eval_dir / "custom.cfr", [
        (0x64000002, 5, 12, [1, -2, 3, -4, 5, -6], 0b001001),
    ], flags=0, width=0x20, mask=0x11, mix=0x33)
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    out.write_text("old events\n")
    audit.write_text('{"old": true}\n')
    probe = tmp_path / "short-anchor-probe"
    probe.write_text("#!/usr/bin/env python3\nprint('rank_score=1 drift=2 anchor=abcd')\n")
    probe.chmod(0o755)
    result = run_tool(eval_dir, out, audit, cal_dir=cal, probe=probe, probe_batch=eval_dir / "custom.cfr")
    assert result.returncode != 0
    assert out.read_text() == "old events\n"
    assert audit.read_text() == '{"old": true}\n'


def test_malformed_packed_width_rejected_without_mutating_outputs(tmp_path: Path) -> None:
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    cfr = eval_dir / "bad_width.cfr"
    write_cfr(cfr, [
        (0x64000001, 1, 9, [3, -5, 7, -2, 6, -1], 0b000011),
    ], flags=0x01 | 0x04 | 0x20, width=0xA6, mask=0x33, mix=0x1111)
    # Force invalid packed width path with no bits.
    corrupt_alt1_width(cfr, new_width=0x20)
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    out.write_text("old events\n")
    audit.write_text('{"old": true}\n')
    result = run_tool(eval_dir, out, audit)
    assert result.returncode != 0
    assert out.read_text() == "old events\n"
    assert audit.read_text() == '{"old": true}\n'


def test_als2_header_corruption_fails_without_output_mutation(tmp_path: Path) -> None:
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    write_cfs2(eval_dir / "segmented.cfr", [
        {
            "flags": 0x01 | 0x02 | 0x04 | 0x10 | 0x20 | 0x40,
            "width": 0xA7,
            "mask": 0x44,
            "rows": [
                (0x65000021, 4, 6, [10, -7, 5, 12, -3, 18, -21, 24], 0b00010001),
                (0x65000025, 1, 13, [-13, 19, -8, 6, 22, -25, 4, 15], 0b01000010),
            ],
        },
    ], container_mask=0x5E, mix=0x6A31)
    cfr = eval_dir / "segmented.cfr"
    # Change segment count without changing payload layout.
    corrupt_als2_header(cfr, segment_count=2)
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    out.write_text("old events\n")
    audit.write_text('{"old": true}\n')
    result = run_tool(eval_dir, out, audit)
    assert result.returncode != 0
    assert out.read_text() == "old events\n"
    assert audit.read_text() == '{"old": true}\n'


def test_sparse_descriptor_corruption_rejected_without_output_mutation(tmp_path: Path) -> None:
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    cfr = eval_dir / "bad_sparse.cfr"
    write_cfr(cfr, [
        (0x65000011, 3, 7, [10, 0, -5, 8, 3, -2], 0b000101),
    ], flags=0x01 | 0x08 | 0x80, width=0x20, mask=0x22, mix=0x77)
    # Inflate explicit sparse present-count to exceed available payload and force descriptor failure.
    corrupt_alt1_explicit_sparse_present_count(cfr, present=200)
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    out.write_text("old events\n")
    audit.write_text('{"old": true}\n')
    result = run_tool(eval_dir, out, audit)
    assert result.returncode != 0
    assert out.read_text() == "old events\n"
    assert audit.read_text() == '{"old": true}\n'


def test_als2_row_count_corruption_rejected_without_output_mutation(tmp_path: Path) -> None:
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    cfr = eval_dir / "segmented_corrupt.cfr"
    write_cfs2(cfr, [
        {
            "flags": 0x01 | 0x02 | 0x04 | 0x10 | 0x20 | 0x40,
            "width": 0xA7,
            "mask": 0x44,
            "rows": [
                (0x66000021, 4, 6, [10, -7, 5, 12, -3, 18], 0b00010001),
                (0x66000025, 1, 13, [-13, 19, -8, 6, 22, -25], 0b000101),
            ],
        },
    ], container_mask=0x5E, mix=0x6A31)
    # Corrupt container total row count, forcing ALS2 length consistency failure.
    corrupt_als2_header(cfr, total_count=0xFFFF)
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    out.write_text("old events\n")
    audit.write_text('{"old": true}\n')
    result = run_tool(eval_dir, out, audit)
    assert result.returncode != 0
    assert out.read_text() == "old events\n"
    assert audit.read_text() == '{"old": true}\n'


def test_events_write_failure_preserves_audit_output(tmp_path: Path) -> None:
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    write_cfr(eval_dir / "one.cfr", [
        (0x61000001, 1, 10, [6, -4, 8, -2, 10, -1], 0b000111),
    ], flags=0, width=0x20, mask=0x12, mix=0x2211)
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    out.write_text("old events\n")
    audit.write_text('{"old": true}\n')
    (tmp_path / "events.tsv.tmp").mkdir()
    result = run_tool(eval_dir, out, audit)
    assert result.returncode != 0
    assert out.read_text() == "old events\n"
    assert audit.read_text() == '{"old": true}\n'


def test_incompatible_manifest_selection_fails_without_mutating_outputs(tmp_path: Path) -> None:
    cal = tmp_path / "cal"
    cal.mkdir()
    base = json.loads((APP / "calibration" / "east.json").read_text())
    good = dict(base)
    good.update({"name": "good", "probe_rank": 1})
    bad = dict(base)
    bad.update({"name": "bad", "scale_den": base["scale_den"] + 1, "probe_rank": 0, "labels": ["A", "B", "C", "D", "E"]})
    (cal / "good.json").write_text(json.dumps(good))
    (cal / "bad.json").write_text(json.dumps(bad))
    (cal / "worse.json").write_text(json.dumps(dict(base, name="worse", probe_rank=2)))
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    write_cfr(eval_dir / "custom.cfr", [
        (0x71000001, 2, 4, [9, -7, 13, -5, 11, -3], 0b010010),
    ], flags=0x01 | 0x04 | 0x20, width=0xA6, mask=0x29, mix=0x55AA)
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    out.write_text("old events\n")
    audit.write_text('{"old": true}\n')
    snapshots = [snapshot_path(eval_dir), snapshot_path(cal)]
    result = run_tool(eval_dir, out, audit, cal_dir=cal)
    assert_snapshots_clean(*snapshots)
    assert result.returncode != 0
    assert out.read_text() == "old events\n"
    assert audit.read_text() == '{"old": true}\n'


def test_audit_write_failure_does_not_replace_events_output(tmp_path: Path) -> None:
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    out.write_text("old events\n")
    audit.write_text('{"old": true}\n')
    (tmp_path / "audit.json.tmp").mkdir()
    result = run_tool(APP / "telemetry", out, audit)
    assert result.returncode != 0
    assert out.read_text() == "old events\n"
    assert audit.read_text() == '{"old": true}\n'


def test_events_tmp_blocking_preserves_audit_output(tmp_path: Path) -> None:
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    write_cfr(eval_dir / "one.cfr", [
        (0x62000002, 2, 12, [8, -4, 9, -2, 11, -3], 0b001001),
    ], flags=0, width=0x20, mask=0x13, mix=0x2244)
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    out.write_text("old events\n")
    audit.write_text('{"old": true}\n')
    (tmp_path / "events.tsv.tmp").mkdir()
    result = run_tool(eval_dir, out, audit)
    assert result.returncode != 0
    assert out.read_text() == "old events\n"
    assert audit.read_text() == '{"old": true}\n'


def test_bad_frame_checksum_fails_without_output_mutation(tmp_path: Path) -> None:
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    cfr = eval_dir / "bad.cfr"
    write_cfr(cfr, [
        (0x62000003, 3, 8, [1, -2, 4, -5, 2, -1], 0b000101),
    ], flags=0, width=0x20, mask=0x17, mix=0x1001)
    # Corrupt the first frame checksum byte.
    corrupt_alt1_first_checksum(cfr)
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    out.write_text("old events\n")
    audit.write_text('{"old": true}\n')
    result = run_tool(eval_dir, out, audit)
    assert result.returncode != 0
    assert out.read_text() == "old events\n"
    assert audit.read_text() == '{"old": true}\n'


def test_malformed_input_fails_without_replacing_outputs(tmp_path: Path) -> None:
    eval_dir = tmp_path / "eval"
    eval_dir.mkdir()
    bad = bytearray(b"ALT1\x01\x06\x00\x00\x01\x00\x12\x00")
    bad.extend(b"\x00" * 20)
    (eval_dir / "bad.cfr").write_bytes(bad)
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    out.write_text("old events\n")
    audit.write_text('{"old": true}\n')
    result = run_tool(eval_dir, out, audit)
    assert result.returncode != 0
    assert out.read_text() == "old events\n"
    assert audit.read_text() == '{"old": true}\n'


def test_solution_preserves_inputs_and_outputs_native_binary(tmp_path: Path) -> None:
    assert_protected_inputs_clean()
    bin_path = build_tool()
    assert os.access(bin_path, os.X_OK)
    assert bin_path.read_bytes()[:4] == b"\x7fELF"
    assert_protected_inputs_clean()


def test_aurora_public_output_is_deterministic_sorted(tmp_path: Path) -> None:
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    result = run_tool(APP / "telemetry", out, audit)
    assert result.returncode == 0
    lines = out.read_text().splitlines()
    assert lines and lines[0] == "frame_id\tbatch\tminute\tzone\tevent\tmargin_milli"
    ids = [int(row.split("\t")[0], 16) for row in lines[1:]]
    assert ids == sorted(ids)


def _aurora_read_audit(path: Path) -> dict:
    payload = json.loads(path.read_text())
    assert isinstance(payload, dict)
    assert "manifests" in payload
    assert "batches" in payload
    return payload


def test_aurora_audit_schema_has_full_batch_shape(tmp_path: Path) -> None:
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    assert run_tool(APP / "telemetry", out, audit).returncode == 0
    payload = _aurora_read_audit(audit)
    assert payload["rows"] > 0
    for batch in payload["batches"]:
        assert len(batch["zone_counts"]) == 8
        assert len(batch["quality_counts"]) == 8
    assert payload["events_sha256"]


def test_aurora_manifest_weights_match_contract(tmp_path: Path) -> None:
    out = tmp_path / "events.tsv"
    audit = tmp_path / "audit.json"
    assert run_tool(APP / "telemetry", out, audit).returncode == 0
    payload = _aurora_read_audit(audit)
    manifest_weights = [entry["weight"] for entry in payload["manifests"]]
    assert manifest_weights in ([4], [4, 2], [2], [4, 2, 2])
