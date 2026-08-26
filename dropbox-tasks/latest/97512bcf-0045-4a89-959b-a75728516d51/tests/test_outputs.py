"""Cryovac sealed N2/He cooldown verifier — free-volume EOS, fugacity sorption, gated calibration."""

from __future__ import annotations

import json
import math
import random
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema

CRYOVAC_BIN = Path("/app/bin/cryovac")
CRYOVAC_SPECIES_PATH = Path("/app/config/species.json")
CRYOVAC_CHAMBER_TOML = Path("/app/config/chamber.toml")
CRYOVAC_FEED_PATH = Path("/app/data/profiles/n2_he_cooldown.json")
CRYOVAC_CAL_PATH = Path("/app/data/calibration/sorption_cal.ndjson")
CRYOVAC_SCHEMA_PATH = Path("/app/docs/schema.json")
CRYOVAC_R_GAS = 8.314
CRYOVAC_CHAMBER_M3 = 0.012


@dataclass(frozen=True)
class CryovacTrace:
    path: Path
    doc: dict[str, Any]

    def station(self, temp_k: float, *, occurrence: int = 0) -> dict[str, Any]:
        hits = [row for row in self.doc["history"] if abs(float(row["temp_k"]) - temp_k) < 1e-9]
        if occurrence >= len(hits):
            raise AssertionError(f"missing station {temp_k}#{occurrence}")
        return hits[occurrence]


def cryovac_rebuild_binary() -> None:
    subprocess.run(["make", "-C", "/app", "clean", "all"], check=True, capture_output=True)


def cryovac_run_trace(
    dest: Path,
    *,
    feed: Path = CRYOVAC_FEED_PATH,
    cal: Path = CRYOVAC_CAL_PATH,
    volume_m3: float = CRYOVAC_CHAMBER_M3,
) -> CryovacTrace:
    proc = subprocess.run(
        [
            str(CRYOVAC_BIN),
            "--profile",
            str(feed),
            "--calibration",
            str(cal),
            "--out",
            str(dest),
            "--volume",
            str(volume_m3),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == ""
    return CryovacTrace(dest, json.loads(dest.read_text(encoding="utf-8")))


def cryovac_load_species() -> tuple[dict[str, float], dict[str, float]]:
    blob = json.loads(CRYOVAC_SPECIES_PATH.read_text(encoding="utf-8"))
    return blob["N2"], blob["He"]


def cryovac_feed_inventory() -> tuple[float, float]:
    feed = json.loads(CRYOVAC_FEED_PATH.read_text(encoding="utf-8"))
    return float(feed["n_n2"]), float(feed["n_he"])


def cryovac_free_volume_from_film(n_cond: float, v_geom: float, n2: dict[str, float]) -> float:
    v = v_geom - float(n2["kappa_film"]) * n_cond
    vmin = v_geom * float(n2["vmin_frac"])
    return max(v, vmin)


def cryovac_lorentz_berthelot_pressure(
    n_n2: float,
    n_he: float,
    v: float,
    t: float,
    a1: float,
    b1: float,
    a2: float,
    b2: float,
) -> float:
    n = n_n2 + n_he
    x1, x2 = n_n2 / n, n_he / n
    a = x1 * x1 * a1 + x2 * x2 * a2 + 2.0 * x1 * x2 * math.sqrt(a1 * a2)
    b = x1 * b1 + x2 * b2
    return (n * CRYOVAC_R_GAS * t) / (v - n * b) - a * n * n / (v * v)


def test_warm_station_pressure_matches_lorentz_berthelot_free_volume(tmp_path: Path) -> None:
    """Warm p_total matches LB VdW on V_free from reported condensate within 0.1%."""
    warm = cryovac_run_trace(tmp_path / "p.json").station(293.15)
    n2, he = cryovac_load_species()
    v = cryovac_free_volume_from_film(float(warm["n_cond_n2"]), CRYOVAC_CHAMBER_M3, n2)
    expect = cryovac_lorentz_berthelot_pressure(
        warm["n_gas_n2"], warm["n_gas_he"], v, 293.15, n2["a"], n2["b"], he["a"], he["b"]
    )
    assert abs(warm["p_total"] - expect) / expect < 0.001


def test_sealed_mole_ledger_closes_for_nitrogen_and_helium(tmp_path: Path) -> None:
    """Sealed N2 and He mole ledgers close at every station."""
    n2_tot, he_tot = cryovac_feed_inventory()
    for row in cryovac_run_trace(tmp_path / "led.json").doc["history"]:
        assert abs(row["n_gas_n2"] + row["n_ads_n2"] + row["n_cond_n2"] - n2_tot) < 1e-9
        assert abs(row["n_gas_he"] + row["n_ads_he"] - he_tot) < 1e-9
        assert row["n_cond_n2"] >= -1e-15  # He never in bulk film; cond is N2-only


def test_sticky_anyleg_retains_authority_through_one_fifty_overlay(tmp_path: Path) -> None:
    """140→150 K sticky any-leg seq 3 survives ascend overlay seq 13."""
    tr = cryovac_run_trace(tmp_path / "s150.json")
    assert tr.station(140.0)["cal_seq"] == 3
    hop = tr.station(150.0)
    assert hop["thermal_leg"] == 1
    assert hop["cal_seq"] == 3


def test_sticky_anyleg_blocks_midband_overlay_at_one_hundred(tmp_path: Path) -> None:
    """90→100 K sticky seq 3 blocks mid-band overlay seq 12."""
    tr = cryovac_run_trace(tmp_path / "s100.json")
    assert tr.station(90.0)["cal_seq"] == 3
    assert tr.station(100.0)["cal_seq"] == 3


def test_requires_prev_seq_gate_arms_ten_not_eleven_at_sixty(tmp_path: Path) -> None:
    """60 K descend: requires_prev_seq arms seq 10; bait seq 11 must not win."""
    deep = cryovac_run_trace(tmp_path / "gate.json").station(60.0)
    assert deep["thermal_leg"] == 0
    assert deep["cal_seq"] == 10
    assert deep["frozen"] is True
    assert deep["n_cond_n2"] > 1.0


def test_ascend_only_band_wins_first_sixty_five_while_frozen(tmp_path: Path) -> None:
    """First 65 K hop is ascend leg with seq 9 while still frozen."""
    mid = cryovac_run_trace(tmp_path / "a65.json").station(65.0, occurrence=0)
    assert mid["thermal_leg"] == 1
    assert mid["cal_seq"] == 9
    assert mid["frozen"] is True


def test_equal_temperature_dwell_reuses_prior_ascend_leg(tmp_path: Path) -> None:
    """Second 65 K equal-T dwell reuses ascend leg and seq 9."""
    dwell = cryovac_run_trace(tmp_path / "dwell.json").station(65.0, occurrence=1)
    assert dwell["thermal_leg"] == 1
    assert dwell["cal_seq"] == 9
    assert dwell["frozen"] is True


def test_freeze_lock_holds_nitrogen_adsorbate_across_leg_flip(tmp_path: Path) -> None:
    """N2 adsorbate locked 60→65 K while cal_seq flips 10→9."""
    tr = cryovac_run_trace(tmp_path / "lock.json")
    deep = tr.station(60.0)
    mid = tr.station(65.0, occurrence=0)
    assert deep["cal_seq"] == 10
    assert mid["cal_seq"] == 9
    assert abs(mid["n_ads_n2"] - deep["n_ads_n2"]) < 1e-12
    assert mid["n_cond_n2"] >= deep["n_cond_n2"] - 1e-12


def test_thaw_station_wall_hold_preserves_nitrogen_adsorbate(tmp_path: Path) -> None:
    """75 K thaw station keeps N2 adsorbate from prior frozen dwell."""
    tr = cryovac_run_trace(tmp_path / "hold.json")
    prior = tr.station(65.0, occurrence=1)
    thaw = tr.station(75.0)
    assert thaw["frozen"] is False
    assert abs(thaw["n_ads_n2"] - prior["n_ads_n2"]) < 1e-12
    assert thaw["regime"] in ("two-phase", "gas")


def test_narrower_duplicate_seq_wins_at_nitrogen_boiloff(tmp_path: Path) -> None:
    """77.3 K descend picks narrower seq-8 band (n_sites=0.15), not the wider 0.12 row."""
    default = cryovac_run_trace(tmp_path / "tie.json").station(77.3)
    assert default["thermal_leg"] == 0
    assert default["cal_seq"] == 8
    assert default["n_cond_n2"] < 1e-9

    lines = [ln for ln in CRYOVAC_CAL_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    narrow_line = (
        '{"seq": 8, "K_n2": 3.0e-6, "K_he": 4.0e-7, "n_sites": 0.15, '
        '"t_min": 50.0, "t_max": 80.0, "leg": "descend"}'
    )
    wide_line = (
        '{"seq": 8, "K_n2": 2.9e-6, "K_he": 4.1e-7, "n_sites": 0.12, '
        '"t_min": 45.0, "t_max": 90.0, "leg": "descend"}'
    )
    base = [ln for ln in lines if '"seq": 8' not in ln and '"seq":8' not in ln.replace(" ", "")]
    narrow_cal = tmp_path / "narrow_only.ndjson"
    wide_cal = tmp_path / "wide_only.ndjson"
    narrow_cal.write_text("\n".join(base + [narrow_line]) + "\n", encoding="utf-8")
    wide_cal.write_text("\n".join(base + [wide_line]) + "\n", encoding="utf-8")
    narrow = cryovac_run_trace(tmp_path / "tie_n.json", cal=narrow_cal).station(77.3)
    wide = cryovac_run_trace(tmp_path / "tie_w.json", cal=wide_cal).station(77.3)
    assert narrow["n_ads_n2"] > wide["n_ads_n2"]
    assert abs(default["n_ads_n2"] - narrow["n_ads_n2"]) < 1e-9
    assert abs(default["n_ads_n2"] - wide["n_ads_n2"]) > 1e-6


def test_inclusive_upper_band_edge_at_eighty_selects_descend_seq_eight(tmp_path: Path) -> None:
    """80 K inclusive upper edge of a sole seq-8 descend band must apply (not half-open)."""
    lines = [ln for ln in CRYOVAC_CAL_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    base = [ln for ln in lines if '"seq": 8' not in ln and '"seq":8' not in ln.replace(" ", "")]
    sole = (
        '{"seq": 8, "K_n2": 3.0e-6, "K_he": 4.0e-7, "n_sites": 0.15, '
        '"t_min": 50.0, "t_max": 80.0, "leg": "descend"}'
    )
    cal = tmp_path / "edge80.ndjson"
    cal.write_text("\n".join(base + [sole]) + "\n", encoding="utf-8")
    edge = cryovac_run_trace(tmp_path / "edge80.json", cal=cal).station(80.0)
    assert edge["thermal_leg"] == 0
    assert edge["cal_seq"] == 8


def test_default_out_path_writes_vacuum_simulation_json() -> None:
    """Omitting --out writes a schema-valid trace to /app/vacuum_simulation.json."""
    default_out = Path("/app/vacuum_simulation.json")
    if default_out.exists():
        default_out.unlink()
    proc = subprocess.run(
        [
            str(CRYOVAC_BIN),
            "--profile",
            str(CRYOVAC_FEED_PATH),
            "--calibration",
            str(CRYOVAC_CAL_PATH),
            "--volume",
            str(CRYOVAC_CHAMBER_M3),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == ""
    assert default_out.is_file()
    doc = json.loads(default_out.read_text(encoding="utf-8"))
    schema = json.loads(CRYOVAC_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=doc, schema=schema)


def test_shuffled_calibration_ndjson_is_authority_invariant(tmp_path: Path) -> None:
    """Shuffled calibration NDJSON leaves cal_seq and N2 adsorbate path unchanged."""
    lines = [ln for ln in CRYOVAC_CAL_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    rng = random.Random(20260716)
    shuffled = lines[:]
    rng.shuffle(shuffled)
    cal = tmp_path / "shuffled.ndjson"
    cal.write_text("\n".join(shuffled) + "\n", encoding="utf-8")
    a = cryovac_run_trace(tmp_path / "o.json")
    b = cryovac_run_trace(tmp_path / "s.json", cal=cal)
    for ta, tb in zip(a.doc["history"], b.doc["history"], strict=True):
        assert ta["cal_seq"] == tb["cal_seq"]
        assert abs(ta["n_ads_n2"] - tb["n_ads_n2"]) < 1e-9


def test_crlf_and_blank_line_calibration_stream_parses_identically(tmp_path: Path) -> None:
    """CRLF terminators and blank lines must not change authority or inventories."""
    lines = [ln for ln in CRYOVAC_CAL_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    crlf = tmp_path / "crlf.ndjson"
    # Insert blank lines and use CRLF endings.
    body = "\r\n\r\n".join(lines) + "\r\n"
    crlf.write_bytes(body.encode("utf-8"))
    a = cryovac_run_trace(tmp_path / "lf.json")
    b = cryovac_run_trace(tmp_path / "cr.json", cal=crlf)
    for ta, tb in zip(a.doc["history"], b.doc["history"], strict=True):
        assert ta["cal_seq"] == tb["cal_seq"]
        assert abs(ta["n_ads_n2"] - tb["n_ads_n2"]) < 1e-9
        assert abs(ta["p_total"] - tb["p_total"]) / max(ta["p_total"], 1e-12) < 0.001


def test_final_warmback_selects_high_temperature_band(tmp_path: Path) -> None:
    """Final 293.15 K station uses seq 6 on ascend leg."""
    final = cryovac_run_trace(tmp_path / "w.json").doc["history"][-1]
    assert abs(final["temp_k"] - 293.15) < 1e-9
    assert final["cal_seq"] == 6
    assert final["thermal_leg"] == 1


def test_fugacity_langmuir_loads_helium_when_warm(tmp_path: Path) -> None:
    """Warm fugacity Langmuir leaves measurable helium on the wall."""
    assert cryovac_run_trace(tmp_path / "he.json").station(293.15)["n_ads_he"] > 1e-4


def test_helium_feed_suppresses_nitrogen_wall_load_at_midband(tmp_path: Path) -> None:
    """Near-pure N2 feed adsorbs more N2 at 140 K than the mixed feed."""
    cryovac_rebuild_binary()
    base = json.loads(CRYOVAC_FEED_PATH.read_text(encoding="utf-8"))
    mixed = tmp_path / "mf.json"
    solo = tmp_path / "sf.json"
    mixed.write_text(json.dumps(base), encoding="utf-8")
    s = dict(base)
    s["n_he"] = 1e-12
    solo.write_text(json.dumps(s), encoding="utf-8")
    assert cryovac_run_trace(tmp_path / "solo.json", feed=solo).station(140.0)["n_ads_n2"] > cryovac_run_trace(
        tmp_path / "mix.json", feed=mixed
    ).station(140.0)["n_ads_n2"]


def test_deep_freeze_fixed_point_needs_multiple_solver_passes(tmp_path: Path) -> None:
    """Deep freeze reports solver_iters >= 2 with coexisting ads and film."""
    deep = cryovac_run_trace(tmp_path / "iter.json").station(60.0)
    assert deep["solver_iters"] >= 2
    assert deep["n_ads_n2"] > 1e-4
    assert deep["regime"] == "frozen-film"


def test_post_thaw_warmback_eventually_clears_bulk_film(tmp_path: Path) -> None:
    """After thaw hold, final warm station is gas with no condensate."""
    final = cryovac_run_trace(tmp_path / "thaw.json").station(293.15)
    assert final["regime"] == "gas"
    assert final["n_cond_n2"] < 1e-9
    assert final["frozen"] is False


def test_tighter_geometry_grows_condensate_via_free_volume(tmp_path: Path) -> None:
    """Smaller geometric volume yields more nitrogen film at 60 K."""
    roomy = cryovac_run_trace(tmp_path / "rv.json", volume_m3=0.015).station(60.0)
    tight = cryovac_run_trace(tmp_path / "tv.json", volume_m3=0.009).station(60.0)
    assert tight["n_cond_n2"] > roomy["n_cond_n2"]


def test_freeze_station_pressure_uses_kappa_displaced_volume(tmp_path: Path) -> None:
    """60 K p_total matches LB on kappa-displaced V_free below geometric V."""
    deep = cryovac_run_trace(tmp_path / "vf.json").station(60.0)
    n2, he = cryovac_load_species()
    v = cryovac_free_volume_from_film(float(deep["n_cond_n2"]), CRYOVAC_CHAMBER_M3, n2)
    assert v < CRYOVAC_CHAMBER_M3 * 0.95
    expect = cryovac_lorentz_berthelot_pressure(
        deep["n_gas_n2"], deep["n_gas_he"], v, 60.0, n2["a"], n2["b"], he["a"], he["b"]
    )
    assert abs(deep["p_total"] - expect) / expect < 0.001


def test_helium_mole_fraction_rises_under_thick_nitrogen_film(tmp_path: Path) -> None:
    """Free-gas x_he at 60 K exceeds warm start and 0.70."""
    tr = cryovac_run_trace(tmp_path / "x.json")
    assert tr.station(60.0)["x_he"] > tr.station(293.15)["x_he"]
    assert tr.station(60.0)["x_he"] > 0.70


def test_output_document_validates_against_schema_contract(tmp_path: Path) -> None:
    """Output document validates against /app/docs/schema.json."""
    doc = cryovac_run_trace(tmp_path / "schema.json").doc
    schema = json.loads(CRYOVAC_SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(instance=doc, schema=schema)


def test_event_counters_and_station_metadata_present(tmp_path: Path) -> None:
    """Event counters and per-station leg/solver/cal metadata are populated."""
    doc = cryovac_run_trace(tmp_path / "meta.json").doc
    assert doc["condensation_events"] >= 1
    assert doc["freeze_events"] >= 1
    for row in doc["history"]:
        assert row["thermal_leg"] in (0, 1)
        assert row["solver_iters"] >= 1
        assert row["cal_seq"] >= 1


def test_species_hysteresis_thresholds_match_normative_model() -> None:
    """species.json N2 thresholds match thermo-model plant constants (63.15/68.0/0.012)."""
    n2, _ = cryovac_load_species()
    assert abs(float(n2["T_freeze"]) - 63.15) < 1e-9
    assert abs(float(n2["T_thaw"]) - 68.0) < 1e-9
    assert float(n2["T_thaw"]) > float(n2["T_freeze"])
    assert abs(float(n2["film_site_beta"]) - 0.012) < 1e-12


def test_chamber_toml_solver_limits_match_normative_model() -> None:
    """chamber.toml matches thermo-model solver limits (48 iters, 1e-10 tols)."""
    text = CRYOVAC_CHAMBER_TOML.read_text(encoding="utf-8")
    vals: dict[str, float] = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, raw = [p.strip() for p in s.split("=", 1)]
        vals[key] = float(raw)
    assert abs(vals["max_solver_iters"] - 48) < 1e-9
    assert abs(vals["ads_tol"] - 1.0e-10) < 1e-20
    assert abs(vals["cond_tol"] - 1.0e-10) < 1e-20


def test_unknown_cli_flag_is_fatal_exit_two(tmp_path: Path) -> None:
    """Unknown flags exit 2 with empty stdout and must not write --out."""
    dest = tmp_path / "nope.json"
    proc = subprocess.run(
        [str(CRYOVAC_BIN), "--profile", str(CRYOVAC_FEED_PATH), "--bogus", "x", "--out", str(dest)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 2
    assert proc.stdout.strip() == ""
    assert not dest.exists()


def test_repeated_out_flag_is_fatal_exit_two(tmp_path: Path) -> None:
    """Repeated --out is fatal exit 2 and must not clobber either destination."""
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    proc = subprocess.run(
        [
            str(CRYOVAC_BIN),
            "--calibration",
            str(CRYOVAC_CAL_PATH),
            "--out",
            str(a),
            "--out",
            str(b),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 2
    assert proc.stdout.strip() == ""
    assert not a.exists()
    assert not b.exists()


def test_nonpositive_volume_is_fatal_exit_two(tmp_path: Path) -> None:
    """Non-positive --volume exits 2 without writing output."""
    dest = tmp_path / "badvol.json"
    proc = subprocess.run(
        [
            str(CRYOVAC_BIN),
            "--out",
            str(dest),
            "--volume",
            "0",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 2
    assert proc.stdout.strip() == ""
    assert not dest.exists()


def test_invalid_negative_kn2_calibration_row_never_becomes_authority(tmp_path: Path) -> None:
    """Invalid K_n2<0 bait row must never appear as cal_seq on the cooldown path."""
    for row in cryovac_run_trace(tmp_path / "inv.json").doc["history"]:
        assert row["cal_seq"] != 5


def test_condensate_footprint_reduces_effective_sites_vs_zero_beta(tmp_path: Path) -> None:
    """With positive film_site_beta, deep-freeze N2 adsorbate is below the zero-beta counterfactual."""
    cryovac_rebuild_binary()
    n2, he = cryovac_load_species()
    assert float(n2["film_site_beta"]) > 0.0
    deep = cryovac_run_trace(tmp_path / "fp.json").station(60.0)
    # Residual sites after film must be strictly below raw n_sites for seq 10 (0.22).
    assert deep["n_ads_n2"] + deep["n_ads_he"] < 0.22 - 1e-6
    assert deep["n_cond_n2"] > 1.0
    _ = he
