"""Eco replay verifier suite."""

import csv
import json
import subprocess
from pathlib import Path

OUT = Path("/app/out")
REPLAY_SNAP = Path("/opt/w9_replay_snap.json")
SIDECAR = Path("/app/ref/sidecar_table.csv")


def _snap():
    return json.loads(REPLAY_SNAP.read_text())


def _require(actual, target, tol, label):
    assert abs(float(actual) - float(target)) <= tol, (
        f"{label}: {actual} vs {target} tol {tol}"
    )


def _row_slot_check(trace, coeff, sidecar, n, tol):
    ix = n - 1
    ref = sidecar[ix]
    for slot in ("slot_a", "slot_b", "slot_c", "slot_d"):
        got_trace = trace[f"band_row_{n}_{slot}"]
        got_coeff = coeff["bands"][ix][slot]
        val = ref[slot]
        _require(got_trace, val, tol, f"band {n} {slot} trace vs sidecar")
        _require(got_coeff, val, tol, f"band {n} {slot} coeff vs sidecar")


class TestEcoReplaySuite:
    @classmethod
    def setup_class(cls):
        OUT.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            ["node", "/app/environment/z9/w9_once.js"],
            cwd="/app",
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            cls.trace = {}
            cls.coeff = {"blend_weights": {}, "bands": [], "profiles": {}, "forcing": {}}
            cls.sidecar = []
            return
        cls.trace = cls._load_trace()
        cls.coeff = json.loads((OUT / "coeff_v9.json").read_text())
        cls.sidecar = cls._load_sidecar()

    @staticmethod
    def _load_sidecar():
        rows = []
        with SIDECAR.open(newline="") as fh:
            for row in csv.DictReader(fh):
                rows.append({
                    k: float(row[k]) if k != "row_ix" else int(row[k])
                    for k in row
                })
        return rows

    @staticmethod
    def _load_trace():
        data = {}
        for ln in (OUT / "trace_v9.log").read_text().splitlines():
            if "=" in ln:
                k, v = ln.split("=", 1)
                data[k.strip()] = float(v.strip())
        return data

    def test_e01_p7_rms(self):
        """p7 profile RMS matches contract replay within class A."""
        snap = _snap()["trace"]["p7_rms"]
        _require(self.trace["p7_rms"], snap, 0.08, "p7 rms vs replay snap")
        _require(self.trace["p7_rms"], self.coeff["profiles"]["p7_rms"], 1e-9, "p7 rms coeff")

    def test_e02_p8_rms(self):
        """p8 profile RMS matches contract replay within class A."""
        snap = _snap()["trace"]["p8_rms"]
        _require(self.trace["p8_rms"], snap, 0.08, "p8 rms vs replay snap")
        _require(self.trace["p8_rms"], self.coeff["profiles"]["p8_rms"], 1e-9, "p8 rms coeff")

    def test_e03_scalar_link(self):
        """Scalar link invariant holds in trace and coeff outputs."""
        w7 = self.coeff["blend_weights"]["p7"]
        w8 = self.coeff["blend_weights"]["p8"]
        link = w7 * self.trace["p7_rms"] + w8 * self.trace["p8_rms"]
        _require(self.trace["link_scalar"], link, 1e-9, "scalar link trace")
        _require(self.coeff["link_scalar"], link, 1e-9, "scalar link coeff")
        _require(self.trace["link_scalar"], _snap()["trace"]["link_scalar"], 0.08, "link scalar vs replay snap")

    def test_e04_weight_bounds(self):
        """Blend weights stay within config bounds and sum to one."""
        w7 = self.coeff["blend_weights"]["p7"]
        w8 = self.coeff["blend_weights"]["p8"]
        assert 0.2 <= w7 <= 0.8
        assert 0.2 <= w8 <= 0.8
        _require(w7 + w8, 1.0, 1e-6, "weight sum")
        _require(w7, _snap()["coeff"]["blend_weights"]["p7"], 1e-9, "p7 weight vs replay snap")
        _require(w8, _snap()["coeff"]["blend_weights"]["p8"], 1e-9, "p8 weight vs replay snap")

    def test_f01_lag_envelope(self):
        """Recovered phase_lag matches forcing estimate and contract replay within class B."""
        _require(self.trace["phase_lag"], self.coeff["forcing"]["phase0"], 0.12, "phase_lag vs forcing")
        _require(self.trace["phase_lag"], _snap()["trace"]["phase_lag"], 0.12, "phase_lag vs replay snap")

    def test_f02_amp_bounds(self):
        """Seasonal amplitudes match contract replay within class B ceilings."""
        _require(self.trace["seasonal_amp_p7"], _snap()["trace"]["seasonal_amp_p7"], 0.12, "amp p7 vs replay snap")
        _require(self.trace["seasonal_amp_p8"], _snap()["trace"]["seasonal_amp_p8"], 0.12, "amp p8 vs replay snap")
        assert self.trace["seasonal_amp_p7"] <= 0.2
        assert self.trace["seasonal_amp_p8"] <= 0.2

    def test_f03_trough_floor(self):
        """Prey trough depth on segment B matches contract replay within class C."""
        _require(self.trace["trough_depth_b"], _snap()["trace"]["trough_depth_b"], 0.18, "trough vs replay snap")
        assert self.trace["trough_depth_b"] >= 0.5

    def test_f04_peak_ceiling(self):
        """Predator peak height on segment B matches contract replay within class C."""
        _require(self.trace["peak_height_b"], _snap()["trace"]["peak_height_b"], 0.18, "peak vs replay snap")
        assert self.trace["peak_height_b"] <= 3.5

    def test_f05_envelope_skew(self):
        """Envelope skew metric matches contract replay within class B."""
        _require(self.trace["envelope_skew"], _snap()["trace"]["envelope_skew"], 0.12, "skew vs replay snap")
        assert self.trace["envelope_skew"] <= 2.0

    def test_g01_shift_metric(self):
        """Category shift metric matches contract replay within class C."""
        _require(self.trace["shift_metric"], _snap()["trace"]["shift_metric"], 0.18, "shift vs replay snap")

    def test_g02_log_restore(self):
        """Log1p restore error matches contract replay within class D."""
        _require(self.trace["log1p_restore_err"], _snap()["trace"]["log1p_restore_err"], 0.02, "log restore vs replay snap")

    def test_g03_coupling_polarity(self):
        """Interaction term polarity matches contract replay sign."""
        assert self.trace["coupling_sign"] == _snap()["trace"]["coupling_sign"]

    def test_g04_matrix_match(self):
        """Replay-derived band rows match sidecar table within class E."""
        for ix in range(66):
            _row_slot_check(self.trace, self.coeff, self.sidecar, ix + 1, 0.0005)

    def test_v01_segment_a_forward(self):
        """Segment A holdout RMS keys in trace match contract replay within class B."""
        snap = _snap()["trace"]
        _require(self.trace["segment_a_rms_x"], snap["segment_a_rms_x"], 0.12, "segment A prey RMS")
        _require(self.trace["segment_a_rms_y"], snap["segment_a_rms_y"], 0.12, "segment A predator RMS")

    def test_v02_segment_b_forward(self):
        """Segment B holdout RMS keys in trace match contract replay within class B."""
        snap = _snap()["trace"]
        _require(self.trace["segment_b_rms_x"], snap["segment_b_rms_x"], 0.12, "segment B prey RMS")
        _require(self.trace["segment_b_rms_y"], snap["segment_b_rms_y"], 0.12, "segment B predator RMS")

    def test_h01_coeff_trace_band_parity(self):
        """coeff bands array matches trace band_row keys row for row."""
        for ix, band in enumerate(self.coeff["bands"], start=1):
            for slot in ("slot_a", "slot_b", "slot_c", "slot_d"):
                trace_key = f"band_row_{ix}_{slot}"
                _require(self.trace[trace_key], band[slot], 1e-9, f"parity row {ix} {slot}")

    def test_h02_replay_idempotence(self):
        """Second replay reproduces byte-identical coeff and trace output files."""
        first = (OUT / "coeff_v9.json").read_bytes() + (OUT / "trace_v9.log").read_bytes()
        subprocess.run(
            [
                "node",
                "/app/environment/z9/w9_once.js",
            ],
            check=True,
            cwd="/app",
        )
        second = (OUT / "coeff_v9.json").read_bytes() + (OUT / "trace_v9.log").read_bytes()
        assert first == second, "replay artifacts changed on second run"


    def test_b01_sidecar_row(self):
        """Sidecar row 1 band slots match replay within class E."""
        _row_slot_check(self.trace, self.coeff, self.sidecar, 1, 0.0005)
    def test_b02_sidecar_row(self):
        """Sidecar row 7 band slots match replay within class E."""
        _row_slot_check(self.trace, self.coeff, self.sidecar, 7, 0.0005)
    def test_b03_sidecar_row(self):
        """Sidecar row 13 band slots match replay within class E."""
        _row_slot_check(self.trace, self.coeff, self.sidecar, 13, 0.0005)
    def test_b04_sidecar_row(self):
        """Sidecar row 19 band slots match replay within class E."""
        _row_slot_check(self.trace, self.coeff, self.sidecar, 19, 0.0005)
    def test_b05_sidecar_row(self):
        """Sidecar row 25 band slots match replay within class E."""
        _row_slot_check(self.trace, self.coeff, self.sidecar, 25, 0.0005)
    def test_b06_sidecar_row(self):
        """Sidecar row 31 band slots match replay within class E."""
        _row_slot_check(self.trace, self.coeff, self.sidecar, 31, 0.0005)
    def test_b07_sidecar_row(self):
        """Sidecar row 37 band slots match replay within class E."""
        _row_slot_check(self.trace, self.coeff, self.sidecar, 37, 0.0005)
    def test_b08_sidecar_row(self):
        """Sidecar row 43 band slots match replay within class E."""
        _row_slot_check(self.trace, self.coeff, self.sidecar, 43, 0.0005)
    def test_b09_sidecar_row(self):
        """Sidecar row 49 band slots match replay within class E."""
        _row_slot_check(self.trace, self.coeff, self.sidecar, 49, 0.0005)
    def test_b10_sidecar_row(self):
        """Sidecar row 55 band slots match replay within class E."""
        _row_slot_check(self.trace, self.coeff, self.sidecar, 55, 0.0005)
    def test_b11_sidecar_row(self):
        """Sidecar row 61 band slots match replay within class E."""
        _row_slot_check(self.trace, self.coeff, self.sidecar, 61, 0.0005)
    def test_b12_sidecar_row(self):
        """Sidecar row 66 band slots match replay within class E."""
        _row_slot_check(self.trace, self.coeff, self.sidecar, 66, 0.0005)
