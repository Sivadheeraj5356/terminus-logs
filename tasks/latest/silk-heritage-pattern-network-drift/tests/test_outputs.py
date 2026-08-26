from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

BUNDLES = Path("/app/data/bundles")
OUT_DIR = Path("/app/output")
OUTPUT = OUT_DIR / "pattern_genealogy.json"
JOURNAL = OUT_DIR / ".genealogy_journal.json"
WEIGHTS = Path("/app/config/weights.toml")
FIXTURES = Path("/app/fixtures/rotation-segment/segments.jsonl")
TESTS_DIR = Path(__file__).parent
INTEGRITY_MANIFEST = TESTS_DIR / "data_integrity.json"


def _scratch(name: str) -> Path:
    return OUT_DIR / name


def _remove_if_present(target: Path) -> None:
    if target.is_file():
        target.unlink()


def _assert_path_absent(target: Path) -> None:
    assert target.is_file() is False


def _assert_path_present(target: Path) -> None:
    assert target.is_file() is True


def _write_json(target: Path, payload: object) -> None:
    target.write_text(json.dumps(payload, indent=2) + "\n")


@pytest.fixture(scope="session", autouse=True)
def _guard_verifier_inputs() -> None:
    manifest = json.loads(INTEGRITY_MANIFEST.read_text())
    runtime_root = Path("/app/data")
    for rel, expected in manifest.items():
        path = runtime_root / rel
        assert path.is_file(), f"missing registry file: {rel}"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == expected, f"tampered registry file: {rel}"


@pytest.fixture(autouse=True)
def _fresh_output() -> None:
    _remove_if_present(OUTPUT)
    yield
    _remove_if_present(OUTPUT)


def bundle_files() -> list[Path]:
    return sorted(p for p in BUNDLES.glob("*.json") if p.name != "index.json")


def _load_registry(directory: Path) -> dict:
    merged: dict = {}
    for path in sorted(directory.glob("*.json")):
        merged.update(json.loads(path.read_text()))
    return merged


def _load_dye_reformulations(data_root: Path) -> dict:
    merged = _load_registry(data_root / "dye_reformulations")
    overlay_dir = data_root / "dye_reformulations" / "overrides"
    if overlay_dir.is_dir():
        for path in sorted(overlay_dir.glob("*.json")):
            overlay = json.loads(path.read_text())
            for panel_id, rows in overlay.items():
                merged.setdefault(panel_id, [])
                merged[panel_id] = list(merged[panel_id]) + list(rows)
    return merged


def _policy_family(bundle: dict[str, Any]) -> str:
    family = bundle.get("policy_family")
    return str(family) if family is not None else "standard"


def _load_blend(bundle: dict[str, Any]) -> dict[str, float]:
    family = _policy_family(bundle)
    section = "genealogy_blend" if family == "standard" else f"genealogy_blend.{family}"
    blend: dict[str, float] = {}
    in_section = False
    header = f"[{section}]"
    for line in WEIGHTS.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_section = stripped == header
            continue
        if not in_section or "=" not in stripped or stripped.startswith("#"):
            continue
        key, value = stripped.split("=", 1)
        blend[key.strip()] = float(value.strip())
    return blend


def _registry_digest(catalogs: dict[str, Any]) -> str:
    payload = json.dumps(catalogs, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _network_seal(bundle: dict[str, Any], catalogs: dict[str, Any]) -> str:
    snapshot = bundle.get("genealogy_snapshot") or {}
    as_of = snapshot.get("as_of_year")
    panel_manifest = ",".join(str(entry["panel_id"]) for entry in bundle.get("panels", []))
    manifest_digest = hashlib.sha256(panel_manifest.encode()).hexdigest()[:8]
    parts = [
        bundle["bundle_id"],
        _policy_family(bundle),
        str(int(as_of)) if as_of is not None else "None",
        _registry_digest(catalogs),
        manifest_digest,
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:24]


def _resolve_entry(panel_id: str, catalog: dict[str, Any]) -> dict[str, Any]:
    row = catalog[panel_id]
    if "alias_of" in row:
        canonical = row["alias_of"]
        base = catalog[canonical]
    else:
        canonical = panel_id
        base = row
    return {
        "panel_id": panel_id,
        "canonical_id": canonical,
        "weaver_id": base["weaver_id"],
        "completion_year": int(base.get("completion_year", 1900)),
    }


def _clip_timeline(
    bundle: dict[str, Any],
    dye_reformulations: list[dict[str, Any]],
    epochs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    snapshot = bundle.get("genealogy_snapshot") or {}
    as_of = snapshot.get("as_of_year")
    if as_of is None:
        return list(dye_reformulations), list(epochs)
    as_of_year = int(as_of)
    clipped_dye_reformulations = [row for row in dye_reformulations if int(row["year"]) <= as_of_year]
    clipped_epochs: list[dict[str, Any]] = []
    for epoch in epochs:
        if int(epoch["from_year"]) > as_of_year:
            continue
        clipped_epochs.append(
            {**epoch, "to_year": min(int(epoch["to_year"]), as_of_year)}
        )
    return clipped_dye_reformulations, clipped_epochs


def _slice_custody_epochs(epochs: list[dict], replay_floor: int) -> list[dict]:
    if replay_floor <= 1:
        return list(epochs)
    skip = replay_floor - 1
    if skip >= len(epochs):
        return []
    return epochs[skip:]


def _load_segments(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def _classify_segment(incremental: bool, rotation_floor: int, seg: dict[str, Any]) -> bool:
    rotation_id = int(seg["rotation_id"])
    generation = int(seg["generation"])
    if not incremental and rotation_id % 2 != 0:
        return False
    if rotation_id > 0 and rotation_id < rotation_floor:
        return False
    return generation <= 9


def _resolve_replay_floor(incremental: bool) -> int:
    segments = _load_segments(FIXTURES)
    if not segments:
        return 0
    rotation_floor = 2 if incremental else 1
    active = [
        seg
        for seg in segments
        if _classify_segment(incremental, rotation_floor, seg)
    ]
    if not active:
        return 0
    return min(int(seg["generation"]) for seg in active)


def _active_mentor_of(
    mentor_of: dict[str, str],
    lineage_epochs: dict[str, Any],
    completion_year: int,
) -> dict[str, str]:
    filtered: dict[str, str] = {}
    for child, parent in mentor_of.items():
        active_from = int(lineage_epochs.get(child, {}).get("active_from_year", 0))
        if completion_year >= active_from:
            filtered[child] = parent
    return filtered


def _accumulate_trust(weaver_id: str, mentor_of: dict, master_weavers: dict) -> float:
    weight = 1.0
    current = weaver_id
    visited: set[str] = set()
    while current in mentor_of:
        if current in visited:
            break
        visited.add(current)
        profile = master_weavers.get(current, {})
        weight *= float(profile.get("thread_trust", 1.0))
        current = mentor_of[current]
    return weight


def _gated_dye_reformulations(
    dye_reformulations: list[dict],
    epochs: list[dict],
    school_recitals: list[dict],
) -> list[dict]:
    recital_years = [int(row["year"]) for row in school_recitals]
    if not recital_years:
        return []
    eligible_years: set[int] = set()
    for epoch in epochs:
        if epoch.get("export_eligible", True):
            eligible_years.update(range(epoch["from_year"], epoch["to_year"] + 1))
    scoped: list[dict] = []
    for repair in dye_reformulations:
        year = int(repair["year"])
        if year not in eligible_years:
            continue
        if not any(recital_year <= year for recital_year in recital_years):
            continue
        scoped.append(repair)
    return scoped


def _compound_dye_reformulations(
    dye_reformulations: list[dict], penalty_rate: float, drift_seed: float = 1.0
) -> float:
    factor = drift_seed
    for event in sorted(dye_reformulations, key=lambda row: row["year"]):
        if event.get("reset_drift"):
            factor = 1.0
            continue
        factor *= 1.0 - penalty_rate * float(event["severity"])
    return max(0.0, factor)


def _ungated_clipped_dye_fidelity(bundle_path: Path, panel_id: str) -> float:
    """Compound clipped dye events without school-recital gating (broken sequencer order)."""
    data_root = Path("/app/data")
    bundle = json.loads(bundle_path.read_text())
    blend = _load_blend(bundle)
    panels = _load_registry(data_root / "panels")
    dye_reformulations = _load_dye_reformulations(data_root)
    export_routes = _load_registry(data_root / "export_routes")
    view = _resolve_entry(panel_id, panels)
    dye_raw = list(dye_reformulations.get(view["canonical_id"], []))
    epochs_raw = list(export_routes.get(view["canonical_id"], []))
    clipped_dye, _epochs = _clip_timeline(bundle, dye_raw, epochs_raw)
    return round(_compound_dye_reformulations(clipped_dye, blend["dye_penalty_rate"]), 6)


def _owner_for_year(epochs: list[dict], year: int) -> str | None:
    for epoch in epochs:
        if epoch["from_year"] <= year <= epoch["to_year"]:
            return epoch["owner_id"]
    return None


def _prev_owner_at_transfer(epochs: list[dict], year: int) -> str | None:
    for epoch in epochs:
        if epoch["from_year"] == year:
            prior = [item for item in epochs if item["to_year"] == year - 1]
            if prior:
                return prior[0]["owner_id"]
    return None


def _cert_valid(cert: dict, year: int) -> bool:
    return cert["issued_year"] <= year <= cert["expires_year"]


def _sale_allows_inheritance(
    sales: list[dict], transfer_year: int, seller: str, buyer: str
) -> bool:
    for sale in sales:
        if (
            sale["year"] == transfer_year
            and sale["seller"] == seller
            and sale["buyer"] == buyer
            and sale.get("kind") == "arms_length"
        ):
            return True
    return False


def _epoch_coverage(
    epochs: list[dict],
    certs: list[dict],
    sales: list[dict],
    replay_floor: int = 0,
) -> float:
    epochs = _slice_custody_epochs(epochs, replay_floor)
    if not epochs:
        return 0.0
    start = min(epoch["from_year"] for epoch in epochs)
    end = max(epoch["to_year"] for epoch in epochs)
    total_years = end - start + 1
    if total_years <= 0:
        return 0.0
    covered = 0
    for year in range(start, end + 1):
        owner = _owner_for_year(epochs, year)
        if owner is None:
            continue
        ok = False
        for cert in certs:
            if cert["holder"] == owner and _cert_valid(cert, year):
                ok = True
                break
        if not ok:
            prev = _prev_owner_at_transfer(epochs, year)
            if prev:
                for cert in certs:
                    if (
                        cert["holder"] == prev
                        and cert.get("transfers_with_sale")
                        and _cert_valid(cert, year)
                        and _sale_allows_inheritance(sales, year, prev, owner)
                    ):
                        ok = True
                        break
        if ok:
            covered += 1
    return 100.0 * covered / total_years


def reference_report(bundle_path: Path, replay_floor: int = 0) -> dict:
    data_root = Path("/app/data")
    bundle = json.loads(bundle_path.read_text())
    blend = _load_blend(bundle)
    master_weavers = _load_registry(data_root / "master_weavers")
    dye_reformulations = _load_dye_reformulations(data_root)
    export_routes = _load_registry(data_root / "export_routes")
    loom_letters = _load_registry(data_root / "loom_letters")
    pattern_anchors = _load_registry(data_root / "pattern_anchors")
    panels = _load_registry(data_root / "panels")
    merchant_transfers = _load_registry(data_root / "merchant_transfers")
    school_recitals = _load_registry(data_root / "school_recitals")
    catalogs = {
        "master_weavers": master_weavers,
        "dye_reformulations": dye_reformulations,
        "export_routes": export_routes,
        "loom_letters": loom_letters,
        "pattern_anchors": pattern_anchors,
        "panels": panels,
        "merchant_transfers": merchant_transfers,
        "school_recitals": school_recitals,
    }

    panels_out = []
    sequential = bundle.get("panel_coupling") == "sequential_drift"
    dye_seed = 1.0
    for entry in bundle["panels"]:
        view = _resolve_entry(entry["panel_id"], panels)
        canonical = view["canonical_id"]
        mentor_of = _active_mentor_of(
            master_weavers["mentor_of"],
            master_weavers.get("lineage_epochs", {}),
            view["completion_year"],
        )
        lineage = _accumulate_trust(view["weaver_id"], mentor_of, master_weavers)
        dye_reformulations_raw = list(dye_reformulations.get(canonical, []))
        epochs_raw = list(export_routes.get(canonical, []))
        dye_reformulations_clip, epochs_clip = _clip_timeline(bundle, dye_reformulations_raw, epochs_raw)
        scoped = _gated_dye_reformulations(
            dye_reformulations_clip,
            epochs_clip,
            school_recitals.get(canonical, []),
        )
        restoration = _compound_dye_reformulations(scoped, blend["dye_penalty_rate"], dye_seed)
        coverage = _epoch_coverage(
            epochs_clip,
            loom_letters.get(canonical, []),
            merchant_transfers.get(canonical, []),
            replay_floor,
        )
        base = pattern_anchors[canonical]["base_appraisal"]
        cert_term = blend["letter_floor"] + blend["letter_span"] * (coverage / 100.0)
        fair = round(base * lineage * restoration * cert_term, 2)
        index = round((fair / base) * 100, 2)
        panels_out.append(
            {
                "panel_id": view["panel_id"],
                "weaver_lineage": round(lineage, 6),
                "dye_fidelity": round(restoration, 6),
                "school_continuity": round(coverage, 4),
                "heritage_score": fair,
                "influence_index": index,
            }
        )
        if sequential:
            dye_seed = round(restoration, 6)
    indices = [row["influence_index"] for row in panels_out]
    weakest = min(panels_out, key=lambda row: row["influence_index"])
    return {
        "bundle_id": bundle["bundle_id"],
        "network_seal": _network_seal(bundle, catalogs),
        "panels": panels_out,
        "summary": {
            "mean_influence": round(sum(indices) / len(indices), 2),
            "weakest_panel": weakest["panel_id"],
        },
    }


def _canonical_json(value: object) -> str:
    if isinstance(value, dict):
        items = sorted(value.items(), key=lambda kv: kv[0])
        inner = ",".join(
            f"{json.dumps(k, ensure_ascii=False)}:{_canonical_json(v)}" for k, v in items
        )
        return "{" + inner + "}"
    if isinstance(value, list):
        return "[" + ",".join(_canonical_json(v) for v in value) + "]"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def report_digest(report: dict) -> str:
    body = _canonical_json(report).encode("utf-8")
    with tempfile.NamedTemporaryFile(delete=False) as handle:
        handle.write(body)
        path = handle.name
    try:
        proc = subprocess.run(
            ["sha256sum", path],
            capture_output=True,
            text=True,
            check=True,
        )
    finally:
        os.unlink(path)
    return proc.stdout.split()[0]


def _write_probe_bundle(body: dict[str, Any]) -> Path:
    dest = Path(tempfile.mkdtemp(prefix="probe_bundle_", dir=str(OUT_DIR)))
    path = dest / f"{body['bundle_id']}.json"
    _write_json(path, body)
    return path


def run_cli(
    bundle_path: Path,
    out_path: Path = OUTPUT,
    extra_env: dict[str, str] | None = None,
    *,
    read_output: bool = True,
) -> dict | None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, **(extra_env or {})}
    proc = subprocess.run(
        [
            "python3",
            "-m",
            "shed_weave.cli",
            "trace",
            "--bundle",
            str(bundle_path),
            "--out",
            str(out_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    if extra_env and extra_env.get("TRACE_HALT") == "1":
        return None
    if not read_output:
        return None
    return json.loads(out_path.read_text())


def test_z01_suzhou_reference_totals() -> None:
    """Suzhou nave division must match the independent authenticity contract."""
    bundle = BUNDLES / "suzhou_brocade_division.json"
    report = run_cli(bundle)
    assert report == reference_report(bundle)
    assert isinstance(report["network_seal"], str)
    assert len(report["network_seal"]) == 24


def test_z02_varanasi_alias_canonical() -> None:
    """Archive alias ids must join canonical custody and appraisal tables."""
    bundle = BUNDLES / "varanasi_banarasi_archive.json"
    report = run_cli(bundle)
    assert report == reference_report(bundle)


def test_z03_lyon_kyoto_cross_module() -> None:
    """Exchange and salon bundles must combine gating, compounding, and blend policy."""
    prague = BUNDLES / "lyon_silk_exchange.json"
    report = run_cli(prague)
    assert report == reference_report(prague)
    venice = BUNDLES / "kyoto_nishijin_salon.json"
    _remove_if_present(OUTPUT)
    report = run_cli(venice)
    assert report == reference_report(venice)


def test_z04_isfahan_snapshot_clip() -> None:
    """Snapshot bundles must clip timelines for restoration and attestation lanes."""
    bundle = BUNDLES / "isfahan_persian_circulation.json"
    report = run_cli(bundle)
    assert report == reference_report(bundle)


def test_z05_genoa_deposit_parity() -> None:
    """Genoa wind society must value alias and canonical ids against one custody record."""
    bundle = BUNDLES / "genoa_merchant_society.json"
    report = run_cli(bundle)
    expected = reference_report(bundle)
    assert report == expected
    canonical_row = next(
        r for r in report["panels"] if r["panel_id"] == "panel_genoa_brocade_merchant"
    )
    alias_row = next(
        r for r in report["panels"] if r["panel_id"] == "panel_genoa_deposit"
    )
    assert alias_row["heritage_score"] == canonical_row["heritage_score"]


def test_z06_session_replay_floor_reset() -> None:
    """Full compile after incremental replay must not inherit stale replay floors."""
    bundle = BUNDLES / "suzhou_brocade_division.json"
    run_cli(bundle, OUTPUT, {"TRACE_INCREMENTAL": "1"})
    _remove_if_present(OUTPUT)
    report = run_cli(bundle, OUTPUT)
    assert report == reference_report(bundle)


def test_z07_incremental_full_agree() -> None:
    """Incremental journal replay and full compile must share report digests."""
    bundle = BUNDLES / "suzhou_brocade_division.json"
    replay_floor = _resolve_replay_floor(True)
    inc = run_cli(bundle, OUTPUT, {"TRACE_INCREMENTAL": "1"})
    _remove_if_present(OUTPUT)
    full = run_cli(bundle, OUTPUT)
    assert report_digest(inc) == report_digest(full)
    assert inc == reference_report(bundle, replay_floor=replay_floor)
    assert full == reference_report(bundle)


def test_z08_halt_resume_recovery() -> None:
    """Interrupted pattern_anchors must recover through the authenticity journal."""
    bundle = BUNDLES / "suzhou_brocade_division.json"
    out = _scratch("halt.json")
    journal = JOURNAL
    _remove_if_present(out)
    _remove_if_present(journal)
    run_cli(bundle, out, {"TRACE_HALT": "1"}, read_output=False)
    _assert_path_present(journal)
    _assert_path_absent(out)
    warm = run_cli(bundle, out, {"TRACE_RESUME": "1"})
    cold = run_cli(bundle, OUTPUT)
    assert warm == cold


def test_z09_multi_bundle_consistency() -> None:
    """Multi-bundle workflow must stay consistent with per-bundle references."""
    digests: list[str] = []
    for bundle in bundle_files():
        _remove_if_present(OUTPUT)
        report = run_cli(bundle, OUTPUT)
        assert report == reference_report(bundle)
        digests = [*digests, report_digest(report)]
    assert len(set(digests)) == len(digests)


def test_z10_lyon_exchange_overlay_blend() -> None:
    """Exchange ledgers require amendment overlays, digest binding, and family blend."""
    prague = BUNDLES / "lyon_silk_exchange.json"
    report = run_cli(prague)
    expected = reference_report(prague)
    assert report == expected
    antwerp = reference_report(BUNDLES / "suzhou_brocade_division.json")
    assert report["network_seal"] != antwerp["network_seal"]
    viola = next(r for r in report["panels"] if r["panel_id"] == "panel_lyon_velours_exchange")
    assert viola["weaver_lineage"] == expected["panels"][0]["weaver_lineage"]


def test_z11_all_bundles_batch() -> None:
    """Every runnable bundle file must trace to full reference parity."""
    for bundle in bundle_files():
        out = _scratch(f"b_{bundle.stem}.json")
        report = run_cli(bundle, out)
        assert report == reference_report(bundle)


def test_z13_kyoto_salon_blend_applied() -> None:
    """Kyoto pedal salon bundle must use the salon genealogy_blend family weights."""
    bundle = BUNDLES / "kyoto_nishijin_salon.json"
    report = run_cli(bundle)
    expected = reference_report(bundle)
    assert report == expected
    suzhou = reference_report(BUNDLES / "suzhou_brocade_division.json")
    assert report["summary"]["mean_influence"] != suzhou["summary"]["mean_influence"]


def test_z14_dye_fidelity_never_exceeds_one() -> None:
    """Restoration decay factors must stay within the multiplicative voicing envelope."""
    for bundle in bundle_files():
        report = run_cli(bundle, _scratch(f"d_{bundle.stem}.json"))
        for row in report["panels"]:
            assert 0.0 <= row["dye_fidelity"] <= 1.0


def test_z15_school_continuity_percentage_band() -> None:
    """Provenance coverage must remain on the documented 0-100 percentage scale."""
    bundle = BUNDLES / "isfahan_persian_circulation.json"
    report = run_cli(bundle)
    for row in report["panels"]:
        assert 0.0 <= row["school_continuity"] <= 100.0


def test_z16_lyon_overlay_lowers_dye_fidelity() -> None:
    """Lyon exchange amendment overlays must participate in restoration decay compounding."""
    bundle = BUNDLES / "lyon_silk_exchange.json"
    report = run_cli(bundle)
    mixture = next(
        r for r in report["panels"] if r["panel_id"] == "panel_lyon_velours_exchange"
    )
    assert mixture["dye_fidelity"] < 1.0
    assert mixture["dye_fidelity"] == reference_report(bundle)["panels"][0]["dye_fidelity"]


def test_z17_varanasi_alias_pedigree_matches_canonical_builder() -> None:
    """Varanasi archive alias must resolve builder lineage through the canonical workshop row."""
    bundle = BUNDLES / "varanasi_banarasi_archive.json"
    report = run_cli(bundle)
    panels = _load_registry(Path("/app/data/panels"))
    view = _resolve_entry("panel_banarasi_archive", panels)
    master_weavers = _load_registry(Path("/app/data/master_weavers"))
    mentor_of = _active_mentor_of(
        master_weavers["mentor_of"],
        master_weavers.get("lineage_epochs", {}),
        view["completion_year"],
    )
    expected_depth = round(_accumulate_trust(view["weaver_id"], mentor_of, master_weavers), 6)
    assert report["panels"][0]["weaver_lineage"] == expected_depth


def test_z20_network_seal_lowercase_hex() -> None:
    """Forge stamps must be 24-character lowercase hexadecimal digests."""
    for bundle in bundle_files():
        report = run_cli(bundle, _scratch(f"s_{bundle.stem}.json"))
        stamp = report["network_seal"]
        assert len(stamp) == 24
        assert stamp == stamp.lower()
        assert all(ch in "0123456789abcdef" for ch in stamp)


def test_z21_halt_journal_network_seal_matches_resume() -> None:
    """Halt journal network_seal must match the resumed cold compile when registries are unchanged."""
    bundle = BUNDLES / "suzhou_brocade_division.json"
    journal = JOURNAL
    halt_out = _scratch("halt.json")
    for path in (journal, halt_out, OUTPUT):
        _remove_if_present(path)
    run_cli(bundle, halt_out, {"TRACE_HALT": "1"}, read_output=False)
    saved = json.loads(journal.read_text())
    resumed = run_cli(bundle, halt_out, {"TRACE_RESUME": "1"})
    cold = run_cli(bundle, OUTPUT)
    assert saved["network_seal"] == resumed["network_seal"] == cold["network_seal"]


def test_z22_heritage_score_within_blend_envelope() -> None:
    """Authenticity score must fall between floor-only and full-span passport blend products."""
    bundle = BUNDLES / "suzhou_brocade_division.json"
    blend = _load_blend(json.loads(bundle.read_text()))
    report = run_cli(bundle)
    anchors = _load_registry(Path("/app/data/pattern_anchors"))
    panels = _load_registry(Path("/app/data/panels"))
    floor = blend["letter_floor"]
    ceiling = floor + blend["letter_span"]
    for row in report["panels"]:
        canonical = _resolve_entry(row["panel_id"], panels)["canonical_id"]
        anchor = anchors[canonical]["base_appraisal"]
        core = anchor * row["weaver_lineage"] * row["dye_fidelity"]
        low = round(core * floor, 2)
        high = round(core * ceiling, 2)
        assert low <= row["heritage_score"] <= high


def test_z23_sequential_drift_coupling_seeds_later_panel() -> None:
    """Sequential panel_coupling must seed later panels from prior dye_fidelity."""
    bundle = BUNDLES / "suzhou_brocade_division.json"
    report = run_cli(bundle)
    panels = _load_registry(Path("/app/data/panels"))
    blend = _load_blend(json.loads(bundle.read_text()))
    first = report["panels"][0]
    second = report["panels"][1]
    view_second = _resolve_entry(second["panel_id"], panels)
    dye_reformulations = _load_dye_reformulations(Path("/app/data"))
    epochs_second = list(_load_registry(Path("/app/data/export_routes")).get(view_second["canonical_id"], []))
    dye_second = list(dye_reformulations.get(view_second["canonical_id"], []))
    dye_clip, epochs_clip = _clip_timeline(json.loads(bundle.read_text()), dye_second, epochs_second)
    scoped = _gated_dye_reformulations(
        dye_clip,
        epochs_clip,
        _load_registry(Path("/app/data/school_recitals")).get(view_second["canonical_id"], []),
    )
    independent = round(_compound_dye_reformulations(scoped, blend["dye_penalty_rate"], 1.0), 6)
    seeded = round(
        _compound_dye_reformulations(scoped, blend["dye_penalty_rate"], first["dye_fidelity"]),
        6,
    )
    assert second["dye_fidelity"] == seeded
    assert second["dye_fidelity"] != independent
    assert report == reference_report(bundle)


def test_z24_reset_drift_event_clears_compounding_sequence() -> None:
    """reset_drift reformulation rows must zero the running drift factor before later events."""
    bundle = BUNDLES / "suzhou_brocade_division.json"
    blend = _load_blend(json.loads(bundle.read_text()))
    panels = _load_registry(Path("/app/data/panels"))
    panel_id = "panel_mandarin_cloud_suzhou"
    canonical = _resolve_entry(panel_id, panels)["canonical_id"]
    dye_reformulations = list(_load_dye_reformulations(Path("/app/data")).get(canonical, []))
    epochs = list(_load_registry(Path("/app/data/export_routes")).get(canonical, []))
    scoped = _gated_dye_reformulations(
        dye_reformulations,
        epochs,
        _load_registry(Path("/app/data/school_recitals")).get(canonical, []),
    )
    with_reset = round(_compound_dye_reformulations(scoped, blend["dye_penalty_rate"]), 6)
    stripped = [row for row in scoped if not row.get("reset_drift")]
    without_reset = round(_compound_dye_reformulations(stripped, blend["dye_penalty_rate"]), 6)
    assert with_reset != without_reset
    report = run_cli(bundle)
    first = next(row for row in report["panels"] if row["panel_id"] == panel_id)
    assert first["dye_fidelity"] == with_reset
    assert report == reference_report(bundle)


def test_z25_isfahan_snapshot_lowers_dye_fidelity() -> None:
    """Isfahan snapshot cutoff must exclude post-1970 restoration events from decay compounding."""
    bundle = BUNDLES / "isfahan_persian_circulation.json"
    report = run_cli(bundle)
    clipped = report["panels"][0]["dye_fidelity"]
    bundle_data = json.loads(bundle.read_text())
    bundle_data.pop("genealogy_snapshot", None)
    unbounded_path = _write_probe_bundle(bundle_data)
    unbounded = run_cli(unbounded_path, _scratch("u_isf.json"))
    unclipped = unbounded["panels"][0]["dye_fidelity"]
    assert clipped > unclipped
    assert clipped == reference_report(bundle)["panels"][0]["dye_fidelity"]


def test_z26_resume_discards_stale_journal_stamp() -> None:
    """Resume must cold-compile when the journal network_seal no longer matches live context."""
    bundle = BUNDLES / "suzhou_brocade_division.json"
    journal = JOURNAL
    out = _scratch("stale.json")
    for path in (journal, out, OUTPUT):
        _remove_if_present(path)
    run_cli(bundle, out, {"TRACE_HALT": "1"}, read_output=False)
    stale = json.loads(journal.read_text())
    stale["network_seal"] = "0" * 24
    _write_json(journal, stale)
    resumed = run_cli(bundle, out, {"TRACE_RESUME": "1"})
    cold = reference_report(bundle)
    assert resumed == cold


def test_z27_cross_bundle_incremental_state_isolation() -> None:
    """Incremental replay state from one bundle must not affect the next bundle compile."""
    suzhou = BUNDLES / "suzhou_brocade_division.json"
    freiburg = BUNDLES / "varanasi_banarasi_archive.json"
    run_cli(suzhou, OUTPUT, {"TRACE_INCREMENTAL": "1"})
    _remove_if_present(OUTPUT)
    report = run_cli(freiburg, OUTPUT)
    assert report == reference_report(freiburg)


def test_z28_genoa_alias_shares_school_continuity() -> None:
    """Genoa trumpet deposit alias must inherit canonical provenance coverage."""
    bundle = BUNDLES / "genoa_merchant_society.json"
    report = run_cli(bundle)
    bundle_data = json.loads(bundle.read_text())
    canonical_id = bundle_data["panels"][0]["panel_id"]
    alias_id = bundle_data["panels"][1]["panel_id"]
    canonical_row = next(r for r in report["panels"] if r["panel_id"] == canonical_id)
    alias_row = next(r for r in report["panels"] if r["panel_id"] == alias_id)
    assert alias_row["school_continuity"] == canonical_row["school_continuity"]


def test_z29_lyon_exchange_family_penalty_differs_from_standard() -> None:
    """Lyon exchange bundle must compound restoration with the exchange policy penalty rate."""
    exchange = BUNDLES / "lyon_silk_exchange.json"
    exchange_report = run_cli(exchange, _scratch("ly_ex.json"))
    standard_blend = _load_blend({"policy_family": "standard"})
    exchange_blend = _load_blend(json.loads(exchange.read_text()))
    assert exchange_blend["dye_penalty_rate"] > standard_blend["dye_penalty_rate"]
    mixture = exchange_report["panels"][0]
    assert mixture["dye_fidelity"] == reference_report(exchange)["panels"][0]["dye_fidelity"]


def test_z31_kyoto_salon_snapshot_clips_parish_span() -> None:
    """Kyoto salon snapshot must clip church-assignment epochs before passport attestation."""
    bundle = BUNDLES / "kyoto_nishijin_salon.json"
    clipped_report = run_cli(bundle)
    bundle_data = json.loads(bundle.read_text())
    bundle_data.pop("genealogy_snapshot", None)
    unbounded_path = _write_probe_bundle(bundle_data)
    unbounded_report = run_cli(unbounded_path, _scratch("u_kyo.json"))
    clipped_cov = clipped_report["panels"][0]["school_continuity"]
    unbounded_cov = unbounded_report["panels"][0]["school_continuity"]
    assert clipped_cov != unbounded_cov
    assert clipped_report == reference_report(bundle)


def test_z32_session_blend_isolation() -> None:
    """Session-scoped blend tables must not leak across policy-family changes."""
    standard = BUNDLES / "suzhou_brocade_division.json"
    exchange = BUNDLES / "lyon_silk_exchange.json"
    run_cli(standard, _scratch("w_suz.json"))
    _remove_if_present(OUTPUT)
    exchange_report = run_cli(exchange, _scratch("w_lyo.json"))
    isolated = run_cli(exchange, _scratch("i_lyo.json"))
    assert exchange_report == reference_report(exchange)
    assert isolated == reference_report(exchange)
    standard_alone = run_cli(standard, _scratch("i_suz.json"))
    assert standard_alone == reference_report(standard)
    assert exchange_report["panels"][0]["heritage_score"] != standard_alone["panels"][0]["heritage_score"]


def test_z33_dye_lane_gate_before_compound() -> None:
    """Dye restoration must gate reformulations before multiplicative compounding."""
    bundle = BUNDLES / "genoa_merchant_society.json"
    report = run_cli(bundle, _scratch("w_gen.json"))
    expected = reference_report(bundle)
    assert report == expected
    merchant = next(
        row for row in report["panels"] if row["panel_id"] == "panel_genoa_brocade_merchant"
    )
    ungated = _ungated_clipped_dye_fidelity(bundle, "panel_genoa_brocade_merchant")
    assert merchant["dye_fidelity"] == expected["panels"][0]["dye_fidelity"]
    assert ungated != merchant["dye_fidelity"]


def test_z34_same_interpreter_multi_build_isolation() -> None:
    """Two or more builds in one interpreter must not leak blend or replay state."""
    from shed_weave.report_builder import build_pattern_genealogy
    from shed_weave.trace_profile import clear_trace_profile

    clear_trace_profile()
    suzhou = BUNDLES / "suzhou_brocade_division.json"
    lyon = BUNDLES / "lyon_silk_exchange.json"
    first = build_pattern_genealogy(suzhou)
    second = build_pattern_genealogy(lyon)
    third = build_pattern_genealogy(suzhou)
    assert first == reference_report(suzhou)
    assert second == reference_report(lyon)
    assert third == reference_report(suzhou)
    assert first["panels"][0]["heritage_score"] != second["panels"][0]["heritage_score"]


def test_z35_trace_data_root_cloned_registry() -> None:
    """TRACE_DATA_ROOT must load a cloned registry tree instead of pinned /app/data."""
    import shutil

    bundle = BUNDLES / "suzhou_brocade_division.json"
    baseline = run_cli(bundle, _scratch("c_base.json"))
    clone = Path(tempfile.mkdtemp(prefix="trace_data_", dir=str(OUT_DIR)))
    shutil.copytree("/app/data", clone, dirs_exist_ok=True)
    anchors_path = clone / "pattern_anchors" / "appraisals.json"
    anchors = json.loads(anchors_path.read_text())
    anchors["panel_mandarin_cloud_suzhou"]["base_appraisal"] = (
        float(anchors["panel_mandarin_cloud_suzhou"]["base_appraisal"]) + 250000.0
    )
    _write_json(anchors_path, anchors)
    cloned = run_cli(
        clone / "bundles" / "suzhou_brocade_division.json",
        _scratch("c_over.json"),
        {"TRACE_DATA_ROOT": str(clone)},
    )
    assert cloned["network_seal"] != baseline["network_seal"]
    assert cloned["panels"][0]["heritage_score"] != baseline["panels"][0]["heritage_score"]
    assert cloned["panels"][0]["heritage_score"] > baseline["panels"][0]["heritage_score"]
    pinned = run_cli(bundle, _scratch("c_pin.json"))
    assert pinned == baseline
