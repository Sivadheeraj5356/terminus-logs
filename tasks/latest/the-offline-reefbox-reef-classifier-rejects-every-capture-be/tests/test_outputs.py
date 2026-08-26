"""End-to-end verification of the ReefBox calibration inference manifest.

The agent's solution wires Terraform to a jq/yq pipeline that decodes the PNG
calibration blocks, merges the YAML model cards, and writes
/app/out/inference_manifest.json. This suite re-runs `terraform apply` and checks
the manifest against a frozen expected table (expected_manifest.json, kept here
and never shipped in the task image):

  * exact set of included devices + quarantined captures with reasons;
  * per-device channel scales (6 dp), sensor variant, and the merged model-card
    fields -- which exercise the field-specific precedence exceptions;
  * stable ordering (devices by device_id, quarantine by source_png);
  * idempotency across re-apply, and localized invalidation when one capture's
    calibration is removed.

Set REEF_TF=0 to validate manifest CONTENT against a pre-produced manifest
without invoking Terraform (used during authoring); the Terraform-driven
behavior tests skip in that mode.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path(os.environ.get("APP_DIR", "/app"))
FIX = APP / "data" / "fixtures"
CARDS = APP / "data" / "modelcards"
OUT = APP / "out"
MANIFEST = OUT / "inference_manifest.json"
RUN_TF = os.environ.get("REEF_TF", "1") != "0"

EXP = json.loads((Path(__file__).parent / "expected_manifest.json").read_text())
EXP_DEVICES = {d["device_id"]: d for d in EXP["devices"]}
EXP_QUAR = {q["source_png"]: q["reason"] for q in EXP["quarantined"]}
CHANNELS = ("RED", "GREEN", "NIR")
VALID_REASONS = {"missing_calibration", "bad_checksum", "sensor_variant_c",
                 "unknown_site", "superseded"}


def _apply(app=APP, fixtures=None, cards=None, out=None):
    if not RUN_TF:
        return
    args = ["terraform", f"-chdir={app}", "apply", "-auto-approve", "-input=false"]
    if fixtures:
        args += ["-var", f"fixtures_dir={fixtures}"]
    if cards:
        args += ["-var", f"cards_dir={cards}"]
    if out:
        args += ["-var", f"out_dir={out}"]
    r = subprocess.run(args, capture_output=True, text=True)
    assert r.returncode == 0, f"terraform apply failed:\n{r.stdout}\n{r.stderr}"


def _load(path):
    return json.loads(Path(path).read_text())


@pytest.fixture(scope="module")
def manifest():
    OUT.mkdir(parents=True, exist_ok=True)
    _apply()
    assert MANIFEST.exists(), f"{MANIFEST} was not produced by `terraform apply`"
    m = _load(MANIFEST)
    return {
        "m": m,
        "dev": {d["device_id"]: d for d in m.get("devices", [])},
        "quar": {q["source_png"]: q["reason"] for q in m.get("quarantined", [])},
    }


# --------------------------------------------------------------------- shape
def test_manifest_shape(manifest):
    m = manifest["m"]
    for k in ("manifest_version", "channel_order", "devices", "quarantined", "summary"):
        assert k in m, f"missing top-level key {k}"
    assert m["manifest_version"] == "1.0"
    assert m["channel_order"] == list(CHANNELS)
    assert isinstance(m["devices"], list) and isinstance(m["quarantined"], list)


def test_no_stub_reasons(manifest):
    for q in manifest["m"]["quarantined"]:
        assert q["reason"] in VALID_REASONS, q


def test_devices_sorted(manifest):
    ids = [d["device_id"] for d in manifest["m"]["devices"]]
    assert ids == sorted(ids), "devices must be sorted by device_id"


def test_quarantine_sorted(manifest):
    pngs = [q["source_png"] for q in manifest["m"]["quarantined"]]
    assert pngs == sorted(pngs), "quarantined must be sorted by source_png"


def test_source_png_is_bare_filename(manifest):
    for d in manifest["m"]["devices"]:
        assert "/" not in d["source_png"] and d["source_png"].endswith(".png")
    for q in manifest["m"]["quarantined"]:
        assert "/" not in q["source_png"] and q["source_png"].endswith(".png")


# ------------------------------------------------------------------- counts
def test_summary_counts(manifest):
    m = manifest["m"]
    assert m["summary"] == {"included": len(EXP_DEVICES), "quarantined": len(EXP_QUAR)}
    assert len(m["devices"]) == len(EXP_DEVICES)
    assert len(m["quarantined"]) == len(EXP_QUAR)


def test_included_device_set(manifest):
    assert set(manifest["dev"]) == set(EXP_DEVICES)


def test_quarantine_set_and_reasons(manifest):
    assert manifest["quar"] == EXP_QUAR


# ----------------------------------------------------- per-device frozen table
@pytest.mark.parametrize("dev_id", sorted(EXP_DEVICES))
def test_device_calibration(manifest, dev_id):
    got = manifest["dev"][dev_id]
    exp = EXP_DEVICES[dev_id]
    assert got["site"] == exp["site"]
    assert got["source_png"] == exp["source_png"]
    assert got["sensor_variant"] == exp["sensor_variant"]
    for ch in CHANNELS:
        v = got["channel_scales"][ch]
        assert abs(v - exp["channel_scales"][ch]) < 1e-9, (dev_id, ch, v)
        assert round(v, 6) == v, f"{dev_id}.{ch} must be rounded to 6 dp, got {v}"


@pytest.mark.parametrize("dev_id", sorted(EXP_DEVICES))
def test_device_modelcard_merge(manifest, dev_id):
    """Exercises the field-specific precedence exceptions (input_size /
    confidence_threshold are site>global only; labels_version is global only)."""
    got = manifest["dev"][dev_id]
    exp = EXP_DEVICES[dev_id]
    assert got["model_name"] == exp["model_name"]
    assert got["model_version"] == exp["model_version"]
    assert got["input_size"] == exp["input_size"]
    assert got["confidence_threshold"] == exp["confidence_threshold"]
    assert got["labels_version"] == exp["labels_version"]


@pytest.mark.parametrize("png", sorted(EXP_QUAR))
def test_quarantine_reason(manifest, png):
    assert manifest["quar"][png] == EXP_QUAR[png]


# ------------------------------------------------- documented-rule checks
# These assert specific outcomes governed by the notebook's documented
# precedence, integrity, and key-precedence rules (including the label-
# governance memo's 2026-03-18 pilot carve-out). Each is already covered by
# the frozen table above; they are restated explicitly so the rule each one
# exercises is auditable.

def test_pilot_site_labels_override(manifest):
    """labels_version is global-only for ordinary sites, EXCEPT the pilot site
    (site-alpha), which takes it from its own site card. This is the label-
    governance memo's 2026-03-18 pilot carve-out to the central-pin rule: the
    two site-alpha devices resolve under that carve-out, while a non-pilot
    device still takes labels_version from global."""
    pilot_devices = [d for d in manifest["m"]["devices"] if d["site"] == "site-alpha"]
    assert pilot_devices, "expected devices at the pilot site site-alpha"
    for d in pilot_devices:
        assert d["labels_version"] == "labels-2025.09-pilot", (
            f"{d['device_id']} at pilot site-alpha must take labels_version from the "
            f"site card, not global; got {d['labels_version']!r}")
    # and a non-pilot device still takes labels_version from global
    non_pilot = next(d for d in manifest["m"]["devices"] if d["site"] != "site-alpha")
    assert non_pilot["labels_version"] == "labels-2026.01"


def test_reopticed_site_input_size(manifest):
    """input_size is a per-site mount-geometry field resolved site>global with
    the device ignored. Because that rule sources input_size from current
    per-site optics, site-bravo's re-opticed (stale) site card does not supply a
    current value, so site-bravo devices resolve input_size from global. A
    non-bravo site with a current site-card input_size still wins over global."""
    g_input = [512, 512]  # global.yaml input_size
    bravo = [d for d in manifest["m"]["devices"] if d["site"] == "site-bravo"]
    assert bravo, "expected devices at site-bravo"
    for d in bravo:
        assert d["input_size"] == g_input, (
            f"{d['device_id']} at re-opticed site-bravo must take input_size from global "
            f"{g_input}, not the stale site card; got {d['input_size']}")
    # a non-bravo site with its own input_size still wins over global
    coral = next((d for d in manifest["m"]["devices"] if d["site"] == "site-coral"), None)
    if coral is not None:
        assert coral["input_size"] != g_input or coral["input_size"] == [640, 640]


def test_integrity_gate_precedes_variant(manifest):
    """reef_019's block fails its CRC. Per the notebook's decode order the
    trailing CRC is verified before any decoded body field (including the
    variant bits) is trusted, so a failed-CRC block is quarantined as
    bad_checksum rather than by the variant it appears to decode to
    (sensor_variant_c)."""
    assert manifest["quar"].get("reef_019.png") == "bad_checksum"


def test_key_precedence_beats_seq(manifest):
    """reef_004 carries both keys. Per the notebook's key-precedence rule, when
    both are present in one PNG the 2.x reefbox:calibration block is
    authoritative and the legacy rbx:cal block is ignored -- a per-PNG source
    choice, not the seq-based dedup (seq only arbitrates between separate
    same-device captures). So the 2.x block (variant B) is used rather than the
    higher-seq legacy block (variant A)."""
    rec = manifest["dev"].get("RBX-0B57")
    assert rec is not None and rec["source_png"] == "reef_004.png"
    assert rec["sensor_variant"] == "B", "the 2.x block (variant B) must win, not the higher-seq legacy block"


# ------------------------------------------------- terraform-driven behavior
@pytest.mark.skipif(not RUN_TF, reason="REEF_TF=0: terraform not invoked")
def test_terraform_ran():
    state = APP / "terraform.tfstate"
    assert state.exists() and state.stat().st_size > 0, "no terraform state -- was `terraform apply` used?"


@pytest.mark.skipif(not RUN_TF, reason="REEF_TF=0: terraform not invoked")
def test_idempotent(manifest):
    first = MANIFEST.read_bytes()
    _apply()
    assert MANIFEST.read_bytes() == first, "re-running apply must be byte-stable"


@pytest.mark.skipif(not RUN_TF, reason="REEF_TF=0: terraform not invoked")
def test_localized_invalidation(manifest, tmp_path):
    """Removing one included capture's calibration must drop exactly that device
    and quarantine exactly that PNG (missing_calibration), leaving all others."""
    victim_id = sorted(EXP_DEVICES)[0]
    victim_png = EXP_DEVICES[victim_id]["source_png"]
    # a fixture PNG that carries no calibration chunk
    no_calib = next(p for p, r in EXP_QUAR.items() if r == "missing_calibration")

    fix2 = tmp_path / "fixtures"
    shutil.copytree(FIX, fix2)
    shutil.copyfile(fix2 / no_calib, fix2 / victim_png)
    out2 = tmp_path / "out"
    out2.mkdir()
    _apply(fixtures=str(fix2), out=str(out2))
    m2 = _load(out2 / "inference_manifest.json")
    dev2 = {d["device_id"]: d for d in m2["devices"]}
    quar2 = {q["source_png"]: q["reason"] for q in m2["quarantined"]}

    assert victim_id not in dev2, "victim device should have dropped out"
    assert quar2.get(victim_png) == "missing_calibration"
    # every other included device is unchanged
    for did, rec in manifest["dev"].items():
        if did == victim_id:
            continue
        assert dev2.get(did) == rec, f"unrelated device {did} changed"
