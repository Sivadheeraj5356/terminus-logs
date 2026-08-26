"""
Verifier test suite for image-derivative-pipeline.

Expected geometry/naming/ordering values are derived independently from
/app/spec/asset_processing_spec.md's rules applied to the shipped source
images (see conftest.TRUTH), not read from the agent's own manifest or code.
Pixel-level checks use ImageMagick identify/compare on the actual produced
bytes.
"""
import os
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

from conftest import (
    CANONICAL_ICC, DERIVE_BIN, DERIV_DIR, MANIFEST_PATH, SOURCES_DIR, TRUTH,
    EXPECTED_ORDER_FILES, SOURCE_FILE_HASHES_BEFORE_ANY_RUN,
    extract_icc_bytes, image_dims, image_orientation, run_derive, sha256_file,
)

TRUTH_BY_SOURCE = {e["source"]: e for e in TRUTH}


# ---------------------------------------------------------------------------
# Build / run sanity
# ---------------------------------------------------------------------------

def test_build_exists():
    assert Path(DERIVE_BIN).exists(), f"{DERIVE_BIN} not found"
    assert os.access(DERIVE_BIN, os.X_OK), f"{DERIVE_BIN} is not executable"


def test_clean_run_exits_zero(first_run):
    assert first_run.returncode == 0


def test_outputs_created(first_run):
    assert Path(DERIV_DIR).is_dir()
    assert Path(MANIFEST_PATH).is_file()


def test_missing_args_exit_nonzero():
    r = subprocess.run([DERIVE_BIN], capture_output=True)
    assert r.returncode != 0


# ---------------------------------------------------------------------------
# Structural completeness (Rule CL-001/002, MF-001)
# ---------------------------------------------------------------------------

def test_derivative_count_matches_csv(first_run):
    files = [f for f in os.listdir(DERIV_DIR) if not f.startswith(".")]
    assert len(files) == len(TRUTH), (
        f"expected {len(TRUTH)} derivatives, found {len(files)}: {sorted(files)}"
    )


def test_no_unexpected_derivative_files(first_run):
    files = set(f for f in os.listdir(DERIV_DIR) if not f.startswith("."))
    expected = set(e["output_file"] for e in TRUTH)
    assert files == expected, f"mismatch: extra={files - expected} missing={expected - files}"


def test_manifest_entry_count(manifest_data):
    assert len(manifest_data["derivatives"]) == len(TRUTH)


# ---------------------------------------------------------------------------
# Manifest schema (Section 15)
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {
    "source_file": str, "asset_class": str, "output_file": str,
    "width": int, "height": int, "icc_policy": str,
    "orientation_normalized": bool, "sha256": str,
}


def test_manifest_schema_fields(manifest_data):
    for entry in manifest_data["derivatives"]:
        for field, typ in REQUIRED_FIELDS.items():
            assert field in entry, f"missing field {field} in {entry}"
            assert isinstance(entry[field], typ), (
                f"field {field} has wrong type in {entry}: {type(entry[field])}"
            )
        assert entry["icc_policy"] in ("preserved", "assumed_srgb")
        assert len(entry["sha256"]) == 64
        int(entry["sha256"], 16)  # valid hex


def test_manifest_ordering(manifest_data):
    actual_order = [e["output_file"] for e in manifest_data["derivatives"]]
    assert actual_order == EXPECTED_ORDER_FILES, (
        f"manifest order mismatch.\nexpected: {EXPECTED_ORDER_FILES}\nactual:   {actual_order}"
    )


def test_manifest_hash_matches_recomputed(manifest_data):
    for entry in manifest_data["derivatives"]:
        path = os.path.join(DERIV_DIR, entry["output_file"])
        assert Path(path).is_file(), f"{path} referenced by manifest but missing"
        actual_hash = sha256_file(path)
        assert actual_hash == entry["sha256"], (
            f"hash mismatch for {entry['output_file']}: manifest={entry['sha256']} actual={actual_hash}"
        )


# ---------------------------------------------------------------------------
# Per-source geometry (long_context: derived from spec rules applied to the
# actual shipped images, cross-checked against real identify output)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("truth", TRUTH, ids=[e["source"] for e in TRUTH])
def test_geometry_matches_expected(first_run, truth):
    path = os.path.join(DERIV_DIR, truth["output_file"])
    assert Path(path).is_file(), f"expected derivative missing: {truth['output_file']}"
    w, h = image_dims(path)
    assert (w, h) == (truth["out_w"], truth["out_h"]), (
        f"{truth['source']}: expected {truth['out_w']}x{truth['out_h']}, got {w}x{h}"
    )


@pytest.mark.parametrize("truth", TRUTH, ids=[e["source"] for e in TRUTH])
def test_manifest_entry_matches_truth(manifest_data, truth):
    entries = [e for e in manifest_data["derivatives"] if e["source_file"] == truth["source"]]
    assert len(entries) == 1, f"expected exactly one manifest entry for {truth['source']}"
    entry = entries[0]
    assert entry["asset_class"] == truth["asset_class"]
    assert entry["output_file"] == truth["output_file"]
    assert entry["width"] == truth["out_w"]
    assert entry["height"] == truth["out_h"]
    assert entry["icc_policy"] == truth["icc_policy"]
    assert entry["orientation_normalized"] == truth["orientation_normalized"]


# ---------------------------------------------------------------------------
# Orientation-ordering proof (Rule OR-001) — fit classes show it directly in
# dimensions since resize-before-orient uses the wrong aspect ratio entirely.
# ---------------------------------------------------------------------------

def test_orientation_ordering_hero_rotated(first_run):
    truth = TRUTH_BY_SOURCE["hero_rotated_portrait.jpg"]
    path = os.path.join(DERIV_DIR, truth["output_file"])
    w, h = image_dims(path)
    assert (w, h) == (810, 1080), (
        f"hero_rotated_portrait geometry {w}x{h} suggests resize ran before "
        f"auto-orient (wrong-order result would be 1080x1512, not 810x1080)"
    )


def test_orientation_ordering_banner_rotated(first_run):
    truth = TRUTH_BY_SOURCE["banner_rotated_strip.tiff"]
    path = os.path.join(DERIV_DIR, truth["output_file"])
    w, h = image_dims(path)
    assert (w, h) == (120, 300), (
        f"banner_rotated_strip geometry {w}x{h} suggests resize ran before "
        f"auto-orient (wrong-order result would be 300x750, not 120x300)"
    )


def test_output_orientation_tags_normalized(first_run):
    for truth in TRUTH:
        path = os.path.join(DERIV_DIR, truth["output_file"])
        orient = image_orientation(path)
        assert orient in (None, 1), (
            f"{truth['output_file']} still carries EXIF orientation {orient}; "
            f"outputs must not carry a non-trivial orientation tag"
        )


# ---------------------------------------------------------------------------
# Shrink-only (hero) vs upscale-permitted (banner)
# ---------------------------------------------------------------------------

def test_hero_shrink_only_no_upscale(first_run):
    truth = TRUTH_BY_SOURCE["hero_small_icon.png"]
    path = os.path.join(DERIV_DIR, truth["output_file"])
    w, h = image_dims(path)
    assert (w, h) == (480, 270), "hero must not upscale a source smaller than its box"


def test_banner_upscale_permitted(first_run):
    truth = TRUTH_BY_SOURCE["banner_tiny_logo_café.png"]
    path = os.path.join(DERIV_DIR, truth["output_file"])
    w, h = image_dims(path)
    assert (w, h) == (900, 300), "banner must upscale an undersized source to fit its box"


# ---------------------------------------------------------------------------
# Rounding tie / odd-excess crop (Rules RD-001/002, CR-001) — tool_specific:
# verified via ImageMagick compare against an independently-rendered
# reference crop using the hardcoded-correct offset.
# ---------------------------------------------------------------------------

def _compare_ae(actual_path, ref_path):
    cmp = subprocess.run(
        ["compare", "-metric", "AE", "-fuzz", "5%", actual_path, ref_path, "/dev/null"],
        capture_output=True, text=True,
    )
    ae_text = (cmp.stderr or cmp.stdout).strip()
    try:
        return float(ae_text)
    except ValueError:
        return float("inf")


def _render_reference_crop(src, truth, tmp_path):
    # Render the reference crop in the same output container/encoding as the
    # real derivative (matching the naming template's extension rule), so
    # the comparison isn't polluted by lossless-vs-lossy encoding noise that
    # has nothing to do with whether the crop offset itself is correct.
    ext = truth["output_file"].rsplit(".", 1)[1]
    crop = truth["crop"]
    ref = str(tmp_path / f"reference.{ext}")
    cmd = [
        "convert", src, "-auto-orient", "-filter", "Lanczos",
        "-resize", f"{crop['scaled_w']}x{crop['scaled_h']}!",
        "-gravity", "NorthWest",
        "-extent", f"{truth['out_w']}x{truth['out_h']}+{crop['left']}+{crop['top']}",
    ]
    if ext == "jpg":
        cmd += ["-quality", "85"]
    cmd += [ref]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, f"reference render failed: {r.stderr}"
    return ref


def test_tie_rounding_and_odd_excess_crop(first_run, tmp_path):
    truth = TRUTH_BY_SOURCE["card_side_profile.jpg"]
    crop = truth["crop"]
    assert crop["scaled_w"] == 641 and crop["left"] == 0, "sanity check on truth table"

    src = os.path.join(SOURCES_DIR, truth["source"])
    ref = _render_reference_crop(src, truth, tmp_path)
    actual = os.path.join(DERIV_DIR, truth["output_file"])
    ae = _compare_ae(actual, ref)
    assert ae < 50, (
        f"crop region mismatch for card_side_profile (odd-excess, tie-rounding case): "
        f"AE={ae}; expected the correct offset ({crop['left']},{crop['top']}) crop"
    )


def test_even_excess_crop_region(first_run, tmp_path):
    truth = TRUTH_BY_SOURCE["card_banner_draft.png"]
    src = os.path.join(SOURCES_DIR, truth["source"])
    ref = _render_reference_crop(src, truth, tmp_path)
    actual = os.path.join(DERIV_DIR, truth["output_file"])
    ae = _compare_ae(actual, ref)
    assert ae < 50, f"crop region mismatch for card_banner_draft: AE={ae}"


def test_orientation_180_pixel_content(first_run, tmp_path):
    """avatar_face_a carries orientation=3 (180 deg); verify pixel content was
    actually rotated, not just left with correct final dimensions."""
    truth = TRUTH_BY_SOURCE["avatar_face_a.jpg"]
    src = os.path.join(SOURCES_DIR, truth["source"])
    ref = _render_reference_crop(src, truth, tmp_path)
    actual = os.path.join(DERIV_DIR, truth["output_file"])
    ae = _compare_ae(actual, ref)
    assert ae < 50, (
        f"avatar_face_a (180-degree orientation) pixel content mismatch: AE={ae}; "
        f"this suggests the 180-degree rotation was not applied to the pixel data"
    )


# ---------------------------------------------------------------------------
# ICC / colorspace policy (Section 11)
# ---------------------------------------------------------------------------

TAGGED_SOURCES = [e for e in TRUTH if e["icc_policy"] == "preserved"]
UNTAGGED_SOURCES = [e for e in TRUTH if e["icc_policy"] == "assumed_srgb"]


@pytest.mark.parametrize("truth", TAGGED_SOURCES, ids=[e["source"] for e in TAGGED_SOURCES])
def test_icc_preserved_exact_bytes(first_run, truth):
    src_path = os.path.join(SOURCES_DIR, truth["source"])
    out_path = os.path.join(DERIV_DIR, truth["output_file"])
    src_icc = extract_icc_bytes(src_path)
    out_icc = extract_icc_bytes(out_path)
    assert src_icc is not None, f"test fixture error: {truth['source']} has no embedded profile"
    assert out_icc is not None, f"{truth['output_file']} has no embedded ICC profile"
    assert out_icc == src_icc, (
        f"{truth['output_file']}: embedded ICC profile does not match source's "
        f"original profile bytes exactly"
    )


@pytest.mark.parametrize("truth", UNTAGGED_SOURCES, ids=[e["source"] for e in UNTAGGED_SOURCES])
def test_icc_assumed_srgb_canonical_bytes(first_run, truth):
    out_path = os.path.join(DERIV_DIR, truth["output_file"])
    out_icc = extract_icc_bytes(out_path)
    canonical = Path(CANONICAL_ICC).read_bytes()
    assert out_icc is not None, (
        f"{truth['output_file']}: source had no embedded profile, but output has none either "
        f"(canonical sRGB profile must be embedded)"
    )
    assert out_icc == canonical, (
        f"{truth['output_file']}: embedded ICC profile does not match the canonical "
        f"/app/assets/color_profiles/sRGB.icc bytes exactly"
    )


# ---------------------------------------------------------------------------
# Passthrough red herring (Rule PC-001) — must be byte-identical, not merely
# pixel-identical, to the shipped source.
# ---------------------------------------------------------------------------

def test_passthrough_byte_identical(first_run):
    truth = TRUTH_BY_SOURCE["thumb_alreadyready.png"]
    src_path = os.path.join(SOURCES_DIR, truth["source"])
    out_path = os.path.join(DERIV_DIR, truth["output_file"])
    src_hash = sha256_file(src_path)
    out_hash = sha256_file(out_path)
    assert out_hash == src_hash, (
        "thumb_alreadyready.png is already fully conformant (correct size, "
        "normalized orientation, correctly tagged profile) and must be copied "
        "byte-for-byte, not re-encoded even if the re-encode is pixel-lossless"
    )


def test_non_passthrough_sources_actually_differ(first_run):
    """Sanity check that the passthrough test isn't trivially satisfied by a
    tool that copies every source unchanged."""
    truth = TRUTH_BY_SOURCE["thumb_hero_shot.png"]
    src_path = os.path.join(SOURCES_DIR, truth["source"])
    out_path = os.path.join(DERIV_DIR, truth["output_file"])
    assert sha256_file(src_path) != sha256_file(out_path), (
        "thumb_hero_shot.png requires real cropping (900x600 -> 320x320) and "
        "must not be a byte-identical copy of its source"
    )


# ---------------------------------------------------------------------------
# Determinism / idempotency (Section 12, Rule IF-004)
# ---------------------------------------------------------------------------

def test_idempotent_derivative_bytes(first_run_snapshot, second_run):
    for fn in os.listdir(DERIV_DIR):
        new_hash = sha256_file(os.path.join(DERIV_DIR, fn))
        assert fn in first_run_snapshot, f"new file {fn} appeared on second run"
        assert new_hash == first_run_snapshot[fn], (
            f"{fn} changed bytes between first and second run"
        )
    assert set(os.listdir(DERIV_DIR)) == set(k for k in first_run_snapshot if k != "__manifest__")


def test_idempotent_manifest(first_run_snapshot, second_run):
    new_hash = sha256_file(MANIFEST_PATH)
    assert new_hash == first_run_snapshot["__manifest__"], (
        "manifest.json changed between first and second run against unchanged inputs"
    )


# ---------------------------------------------------------------------------
# Source directory must never be modified
# ---------------------------------------------------------------------------

def test_source_directory_unmodified(first_run):
    expected_files = set(e["source"] for e in TRUTH) | {"manifest_inputs.csv"}
    actual_files = set(os.listdir(SOURCES_DIR))
    assert actual_files == expected_files, (
        f"source directory contents changed: extra={actual_files - expected_files} "
        f"missing={expected_files - actual_files}"
    )


def test_high_byte_filename_handled(first_run, manifest_data):
    """banner_tiny_logo_café.png exercises non-ASCII filename handling
    (classification lookup + naming template byte transform)."""
    src_path = os.path.join(SOURCES_DIR, "banner_tiny_logo_café.png")
    assert Path(src_path).is_file(), "test fixture itself missing"
    entries = [e for e in manifest_data["derivatives"]
               if e["source_file"] == "banner_tiny_logo_café.png"]
    assert len(entries) == 1
    assert entries[0]["output_file"] == "banner__banner_tiny_logo_café__900x300.png"
    out_path = os.path.join(DERIV_DIR, entries[0]["output_file"])
    assert Path(out_path).is_file()


def test_source_file_contents_unchanged(first_run):
    """Stronger than membership: every shipped source's bytes must be
    identical to what they were before the binary ever ran."""
    for fn, hash_before in SOURCE_FILE_HASHES_BEFORE_ANY_RUN.items():
        hash_after = sha256_file(os.path.join(SOURCES_DIR, fn))
        assert hash_after == hash_before, f"{fn} content changed after running derive"


# ---------------------------------------------------------------------------
# Nested output directory creation / unrecoverable input handling
# ---------------------------------------------------------------------------

def test_nested_output_directory_created(tmp_path):
    fresh_out = tmp_path / "does" / "not" / "exist" / "yet"
    assert not fresh_out.exists()
    r = run_derive(out=str(fresh_out))
    assert r.returncode == 0, f"derive failed against a non-existent nested --out path: {r.stderr}"
    assert (fresh_out / "derivatives").is_dir(), "derivatives/ was not created under a fresh --out tree"
    assert (fresh_out / "manifest.json").is_file()
    produced = list((fresh_out / "derivatives").iterdir())
    assert len(produced) == len(TRUTH)


def test_unrecoverable_input_no_partial_manifest(tmp_path):
    scratch_sources = tmp_path / "sources"
    scratch_sources.mkdir()
    real_src = os.path.join(SOURCES_DIR, "thumb_hero_shot.png")
    shutil.copyfile(real_src, scratch_sources / "thumb_hero_shot.png")

    csv_path = tmp_path / "manifest_inputs.csv"
    csv_path.write_text(
        "filename,asset_class\n"
        "thumb_hero_shot.png,thumbnail\n"
        "does_not_exist.png,thumbnail\n"
    )
    out_dir = tmp_path / "out"

    r = run_derive(sources=str(scratch_sources), csv=str(csv_path), out=str(out_dir))
    assert r.returncode != 0, "derive must fail when a CSV row references a missing source file"
    assert not (out_dir / "manifest.json").exists(), (
        "derive must not leave a partial manifest.json after an unrecoverable input error, "
        "even though one of the two rows referenced a valid, processable source"
    )


# ---------------------------------------------------------------------------
# All eight standard EXIF orientation values (spec Section 2 requires the
# tool to handle all of them; the shipped fixtures only exercise 1, 3, 6, 8,
# so 2/4/5/7 are covered here via images synthesized at test time and
# verified against ImageMagick's own -auto-orient as an independent ground
# truth, the same tool this pipeline is required to use). ImageMagick has no
# reliable way to write a fresh EXIF orientation tag from scratch via -set,
# -orient, or -profile on a synthetic image with no pre-existing EXIF block,
# so the tag is injected directly as a real APP1 marker in the JPEG bytes.
# ---------------------------------------------------------------------------

ORIENTATION_NAMES = {
    1: "TopLeft", 2: "TopRight", 3: "BottomRight", 4: "BottomLeft",
    5: "LeftTop", 6: "RightTop", 7: "RightBottom", 8: "LeftBottom",
}


def _make_tiff_orientation_ifd(value):
    """A minimal single-entry TIFF/IFD structure carrying just the
    Orientation tag (0x0112, SHORT), suitable as an EXIF payload."""
    header = b"II" + struct.pack("<H", 42) + struct.pack("<I", 8)
    ifd_count = struct.pack("<H", 1)
    entry = struct.pack("<HHI", 0x0112, 3, 1) + struct.pack("<H", value) + b"\x00\x00"
    next_ifd = struct.pack("<I", 0)
    return header + ifd_count + entry + next_ifd


def _write_jpeg_with_orientation(src_plain_jpeg, dst_path, value):
    data = Path(src_plain_jpeg).read_bytes()
    assert data[:2] == b"\xff\xd8", "not a JPEG"
    payload = b"Exif\x00\x00" + _make_tiff_orientation_ifd(value)
    app1 = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    Path(dst_path).write_bytes(data[:2] + app1 + data[2:])


def test_all_eight_orientation_values(tmp_path):
    scratch_sources = tmp_path / "sources"
    scratch_sources.mkdir()
    base_w, base_h = 60, 40

    plain_path = tmp_path / "plain.jpg"
    r = subprocess.run([
        "convert", "-size", f"{base_w}x{base_h}", "xc:red",
        "-fill", "blue", "-draw", f"rectangle 0,0 {base_w // 3},{base_h - 1}",
        str(plain_path),
    ], capture_output=True, text=True)
    assert r.returncode == 0, f"failed to synthesize base orientation fixture: {r.stderr}"

    rows = ["filename,asset_class"]
    for orient_value in ORIENTATION_NAMES:
        fn = f"orient_{orient_value}.jpg"
        src_path = scratch_sources / fn
        _write_jpeg_with_orientation(plain_path, src_path, orient_value)
        rows.append(f"{fn},avatar")

    csv_path = tmp_path / "manifest_inputs.csv"
    csv_path.write_text("\n".join(rows) + "\n")
    out_dir = tmp_path / "out"

    r = run_derive(sources=str(scratch_sources), csv=str(csv_path), out=str(out_dir))
    assert r.returncode == 0, f"derive failed on synthetic orientation fixtures: {r.stderr}"

    for orient_value, orient_name in ORIENTATION_NAMES.items():
        fn = f"orient_{orient_value}.jpg"
        src_path = scratch_sources / fn

        assert image_orientation(str(src_path)) == orient_value, (
            f"test fixture error: orientation {orient_value} was not embedded correctly "
            f"in the synthesized source"
        )

        stored_w, stored_h = image_dims(str(src_path))
        swap = orient_value in (5, 6, 7, 8)
        true_w, true_h = (stored_h, stored_w) if swap else (stored_w, stored_h)
        scale = max(200.0 / true_w, 200.0 / true_h)
        scaled_w = round(true_w * scale)
        scaled_h = round(true_h * scale)
        left = (scaled_w - 200) // 2
        top = (scaled_h - 200) // 2

        ref_path = tmp_path / f"ref_{orient_value}.jpg"
        conv = subprocess.run([
            "convert", str(src_path), "-auto-orient", "-filter", "Lanczos",
            "-resize", f"{scaled_w}x{scaled_h}!", "-gravity", "NorthWest",
            "-extent", f"200x200+{left}+{top}", "-profile", CANONICAL_ICC,
            "-quality", "85", "-sampling-factor", "4:2:0", str(ref_path),
        ], capture_output=True, text=True)
        assert conv.returncode == 0, f"reference render failed: {conv.stderr}"

        out_path = out_dir / "derivatives" / f"avatar__orient_{orient_value}__200x200.jpg"
        assert out_path.is_file(), f"missing derivative for orientation {orient_value} ({orient_name})"

        ae = _compare_ae(str(out_path), str(ref_path))
        assert ae < 50, (
            f"orientation {orient_value} ({orient_name}) pixel content mismatch: AE={ae}"
        )

        orient_after = image_orientation(str(out_path))
        assert orient_after in (None, 1), (
            f"output for orientation {orient_value} ({orient_name}) still carries "
            f"orientation tag {orient_after}"
        )


# ---------------------------------------------------------------------------
# Full cross-consistency (holistic)
# ---------------------------------------------------------------------------

def test_full_consistency_images_manifest_hashes(first_run, manifest_data):
    assert len(manifest_data["derivatives"]) == len(TRUTH)
    seen_sources = set()
    for entry in manifest_data["derivatives"]:
        truth = TRUTH_BY_SOURCE.get(entry["source_file"])
        assert truth is not None, f"unexpected source_file in manifest: {entry['source_file']}"
        seen_sources.add(entry["source_file"])

        path = os.path.join(DERIV_DIR, entry["output_file"])
        w, h = image_dims(path)
        assert (w, h) == (entry["width"], entry["height"]) == (truth["out_w"], truth["out_h"])
        assert sha256_file(path) == entry["sha256"]

    assert seen_sources == set(TRUTH_BY_SOURCE.keys())
