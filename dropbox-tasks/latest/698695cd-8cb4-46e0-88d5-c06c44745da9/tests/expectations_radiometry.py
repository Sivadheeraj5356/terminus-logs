"""Verifier-only radiometry expectations (mounted under /tests, not /app)."""

from __future__ import annotations

import hashlib
import json
import math
import shutil
import struct
import subprocess
import zlib
from pathlib import Path
from typing import Any


def read_gray16_png(path: Path) -> tuple[int, int, list[int]]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos = 8
    width = height = bit_depth = 0
    color_type = 0
    idat = b""
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        pos += 4
        ctype = data[pos : pos + 4]
        pos += 4
        chunk = data[pos : pos + length]
        pos += length + 4
        if ctype == b"IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", chunk)
        elif ctype == b"IDAT":
            idat += chunk
        elif ctype == b"IEND":
            break
    if bit_depth != 16 or color_type != 0:
        raise ValueError(f"expected 16-bit grayscale: {path}")
    raw = zlib.decompress(idat)
    out: list[int] = []
    stride = 1 + width * 2
    for y in range(height):
        row = raw[y * stride + 1 : y * stride + 1 + width * 2]
        for x in range(width):
            out.append(struct.unpack(">H", row[x * 2 : x * 2 + 2])[0])
    return width, height, out


def directory_digest(root: Path) -> str:
    files = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    h = hashlib.sha256()
    for rel in files:
        h.update(rel.encode())
        h.update(b"\n")
        h.update((root / rel).read_bytes())
        h.update(b"\n")
    return h.hexdigest()


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def terraform_constants(project_root: Path) -> tuple[dict[str, Any], str]:
    manifest = json.loads((project_root / "vendor/hashicorp/terraform_manifest.json").read_text())
    module = Path(manifest.get("module_path", "/usr/local/share/calibration_tf"))
    out = subprocess.check_output(
        ["terraform", "-chdir=" + str(module), "output", "-json", "calibration_constants"],
        text=True,
    )
    tf_manifest = json.loads((project_root / "vendor/hashicorp/terraform_manifest.json").read_text())
    return json.loads(out), tf_manifest["terraform_version"]


def erode_mask(mask: list[bool], width: int, height: int, px: int) -> list[bool]:
    cur = mask[:]
    for _ in range(px):
        nxt = cur[:]
        for y in range(height):
            for x in range(width):
                i = y * width + x
                if not cur[i]:
                    continue
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = y + dy, x + dx
                        if ny < 0 or ny >= height or nx < 0 or nx >= width:
                            nxt[i] = False
                            break
                        if not cur[ny * width + nx]:
                            nxt[i] = False
                            break
        cur = nxt
    return cur


def trimmed_mean(vals: list[float], fraction: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    trim = int(len(s) * fraction)
    if trim * 2 >= len(s):
        return sum(s) / len(s)
    core = s[trim : len(s) - trim]
    return sum(core) / len(core)


def fit_cooling(times: list[float], temps: list[float]) -> dict[str, float]:
    if len(times) < 2:
        ambient = temps[-1] if temps else 0.0
        return {
            "ambient_temperature_c": ambient,
            "amplitude_c": 0.0,
            "cooling_rate_k": 0.0,
            "half_life_s": 0.0,
            "residual_rms_c": 0.0,
            "max_abs_residual_c": 0.0,
            "start_temperature_c": temps[0] if temps else 0.0,
            "end_temperature_c": temps[-1] if temps else 0.0,
        }
    ambient = temps[-1]
    sw = sx = sy = sxx = sxy = 0.0
    for t, temp in zip(times, temps):
        y = temp - ambient
        if y <= 0:
            continue
        w = 1.0 / (y + 1e-6)
        ly = math.log(y)
        sw += w
        sx += w * t
        sy += w * ly
        sxx += w * t * t
        sxy += w * t * ly
    if sw == 0:
        k = 0.0
        amp = 0.0
    else:
        denom = sw * sxx - sx * sx
        k = -(sw * sxy - sx * sy) / denom if denom else 0.0
        k = max(k, 0.0)
        ln_a = (sy - (-k) * sx) / sw
        amp = math.exp(ln_a) if k > 1e-12 else (temps[0] - ambient)
    rss = 0.0
    max_abs = 0.0
    for t, temp in zip(times, temps):
        pred = ambient + amp * math.exp(-k * t)
        res = temp - pred
        rss += res * res
        max_abs = max(max_abs, abs(res))
    rms = math.sqrt(rss / len(times))
    half = math.log(2) / k if k > 1e-12 else 0.0
    return {
        "ambient_temperature_c": ambient,
        "amplitude_c": amp,
        "cooling_rate_k": k,
        "half_life_s": half,
        "residual_rms_c": rms,
        "max_abs_residual_c": max_abs,
        "start_temperature_c": temps[0],
        "end_temperature_c": temps[-1],
    }


def run_pipeline(project_root: Path, input_dir: Path) -> dict[str, Any]:
    manifest = load_manifest(input_dir / "manifest.json")
    constants, tf_version = terraform_constants(project_root)
    digest = directory_digest(input_dir)

    w, h, dark = read_gray16_png(input_dir / manifest["calrefs"]["dark"])
    _, _, flat = read_gray16_png(input_dir / manifest["calrefs"]["flat"])
    _, _, roi = read_gray16_png(input_dir / manifest["calrefs"]["roi_mask"])
    _, _, dead = read_gray16_png(input_dir / manifest["calrefs"]["dead_pixel_mask"])

    per_pixel_dark = [float(v) for v in dark]
    flat_gain = [float(v) / 12000.0 if v else 1.0 for v in flat]
    roi_mask = [v >= 32768 for v in roi]
    dead_mask = [v >= 32768 for v in dead]
    combined = [a and b for a, b in zip(roi_mask, dead_mask)]
    active = erode_mask(combined, w, h, manifest["mask_erosion_px"])

    frame_rows: list[dict[str, Any]] = []
    session_fits: list[dict[str, Any]] = []
    sessions_out: list[dict[str, Any]] = []
    total_frames = 0
    residual_sum = 0.0

    for sess in sorted(manifest["sessions"], key=lambda s: s["session_id"]):
        cam = constants[sess["camera_id"]]
        frames = sorted(sess["frames"], key=lambda f: (f["timestamp_s"], f["frame_id"]))
        times: list[float] = []
        temps: list[float] = []
        usable_frames = 0
        pixel_sum = 0.0

        for fr in frames:
            _, _, raw = read_gray16_png(input_dir / fr["path"])
            dark_t = cam["dark_offset_base"] + cam["dark_offset_rate"] * fr["timestamp_s"]
            temp_vals: list[float] = []
            raw_vals: list[int] = []
            for i, rv in enumerate(raw):
                if not active[i]:
                    continue
                if rv >= manifest["saturation_dn"]:
                    continue
                if rv < manifest["noise_floor_dn"]:
                    continue
                linearized = (rv - dark_t - per_pixel_dark[i]) / flat_gain[i]
                temp_vals.append(
                    cam["gain"] * linearized + cam["offset"] + cam["emissivity_correction"]
                )
                raw_vals.append(rv)

            trimmed = trimmed_mean(temp_vals, manifest["trim_fraction"])
            raw_min = min(raw_vals) if raw_vals else 0
            raw_max = max(raw_vals) if raw_vals else 0
            usable = len(temp_vals)
            masked = sum(1 for m in active if not m)
            frac = masked / len(active) if active else 0.0
            sat = sum(1 for i, rv in enumerate(raw) if active[i] and rv >= manifest["saturation_dn"])

            frame_rows.append(
                {
                    "session_id": sess["session_id"],
                    "frame_id": fr["frame_id"],
                    "timestamp_s": fr["timestamp_s"],
                    "raw_min": raw_min,
                    "raw_max": raw_max,
                    "usable_pixels": usable,
                    "trimmed_mean_c": trimmed,
                    "mask_fraction": frac,
                    "saturated_pixels": sat,
                }
            )
            if usable > 0:
                usable_frames += 1
                pixel_sum += usable
                times.append(fr["timestamp_s"])
                temps.append(trimmed)
            total_frames += 1

        fit = fit_cooling(times, temps)
        session_fits.append(
            {
                "session_id": sess["session_id"],
                "ambient_temperature_c": fit["ambient_temperature_c"],
                "amplitude_c": fit["amplitude_c"],
                "cooling_rate_k": fit["cooling_rate_k"],
                "half_life_s": fit["half_life_s"],
                "residual_rms_c": fit["residual_rms_c"],
            }
        )
        mean_pixels = pixel_sum / usable_frames if usable_frames else 0.0
        sessions_out.append(
            {
                "session_id": sess["session_id"],
                "camera_id": sess["camera_id"],
                "frame_count": len(frames),
                "usable_frame_count": usable_frames,
                "start_temperature_c": fit["start_temperature_c"],
                "end_temperature_c": fit["end_temperature_c"],
                "ambient_temperature_c": fit["ambient_temperature_c"],
                "cooling_rate_k": fit["cooling_rate_k"],
                "half_life_s": fit["half_life_s"],
                "residual_rms_c": fit["residual_rms_c"],
                "max_abs_residual_c": fit["max_abs_residual_c"],
                "mean_usable_pixels": mean_pixels,
                "flags": [],
            }
        )
        residual_sum += fit["residual_rms_c"]

    report = {
        "schema_version": "1.0",
        "terraform_version": tf_version,
        "input_digest": digest,
        "sessions": sessions_out,
        "global_summary": {
            "session_count": len(sessions_out),
            "total_frames": total_frames,
            "mean_residual_rms_c": residual_sum / max(1, len(sessions_out)),
        },
    }
    frame_rows.sort(key=lambda r: (r["session_id"], r["timestamp_s"], r["frame_id"]))
    session_fits.sort(key=lambda r: r["session_id"])
    return {
        "calibration_report.json": report,
        "intermediate/frame_summaries.jsonl": frame_rows,
        "intermediate/session_fits.jsonl": session_fits,
    }


def close(a: float, b: float, rtol: float = 0.002, atol: float = 0.05) -> bool:
    return abs(a - b) <= max(atol, rtol * max(abs(a), abs(b), 1.0))


def write_gray16_png(path: Path, data: list[int], width: int, height: int) -> None:
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            raw.extend(struct.pack(">H", data[y * width + x]))
    compressed = zlib.compress(bytes(raw), 9)

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 16, 0, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def build_synthetic_input(
    template_input: Path,
    output_input: Path,
    *,
    ambient: float = 23.0,
    amplitude: float = 30.0,
    k: float = 0.02,
    n_frames: int = 8,
) -> None:
    if output_input.exists():
        shutil.rmtree(output_input)
    shutil.copytree(template_input, output_input)
    manifest = json.loads((template_input / "manifest.json").read_text(encoding="utf-8"))
    width, height, _ = read_gray16_png(template_input / manifest["calrefs"]["roi_mask"])
    _, _, dark = read_gray16_png(template_input / manifest["calrefs"]["dark"])
    _, _, flat = read_gray16_png(template_input / manifest["calrefs"]["flat"])
    sess = {"session_id": "synth-one", "camera_id": "cam-ir7", "frames": []}
    for i in range(n_frames):
        t = float(i * 4)
        temp = ambient + amplitude * math.exp(-k * t)
        frame_data = []
        for y in range(height):
            for x in range(width):
                idx = y * width + x
                fg = flat[idx] / 12000.0 if flat[idx] else 1.0
                raw = ((temp - (-273.15) - 1.2) / 0.042) * fg + 1800.0 + dark[idx] + 0.35 * t
                frame_data.append(int(raw))
        fname = f"frames/synth_{i:03d}.png"
        write_gray16_png(output_input / fname, frame_data, width, height)
        sess["frames"].append({"frame_id": f"syn-{i}", "timestamp_s": t, "path": fname})
    manifest["sessions"] = [sess]
    (output_input / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    import sys

    cmd = sys.argv[1]
    if cmd == "pipeline":
        project = Path(sys.argv[2])
        input_dir = Path(sys.argv[3])
        print(json.dumps(run_pipeline(project, input_dir), sort_keys=True))
    elif cmd == "digest":
        print(directory_digest(Path(sys.argv[2])))
    elif cmd == "synth":
        build_synthetic_input(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        raise SystemExit(f"unknown command: {cmd}")
