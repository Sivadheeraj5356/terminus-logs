"""End-to-end verifier for the SPECZ spectral-drift spool worker."""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import struct
import subprocess
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import pytest


MAGIC = b"SPZ0"

CALIBRATION_LABELS = {
    ("SPC07", 11): (650.102341, 0.023100120, -0.000000012, 4.750, 20.00),
    ("SPC07", 17): (650.098115, 0.023114880, -0.000000015, 4.625, 20.00),
    ("SPC12", 11): (648.550200, 0.022980000, -0.000000010, 5.100, 20.00),
    ("SPC12", 17): (648.544880, 0.022995500, -0.000000013, 4.900, 20.00),
}

DEFAULT_REFERENCE_NM = 656.281230
DEFAULT_PEAK_WINDOW = (655.70, 656.90)
DEFAULT_BASELINE_WINDOWS_PX = ((0, 31), (224, 255))


def crc32_iso(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


@dataclass
class FrameMeta:
    revision: int
    flags: int
    instrument: str
    session: str
    sequence: int
    acq_unix: int
    sample_count: int
    integration_ticks: int
    temp_centi_c: int
    calibration_revision: int
    masked_pixels: list[int] = field(default_factory=list)


@dataclass
class DecodedFrame:
    meta: FrameMeta
    samples: list[int]
    crc_ok: bool
    raw: bytes


def pack_raw12(samples: Iterable[int]) -> bytes:
    vals = [int(s) & 0xFFF for s in samples]
    out = bytearray()
    i = 0
    while i < len(vals):
        s0 = vals[i]
        if i + 1 < len(vals):
            s1 = vals[i + 1]
            out.append(s0 & 0xFF)
            out.append(((s0 >> 8) & 0x0F) | ((s1 & 0x0F) << 4))
            out.append((s1 >> 4) & 0xFF)
            i += 2
        else:
            out.append(s0 & 0xFF)
            out.append((s0 >> 8) & 0x0F)
            i += 1
    return bytes(out)


def pack_delta8(samples: Iterable[int]) -> bytes:
    vals = [int(s) & 0xFFF for s in samples]
    if not vals:
        return b""
    out = bytearray()
    out.extend(struct.pack("<H", vals[0]))
    prev = vals[0]
    for s in vals[1:]:
        delta = s - prev
        if delta < -127 or delta > 127:
            out.append(0x80)
            out.extend(struct.pack("<H", s))
            prev = s
        else:
            out.append(delta & 0xFF if delta >= 0 else (delta + 256) & 0xFF)
            prev = s
    return bytes(out)


def encode_frame(
    *,
    revision: int,
    flags: int,
    instrument: str,
    session: str,
    sequence: int,
    acq_unix: int,
    samples: list[int],
    integration_ticks: int = 100,
    temp_centi_c: int = 2000,
    calibration_revision: int = 17,
    masked_pixels: list[int] | None = None,
    corrupt_crc: bool = False,
    truncate: int | None = None,
    reserved_flags: int | None = None,
) -> bytes:
    masked_pixels = sorted(set(masked_pixels or []))
    if reserved_flags is not None:
        flags = reserved_flags
    else:
        flags = flags & 0x07
        if masked_pixels:
            flags |= 0x02
    payload = pack_delta8(samples) if (flags & 0x04) else pack_raw12(samples)
    header_len = 48 + 2 * len(masked_pixels)
    crc = crc32_iso(payload)
    if corrupt_crc:
        crc ^= 0x00FF00FF
    inst = instrument.encode("ascii")[:8].ljust(8, b"\x00")
    sess = session.encode("ascii")[:8].ljust(8, b"\x00")
    hdr = bytearray()
    hdr.extend(MAGIC)
    hdr.append(revision & 0xFF)
    hdr.append(flags & 0xFF)
    hdr.extend(struct.pack("<H", header_len))
    hdr.extend(inst)
    hdr.extend(sess)
    hdr.extend(struct.pack("<I", sequence))
    hdr.extend(struct.pack("<I", acq_unix))
    hdr.extend(struct.pack("<H", len(samples)))
    hdr.extend(struct.pack("<H", integration_ticks))
    hdr.extend(struct.pack("<h", temp_centi_c))
    hdr.append(calibration_revision & 0xFF)
    hdr.append(len(masked_pixels) & 0xFF)
    hdr.extend(struct.pack("<I", len(payload)))
    hdr.extend(struct.pack("<I", crc))
    for px in masked_pixels:
        hdr.extend(struct.pack("<H", px))
    blob = bytes(hdr) + payload
    if truncate is not None:
        blob = blob[:truncate]
    return blob


def decode_frame(data: bytes) -> DecodedFrame:
    if len(data) < 48 or data[:4] != MAGIC:
        raise ValueError("invalid magic")
    revision = data[4]
    flags = data[5]
    header_len = struct.unpack_from("<H", data, 6)[0]
    instrument = data[8:16].split(b"\x00", 1)[0].decode("ascii", errors="replace")
    session = data[16:24].split(b"\x00", 1)[0].decode("ascii", errors="replace")
    sequence = struct.unpack_from("<I", data, 24)[0]
    acq_unix = struct.unpack_from("<I", data, 28)[0]
    sample_count = struct.unpack_from("<H", data, 32)[0]
    integration_ticks = struct.unpack_from("<H", data, 34)[0]
    temp_centi_c = struct.unpack_from("<h", data, 36)[0]
    calibration_revision = data[38]
    mask_count = data[39]
    payload_len = struct.unpack_from("<I", data, 40)[0]
    stored_crc = struct.unpack_from("<I", data, 44)[0]
    if header_len != 48 + 2 * mask_count:
        raise ValueError("header length mismatch")
    if flags & 0xF8:
        raise ValueError("reserved flags")
    masked = []
    off = 48
    for _ in range(mask_count):
        if off + 2 > len(data):
            raise ValueError("truncated mask")
        px = struct.unpack_from("<H", data, off)[0]
        if px in masked or px >= sample_count:
            raise ValueError("bad mask index")
        masked.append(px)
        off += 2
    if off + payload_len > len(data):
        raise ValueError("payload overrun")
    payload = data[off : off + payload_len]
    crc_ok = crc32_iso(payload) == stored_crc
    samples = unpack_payload(payload, revision, flags, sample_count) if crc_ok else []
    meta = FrameMeta(
        revision=revision,
        flags=flags,
        instrument=instrument,
        session=session,
        sequence=sequence,
        acq_unix=acq_unix,
        sample_count=sample_count,
        integration_ticks=integration_ticks,
        temp_centi_c=temp_centi_c,
        calibration_revision=calibration_revision,
        masked_pixels=masked,
    )
    return DecodedFrame(meta=meta, samples=samples, crc_ok=crc_ok, raw=data)


def unpack_payload(payload: bytes, revision: int, flags: int, sample_count: int) -> list[int]:
    if revision not in (1, 2):
        raise ValueError("bad revision")
    if flags & 0x04:
        samples = unpack_delta8(payload, sample_count)
    else:
        samples = unpack_raw12(payload, sample_count)
    if flags & 0x01:
        samples = list(reversed(samples))
    if len(samples) != sample_count:
        raise ValueError("sample count mismatch")
    return samples


def unpack_raw12(payload: bytes, sample_count: int) -> list[int]:
    out: list[int] = []
    i = 0
    idx = 0
    while idx < sample_count:
        if i >= len(payload):
            raise ValueError("short payload")
        b0 = payload[i]
        i += 1
        if idx + 1 < sample_count:
            if i >= len(payload):
                raise ValueError("short payload")
            b1 = payload[i]
            i += 1
            if i >= len(payload):
                raise ValueError("short payload")
            b2 = payload[i]
            i += 1
            s0 = b0 | ((b1 & 0x0F) << 8)
            s1 = ((b1 >> 4) & 0x0F) | (b2 << 4)
            out.extend([s0, s1])
            idx += 2
        else:
            if i >= len(payload):
                raise ValueError("short payload")
            b1 = payload[i]
            i += 1
            if (b1 & 0xF0) != 0:
                raise ValueError("odd tail nibble")
            out.append(b0 | ((b1 & 0x0F) << 8))
            idx += 1
    return out


def unpack_delta8(payload: bytes, sample_count: int) -> list[int]:
    if len(payload) < 2:
        raise ValueError("short delta payload")
    first = struct.unpack_from("<H", payload, 0)[0]
    if first & 0xF000:
        raise ValueError("bad first word")
    out = [first & 0xFFF]
    i = 2
    while len(out) < sample_count:
        if i >= len(payload):
            raise ValueError("short delta payload")
        b = payload[i]
        i += 1
        if b == 0x80:
            if i + 2 > len(payload):
                raise ValueError("short escape")
            val = struct.unpack_from("<H", payload, i)[0] & 0xFFF
            i += 2
            out.append(val)
        else:
            delta = b if b < 128 else b - 256
            nxt = out[-1] + delta
            if nxt < 0 or nxt > 4095:
                raise ValueError("delta overflow")
            out.append(nxt)
    return out


def wavelength_nm(pixel: int, coeffs: tuple[float, float, float, float, float], temp_c: float) -> float:
    c0, c1, c2, tc, tref = coeffs
    return c0 + c1 * pixel + c2 * pixel * pixel + (tc * (temp_c - tref)) / 1000.0


def fit_baseline(
    wavelengths: list[float],
    values: list[float],
    mask_set: set[int],
    windows: tuple[tuple[int, int], tuple[int, int]],
) -> tuple[float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for lo, hi in windows:
        for p in range(lo, hi + 1):
            if p in mask_set or p >= len(values):
                continue
            xs.append(wavelengths[p])
            ys.append(float(values[p]))
    if len(xs) < 2:
        return 0.0, 0.0
    n = len(xs)
    sx = sum(xs)
    sy = sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-15:
        return 0.0, sy / n
    b = (n * sxy - sx * sy) / denom
    a = (sy - b * sx) / n
    return a, b


def compute_metrics(
    decoded: DecodedFrame,
    *,
    reference_nm: float = DEFAULT_REFERENCE_NM,
    peak_window: tuple[float, float] = DEFAULT_PEAK_WINDOW,
    baseline_windows: tuple[tuple[int, int], tuple[int, int]] = DEFAULT_BASELINE_WINDOWS_PX,
    site_reference_nm: float | None = None,
    site_peak_window: tuple[float, float] | None = None,
) -> dict[str, float | str | int]:
    meta = decoded.meta
    coeffs = CALIBRATION_LABELS.get((meta.instrument, meta.calibration_revision))
    if coeffs is None:
        raise ValueError(f"no calibration for {meta.instrument} rev {meta.calibration_revision}")
    temp_c = meta.temp_centi_c / 100.0
    mask_set = set(meta.masked_pixels)
    wavelengths = [wavelength_nm(p, coeffs, temp_c) for p in range(meta.sample_count)]
    ref_nm = site_reference_nm if site_reference_nm is not None else reference_nm
    peak_lo, peak_hi = site_peak_window if site_peak_window is not None else peak_window
    a, b = fit_baseline(wavelengths, decoded.samples, mask_set, baseline_windows)
    residuals = []
    baseline_side_res = []
    for p, val in enumerate(decoded.samples):
        if p in mask_set:
            continue
        lam = wavelengths[p]
        base = a + b * lam
        res = val - base
        residuals.append((lam, res))
        for lo, hi in baseline_windows:
            if lo <= p <= hi:
                baseline_side_res.append(res)
                break
    weights = []
    w_lams = []
    for lam, res in residuals:
        if peak_lo <= lam <= peak_hi:
            w = max(res, 0.0)
            if w > 0:
                weights.append(w)
                w_lams.append(lam)
    if weights:
        centroid = sum(lam * w for lam, w in zip(w_lams, weights)) / sum(weights)
    else:
        centroid = ref_nm
    # trapezoidal integration in wavelength space over peak window
    pts = sorted((lam, max(res, 0.0)) for lam, res in residuals if peak_lo <= lam <= peak_hi)
    intensity = 0.0
    for i in range(1, len(pts)):
        x0, y0 = pts[i - 1]
        x1, y1 = pts[i]
        intensity += (y0 + y1) * 0.5 * (x1 - x0)
    if len(baseline_side_res) > 1:
        mean = sum(baseline_side_res) / len(baseline_side_res)
        var = sum((x - mean) ** 2 for x in baseline_side_res) / (len(baseline_side_res) - 1)
        noise = math.sqrt(var)
    elif baseline_side_res:
        noise = 0.0
    else:
        noise = 0.0
    drift_pm = (centroid - ref_nm) * 1000.0
    return {
        "instrument": meta.instrument,
        "session": meta.session,
        "sequence": meta.sequence,
        "calibration_revision": str(meta.calibration_revision),
        "sample_count": meta.sample_count,
        "peak_centroid_nm": centroid,
        "drift_pm": drift_pm,
        "integrated_intensity": intensity,
        "baseline_noise": noise,
    }


def content_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def synthetic_peak_samples(
    n: int,
    *,
    baseline_slope: float = 0.5,
    peak_center_px: float = 128.0,
    peak_width_px: float = 12.0,
    peak_amp: float = 800.0,
    noise_seed: int = 0,
) -> list[int]:
    import random

    rng = random.Random(noise_seed)
    out = []
    for p in range(n):
        base = 100.0 + baseline_slope * p
        dist = (p - peak_center_px) / max(peak_width_px, 1.0)
        peak = peak_amp * math.exp(-0.5 * dist * dist)
        val = base + peak + rng.uniform(-2.0, 2.0)
        out.append(int(max(0, min(4095, round(val)))))
    return out


HIDDEN_SEEDS = (0x5A17, 0xB04D, 0xC011, 0xE5CA)

IMMUTABLE_PATHS = (
    Path("/app/docs/observatory-operations-notebook.md"),
    Path("/app/container/specz-worker.def"),
    Path("/app/docs/operator-runbook.md"),
)


@dataclass(frozen=True)
class FrameSpec:
    revision: int
    flags: int
    instrument: str
    session: str
    sequence: int
    acq_unix: int
    samples: list[int]
    integration_ticks: int = 100
    temp_centi_c: int = 2000
    calibration_revision: int = 17
    masked_pixels: list[int] | None = None
    corrupt_crc: bool = False
    truncate: int | None = None
    reserved_flags: int | None = None


def build_frame(spec: FrameSpec) -> bytes:
  return encode_frame(
      revision=spec.revision,
      flags=spec.flags,
      instrument=spec.instrument,
      session=spec.session,
      sequence=spec.sequence,
      acq_unix=spec.acq_unix,
      samples=spec.samples,
      integration_ticks=spec.integration_ticks,
      temp_centi_c=spec.temp_centi_c,
      calibration_revision=spec.calibration_revision,
      masked_pixels=spec.masked_pixels,
      corrupt_crc=spec.corrupt_crc,
      truncate=spec.truncate,
      reserved_flags=spec.reserved_flags,
  )


def expected_scan_record(
    frame_bytes: bytes,
    *,
    reference_nm: float | None = None,
    peak_window: tuple[float, float] | None = None,
) -> dict:
    decoded = decode_frame(frame_bytes)
    if not decoded.crc_ok:
        raise ValueError("cannot compute metrics for invalid CRC frame")
    metrics = compute_metrics(
        decoded,
        site_reference_nm=reference_nm,
        site_peak_window=peak_window,
    )
    return {
        "type": "scan",
        "instrument": metrics["instrument"],
        "session": metrics["session"],
        "sequence": metrics["sequence"],
        "source_sha256": content_sha256(frame_bytes),
        "calibration_revision": metrics["calibration_revision"],
        "sample_count": metrics["sample_count"],
        "peak_centroid_nm": metrics["peak_centroid_nm"],
        "drift_pm": metrics["drift_pm"],
        "integrated_intensity": metrics["integrated_intensity"],
        "baseline_noise": metrics["baseline_noise"],
    }


def fragment_name(source_sha256: str) -> str:
    return f"{source_sha256}.json"


def write_fragment(results_dir: Path, record: dict) -> Path:
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / fragment_name(record["source_sha256"])
    path.write_text(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    return path


def manifest_line(record: dict) -> str:
    return "\t".join(
        [
            record["source_sha256"],
            record["instrument"],
            record["session"],
            str(record["sequence"]),
            fragment_name(record["source_sha256"]),
        ]
    )


def write_manifest(manifest_path: Path, records: Iterable[dict]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [manifest_line(r) for r in records]
    manifest_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def write_drift_jsonl(path: Path, records: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sorted_records = sorted(records, key=lambda r: (r["instrument"], r["session"], r["sequence"]))
    text = "".join(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n" for r in sorted_records)
    path.write_text(text, encoding="utf-8")


def reset_spool_dirs(data_root: Path, output_root: Path) -> None:
    for sub in ("inbox", "work", "quarantine", "archive", "state/results"):
        target = data_root / sub
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True, exist_ok=True)
    manifest = data_root / "state" / "manifest.tsv"
    if manifest.exists():
        manifest.unlink()
    if output_root.exists():
        for entry in output_root.iterdir():
            if entry.is_file():
                entry.unlink()
            elif entry.is_dir():
                shutil.rmtree(entry)
    else:
        output_root.mkdir(parents=True, exist_ok=True)


def restore_pristine_seed(data_root: Path) -> None:
    # Restore bundled visible spool files so immutable checksum tests stay valid.
    bundle = Path("/seed-data")
    if not bundle.is_dir():
        return
    for sub in ("inbox", "work"):
        src_dir = bundle / sub
        if not src_dir.is_dir():
            continue
        dst_dir = data_root / sub
        dst_dir.mkdir(parents=True, exist_ok=True)
        for src in sorted(src_dir.iterdir()):
            if src.is_file():
                shutil.copy2(src, dst_dir / src.name)


def write_inbox_frame(data_root: Path, name: str, frame_bytes: bytes) -> Path:
    path = data_root / "inbox" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(frame_bytes)
    return path


def write_work_frame(data_root: Path, name: str, frame_bytes: bytes) -> Path:
    path = data_root / "work" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(frame_bytes)
    return path


def visible_spc07_r11_even() -> bytes:
    samples = synthetic_peak_samples(256, baseline_slope=0.45, peak_center_px=127.0, noise_seed=11)
    return build_frame(
        FrameSpec(
            revision=1,
            flags=0,
            instrument="SPC07",
            session="CAL2024",
            sequence=101,
            acq_unix=1_700_000_100,
            samples=samples,
            calibration_revision=11,
            temp_centi_c=2015,
        )
    )


def visible_spc07_r17_odd() -> bytes:
    samples = synthetic_peak_samples(257, baseline_slope=0.52, peak_center_px=130.0, noise_seed=17)
    for idx in (0, 1, 64, 128, 256):
        samples[idx] = [0, 1, 2047, 2048, 4095][idx % 5]
    return build_frame(
        FrameSpec(
            revision=1,
            flags=0,
            instrument="SPC07",
            session="CAL2024",
            sequence=102,
            acq_unix=1_700_000_200,
            samples=samples,
            calibration_revision=17,
            temp_centi_c=1998,
        )
    )


def visible_spc12_r17_reversed_masked() -> bytes:
    samples = synthetic_peak_samples(256, baseline_slope=0.38, peak_center_px=140.0, peak_width_px=10.0, noise_seed=23)
    return build_frame(
        FrameSpec(
            revision=2,
            flags=0x01 | 0x02 | 0x04,
            instrument="SPC12",
            session="NIGHT01",
            sequence=7,
            acq_unix=1_700_000_300,
            samples=samples,
            calibration_revision=17,
            temp_centi_c=2050,
            masked_pixels=[64, 192],
        )
    )


def visible_corrupt_crc() -> bytes:
    samples = synthetic_peak_samples(128, noise_seed=31)
    return build_frame(
        FrameSpec(
            revision=2,
            flags=0x04,
            instrument="SPC07",
            session="CAL2024",
            sequence=999,
            acq_unix=1_700_000_400,
            samples=samples,
            calibration_revision=17,
            corrupt_crc=True,
        )
    )


def visible_interrupted_r17() -> bytes:
    samples = synthetic_peak_samples(256, baseline_slope=0.41, peak_center_px=125.0, noise_seed=41)
    return build_frame(
        FrameSpec(
            revision=2,
            flags=0x04,
            instrument="SPC07",
            session="CAL2024",
            sequence=103,
            acq_unix=1_700_000_150,
            samples=samples,
            calibration_revision=17,
            temp_centi_c=2005,
        )
    )


def revision1_odd_extremes_frame() -> bytes:
    samples = synthetic_peak_samples(257, baseline_slope=0.55, peak_center_px=132.0, noise_seed=0x2A11)
    edge_vals = (0, 1, 2047, 2048, 4095)
    for i in range(257):
        if i % 17 == 0:
            samples[i] = edge_vals[i % len(edge_vals)]
    return build_frame(
        FrameSpec(
            revision=1,
            flags=0,
            instrument="SPC07",
            session="EDGE01",
            sequence=1,
            acq_unix=1_700_100_000,
            samples=samples,
            calibration_revision=17,
        )
    )


def revision2_delta_escape_reverse_frame() -> bytes:
    samples = synthetic_peak_samples(200, baseline_slope=0.33, peak_center_px=95.0, peak_width_px=8.0, noise_seed=0xD377)
    samples[50] = 0
    samples[51] = 2000
    samples[80] = 100
    samples[81] = 3900
    return build_frame(
        FrameSpec(
            revision=2,
            flags=0x01 | 0x04,
            instrument="SPC12",
            session="DELTA1",
            sequence=3,
            acq_unix=1_700_200_000,
            samples=samples,
            calibration_revision=17,
            temp_centi_c=1985,
        )
    )


def masked_hot_pixel_frame() -> bytes:
    samples = synthetic_peak_samples(256, baseline_slope=0.48, peak_center_px=128.0, peak_amp=900.0, noise_seed=0xB0E5)
    samples[128] = 4095
    samples[129] = 4090
    return build_frame(
        FrameSpec(
            revision=2,
            flags=0x02,
            instrument="SPC07",
            session="MASK01",
            sequence=4,
            acq_unix=1_700_300_000,
            samples=samples,
            calibration_revision=17,
            masked_pixels=[128, 129],
        )
    )


def calibration_matrix_frames() -> list[bytes]:
    base = synthetic_peak_samples(256, baseline_slope=0.44, peak_center_px=126.0, noise_seed=0xCA11)
    frames = []
    for idx, (cal_rev, temp_c) in enumerate(((11, 1850), (17, 2150), (11, 2150), (17, 1850)), start=1):
        frames.append(
            build_frame(
                FrameSpec(
                    revision=2,
                    flags=0,
                    instrument="SPC07",
                    session="CALMAT",
                    sequence=idx,
                    acq_unix=1_700_400_000 + idx,
                    samples=list(base),
                    calibration_revision=cal_rev,
                    temp_centi_c=temp_c,
                )
            )
        )
    return frames


def sloped_baseline_frame() -> bytes:
    samples = synthetic_peak_samples(
        256,
        baseline_slope=1.25,
        peak_center_px=128.0,
        peak_width_px=14.0,
        peak_amp=950.0,
        noise_seed=0xBA5E,
    )
    return build_frame(
        FrameSpec(
            revision=2,
            flags=0,
            instrument="SPC07",
            session="SLOPE1",
            sequence=5,
            acq_unix=1_700_500_000,
            samples=samples,
            calibration_revision=17,
            temp_centi_c=2000,
        )
    )


def corrupt_batch_frames() -> dict[str, bytes]:
    good = build_frame(
        FrameSpec(
            revision=1,
            flags=0,
            instrument="SPC07",
            session="MIX01",
            sequence=1,
            acq_unix=1_700_600_000,
            samples=synthetic_peak_samples(200, noise_seed=1),
            calibration_revision=17,
        )
    )
    crc_bad = build_frame(
        FrameSpec(
            revision=2,
            flags=0x04,
            instrument="SPC07",
            session="MIX01",
            sequence=2,
            acq_unix=1_700_600_001,
            samples=synthetic_peak_samples(200, noise_seed=2),
            calibration_revision=17,
            corrupt_crc=True,
        )
    )
    truncated = build_frame(
        FrameSpec(
            revision=1,
            flags=0,
            instrument="SPC07",
            session="MIX01",
            sequence=3,
            acq_unix=1_700_600_002,
            samples=synthetic_peak_samples(200, noise_seed=3),
            calibration_revision=17,
            truncate=40,
        )
    )
    overrun = build_frame(
        FrameSpec(
            revision=2,
            flags=0x04,
            instrument="SPC07",
            session="MIX01",
            sequence=4,
            acq_unix=1_700_600_003,
            samples=synthetic_peak_samples(200, noise_seed=4),
            calibration_revision=17,
        )
    )
    overrun = overrun[: len(overrun) - 8]
    reserved = build_frame(
        FrameSpec(
            revision=2,
            flags=0,
            instrument="SPC07",
            session="MIX01",
            sequence=5,
            acq_unix=1_700_600_004,
            samples=synthetic_peak_samples(200, noise_seed=5),
            calibration_revision=17,
            reserved_flags=0x20,
        )
    )
    return {
        "valid.spz": good,
        "crc-bad.spz": crc_bad,
        "truncated.spz": truncated,
        "overrun.spz": overrun,
        "reserved-flags.spz": reserved,
    }


def seeded_matrix_frame(seed: int) -> bytes:
    n = 180 + (seed & 0x3F)
    revision = 1 if (seed & 1) else 2
    flags = 0
    if revision == 2 and (seed & 0x10):
        flags |= 0x04
    if seed & 0x20:
        flags |= 0x01
    masked = []
    if seed & 0x40:
        masked = [32, 96]
        flags |= 0x02
    cal_rev = 11 if (seed & 0x08) else 17
    temp_c = 1900 + (seed % 300)
    samples = synthetic_peak_samples(
        n,
        baseline_slope=0.3 + (seed % 7) * 0.05,
        peak_center_px=90.0 + (seed % 50),
        peak_width_px=8.0 + (seed % 5),
        peak_amp=700.0 + (seed % 200),
        noise_seed=seed,
    )
    return build_frame(
        FrameSpec(
            revision=revision,
            flags=flags,
            instrument="SPC12" if (seed & 0x100) else "SPC07",
            session=f"S{seed & 0xFFFF:04X}",
            sequence=(seed >> 8) & 0xFFFF,
            acq_unix=1_701_000_000 + seed,
            samples=samples,
            calibration_revision=cal_rev,
            temp_centi_c=temp_c,
            masked_pixels=masked or None,
        )
    )


def deploy_visible_default_spool(data_root: Path, output_root: Path) -> dict[str, bytes]:
    reset_spool_dirs(data_root, output_root)
    frames = {
        "spc07-r11-even.spz": visible_spc07_r11_even(),
        "spc07-r17-odd.spz": visible_spc07_r17_odd(),
        "spc12-r17-reversed.spz": visible_spc12_r17_reversed_masked(),
        "corrupt-crc.spz": visible_corrupt_crc(),
    }
    for name, blob in frames.items():
        write_inbox_frame(data_root, name, blob)
    interrupted = visible_interrupted_r17()
    write_work_frame(data_root, "interrupted-r17.processing", interrupted)
    frames["interrupted-r17.processing"] = interrupted
    return frames


def deploy_stale_uncommitted(data_root: Path, output_root: Path) -> tuple[bytes, bytes]:
    reset_spool_dirs(data_root, output_root)
    stale = revision2_delta_escape_reverse_frame()
    fresh = sloped_baseline_frame()
    write_work_frame(data_root, "stale-claim.processing", stale)
    write_inbox_frame(data_root, "fresh-inbox.spz", fresh)
    return stale, fresh


def deploy_committed_unarchived(data_root: Path, output_root: Path) -> dict:
    reset_spool_dirs(data_root, output_root)
    frame = visible_spc07_r11_even()
    record = expected_scan_record(frame)
    write_work_frame(data_root, "committed.processing", frame)
    write_fragment(data_root / "state" / "results", record)
    write_manifest(data_root / "state" / "manifest.tsv", [record])
    return record


def deploy_orphan_partial_output(data_root: Path, output_root: Path) -> tuple[dict, dict]:
    reset_spool_dirs(data_root, output_root)
    committed_frame = visible_spc07_r17_odd()
    orphan_frame = sloped_baseline_frame()
    committed = expected_scan_record(committed_frame)
    orphan = expected_scan_record(orphan_frame)
    write_fragment(data_root / "state" / "results", committed)
    write_fragment(data_root / "state" / "results", orphan)
    write_manifest(data_root / "state" / "manifest.tsv", [committed])
    partial = json.dumps(committed, separators=(",", ":"), sort_keys=True)
    (output_root / "drift.jsonl").write_text(partial[: max(20, len(partial) // 2)], encoding="utf-8")
    return committed, orphan


def deploy_replay_identity_setup(data_root: Path, output_root: Path) -> tuple[bytes, bytes, bytes]:
    reset_spool_dirs(data_root, output_root)
    original = revision1_odd_extremes_frame()
    write_inbox_frame(data_root, "primary.spz", original)
    return original, original, build_frame(
        FrameSpec(
            revision=1,
            flags=0,
            instrument="SPC07",
            session="EDGE01",
            sequence=1,
            acq_unix=1_700_100_001,
            samples=synthetic_peak_samples(257, noise_seed=0xC0FF),
            calibration_revision=17,
        )
    )


def checksum_immutable_files(extra_paths: Iterable[Path] = ()) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in list(IMMUTABLE_PATHS) + list(extra_paths):
        if path.is_file():
            out[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out

WORKER_BIN = "/app/bin/specz-worker"
DATA = Path("/data")
INBOX = DATA / "inbox"
WORK = DATA / "work"
QUARANTINE = DATA / "quarantine"
ARCHIVE = DATA / "archive"
STATE = DATA / "state"
MANIFEST = STATE / "manifest.tsv"
RESULTS = STATE / "results"
OUTPUT = Path("/output")
DRIFT = OUTPUT / "drift.jsonl"
SITE_CONF = Path("/app/config/site.conf")
PRISTINE_CHECKSUMS = Path(__file__).with_name("pristine_checksums.json")

TOL_PEAK_NM = 2e-6
TOL_DRIFT_PM = 0.002
TOL_INTENSITY_REL = 2e-7
TOL_NOISE_REL = 2e-6

SCAN_FIELDS = (
    "type",
    "instrument",
    "session",
    "sequence",
    "source_sha256",
    "calibration_revision",
    "sample_count",
    "peak_centroid_nm",
    "drift_pm",
    "integrated_intensity",
    "baseline_noise",
)


def reset_data_and_output() -> None:
    """Clear writable spool and output paths before each isolated test."""
    reset_spool_dirs(DATA, OUTPUT)


def run_worker(*, env: dict[str, str] | None = None, extra_args: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    """Invoke the public worker binary and capture stdout/stderr."""
    merged = os.environ.copy()
    if env:
        merged.update(env)
    cmd = [WORKER_BIN, "--once"]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True, env=merged, check=False)


def run_inspect(frame_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([WORKER_BIN, "inspect", str(frame_path)], capture_output=True, text=True, check=False)


def parse_lifecycle_jsonl(stdout: str) -> list[dict[str, Any]]:
    """Parse worker lifecycle events emitted on stdout as JSON Lines."""
    events: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        events.append(json.loads(line))
    return events


def load_drift_records() -> list[dict[str, Any]]:
    assert DRIFT.is_file(), "expected /output/drift.jsonl"
    records = []
    for line in DRIFT.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def filesystem_snapshot() -> dict[str, str]:
    """Hash every file under /data and /output for side-effect checks."""
    snap: dict[str, str] = {}
    for root in (DATA, OUTPUT):
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file():
                snap[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snap


def _close(a: float, b: float, *, abs_tol: float, rel_tol: float = 0.0) -> bool:
    if not (math.isfinite(a) and math.isfinite(b)):
        return False
    diff = abs(a - b)
    if diff <= abs_tol:
        return True
    scale = max(abs(a), abs(b), 1.0)
    return diff <= rel_tol * scale


def compare_scan_records(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    """Compare one scan record against the independent reference within tolerances."""
    for key in SCAN_FIELDS:
        assert key in actual, f"missing field {key}"
    assert actual["type"] == "scan"
    assert actual["instrument"] == expected["instrument"]
    assert actual["session"] == expected["session"]
    assert actual["sequence"] == expected["sequence"]
    assert actual["source_sha256"] == expected["source_sha256"]
    assert actual["calibration_revision"] == expected["calibration_revision"]
    assert actual["sample_count"] == expected["sample_count"]
    assert _close(actual["peak_centroid_nm"], expected["peak_centroid_nm"], abs_tol=TOL_PEAK_NM)
    assert _close(actual["drift_pm"], expected["drift_pm"], abs_tol=TOL_DRIFT_PM)
    assert _close(
        actual["integrated_intensity"],
        expected["integrated_intensity"],
        abs_tol=TOL_INTENSITY_REL,
        rel_tol=TOL_INTENSITY_REL,
    )
    assert _close(
        actual["baseline_noise"],
        expected["baseline_noise"],
        abs_tol=TOL_NOISE_REL,
        rel_tol=TOL_NOISE_REL,
    )


def assert_lifecycle_well_formed(events: list[dict[str, Any]]) -> dict[str, int]:
    """Validate lifecycle JSONL envelope and return stop-event counters."""
    assert events, "worker produced no lifecycle events"
    assert events[0].get("type") == "worker/start"
    assert events[-1].get("type") == "worker/stop"
    stop = events[-1]
    counts = {
        "processed": int(stop.get("processed", -1)),
        "skipped": int(stop.get("skipped", -1)),
        "quarantined": int(stop.get("quarantined", -1)),
    }
    file_events = [e for e in events[1:-1] if e.get("type") in {"processed", "skipped", "quarantined"}]
    processed = sum(1 for e in file_events if e["type"] == "processed")
    skipped = sum(1 for e in file_events if e["type"] == "skipped")
    quarantined = sum(1 for e in file_events if e["type"] == "quarantined")
    assert counts["processed"] == processed
    assert counts["skipped"] == skipped
    assert counts["quarantined"] == quarantined
    return counts


def expected_records_for_frames(frames: dict[str, bytes]) -> list[dict[str, Any]]:
    records = [expected_scan_record(blob) for blob in frames.values() if decode_frame(blob).crc_ok]
    return sorted(records, key=lambda r: (r["instrument"], r["session"], r["sequence"]))


@pytest.fixture(autouse=True)
def _isolate_spool() -> None:
    reset_data_and_output()


def test_default_spool_end_to_end() -> None:
    """Process the visible inbox plus stale work and verify schemas, ordering, and quarantine."""
    frames = deploy_visible_default_spool(DATA, OUTPUT)
    expected = expected_records_for_frames(frames)
    proc = run_worker()
    assert proc.returncode == 0, proc.stderr
    events = parse_lifecycle_jsonl(proc.stdout)
    counts = assert_lifecycle_well_formed(events)
    assert counts["quarantined"] >= 1
    records = load_drift_records()
    assert len(records) == len(expected)
    for actual, exp in zip(records, expected):
        compare_scan_records(actual, exp)
    assert list(QUARANTINE.glob("*.spz"))


def test_revision1_raw12_odd_count_and_extremes() -> None:
    """Revision-1 odd sample counts and edge ADC values must decode and analyze correctly."""
    frame = revision1_odd_extremes_frame()
    path = write_inbox_frame(DATA, "odd-edge.spz", frame)
    inspect = run_inspect(path)
    assert inspect.returncode == 0, inspect.stderr
    meta = json.loads(inspect.stdout)
    assert meta["version"] == 1
    assert meta["crc_ok"] is True
    assert meta["sample_count"] == 257
    proc = run_worker()
    assert proc.returncode == 0, proc.stderr
    records = load_drift_records()
    assert len(records) == 1
    compare_scan_records(records[0], expected_scan_record(frame))


def test_revision2_delta_escape_and_reverse_order() -> None:
    """Delta escapes and post-decode reversal must be applied in the documented order."""
    frame = revision2_delta_escape_reverse_frame()
    write_inbox_frame(DATA, "delta-reverse.spz", frame)
    proc = run_worker()
    assert proc.returncode == 0, proc.stderr
    records = load_drift_records()
    assert len(records) == 1
    compare_scan_records(records[0], expected_scan_record(frame))
    assert not list(QUARANTINE.glob("*.spz"))


def test_optional_mask_moves_payload_and_excludes_hot_pixels() -> None:
    """Masked-pixel headers must shift payload offsets and exclude hot pixels from metrics."""
    frame = masked_hot_pixel_frame()
    path = write_inbox_frame(DATA, "masked-hot.spz", frame)
    inspect = run_inspect(path)
    assert inspect.returncode == 0, inspect.stderr
    meta = json.loads(inspect.stdout)
    decoded = decode_frame(frame)
    assert meta["masked_pixels"] == decoded.meta.masked_pixels
    proc = run_worker()
    assert proc.returncode == 0, proc.stderr
    records = load_drift_records()
    compare_scan_records(records[0], expected_scan_record(frame))


def test_calibration_revision_temperature_and_zero_based_pixels() -> None:
    """Frame-selected calibration revision and centi-Celsius temperature must affect drift."""
    frames = calibration_matrix_frames()
    for idx, blob in enumerate(frames):
        write_inbox_frame(DATA, f"cal-{idx}.spz", blob)
    proc = run_worker()
    assert proc.returncode == 0, proc.stderr
    records = load_drift_records()
    expected = [expected_scan_record(blob) for blob in frames]
    assert len(records) == len(expected)
    for actual, exp in zip(records, expected):
        compare_scan_records(actual, exp)
    by_rev = {r["calibration_revision"]: r["drift_pm"] for r in records}
    assert by_rev["11"] != by_rev["17"]


def test_sloped_baseline_wavelength_centroid_and_trapezoidal_intensity() -> None:
    """Sloped baseline regression and wavelength-space integration must match the reference."""
    frame = sloped_baseline_frame()
    write_inbox_frame(DATA, "sloped.spz", frame)
    proc = run_worker()
    assert proc.returncode == 0, proc.stderr
    records = load_drift_records()
    compare_scan_records(records[0], expected_scan_record(frame))
    for key in ("peak_centroid_nm", "integrated_intensity", "baseline_noise"):
        assert math.isfinite(records[0][key])


def test_corrupt_and_truncated_frames_are_quarantined_without_aborting_batch() -> None:
    """Invalid frames are quarantined while valid work still completes with exit code zero."""
    batch = corrupt_batch_frames()
    for name, blob in batch.items():
        write_inbox_frame(DATA, name, blob)
    proc = run_worker()
    assert proc.returncode == 0, proc.stderr
    events = parse_lifecycle_jsonl(proc.stdout)
    counts = assert_lifecycle_well_formed(events)
    assert counts["processed"] == 1
    assert counts["quarantined"] == 4
    records = load_drift_records()
    assert len(records) == 1
    compare_scan_records(records[0], expected_scan_record(batch["valid.spz"]))


def test_stale_uncommitted_work_is_reprocessed_once() -> None:
    """A claimed .processing file without commit state must be recovered and archived once."""
    stale, fresh = deploy_stale_uncommitted(DATA, OUTPUT)
    proc = run_worker()
    assert proc.returncode == 0, proc.stderr
    events = parse_lifecycle_jsonl(proc.stdout)
    counts = assert_lifecycle_well_formed(events)
    assert counts["processed"] == 2
    records = load_drift_records()
    assert len(records) == 2
    expected = sorted(
        [expected_scan_record(stale), expected_scan_record(fresh)],
        key=lambda r: (r["instrument"], r["session"], r["sequence"]),
    )
    for actual, exp in zip(records, expected):
        compare_scan_records(actual, exp)
    assert list(ARCHIVE.glob("*.processing")) or list(ARCHIVE.glob("*.spz"))


def test_committed_but_unarchived_work_is_not_duplicated() -> None:
    """Committed manifest entries must not produce duplicate scans when source remains in work."""
    record = deploy_committed_unarchived(DATA, OUTPUT)
    proc = run_worker()
    assert proc.returncode == 0, proc.stderr
    events = parse_lifecycle_jsonl(proc.stdout)
    counts = assert_lifecycle_well_formed(events)
    assert counts["processed"] == 0
    assert counts["skipped"] >= 1
    records = load_drift_records()
    assert len(records) == 1
    compare_scan_records(records[0], record)
    assert list(ARCHIVE.glob("*"))


def test_orphan_fragment_and_partial_output_are_reconciled() -> None:
    """Orphan fragments and truncated output must be reconciled into a valid sorted manifest view."""
    committed, orphan = deploy_orphan_partial_output(DATA, OUTPUT)
    proc = run_worker()
    assert proc.returncode == 0, proc.stderr
    records = load_drift_records()
    expected = sorted([committed, orphan], key=lambda r: (r["instrument"], r["session"], r["sequence"]))
    assert len(records) == len(expected)
    for actual, exp in zip(records, expected):
        compare_scan_records(actual, exp)
    assert MANIFEST.is_file()
    for line in DRIFT.read_text(encoding="utf-8").splitlines():
        json.loads(line)


def test_replay_identity_uses_hash_and_logical_scan_key() -> None:
    """Identical content replays are skipped and logical-key conflicts are quarantined."""
    original, _, conflict = deploy_replay_identity_setup(DATA, OUTPUT)
    first = run_worker()
    assert first.returncode == 0, first.stderr
    before = DRIFT.read_bytes()
    write_inbox_frame(DATA, "replay-copy.spz", original)
    write_inbox_frame(DATA, "conflict.spz", conflict)
    second = run_worker()
    assert second.returncode == 0, second.stderr
    events = parse_lifecycle_jsonl(second.stdout)
    counts = assert_lifecycle_well_formed(events)
    assert counts["skipped"] >= 1
    assert counts["quarantined"] >= 1
    assert DRIFT.read_bytes() == before


def test_empty_spool_exits_quickly_without_duplicating_output() -> None:
    """An empty inbox and work queue must finish promptly with zero-count lifecycle events."""
    frame = revision1_odd_extremes_frame()
    write_inbox_frame(DATA, "batch-a.spz", frame)
    first = run_worker()
    assert first.returncode == 0, first.stderr
    before_bytes = DRIFT.read_bytes()
    before_records = load_drift_records()
    assert not list(INBOX.glob("*.spz"))
    assert not list(WORK.glob("*.processing"))

    second = subprocess.run(
        [WORKER_BIN, "--once"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert second.returncode == 0, second.stderr
    events = parse_lifecycle_jsonl(second.stdout)
    counts = assert_lifecycle_well_formed(events)
    assert counts == {"processed": 0, "skipped": 0, "quarantined": 0}
    assert DRIFT.read_bytes() == before_bytes
    assert load_drift_records() == before_records


def test_second_run_is_idempotent_and_new_scans_preserve_history() -> None:
    """Repeated runs are byte-stable and incremental scans append without reordering history."""
    frame_a = revision1_odd_extremes_frame()
    frame_b = sloped_baseline_frame()
    write_inbox_frame(DATA, "batch-a.spz", frame_a)
    write_inbox_frame(DATA, "batch-b.spz", frame_b)
    first = run_worker()
    assert first.returncode == 0, first.stderr
    first_hash = DRIFT.read_bytes()
    second = run_worker()
    assert second.returncode == 0, second.stderr
    assert DRIFT.read_bytes() == first_hash
    frame_c = revision2_delta_escape_reverse_frame()
    write_inbox_frame(DATA, "batch-c.spz", frame_c)
    third = run_worker()
    assert third.returncode == 0, third.stderr
    records = load_drift_records()
    assert len(records) == 3
    expected = sorted(
        [expected_scan_record(frame_a), expected_scan_record(frame_b), expected_scan_record(frame_c)],
        key=lambda r: (r["instrument"], r["session"], r["sequence"]),
    )
    for actual, exp in zip(records, expected):
        compare_scan_records(actual, exp)


def test_config_precedence_and_frame_revision_are_preserved() -> None:
    """Environment and site overrides must win over defaults without rewriting frame revision."""
    frame = visible_spc07_r11_even()
    write_inbox_frame(DATA, "config-frame.spz", frame)
    site_backup = SITE_CONF.read_text(encoding="utf-8") if SITE_CONF.exists() else ""
    try:
        SITE_CONF.parent.mkdir(parents=True, exist_ok=True)
        SITE_CONF.write_text(
            "reference_nm=656.500000\npeak_window_nm=655.80,656.95\ninstrument=SPC07\n",
            encoding="utf-8",
        )
        proc = run_worker(env={"SPECZ_REFERENCE_NM": "656.100000", "SPECZ_CONFIG": str(SITE_CONF)})
        assert proc.returncode == 0, proc.stderr
        records = load_drift_records()
        assert records[0]["calibration_revision"] == "11"
        assert _close(
            records[0]["peak_centroid_nm"],
            expected_scan_record(frame, reference_nm=656.500000, peak_window=(655.80, 656.95))[
                "peak_centroid_nm"
            ],
            abs_tol=TOL_PEAK_NM,
        )
    finally:
        if site_backup:
            SITE_CONF.write_text(site_backup, encoding="utf-8")


def test_inspect_subcommand_remains_side_effect_free_and_compatible() -> None:
    """inspect emits the documented JSON schema without mutating spool or output state."""
    frames = {
        "r1.spz": revision1_odd_extremes_frame(),
        "r2.spz": revision2_delta_escape_reverse_frame(),
    }
    paths = {name: write_inbox_frame(DATA, name, blob) for name, blob in frames.items()}
    before = filesystem_snapshot()
    for path, blob in zip(paths.values(), frames.values()):
        proc = run_inspect(path)
        assert proc.returncode == 0, proc.stderr
        meta = json.loads(proc.stdout)
        decoded = decode_frame(blob)
        assert meta["version"] == decoded.meta.revision
        assert meta["instrument"] == decoded.meta.instrument
        assert meta["session"] == decoded.meta.session
        assert meta["sequence"] == decoded.meta.sequence
        assert meta["sample_count"] == decoded.meta.sample_count
        assert meta["calibration_revision"] == str(decoded.meta.calibration_revision)
        assert meta["masked_pixels"] == decoded.meta.masked_pixels
        assert meta["crc_ok"] == decoded.crc_ok
    after = filesystem_snapshot()
    assert before == after


def test_output_is_byte_stable_across_input_order_and_locale() -> None:
    """Identical logical batches produce byte-identical output regardless of creation order or locale."""
    frame_a = revision1_odd_extremes_frame()
    frame_b = sloped_baseline_frame()

    def run_ordered(order: list[tuple[str, bytes]], locale: str) -> bytes:
        reset_data_and_output()
        for name, blob in order:
            write_inbox_frame(DATA, name, blob)
        proc = run_worker(env={"LC_ALL": locale, "LANG": locale})
        assert proc.returncode == 0, proc.stderr
        return DRIFT.read_bytes()

    forward = run_ordered([("z-last.spz", frame_b), ("a-first.spz", frame_a)], "C")
    reverse = run_ordered([("a-first.spz", frame_a), ("z-last.spz", frame_b)], "de_DE.UTF-8")
    assert forward == reverse


def test_seeded_hidden_fixture_matrix_prevents_static_answers() -> None:
    """Fixed hidden seeds must exercise broad encoder and analysis combinations."""
    for seed in HIDDEN_SEEDS:
        reset_data_and_output()
        frame = seeded_matrix_frame(seed)
        write_inbox_frame(DATA, f"seed-{seed:04x}.spz", frame)
        proc = run_worker()
        assert proc.returncode == 0, proc.stderr
        records = load_drift_records()
        assert len(records) == 1
        compare_scan_records(records[0], expected_scan_record(frame))


def test_immutable_source_records_remain_pristine() -> None:
    """Authoritative notebook, definition, and bundled frames must not be modified by the agent."""
    restore_pristine_seed(DATA)
    checksums = json.loads(PRISTINE_CHECKSUMS.read_text(encoding="utf-8"))
    if not checksums:
        pytest.skip("pristine checksums not populated yet")
    for path_str, expected in checksums.items():
        path = Path(path_str)
        assert path.is_file(), f"missing immutable record {path}"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == expected, f"immutable record changed: {path}"
