import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

DERIVE_BIN = "/app/build/derive"
SOURCES_DIR = "/app/assets/src"
CSV_PATH = "/app/assets/src/manifest_inputs.csv"
SPEC_PATH = "/app/spec/asset_processing_spec.md"
CANONICAL_ICC = "/app/assets/color_profiles/sRGB.icc"
OUT_DIR = "/app/out"
DERIV_DIR = "/app/out/derivatives"
MANIFEST_PATH = "/app/out/manifest.json"

# Independently-derived truth table (computed from the specification's rules
# applied to the actual shipped source images -- not read from the agent's
# own manifest or code). Each entry:
#   source_file, asset_class, out_w, out_h, orientation_normalized,
#   icc_policy, output_file, cover_crop (scaled_w, scaled_h, left, top) or None
TRUTH = [
    dict(source="avatar_face_a.jpg", asset_class="avatar", out_w=200, out_h=200,
         orientation_normalized=True, icc_policy="assumed_srgb",
         output_file="avatar__avatar_face_a__200x200.jpg",
         crop=dict(scaled_w=200, scaled_h=200, left=0, top=0)),
    dict(source="avatar_face_b.jpg", asset_class="avatar", out_w=200, out_h=200,
         orientation_normalized=False, icc_policy="preserved",
         output_file="avatar__avatar_face_b__200x200.jpg",
         crop=dict(scaled_w=266, scaled_h=200, left=33, top=0)),
    dict(source="avatar_face_c.png", asset_class="avatar", out_w=200, out_h=200,
         orientation_normalized=False, icc_policy="assumed_srgb",
         output_file="avatar__avatar_face_c__200x200.png",
         crop=dict(scaled_w=200, scaled_h=260, left=0, top=30)),
    dict(source="avatar_face_d.jpg", asset_class="avatar", out_w=200, out_h=200,
         orientation_normalized=True, icc_policy="assumed_srgb",
         output_file="avatar__avatar_face_d__200x200.jpg",
         crop=dict(scaled_w=200, scaled_h=300, left=0, top=50)),
    dict(source="banner_rotated_strip.tiff", asset_class="banner", out_w=120, out_h=300,
         orientation_normalized=True, icc_policy="assumed_srgb",
         output_file="banner__banner_rotated_strip__120x300.tiff", crop=None),
    dict(source="banner_tiny_logo_café.png", asset_class="banner", out_w=900, out_h=300,
         orientation_normalized=False, icc_policy="assumed_srgb",
         output_file="banner__banner_tiny_logo_café__900x300.png", crop=None),
    dict(source="banner_wide_source.png", asset_class="banner", out_w=1200, out_h=240,
         orientation_normalized=False, icc_policy="assumed_srgb",
         output_file="banner__banner_wide_source__1200x240.png", crop=None),
    dict(source="card_banner_draft.png", asset_class="card", out_w=640, out_h=400,
         orientation_normalized=False, icc_policy="assumed_srgb",
         output_file="card__card_banner_draft__640x400.png",
         crop=dict(scaled_w=640, scaled_h=640, left=0, top=120)),
    dict(source="card_product_wide.jpg", asset_class="card", out_w=640, out_h=400,
         orientation_normalized=False, icc_policy="preserved",
         output_file="card__card_product_wide__640x400.jpg",
         crop=dict(scaled_w=1066, scaled_h=400, left=213, top=0)),
    dict(source="card_side_profile.jpg", asset_class="card", out_w=640, out_h=400,
         orientation_normalized=False, icc_policy="assumed_srgb",
         output_file="card__card_side_profile__640x400.jpg",
         crop=dict(scaled_w=641, scaled_h=400, left=0, top=0)),
    dict(source="hero_landing_bg.jpg", asset_class="hero", out_w=1920, out_h=1080,
         orientation_normalized=False, icc_policy="assumed_srgb",
         output_file="hero__hero_landing_bg__1920x1080.jpg", crop=None),
    dict(source="hero_rotated_portrait.jpg", asset_class="hero", out_w=810, out_h=1080,
         orientation_normalized=True, icc_policy="preserved",
         output_file="hero__hero_rotated_portrait__810x1080.jpg", crop=None),
    dict(source="hero_small_icon.png", asset_class="hero", out_w=480, out_h=270,
         orientation_normalized=False, icc_policy="assumed_srgb",
         output_file="hero__hero_small_icon__480x270.png", crop=None),
    dict(source="thumb_alreadyready.png", asset_class="thumbnail", out_w=320, out_h=320,
         orientation_normalized=False, icc_policy="preserved",
         output_file="thumbnail__thumb_alreadyready__320x320.png",
         crop=dict(scaled_w=320, scaled_h=320, left=0, top=0), passthrough=True),
    dict(source="thumb_hero_shot.png", asset_class="thumbnail", out_w=320, out_h=320,
         orientation_normalized=False, icc_policy="assumed_srgb",
         output_file="thumbnail__thumb_hero_shot__320x320.png",
         crop=dict(scaled_w=480, scaled_h=320, left=80, top=0)),
    dict(source="thumb_portrait_snap.jpg", asset_class="thumbnail", out_w=320, out_h=320,
         orientation_normalized=False, icc_policy="preserved",
         output_file="thumbnail__thumb_portrait_snap__320x320.jpg",
         crop=dict(scaled_w=320, scaled_h=448, left=0, top=64)),
]

for _e in TRUTH:
    _e.setdefault("passthrough", False)

def _sort_stem(entry):
    return entry["output_file"].split("__")[1]


EXPECTED_ORDER = sorted(TRUTH, key=lambda e: (e["asset_class"], _sort_stem(e)))
EXPECTED_ORDER_FILES = [e["output_file"] for e in EXPECTED_ORDER]
EXPECTED_ORDER_SOURCES = [e["source"] for e in EXPECTED_ORDER]


def identify_field(path, fmt):
    r = subprocess.run(["identify", "-format", fmt, f"{path}[0]"],
                        capture_output=True, text=True)
    assert r.returncode == 0, f"identify failed for {path}: {r.stderr}"
    return r.stdout


def image_dims(path):
    wh = identify_field(path, "%w %h").split()
    return int(wh[0]), int(wh[1])


_ORIENTATION_NAME_TO_VALUE = {
    "Undefined": None,
    "TopLeft": 1,
    "TopRight": 2,
    "BottomRight": 3,
    "BottomLeft": 4,
    "LeftTop": 5,
    "RightTop": 6,
    "RightBottom": 7,
    "LeftBottom": 8,
}


def image_orientation(path):
    # %[EXIF:Orientation] is only populated for formats with a literal EXIF
    # block (JPEG); TIFF's native orientation tag only shows up via the
    # symbolic %[orientation] property, so that's the one that works for
    # every container format this pipeline handles.
    name = identify_field(path, "%[orientation]").strip()
    return _ORIENTATION_NAME_TO_VALUE.get(name)


def extract_icc_bytes(path):
    r = subprocess.run(["convert", f"{path}[0]", "icc:-"], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    return r.stdout


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def run_derive(sources=SOURCES_DIR, csv=CSV_PATH, spec=SPEC_PATH, out=OUT_DIR):
    r = subprocess.run(
        [DERIVE_BIN,
         "--sources", sources,
         "--csv", csv,
         "--spec", spec,
         "--out", out],
        capture_output=True, text=True,
    )
    return r


# Hashed at collection time, before any test invokes the binary, so this is
# a genuine pre-run snapshot of the shipped sources' bytes.
SOURCE_FILE_HASHES_BEFORE_ANY_RUN = {
    fn: sha256_file(os.path.join(SOURCES_DIR, fn))
    for fn in os.listdir(SOURCES_DIR)
}


@pytest.fixture(scope="session")
def first_run():
    r = run_derive()
    assert r.returncode == 0, (
        f"derive failed:\nSTDOUT: {r.stdout}\nSTDERR: {r.stderr}"
    )
    return r


@pytest.fixture(scope="session")
def manifest_data(first_run):
    return json.loads(Path(MANIFEST_PATH).read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def first_run_snapshot(first_run):
    snap = {}
    for fn in os.listdir(DERIV_DIR):
        snap[fn] = sha256_file(os.path.join(DERIV_DIR, fn))
    snap["__manifest__"] = sha256_file(MANIFEST_PATH)
    return snap


@pytest.fixture(scope="session")
def second_run(first_run_snapshot):
    r = run_derive()
    assert r.returncode == 0, (
        f"second derive run failed:\nSTDOUT: {r.stdout}\nSTDERR: {r.stderr}"
    )
    return r
