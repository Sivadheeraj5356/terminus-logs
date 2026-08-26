#!/usr/bin/env python3
"""Verifier for epoch-fuse FEM seal: coupling gaps, cascade compose, tip/bind replay."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
REPORT = APP / "output" / "invariant_proof_log.json"
STIFF = APP / "data" / "num_auth" / "gain_map.json"
DAMP = APP / "data" / "num_auth" / "fringe_map.json"
CPL = APP / "data" / "num_auth" / "coupling.json"
REFS = APP / "data" / "num_auth" / "ref_weights.json"
CLOCK = APP / "data" / "tb_state" / "clock.json"
CONTROLS = APP / "data" / "qv7_ctl" / "controls.json"
TIP = APP / "data" / "ms_store" / "tip.json"
BIND = APP / "data" / "ms_store" / "seal.bind"
JOURNAL = APP / "data" / "ms_store" / "mesh.wal"

# Verifier-owned fixed inputs (not agent-editable for grading).
_TESTS = Path(__file__).resolve().parent
FIXED = _TESTS / "fixed"
FIXED_BANDS_LIVE = FIXED / "bands_live"
FIXED_BANDS_SHADOW = FIXED / "bands_shadow"
FIXED_FIXTURES = FIXED / "fixtures"
FIXED_BOUNDS = FIXED / "num_auth" / "family_intervals.json"
PINNED = json.loads((_TESTS / "pinned_sha256.json").read_text(encoding="utf-8"))

NEXT = {"M1": "M2", "M2": "M3", "M3": "M4", "M4": "M1"}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_fixed_inputs_intact() -> None:
    """Protected catalogs/fixtures/bounds under /app/data must match verifier pins."""
    for rel, expected in PINNED.items():
        path = APP / rel
        assert path.is_file(), f"missing protected input {rel}"
        got = _sha256_file(path)
        assert got == expected, f"protected input mutated: {rel}"


def _fmt6(v: float) -> str:
    r = round(v, 6)
    if r == 0.0:
        r = 0.0
    return f"{r:.6f}"


def _weights(dir_path: Path) -> dict[str, float]:
    out: dict[str, float] = {}
    for path in sorted(dir_path.glob("L*.json")):
        obj = json.loads(path.read_text(encoding="utf-8"))
        out[obj["locale_id"]] = float(obj["weight"])
    return out


def _live_weights() -> dict[str, float]:
    return _weights(FIXED_BANDS_LIVE)


def _shadow_weights() -> dict[str, float]:
    return _weights(FIXED_BANDS_SHADOW)


def _require_epoch() -> int:
    idx = json.loads((FIXED_BANDS_LIVE / "index.json").read_text(encoding="utf-8"))
    return int(idx["require_epoch"])


def _peel_weights() -> tuple[dict[str, float], str]:
    clock = json.loads(CLOCK.read_text(encoding="utf-8"))
    epoch = int(clock["epoch"])
    if epoch >= _require_epoch():
        return _live_weights(), "live"
    return _shadow_weights(), "shadow"


def _load_cells() -> list[dict]:
    cells: list[dict] = []
    for path in sorted(FIXED_FIXTURES.glob("*.modes.json")):
        cells.extend(json.loads(path.read_text(encoding="utf-8")))
    return cells


def _family_bounds() -> dict:
    return json.loads(FIXED_BOUNDS.read_text(encoding="utf-8"))


def _scale(
    mode: str,
    excit: float,
    stiff: dict[str, float],
    damp: dict[str, float],
    cpl: dict[str, float],
    weight: float,
) -> float:
    nxt = NEXT[mode]
    return weight * excit * (
        stiff[mode] * damp[mode] + cpl[mode] * stiff[nxt] * damp[nxt]
    )


def _gap(
    cell: dict,
    stiff: dict[str, float],
    damp: dict[str, float],
    cpl: dict[str, float],
    weights: dict[str, float],
) -> float:
    return (cell["omega_obs"] - cell["omega_ref"]) - _scale(
        cell["mode"],
        cell["excit"],
        stiff,
        damp,
        cpl,
        weights[cell["locale"]],
    )


def _digest(
    cells: list[dict],
    stiff: dict[str, float],
    damp: dict[str, float],
    cpl: dict[str, float],
    weights: dict[str, float],
) -> str:
    by_panel: dict[str, list[float]] = {}
    for c in cells:
        by_panel.setdefault(c["panel_id"], []).append(_gap(c, stiff, damp, cpl, weights))
    parts = []
    for pid in sorted(by_panel):
        rs = ",".join(_fmt6(v) for v in by_panel[pid])
        parts.append(f"{pid}:{rs}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _rotate(m: dict[str, float]) -> dict[str, float]:
    return {"M1": m["M4"], "M2": m["M1"], "M3": m["M2"], "M4": m["M3"]}


def _permute_cells(cells: list[dict]) -> list[dict]:
    mapping = {"M1": "M2", "M2": "M3", "M3": "M4", "M4": "M1"}
    out = []
    for c in cells:
        n = dict(c)
        n["mode"] = mapping[c["mode"]]
        out.append(n)
    return out


def _reverse_weights(weights: dict[str, float]) -> dict[str, float]:
    locales = sorted(weights)
    vals = [weights[locale] for locale in locales][::-1]
    return {locale: vals[i] for i, locale in enumerate(locales)}


def _reverse_cells(cells: list[dict]) -> list[dict]:
    locales = sorted({c["locale"] for c in cells})
    mapping = {locales[i]: locales[len(locales) - 1 - i] for i in range(len(locales))}
    out = []
    for c in cells:
        n = dict(c)
        n["locale"] = mapping[c["locale"]]
        out.append(n)
    return out


def _chain(full: str, perm: str, rev: str, compose: str) -> str:
    return hashlib.sha256(f"{full}|{perm}|{rev}|{compose}".encode()).hexdigest()


def _seal() -> dict:
    subprocess.run(["bash", str(APP / "scripts" / "proof_run.sh")], check=True)
    assert REPORT.is_file(), "missing invariant proof log after seal"
    return json.loads(REPORT.read_text(encoding="utf-8"))


def _set_resume(flag: bool) -> None:
    obj = json.loads(CONTROLS.read_text(encoding="utf-8"))
    obj["resume_from_checkpoint"] = flag
    CONTROLS.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")


def _assert_report_contract(r: dict) -> None:
    for key in (
        "annex_slice",
        "authority_agreement",
        "digest_full",
        "digest_permute_modes",
        "digest_reverse_locale_bands",
        "digest_cascade_compose",
        "chain_digest",
        "metamorphic_equivalent",
        "panels",
        "total_bound_violations",
        "table_hash",
        "epoch_bind",
        "peel_source",
        "epoch",
        "lineage_id",
        "resumed",
    ):
        assert key in r
    assert r["annex_slice"] == 19
    assert isinstance(r["panels"], dict) and r["panels"]
    assert set(r["panels"]) >= {"P-SMOKE", "P-CORE", "P-EDGE", "P-CASCADE"}
    assert r["peel_source"] in {"live", "shadow"}
    assert int(r["epoch"]) > 0
    assert isinstance(r["authority_agreement"], bool)


@pytest.fixture(scope="module")
def sealed_report() -> dict:
    _assert_fixed_inputs_intact()
    _set_resume(False)
    return _seal()


def test_report_schema_epoch_and_cascade_coverage(sealed_report: dict) -> None:
    """Report carries epoch/peel/chain fields and the closed panel set including cascade."""
    _assert_fixed_inputs_intact()
    r = sealed_report
    _assert_report_contract(r)
    assert r["resumed"] is False
    assert r["peel_source"] == "live"
    assert int(r["epoch"]) >= _require_epoch()


def test_catalog_matches_live_peel_not_shadow_or_decoy(sealed_report: dict) -> None:
    """Catalog must match live peel weights — not shadow, not index decoy rows."""
    _assert_fixed_inputs_intact()
    refs = {k: float(v) for k, v in json.loads(REFS.read_text(encoding="utf-8")).items()}
    live = _live_weights()
    shadow = _shadow_weights()
    decoy = {
        k: float(v)
        for k, v in json.loads((FIXED_BANDS_LIVE / "index.json").read_text(encoding="utf-8"))[
            "weights_decoy"
        ].items()
    }
    assert refs == live
    assert refs != shadow
    assert refs != decoy
    assert sealed_report["authority_agreement"] is True
    assert sealed_report["authority_mismatched_locales"] == []
    assert sealed_report["peel_source"] == "live"


def test_zero_bound_violations_including_cascade(sealed_report: dict) -> None:
    """Every panel including cascade reports zero bound violations."""
    _assert_fixed_inputs_intact()
    assert sealed_report["total_bound_violations"] == 0
    for pid, row in sealed_report["panels"].items():
        assert row["bound_violations"] == 0, pid


def test_tightness_within_family_caps(sealed_report: dict) -> None:
    """Panel tightness stays at or below published max_tightness."""
    _assert_fixed_inputs_intact()
    bounds = _family_bounds()
    for pid, row in sealed_report["panels"].items():
        assert row["tightness"] <= row["max_tightness"] + 1e-9, pid
        assert row["tightness"] <= bounds[row["family"]]["max_tightness"] + 1e-9, pid


def test_metamorphic_and_cascade_compose_equivalence(sealed_report: dict) -> None:
    """Full digest matches permute, reverse, and cascade-compose arms."""
    _assert_fixed_inputs_intact()
    r = sealed_report
    assert r["total_bound_violations"] == 0
    assert r["peel_source"] == "live"
    assert r["authority_agreement"] is True
    assert r["metamorphic_equivalent"] is True
    assert r["digest_full"] == r["digest_permute_modes"]
    assert r["digest_full"] == r["digest_reverse_locale_bands"]
    assert r["digest_full"] == r["digest_cascade_compose"]


def test_coupled_recompute_and_chain_digest(sealed_report: dict) -> None:
    """Independent coupled-gap recompute matches sealed digests and chain digest."""
    _assert_fixed_inputs_intact()
    stiff = {k: float(v) for k, v in json.loads(STIFF.read_text(encoding="utf-8")).items()}
    damp = {k: float(v) for k, v in json.loads(DAMP.read_text(encoding="utf-8")).items()}
    cpl = {k: float(v) for k, v in json.loads(CPL.read_text(encoding="utf-8")).items()}
    peel, source = _peel_weights()
    assert source == "live"
    assert any(abs(v) > 1e-12 for v in cpl.values()), "coupling must be non-zero for cascade"
    cells = _load_cells()
    d_full = _digest(cells, stiff, damp, cpl, peel)
    d_perm = _digest(
        _permute_cells(cells),
        _rotate(stiff),
        _rotate(damp),
        _rotate(cpl),
        peel,
    )
    d_rev = _digest(_reverse_cells(cells), stiff, damp, cpl, _reverse_weights(peel))
    d_compose = _digest(
        _reverse_cells(_permute_cells(cells)),
        _rotate(stiff),
        _rotate(damp),
        _rotate(cpl),
        _reverse_weights(peel),
    )
    assert d_full == sealed_report["digest_full"]
    assert d_perm == sealed_report["digest_permute_modes"]
    assert d_rev == sealed_report["digest_reverse_locale_bands"]
    assert d_compose == sealed_report["digest_cascade_compose"]
    assert d_full == d_perm == d_rev == d_compose
    assert _chain(d_full, d_perm, d_rev, d_compose) == sealed_report["chain_digest"]
    # Scalar-only residual (coupling ignored) must diverge for cascade cells.
    for c in cells:
        if c["family"] != "heldout_cascade":
            continue
        scalar = (c["omega_obs"] - c["omega_ref"]) - (
            stiff[c["mode"]] * peel[c["locale"]] * c["excit"] * damp[c["mode"]]
        )
        coupled = _gap(c, stiff, damp, cpl, peel)
        assert abs(scalar - coupled) > 1e-6


def test_heldout_cascade_not_smoke_green(sealed_report: dict) -> None:
    """Held-out core/edge/cascade must clear; smoke-only green is insufficient."""
    _assert_fixed_inputs_intact()
    families = {row["family"] for row in sealed_report["panels"].values()}
    assert families >= {"smoke", "heldout_core", "heldout_edge", "heldout_cascade"}
    for row in sealed_report["panels"].values():
        assert row["bound_violations"] == 0


def test_tip_and_epoch_bind_regenerated(sealed_report: dict) -> None:
    """Tip and seal.bind are rewritten fresh and bind digest/chain/table hash."""
    _assert_fixed_inputs_intact()
    assert sealed_report["total_bound_violations"] == 0
    assert sealed_report["peel_source"] == "live"
    assert sealed_report["authority_agreement"] is True
    tip = json.loads(TIP.read_text(encoding="utf-8"))
    bind = json.loads(BIND.read_text(encoding="utf-8"))
    assert tip.get("stale") is False
    assert tip["total_bound_violations"] == 0
    assert tip["digest_full"] == sealed_report["digest_full"]
    assert tip["chain_digest"] == sealed_report["chain_digest"]
    assert tip["table_hash"] == sealed_report["table_hash"]
    assert tip["epoch_bind"] == sealed_report["epoch_bind"]
    assert bind["epoch_bind"] == tip["epoch_bind"]
    assert bind["table_hash"] == tip["table_hash"]
    assert int(bind["lineage_id"]) == int(tip["lineage_id"])
    clock_raw = CLOCK.read_bytes()
    expect = hashlib.sha256(clock_raw + b"|" + tip["table_hash"].encode()).hexdigest()
    assert tip["epoch_bind"] == expect


def test_repeat_seal_chain_idempotent(sealed_report: dict) -> None:
    """A second seal on an unchanged tree preserves digests and chain digest."""
    _assert_fixed_inputs_intact()
    assert sealed_report["total_bound_violations"] == 0
    assert sealed_report["peel_source"] == "live"
    first = sealed_report["digest_full"]
    first_chain = sealed_report["chain_digest"]
    _set_resume(False)
    second = _seal()
    assert second["total_bound_violations"] == 0
    assert second["digest_full"] == first
    assert second["chain_digest"] == first_chain
    assert second["digest_cascade_compose"] == sealed_report["digest_cascade_compose"]
    assert second["resumed"] is False


def test_clean_resume_preserves_full_report(sealed_report: dict) -> None:
    """A valid tip resume keeps digests and emits a complete public report contract."""
    _assert_fixed_inputs_intact()
    tip_before = json.loads(TIP.read_text(encoding="utf-8"))
    lineage_before = int(tip_before["lineage_id"])
    _set_resume(True)
    try:
        out = _seal()
        _assert_report_contract(out)
        assert out["resumed"] is True
        assert out["authority_agreement"] is True
        assert out["peel_source"] == "live"
        assert int(out["epoch"]) >= _require_epoch()
        assert out["total_bound_violations"] == 0
        assert out["metamorphic_equivalent"] is True
        assert out["digest_full"] == sealed_report["digest_full"]
        assert out["digest_permute_modes"] == sealed_report["digest_permute_modes"]
        assert out["digest_reverse_locale_bands"] == sealed_report["digest_reverse_locale_bands"]
        assert out["digest_cascade_compose"] == sealed_report["digest_cascade_compose"]
        assert out["chain_digest"] == sealed_report["chain_digest"]
        assert out["table_hash"] == sealed_report["table_hash"]
        assert out["epoch_bind"] == sealed_report["epoch_bind"]
        tip = json.loads(TIP.read_text(encoding="utf-8"))
        assert int(tip["lineage_id"]) == lineage_before
        assert tip["digest_full"] == out["digest_full"]
    finally:
        _set_resume(False)
        restored = _seal()
        assert restored["resumed"] is False
        assert restored["digest_full"] == sealed_report["digest_full"]


def test_torn_wal_recovers_and_advances_lineage(sealed_report: dict) -> None:
    """Torn WAL trailer must recover, reseal cleanly, and advance lineage."""
    _assert_fixed_inputs_intact()
    tip_before = json.loads(TIP.read_text(encoding="utf-8"))
    lineage_before = int(tip_before["lineage_id"])
    assert JOURNAL.is_file() and JOURNAL.stat().st_size > 8
    with JOURNAL.open("ab") as fh:
        fh.write(b"\xff\xfeTORN")
    _set_resume(False)
    recovered = _seal()
    assert recovered["total_bound_violations"] == 0
    assert recovered["metamorphic_equivalent"] is True
    assert recovered["digest_full"] == sealed_report["digest_full"]
    assert recovered["chain_digest"] == sealed_report["chain_digest"]
    tip = json.loads(TIP.read_text(encoding="utf-8"))
    bind = json.loads(BIND.read_text(encoding="utf-8"))
    assert tip.get("stale") is False
    assert tip["digest_full"] == recovered["digest_full"]
    assert int(tip["lineage_id"]) == lineage_before + 1
    assert int(bind["lineage_id"]) == int(tip["lineage_id"])


def test_bind_mismatch_or_authority_edit_blocks_resume(sealed_report: dict) -> None:
    """Broken seal.bind or clock edit must force rematerialize under resume."""
    _assert_fixed_inputs_intact()
    assert sealed_report["total_bound_violations"] == 0
    assert sealed_report["peel_source"] == "live"
    tip = json.loads(TIP.read_text(encoding="utf-8"))
    tip["stale"] = False
    tip["digest_full"] = sealed_report["digest_full"]
    tip["chain_digest"] = sealed_report["chain_digest"]
    tip["table_hash"] = sealed_report["table_hash"]
    tip["epoch_bind"] = sealed_report["epoch_bind"]
    tip["total_bound_violations"] = 0
    TIP.write_text(json.dumps(tip, indent=2) + "\n", encoding="utf-8")
    # Corrupt bind while leaving tip looking clean.
    BIND.write_text(
        json.dumps(
            {
                "epoch_bind": "e" * 64,
                "table_hash": sealed_report["table_hash"],
                "lineage_id": tip["lineage_id"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _set_resume(True)
    try:
        out = _seal()
        assert out.get("resumed") is False
        assert out["total_bound_violations"] == 0
        assert out["digest_full"] == sealed_report["digest_full"]
        bind = json.loads(BIND.read_text(encoding="utf-8"))
        assert bind["epoch_bind"] == out["epoch_bind"]
        assert bind["epoch_bind"] != "e" * 64
    finally:
        clock = json.loads(CLOCK.read_text(encoding="utf-8"))
        # Force a second rematerialize after a stale clock peek/repair path.
        clock["epoch"] = int(clock["epoch"])
        CLOCK.write_text(json.dumps(clock, indent=2) + "\n", encoding="utf-8")
        _set_resume(False)
        _seal()


def test_stale_resume_after_coupling_edit_does_not_skip(sealed_report: dict) -> None:
    """Mutating coupling invalidates table hash and must rematerialize under resume."""
    _assert_fixed_inputs_intact()
    assert sealed_report["total_bound_violations"] == 0
    assert sealed_report["peel_source"] == "live"
    cpl = json.loads(CPL.read_text(encoding="utf-8"))
    original = dict(cpl)
    mode = sorted(cpl.keys())[0]
    cpl[mode] = 0.0
    CPL.write_text(json.dumps(cpl, indent=2) + "\n", encoding="utf-8")
    tip = json.loads(TIP.read_text(encoding="utf-8"))
    tip["stale"] = False
    tip["digest_full"] = sealed_report["digest_full"]
    tip["chain_digest"] = sealed_report["chain_digest"]
    tip["table_hash"] = sealed_report["table_hash"]
    tip["epoch_bind"] = sealed_report["epoch_bind"]
    tip["total_bound_violations"] = 0
    TIP.write_text(json.dumps(tip, indent=2) + "\n", encoding="utf-8")
    bind = {
        "epoch_bind": sealed_report["epoch_bind"],
        "table_hash": sealed_report["table_hash"],
        "lineage_id": tip["lineage_id"],
    }
    BIND.write_text(json.dumps(bind, indent=2) + "\n", encoding="utf-8")
    _set_resume(True)
    try:
        out = _seal()
        assert out.get("resumed") is False
        assert out.get("table_hash") != sealed_report["table_hash"]
        assert len(out.get("digest_full", "")) == 64
        # Coupling drift must surface as cascade/held-out stress under live peel.
        assert out["total_bound_violations"] > 0
    finally:
        CPL.write_text(json.dumps(original, indent=2) + "\n", encoding="utf-8")
        _set_resume(False)
        restored = _seal()
        assert restored["total_bound_violations"] == 0


def test_family_intervals_include_cascade(sealed_report: dict) -> None:
    """Family bound table includes cascade; sealed run must respect those caps."""
    _assert_fixed_inputs_intact()
    bounds = _family_bounds()
    assert set(bounds) >= {"smoke", "heldout_core", "heldout_edge", "heldout_cascade"}
    for fam, b in bounds.items():
        assert b["hi"] > b["lo"], fam
        assert 0 < b["max_tightness"] <= 1.0
    assert sealed_report["total_bound_violations"] == 0
    assert sealed_report["peel_source"] == "live"
    for row in sealed_report["panels"].values():
        assert row["tightness"] <= bounds[row["family"]]["max_tightness"] + 1e-9
