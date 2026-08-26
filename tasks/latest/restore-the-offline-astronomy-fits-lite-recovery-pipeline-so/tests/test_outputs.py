import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
BIN = APP_ROOT / "bin/mosaicctl"
TOL = 1e-6


class NS:
    def __init__(self, **values):
        self.__dict__.update(values)


@pytest.fixture(scope="session", autouse=True)
def build_tool():
    result = subprocess.run(["make", "-C", "/app/environment", "clean", "all"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert result.returncode == 0, result.stdout + result.stderr
    assert BIN.is_file(), "mosaicctl was not built"


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def run_recover(data: Path, work: Path, check: bool = True):
    work.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([str(BIN), "recover", str(data), str(work)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check:
        assert result.returncode == 0, result.stdout + result.stderr
    return result


def read_tsv(path: Path):
    rows = []
    lines = [line.strip() for line in path.read_text().splitlines() if line.strip() and not line.startswith("#")]
    header = lines[0].split("\t")
    for line in lines[1:]:
        rows.append(dict(zip(header, line.split("\t"))))
    return rows


def parse_config(data: Path):
    raw = {row["key"]: row["value"] for row in read_tsv(data / "run-config.tsv")}
    return NS(
        profile=raw["profile"],
        epoch=raw["epoch"],
        width=int(raw["width"]),
        height=int(raw["height"]),
        crval=(float(raw["crval1"]), float(raw["crval2"])),
        cdelt=(float(raw["cdelt1"]), float(raw["cdelt2"])),
    )


def parse_tile(path: Path):
    fields = {}
    pixels = []
    in_pixels = False
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == "PIXELS":
            in_pixels = True
            continue
        if line == "END_PIXELS":
            in_pixels = False
            continue
        if in_pixels:
            pixels.append([float(value) for value in line.split()])
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key] = value
    primary = (
        float(fields.get("CRVAL1", fields.get("LEGACY_PRIMARY_CRVAL1", "0"))),
        float(fields.get("CRVAL2", fields.get("LEGACY_PRIMARY_CRVAL2", "0"))),
    )
    primary_step = (float(fields.get("CDELT1", "0.1")), float(fields.get("CDELT2", "0.1")))
    alt = (float(fields.get("ALT_CRVAL1", primary[0])), float(fields.get("ALT_CRVAL2", primary[1])))
    alt_step = (float(fields.get("ALT_CDELT1", primary_step[0])), float(fields.get("ALT_CDELT2", primary_step[1])))
    return NS(tile_id=fields["TILE_ID"], mode=fields["WCS_MODE"], primary=primary, primary_step=primary_step, alt=alt, alt_step=alt_step, pixels=pixels)


def authority_rows(data: Path):
    rows = read_tsv(data / "tile-order-authority.tsv")
    return sorted(rows, key=lambda row: int(row["order_index"]))


def selected_weights(data: Path, cfg, order):
    rows = read_tsv(data / "calibration.tsv")
    weights = {}
    for tile_id in order:
        matches = [
            row for row in rows
            if row["tile_id"] == tile_id and row["profile"] == cfg.profile and row["epoch"] == cfg.epoch
        ]
        assert matches, f"expected an active calibration row for {tile_id}"
        first, *rest = matches
        if rest:
            raise AssertionError(f"expected one active calibration row for {tile_id}")
        weights[tile_id] = float(first["weight"])
    return weights


def derive_expected(data: Path):
    cfg = parse_config(data)
    rows = authority_rows(data)
    order = [row["tile_id"] for row in rows]
    phases = {row["tile_id"]: row["phase"] for row in rows}
    weights = selected_weights(data, cfg, order)
    tiles = {tile_id: parse_tile(data / "tiles" / f"{tile_id}.tile") for tile_id in order}
    accum = [[0.0 for _ in range(cfg.width)] for _ in range(cfg.height)]
    wsum = [[0.0 for _ in range(cfg.width)] for _ in range(cfg.height)]
    coverage = [[0 for _ in range(cfg.width)] for _ in range(cfg.height)]
    contributed = {tile_id: 0 for tile_id in order}
    weighted_flux_total = 0.0

    for tile_id in order:
        tile = tiles[tile_id]
        if tile.mode == "ALT":
            crval = tile.alt
            cdelt = tile.alt_step
        else:
            crval = tile.primary
            cdelt = tile.primary_step
        weight = weights[tile_id]
        for j, row in enumerate(tile.pixels):
            for i, pixel in enumerate(row):
                x = round((crval[0] + i * cdelt[0] - cfg.crval[0]) / cfg.cdelt[0])
                y = round((crval[1] + j * cdelt[1] - cfg.crval[1]) / cfg.cdelt[1])
                if 0 <= x < cfg.width and 0 <= y < cfg.height:
                    accum[y][x] += pixel * weight
                    wsum[y][x] += weight
                    coverage[y][x] += 1
                    contributed[tile_id] += 1
                    weighted_flux_total += pixel * weight
    image = [
        [(accum[y][x] / wsum[y][x]) if wsum[y][x] else 0.0 for x in range(cfg.width)]
        for y in range(cfg.height)
    ]
    return NS(
        config=cfg,
        order=order,
        phases=phases,
        weights=weights,
        tiles=tiles,
        coverage=coverage,
        contributed=contributed,
        image=image,
        weighted_flux_total=weighted_flux_total,
        thresholds=[float(row["threshold"]) for row in read_tsv(data / "contour-thresholds.tsv")],
        samples=read_tsv(data / "world-samples.tsv"),
    )


def parse_hdus(path: Path):
    lines = path.read_text().splitlines()
    assert lines[0] == "FITS-LITE 2"
    hdus = {}
    current = None
    chunk = []
    for line in lines[1:]:
        if line.startswith("HDU "):
            assert current is None
            current = line[4:]
            chunk = [line]
        elif line == "END_HDU":
            assert current is not None
            chunk.append(line)
            hdus[current] = chunk
            current = None
            chunk = []
        else:
            assert current is not None
            chunk.append(line)
    assert current is None
    return hdus


def hdu_body(hdus, name):
    assert name in hdus, f"missing HDU {name}"
    return hdus[name][1:-1]


def parse_matrix(body, numeric=float):
    idx = body.index("DATA")
    return [[numeric(value) for value in row.split()] for row in body[idx + 1:]]


def parse_key_values(body):
    values = {}
    for line in body:
        if line == "DATA":
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            values[parts[0]] = parts[1]
    return values


def fnv64(lines):
    value = 1469598103934665603
    for byte in ("\n".join(lines) + "\n").encode():
        value ^= byte
        value = (value * 1099511628211) & ((1 << 64) - 1)
    return f"{value:016x}"


def render_svg(image, thresholds):
    height = len(image)
    width = len(image[0])
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width * 100}" height="{height * 100}" viewBox="0 0 {width} {height}" data-source="mosaic.fits">'
    ]
    for level in thresholds:
        cells = []
        fragments = []
        for y, row in enumerate(image):
            for x, value in enumerate(row):
                if value + 1e-12 >= level:
                    cells.append(f"{x},{y}")
                    fragments.append(f"M{x},{y}h1v1h-1z")
        lines.append(
            f'  <path id="level-{int(level)}" data-threshold="{level:.6f}" data-cells="{";".join(cells)}" d="{"".join(fragments)}"/>'
        )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def assert_matrix_close(observed, expected):
    assert len(observed) == len(expected)
    for y, row in enumerate(expected):
        assert len(observed[y]) == len(row)
        for x, value in enumerate(row):
            assert observed[y][x] == pytest.approx(value, abs=TOL), f"matrix[{y}][{x}]"


def assert_outputs(work: Path, expected, require_rolled_back=False):
    manifest = [line.strip() for line in (work / "tile-order.manifest").read_text().splitlines() if line.strip()]
    assert manifest == expected.order

    hdus = parse_hdus(work / "mosaic.fits")
    assert set(hdus) == {"PRIMARY_IMAGE", "COVERAGE", "CHECKPOINT", "PROVENANCE", "CHECKSUMS"}
    assert_matrix_close(parse_matrix(hdu_body(hdus, "PRIMARY_IMAGE"), float), expected.image)
    assert parse_matrix(hdu_body(hdus, "COVERAGE"), int) == expected.coverage

    checkpoint = parse_key_values(hdu_body(hdus, "CHECKPOINT"))
    assert checkpoint["RUN_PROFILE"] == expected.config.profile
    assert checkpoint["CALIBRATION_EPOCH"] == expected.config.epoch
    assert checkpoint["EXPECTED_TILE_ORDER"].split(",") == expected.order
    assert checkpoint["COMMITTED"].split(",") == expected.order

    provenance_rows = [line.split() for line in hdu_body(hdus, "PROVENANCE") if line.startswith("TILE ")]
    assert [row[1] for row in provenance_rows] == expected.order
    for index, row in enumerate(provenance_rows, start=1):
        _, tile_id, order_index, phase, weight, wcs_mode, contributed = row
        assert int(order_index) == index
        assert phase == expected.phases[tile_id]
        assert float(weight) == pytest.approx(expected.weights[tile_id], abs=TOL)
        assert wcs_mode == expected.tiles[tile_id].mode
        assert int(contributed) == expected.contributed[tile_id]

    checksums = dict(line.split() for line in hdu_body(hdus, "CHECKSUMS"))
    for name in ("PRIMARY_IMAGE", "COVERAGE", "CHECKPOINT", "PROVENANCE"):
        assert checksums[name] == fnv64(hdus[name])

    assert (work / "mosaic-contours.svg").read_text() == render_svg(expected.image, expected.thresholds)

    report = json.loads((work / "reconciliation-report.json").read_text())
    assert report["weighted_flux_total"] == pytest.approx(expected.weighted_flux_total, abs=TOL)
    assert report["calibration_profile"] == expected.config.profile
    assert report["calibration_epoch"] == expected.config.epoch
    assert report["contours_regenerated"]
    assert [sample["sample_id"] for sample in report["samples"]] == [sample["sample_id"] for sample in expected.samples]
    for observed, sample in zip(report["samples"], expected.samples):
        cfg = expected.config
        x = round((float(sample["world_x"]) - cfg.crval[0]) / cfg.cdelt[0])
        y = round((float(sample["world_y"]) - cfg.crval[1]) / cfg.cdelt[1])
        image_value = expected.image[y][x] if 0 <= x < cfg.width and 0 <= y < cfg.height else 0.0
        coverage_value = expected.coverage[y][x] if 0 <= x < cfg.width and 0 <= y < cfg.height else 0
        assert observed["image"] == pytest.approx(image_value, abs=TOL)
        assert observed["coverage"] == coverage_value

    status = json.loads((work / "recovery-status.json").read_text())
    assert status["status"] == "complete"
    assert status["expected_tile_order"] == expected.order
    assert status["committed_tiles"] == expected.order
    assert set(status["published_artifacts"]) == {
        "mosaic.fits",
        "tile-order.manifest",
        "mosaic-contours.svg",
        "reconciliation-report.json",
        "recovery-status.json",
    }
    if require_rolled_back:
        assert {"T030", "T040", "T050"}.issubset(set(status["rolled_back_records"]))


def semantic_snapshot(work: Path):
    return {
        name: (work / name).read_text()
        for name in [
            "mosaic.fits",
            "tile-order.manifest",
            "mosaic-contours.svg",
            "reconciliation-report.json",
            "recovery-status.json",
        ]
    }


def test_fresh_recover_rebuilds_from_data_authorities(tmp_path):
    """A clean work directory is rebuilt entirely from the immutable data authorities."""
    data = tmp_path / "data"
    work = tmp_path / "work"
    copy_tree(APP_ROOT / "data", data)
    run_recover(data, work)
    assert_outputs(work, derive_expected(data))


def test_interrupted_resume_rolls_back_stale_state_and_republishes(tmp_path):
    """The shipped interrupted work state is rolled back and republished coherently."""
    data = tmp_path / "data"
    work = tmp_path / "work"
    copy_tree(APP_ROOT / "data", data)
    copy_tree(APP_ROOT / "work", work)
    run_recover(data, work)
    assert_outputs(work, derive_expected(data), require_rolled_back=True)


def test_recover_is_idempotent_after_completed_publish(tmp_path):
    """Running recovery twice over a completed publish leaves semantic artifacts byte-stable."""
    data = tmp_path / "data"
    work = tmp_path / "work"
    copy_tree(APP_ROOT / "data", data)
    copy_tree(APP_ROOT / "work", work)
    run_recover(data, work)
    first = semantic_snapshot(work)
    run_recover(data, work)
    assert semantic_snapshot(work) == first


def test_changed_authority_order_drives_manifest_checkpoint_and_provenance(tmp_path):
    """Authority order, not stale manifest or directory order, controls published tile order."""
    data = tmp_path / "data"
    work = tmp_path / "work"
    copy_tree(APP_ROOT / "data", data)
    copy_tree(APP_ROOT / "work", work)
    reordered = ["T030", "T010", "T020", "T050", "T040"]
    phases = {"T010": "fresh", "T020": "fresh", "T030": "resume", "T040": "resume", "T050": "resume"}
    lines = ["order_index\ttile_id\tphase"]
    for index, tile_id in enumerate(reordered, start=1):
        lines.append(f"{index}\t{tile_id}\t{phases[tile_id]}")
    (data / "tile-order-authority.tsv").write_text("\n".join(lines) + "\n")
    run_recover(data, work)
    expected = derive_expected(data)
    assert expected.order == reordered
    assert_outputs(work, expected, require_rolled_back=True)


def test_failed_recovery_preserves_last_completed_publish(tmp_path):
    """A failed recovery exits nonzero and does not disturb the previous complete publish."""
    data = tmp_path / "data"
    work = tmp_path / "work"
    copy_tree(APP_ROOT / "data", data)
    run_recover(data, work)
    before = semantic_snapshot(work)
    (data / "calibration.tsv").unlink()
    result = run_recover(data, work, check=False)
    assert result.returncode != 0
    assert semantic_snapshot(work) == before


def test_uniform_active_weight_scaling_preserves_image_and_scales_flux(tmp_path):
    """Uniformly scaling active weights preserves weighted averages and scales flux totals."""
    scratch_names = ["base-data", "scaled-data", "base-work", "scaled-work"]
    base_data, scaled_data, base_work, scaled_work = [tmp_path / name for name in scratch_names]
    copy_tree(APP_ROOT / "data", base_data)
    copy_tree(APP_ROOT / "data", scaled_data)

    rows = read_tsv(scaled_data / "calibration.tsv")
    active = parse_config(scaled_data)
    scale = 3.0
    header = "tile_id\tprofile\tepoch\tweight"
    lines = [header]
    for row in rows:
        weight = float(row["weight"])
        if row["profile"] == active.profile and row["epoch"] == active.epoch:
            weight *= scale
        lines.append(f"{row['tile_id']}\t{row['profile']}\t{row['epoch']}\t{weight:.6f}")
    (scaled_data / "calibration.tsv").write_text("\n".join(lines) + "\n")

    run_recover(base_data, base_work)
    run_recover(scaled_data, scaled_work)
    base_expected = derive_expected(base_data)
    scaled_expected = derive_expected(scaled_data)
    assert_outputs(base_work, base_expected)
    assert_outputs(scaled_work, scaled_expected)
    assert_matrix_close(parse_matrix(hdu_body(parse_hdus(base_work / "mosaic.fits"), "PRIMARY_IMAGE"), float), scaled_expected.image)


def test_support_commands_agree_with_published_artifacts(tmp_path):
    """The audit, render, and sample commands agree with the recovered artifact bundle."""
    data = tmp_path / "data"
    work = tmp_path / "work"
    copy_tree(APP_ROOT / "data", data)
    copy_tree(APP_ROOT / "work", work)
    run_recover(data, work)
    expected = derive_expected(data)
    assert_outputs(work, expected, require_rolled_back=True)

    audit = subprocess.run([str(BIN), "audit", str(work / "mosaic.fits")], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert audit.returncode == 0, audit.stdout + audit.stderr

    scratch_names = ["rendered.svg"]
    rendered = tmp_path / scratch_names[0]
    render = subprocess.run([str(BIN), "render", str(work / "mosaic.fits"), str(rendered)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert render.returncode == 0, render.stdout + render.stderr
    assert rendered.read_text() == (work / "mosaic-contours.svg").read_text()

    for sample in expected.samples:
        result = subprocess.run(
            [str(BIN), "sample", str(work / "mosaic.fits"), sample["world_x"], sample["world_y"]],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        cfg = expected.config
        x = round((float(sample["world_x"]) - cfg.crval[0]) / cfg.cdelt[0])
        y = round((float(sample["world_y"]) - cfg.crval[1]) / cfg.cdelt[1])
        inside = 0 <= x < cfg.width and 0 <= y < cfg.height
        if inside:
            assert result.returncode == 0, result.stdout + result.stderr
            assert float(result.stdout.strip()) == pytest.approx(expected.image[y][x], abs=TOL)
        else:
            assert result.returncode != 0
