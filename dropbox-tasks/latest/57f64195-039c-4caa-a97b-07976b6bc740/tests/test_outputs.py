"""Independent black-box verifier for the TOF-MS axis reconciler."""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

APP = Path("/app")
BIN = APP / "bin" / "tofmass-bin"
WRAP = APP / "bin" / "tofmass"
SCHEMA = APP / "docs" / "report.schema.json"
MATCH_WINDOW = 0.015
K_SIGMA = 2.5
LOCK_RATIO = 0.4
MONO_EPS = 1e-9
GLS_THRESH = 11.344866730144373
D2_TIE = 1e-12


def _near(a: float, b: float, atol: float = 1e-9, rtol: float = 1e-9) -> bool:
    return abs(a - b) <= max(atol, rtol * max(abs(a), abs(b)))


def _cov_near(A: list[list[float]], B: list[list[float]]) -> bool:
    for i in range(3):
        for j in range(3):
            if not _near(A[i][j], B[i][j], atol=1e-18, rtol=1e-9):
                return False
    return True


def mat_det(C: list[list[float]]) -> float:
    m = C
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )


def mat_inv(C: list[list[float]]) -> list[list[float]]:
    det = mat_det(C)
    if abs(det) < 1e-300:
        raise ValueError("singular")
    m = C
    return [
        [
            (m[1][1] * m[2][2] - m[1][2] * m[2][1]) / det,
            (m[0][2] * m[2][1] - m[0][1] * m[2][2]) / det,
            (m[0][1] * m[1][2] - m[0][2] * m[1][1]) / det,
        ],
        [
            (m[1][2] * m[2][0] - m[1][0] * m[2][2]) / det,
            (m[0][0] * m[2][2] - m[0][2] * m[2][0]) / det,
            (m[0][2] * m[1][0] - m[0][0] * m[1][2]) / det,
        ],
        [
            (m[1][0] * m[2][1] - m[1][1] * m[2][0]) / det,
            (m[0][1] * m[2][0] - m[0][0] * m[2][1]) / det,
            (m[0][0] * m[1][1] - m[0][1] * m[1][0]) / det,
        ],
    ]


def mat_add(A: list[list[float]], B: list[list[float]]) -> list[list[float]]:
    return [[A[i][j] + B[i][j] for j in range(3)] for i in range(3)]


def mat_vec(A: list[list[float]], v: list[float]) -> list[float]:
    return [sum(A[i][j] * v[j] for j in range(3)) for i in range(3)]


def quad(x: list[float], A: list[list[float]]) -> float:
    Ax = mat_vec(A, x)
    return sum(x[i] * Ax[i] for i in range(3))


def is_spd(C: list[list[float]]) -> bool:
    # Cholesky
    L = [[0.0] * 3 for _ in range(3)]
    for i in range(3):
        for j in range(i + 1):
            s = C[i][j] - sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                if s <= 0 or not math.isfinite(s):
                    return False
                L[i][j] = math.sqrt(s)
            else:
                if abs(L[j][j]) < 1e-300:
                    return False
                L[i][j] = s / L[j][j]
    return True


def gscale(C: list[list[float]]) -> float:
    return mat_det(C) ** (1.0 / 6.0)


def cov_from(sig: list[float], rho: list[float]) -> list[list[float]]:
    sk, st, sq = sig
    rkt0, rkq, rt0q = rho
    return [
        [sk * sk, rkt0 * sk * st, rkq * sk * sq],
        [rkt0 * sk * st, st * st, rt0q * st * sq],
        [rkq * sk * sq, rt0q * st * sq, sq * sq],
    ]


def scale_units(theta: list[float], C: list[list[float]], S: list[float]):
    th = [theta[i] * S[i] for i in range(3)]
    Cout = [[0.0] * 3 for _ in range(3)]
    for i in range(3):
        for j in range(3):
            Cout[i][j] = S[i] * C[i][j] * S[j]
    return th, Cout


def unit_scale(kind: str, units: str) -> float:
    u = units.lower()
    if kind == "k":
        if u in ("da_per_us2", "da/us^2"):
            return 1.0
        if u in ("mda_per_us2", "mda/us^2"):
            return 0.001
    if kind == "t0":
        if u == "us":
            return 1.0
        if u == "ns":
            return 0.001
    if kind == "q":
        if u in ("da_per_us3", "da/us^3"):
            return 1.0
    raise ValueError(units)


def canonicalize_candidate(raw: dict[str, Any]) -> tuple[list[float], list[list[float]]]:
    theta = [float(raw["k"]), float(raw["t0"]), float(raw["q"])]
    sig = [float(raw["sigma_k"]), float(raw["sigma_t0"]), float(raw["sigma_q"])]
    rho = [float(raw["rho_k_t0"]), float(raw["rho_k_q"]), float(raw["rho_t0_q"])]
    if any(s <= 0 for s in sig) or any(abs(r) > 1 for r in rho):
        raise ValueError("invalid")
    C = cov_from(sig, rho)
    S = [
        unit_scale("k", raw["k_units"]),
        unit_scale("t0", raw["t0_units"]),
        unit_scale("q", raw["q_units"]),
    ]
    th, Cc = scale_units(theta, C, S)
    if not is_spd(Cc):
        raise ValueError("not spd")
    return th, Cc


def is_monotonic(theta: list[float], lo: float, hi: float) -> bool:
    k, t0, q = theta
    pts = [lo, hi]
    if abs(q) > 0:
        dt = -k / (3 * q)
        t = t0 + dt
        if lo <= t <= hi:
            pts.append(t)
    mps = []
    for tof in pts:
        dt = tof - t0
        mps.append(2 * k * dt + 3 * q * dt * dt)
    return min(mps) > MONO_EPS


def gls(thetas: list[list[float]], Cs: list[list[list[float]]]):
    P = [[0.0] * 3 for _ in range(3)]
    for C in Cs:
        inv = mat_inv(C)
        P = mat_add(P, inv)
    Chat = mat_inv(P)
    acc = [0.0, 0.0, 0.0]
    for th, C in zip(thetas, Cs):
        inv = mat_inv(C)
        w = mat_vec(inv, th)
        acc = [acc[i] + w[i] for i in range(3)]
    return mat_vec(Chat, acc), Chat


def mass(theta, tof):
    k, t0, q = theta
    dt = tof - t0
    return k * dt * dt + q * dt * dt * dt


def sigma_corr(theta, C, tof, sigma_tof_us):
    k, t0, q = theta
    dt = tof - t0
    J = [dt * dt, -2 * k * dt - 3 * q * dt * dt, dt * dt * dt]
    dm = 2 * k * dt + 3 * q * dt * dt
    return math.sqrt(quad(J, C) + (dm * sigma_tof_us) ** 2)


def global_assign(peaks, ions):
    # peaks: list of dict with corrected, sigma, peak_id
    # ions: list of dict ion_id, mz, sigma
    n_p, n_i = len(peaks), len(ions)
    edges = {}
    for pi, p in enumerate(peaks):
        for ji, ion in enumerate(ions):
            res = p["corrected"] - ion["mz"]
            if abs(res) <= MATCH_WINDOW:
                denom = p["sigma"] ** 2 + ion["sigma"] ** 2
                edges[(pi, ji)] = (res * res) / denom

    # bitmask DP
    nmasks = 1 << n_i
    # state after processing peak p: mask -> (matched, cost, prev, ion)
    INF = 1e300
    best_m = [[-1] * nmasks for _ in range(n_p + 1)]
    best_c = [[INF] * nmasks for _ in range(n_p + 1)]
    prev = [[-1] * nmasks for _ in range(n_p + 1)]
    ch = [[-1] * nmasks for _ in range(n_p + 1)]
    best_m[0][0] = 0
    best_c[0][0] = 0.0
    for p in range(n_p):
        for mask in range(nmasks):
            if best_m[p][mask] < 0:
                continue
            bm, bc = best_m[p][mask], best_c[p][mask]
            # skip
            if bm > best_m[p + 1][mask] or (
                bm == best_m[p + 1][mask] and bc < best_c[p + 1][mask]
            ):
                best_m[p + 1][mask] = bm
                best_c[p + 1][mask] = bc
                prev[p + 1][mask] = mask
                ch[p + 1][mask] = -1
            for j in range(n_i):
                if mask & (1 << j):
                    continue
                if (p, j) not in edges:
                    continue
                nmask = mask | (1 << j)
                nm, nc = bm + 1, bc + edges[(p, j)]
                if nm > best_m[p + 1][nmask] or (
                    nm == best_m[p + 1][nmask] and nc < best_c[p + 1][nmask]
                ):
                    best_m[p + 1][nmask] = nm
                    best_c[p + 1][nmask] = nc
                    prev[p + 1][nmask] = mask
                    ch[p + 1][nmask] = j

    best_tuple = None
    best_map = None
    for mask in range(nmasks):
        if best_m[n_p][mask] < 0:
            continue
        mapping = [-1] * n_p
        m = mask
        for p in range(n_p, 0, -1):
            mapping[p - 1] = ch[p][m]
            m = prev[p][m]
        pairs = []
        for pi, ji in enumerate(mapping):
            if ji >= 0:
                pairs.append(f"{peaks[pi]['peak_id']}={ions[ji]['ion_id']}")
        pairs.sort()
        sig = ";".join(pairs)
        tup = (best_m[n_p][mask], -best_c[n_p][mask], sig)
        if best_tuple is None or tup > best_tuple:
            best_tuple = tup
            best_map = mapping
    return best_map or [-1] * n_p


def ledger_digest(schema_digest: str, axis: dict, used: list[str], rejected: list[dict], peaks: list[dict]) -> str:
    lines = [
        f"schema|version=2|sha256={schema_digest}",
        (
            f"axis|k={axis['k']:.12e}|t0={axis['t0']:.12e}|q={axis['q']:.12e}|"
            f"c00={axis['covariance'][0][0]:.12e}|c01={axis['covariance'][0][1]:.12e}|"
            f"c02={axis['covariance'][0][2]:.12e}|c11={axis['covariance'][1][1]:.12e}|"
            f"c12={axis['covariance'][1][2]:.12e}|c22={axis['covariance'][2][2]:.12e}|"
            f"source={axis['source']}"
        ),
    ]
    for k in sorted(used):
        lines.append(f"used|{k}")
    for r in sorted(rejected, key=lambda x: (x["candidate_key"], x["reason"])):
        lines.append(f"rejected|{r['candidate_key']}|{r['reason']}")
    for p in sorted(peaks, key=lambda x: x["peak_id"]):
        if p.get("catalog_id") is None:
            lines.append(
                f"peak|{p['peak_id']}|tof={p['tof_us']:.10f}|sigma_tof={p['tof_sigma_us']:.12e}|"
                f"mass={p['corrected_da']:.10f}|sigma={p['sigma_corr_da']:.12e}|"
                f"catalog=-|residual=null|z=null|accepted=0|reason={p['reject_reason']}"
            )
        else:
            reason = "-" if p["accepted"] else p["reject_reason"]
            lines.append(
                f"peak|{p['peak_id']}|tof={p['tof_us']:.10f}|sigma_tof={p['tof_sigma_us']:.12e}|"
                f"mass={p['corrected_da']:.10f}|sigma={p['sigma_corr_da']:.12e}|"
                f"catalog={p['catalog_id']}|residual={p['residual_da']:.10f}|z={p['z_score']:.10f}|"
                f"accepted={1 if p['accepted'] else 0}|reason={reason}"
            )
    blob = "\n".join(lines).encode()
    return hashlib.sha256(blob).hexdigest()



def reconcile_reference(
    run_id: str,
    calibration: dict,
    peaks_doc: dict,
    catalog: dict,
    lab_candidates: list[dict],
    schema_digest: str,
    extra_rejected: list[dict] | None = None,
) -> dict:
    if calibration["run_id"] != run_id or peaks_doc["run_id"] != run_id:
        raise ValueError("run mismatch")
    active = calibration["active"]
    api_th, api_C = canonicalize_candidate(active)
    api_key = f"instrument::{active['candidate_id']}"

    tofs = [float(p["tof_us"]) for p in peaks_doc["peaks"]]
    lo, hi = min(tofs), max(tofs)
    if not is_monotonic(api_th, lo, hi):
        raise ValueError("api non-monotonic")

    rejected: list[dict] = list(extra_rejected or [])
    admissible = []
    for lab in lab_candidates:
        key = lab["key"]
        try:
            th, C = canonicalize_candidate(lab)
        except ValueError:
            rejected.append({"candidate_key": key, "reason": "invalid_covariance"})
            continue
        if not is_monotonic(th, lo, hi):
            rejected.append({"candidate_key": key, "reason": "non_monotonic"})
            continue
        admissible.append((key, th, C))

    if not admissible:
        theta, C, source = api_th, api_C, "api_only"
        used = [api_key]
    else:
        gmin = min(gscale(c) for _, _, c in admissible)
        if gscale(api_C) <= LOCK_RATIO * gmin:
            theta, C, source = api_th, api_C, "api_lock"
            used = [api_key]
        else:
            alive = list(admissible)
            gls_rej = []
            source = None
            while True:
                if not alive:
                    theta, C = api_th, api_C
                    source = "api_only_after_rejection"
                    used = [api_key]
                    break
                thetas = [api_th] + [t for _, t, _ in alive]
                Cs = [api_C] + [c for _, _, c in alive]
                th, Chat = gls(thetas, Cs)
                worst_key = None
                worst_d2 = -1.0
                for key, ti, Ci in alive:
                    d = [ti[i] - th[i] for i in range(3)]
                    d2 = quad(d, mat_inv(mat_add(Ci, Chat)))
                    if (
                        worst_key is None
                        or d2 > worst_d2 + D2_TIE
                        or (abs(d2 - worst_d2) <= D2_TIE and key > worst_key)
                    ):
                        worst_d2, worst_key = d2, key
                if worst_d2 <= GLS_THRESH:
                    theta, C = th, Chat
                    source = "robust_gls"
                    used = [api_key] + [k for k, _, _ in alive]
                    break
                gls_rej.append({"candidate_key": worst_key, "reason": "gls_outlier"})
                alive = [x for x in alive if x[0] != worst_key]
            rejected.extend(gls_rej)

    used = sorted(set(used))
    work_peaks = []
    for p in peaks_doc["peaks"]:
        tof = float(p["tof_us"])
        sig_us = float(p["tof_sigma_ns"]) / 1000.0
        corr = mass(theta, tof)
        sc = sigma_corr(theta, C, tof, sig_us)
        work_peaks.append(
            {
                "peak_id": p["peak_id"],
                "tof_us": tof,
                "tof_sigma_us": sig_us,
                "corrected": corr,
                "sigma": sc,
            }
        )

    ions = []
    seen = set()
    for ion in catalog["ions"]:
        iid = ion["ion_id"]
        if iid in seen:
            raise ValueError("dup ion")
        seen.add(iid)
        if "sigma_da" not in ion or float(ion["sigma_da"]) <= 0:
            raise ValueError("bad ion")
        ions.append(
            {"ion_id": iid, "mz": float(ion["mz_da"]), "sigma": float(ion["sigma_da"])}
        )

    mapping = global_assign(work_peaks, ions)
    matched = accepted = rejected_n = no_match = outlier = 0
    zs = []
    peak_rows = []
    for i, wp in enumerate(work_peaks):
        j = mapping[i]
        row = {
            "peak_id": wp["peak_id"],
            "tof_us": wp["tof_us"],
            "tof_sigma_us": wp["tof_sigma_us"],
            "corrected_da": wp["corrected"],
            "sigma_corr_da": wp["sigma"],
        }
        if j < 0:
            row.update(
                {
                    "catalog_id": None,
                    "catalog_da": None,
                    "residual_da": None,
                    "z_score": None,
                    "accepted": False,
                    "reject_reason": "no_match",
                }
            )
            no_match += 1
            rejected_n += 1
        else:
            res = wp["corrected"] - ions[j]["mz"]
            z = res / math.sqrt(wp["sigma"] ** 2 + ions[j]["sigma"] ** 2)
            zs.append(z)
            matched += 1
            if abs(z) > K_SIGMA:
                row.update(
                    {
                        "catalog_id": ions[j]["ion_id"],
                        "catalog_da": ions[j]["mz"],
                        "residual_da": res,
                        "z_score": z,
                        "accepted": False,
                        "reject_reason": "outlier",
                    }
                )
                outlier += 1
                rejected_n += 1
            else:
                row.update(
                    {
                        "catalog_id": ions[j]["ion_id"],
                        "catalog_da": ions[j]["mz"],
                        "residual_da": res,
                        "z_score": z,
                        "accepted": True,
                        "reject_reason": None,
                    }
                )
                accepted += 1
        peak_rows.append(row)

    peak_rows.sort(key=lambda x: x["peak_id"])
    rejected.sort(key=lambda x: (x["candidate_key"], x["reason"]))
    axis = {
        "k": theta[0],
        "t0": theta[1],
        "q": theta[2],
        "covariance_order": ["k", "t0", "q"],
        "covariance": C,
        "source": source,
        "monotonic_interval_us": [lo, hi],
    }
    summary = {
        "matched": matched,
        "accepted": accepted,
        "rejected": rejected_n,
        "no_match": no_match,
        "outlier": outlier,
        "weighted_rms_z": math.sqrt(sum(z * z for z in zs) / matched) if matched else None,
        "max_abs_z": max(abs(z) for z in zs) if matched else None,
    }
    digest = ledger_digest(schema_digest, axis, used, rejected, peak_rows)
    return {
        "schema_version": 2,
        "producer": "tofmass",
        "run_id": run_id,
        "schema_digest": schema_digest,
        "axis": axis,
        "provenance": {"used_candidate_keys": used, "rejected_candidates": rejected},
        "peaks": peak_rows,
        "summary": summary,
        "ledger_digest": digest,
    }


class FixtureServer:
    def __init__(self, calibration, peaks, catalog, runs=None):
        self.calibration = calibration
        self.peaks = peaks
        self.catalog = catalog
        self.runs = runs or {"runs": [{"run_id": calibration["run_id"]}]}
        self._httpd = None
        self.port = None

    def start(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                return

            def _send(self, code, obj):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path == "/health":
                    self._send(200, {"ok": True})
                elif self.path == "/v1/runs":
                    self._send(200, outer.runs)
                elif self.path.startswith("/v1/runs/") and self.path.endswith("/calibration"):
                    self._send(200, outer.calibration)
                elif self.path.startswith("/v1/runs/") and self.path.endswith("/peaks"):
                    self._send(200, outer.peaks)
                elif self.path == "/v1/catalog/ions":
                    self._send(200, outer.catalog)
                else:
                    self._send(404, {"error": "missing"})

        self._httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._httpd.server_address[1]
        t = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        t.start()
        return f"http://127.0.0.1:{self.port}"

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()


def write_notes(root: Path, files: dict[str, str]):
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def note_table(heading: str, rows: list[dict], decoy: bool = False) -> str:
    cols = [
        "candidate_id",
        "rev",
        "status",
        "k",
        "t0",
        "q",
        "sigma_k",
        "sigma_t0",
        "sigma_q",
        "rho_k_t0",
        "rho_k_q",
        "rho_t0_q",
        "k_units",
        "t0_units",
        "q_units",
    ]
    token = "fragment_survey" if decoy else "axis_candidate"
    lines = [f"## {heading} {token}", "", "| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def run_bin(api: str, run_id: str, notes: Path, schema: Path, out: Path, use_wrapper=False):
    exe = str(WRAP if use_wrapper else BIN)
    cmd = [
        exe,
        "--api",
        api,
        "--run-id",
        run_id,
        "--notes",
        str(notes),
        "--schema",
        str(schema),
        "--out",
        str(out),
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


@pytest.fixture(scope="session", autouse=True)
def build_evaluator():
    r = subprocess.run(["make", "-C", "/app", "clean", "all"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr + r.stdout
    assert BIN.is_file()
    data = BIN.read_bytes()
    assert data[:4] == b"\x7fELF"
    assert os.access(BIN, os.X_OK)


def cand(**kwargs):
    base = {
        "rho_k_t0": 0.0,
        "rho_k_q": 0.0,
        "rho_t0_q": 0.0,
        "k_units": "Da_per_us2",
        "t0_units": "us",
        "q_units": "Da_per_us3",
        "status": "active",
        "rev": 1,
    }
    base.update(kwargs)
    return base


def assert_report_matches(got: dict, exp: dict):
    assert got["schema_version"] == 2
    assert got["axis"]["source"] == exp["axis"]["source"]
    assert _near(got["axis"]["k"], exp["axis"]["k"])
    assert _near(got["axis"]["t0"], exp["axis"]["t0"])
    assert _near(got["axis"]["q"], exp["axis"]["q"], atol=1e-14)
    assert _cov_near(got["axis"]["covariance"], exp["axis"]["covariance"])
    assert got["provenance"]["used_candidate_keys"] == exp["provenance"]["used_candidate_keys"]
    grej = sorted(
        got["provenance"]["rejected_candidates"],
        key=lambda x: (x["candidate_key"], x["reason"]),
    )
    erej = sorted(
        exp["provenance"]["rejected_candidates"],
        key=lambda x: (x["candidate_key"], x["reason"]),
    )
    assert grej == erej
    assert got["summary"]["matched"] == exp["summary"]["matched"]
    assert got["summary"]["accepted"] == exp["summary"]["accepted"]
    assert got["summary"]["outlier"] == exp["summary"]["outlier"]
    assert got["summary"]["no_match"] == exp["summary"]["no_match"]
    gpeaks = {p["peak_id"]: p for p in got["peaks"]}
    for ep in exp["peaks"]:
        gp = gpeaks[ep["peak_id"]]
        assert gp["accepted"] == ep["accepted"]
        assert gp["reject_reason"] == ep["reject_reason"]
        assert gp.get("catalog_id") == ep.get("catalog_id")
        if ep.get("z_score") is not None:
            assert _near(gp["z_score"], ep["z_score"])
            assert _near(gp["sigma_corr_da"], ep["sigma_corr_da"], atol=1e-18, rtol=1e-9)
    # Digest must be a faithful hash of the emitted report fields (exact ledger grammar).
    rebuilt = ledger_digest(
        got["schema_digest"],
        got["axis"],
        got["provenance"]["used_candidate_keys"],
        got["provenance"]["rejected_candidates"],
        got["peaks"],
    )
    assert got["ledger_digest"] == rebuilt


def test_production_incident_version2_report():
    """Production shot report must match an independent robust-GLS reference."""
    # Use live instrument + notes; compare against reference built from the same
    # immutable scenario dictionaries mirrored from the production fixtures, not
    # by reading mutable /app fixtures as oracle truth after agent edits.
    cal = {
        "run_id": "shot-2025-0314",
        "active": cand(
            candidate_id="api-active",
            k=0.5082,
            t0=4.85,
            q=-1.85e-5,
            sigma_k=6e-6,
            sigma_t0=2e-5,
            sigma_q=4e-8,
            rho_k_t0=0.3,
            rho_k_q=-0.2,
            rho_t0_q=0.15,
        ),
    }
    peaks = {
        "run_id": "shot-2025-0314",
        "peaks": [
            {"peak_id": "ion-922", "tof_us": 47.4773175922, "tof_sigma_ns": 0.12},
            {"peak_id": "ion-noise", "tof_us": 8.25, "tof_sigma_ns": 1.5},
            {"peak_id": "ion-118", "tof_us": 20.0977111726, "tof_sigma_ns": 0.08},
            {"peak_id": "ion-shift", "tof_us": 20.0980294767, "tof_sigma_ns": 0.08},
            {"peak_id": "ion-322", "tof_us": 30.0350725928, "tof_sigma_ns": 0.08},
            {"peak_id": "ion-622", "tof_us": 39.8578509303, "tof_sigma_ns": 0.1},
        ],
    }
    catalog = {
        "ions": [
            {"ion_id": "ESI-L-922", "mz_da": 922.009798, "sigma_da": 0.0003},
            {"ion_id": "ESI-L-118", "mz_da": 118.086255, "sigma_da": 0.00015},
            {"ion_id": "CONTAM-118", "mz_da": 118.1, "sigma_da": 0.0001},
            {"ion_id": "PEG-Na-525", "mz_da": 525.2975, "sigma_da": 0.0005},
            {"ion_id": "ESI-L-622", "mz_da": 622.02896, "sigma_da": 0.00025},
            {"ion_id": "ESI-L-322", "mz_da": 322.048121, "sigma_da": 0.0002},
        ]
    }
    labs = [
        {
            **cand(
                candidate_id="lab-a",
                rev=2,
                k=0.508190,
                t0=4.850150,
                q=-1.848e-5,
                sigma_k=1e-5,
                sigma_t0=3.5e-5,
                sigma_q=7e-8,
                rho_k_t0=0.10,
                rho_k_q=0.05,
                rho_t0_q=-0.08,
            ),
            "key": "bench-a.md::lab-a@2",
        },
        {
            **cand(
                candidate_id="lab-b",
                rev=4,
                k=508.210,
                t0=4850.20,
                q=-1.842e-5,
                sigma_k=0.012,
                sigma_t0=0.045,
                sigma_q=6.5e-8,
                rho_k_t0=0.45,
                rho_k_q=-0.12,
                rho_t0_q=0.18,
                k_units="mDa_per_us2",
                t0_units="ns",
                q_units="Da/us^3",
            ),
            "key": "bench-b.md::lab-b@4",
        },
        {
            **cand(
                candidate_id="lab-out",
                k=0.511,
                t0=4.865,
                q=-1.4e-5,
                sigma_k=9e-6,
                sigma_t0=3e-5,
                sigma_q=5.5e-8,
            ),
            "key": "runbook.md::lab-out@1",
        },
        {
            **cand(
                candidate_id="lab-nm",
                k=0.508,
                t0=4.85,
                q=-0.010,
                sigma_k=1e-5,
                sigma_t0=3e-5,
                sigma_q=1e-7,
            ),
            "key": "runbook.md::lab-nm@1",
        },
    ]
    schema_digest = hashlib.sha256(SCHEMA.read_bytes()).hexdigest()
    # Reference includes non_monotonic rejection for lab-nm and gls_outlier for lab-out
    exp = reconcile_reference("shot-2025-0314", cal, peaks, catalog, labs, schema_digest)

    srv = FixtureServer(cal, peaks, catalog)
    api = srv.start()
    try:
        with tempfile.TemporaryDirectory() as td:
            notes = Path(td)
            write_notes(
                notes,
                {
                    "bench-a.md": note_table(
                        "Bench A",
                        [
                            cand(
                                candidate_id="lab-a",
                                rev=2,
                                k=0.508190,
                                t0=4.850150,
                                q=-1.848e-5,
                                sigma_k=1e-5,
                                sigma_t0=3.5e-5,
                                sigma_q=7e-8,
                                rho_k_t0=0.10,
                                rho_k_q=0.05,
                                rho_t0_q=-0.08,
                            )
                        ],
                    ),
                    "bench-b.md": note_table(
                        "Bench B",
                        [
                            cand(
                                candidate_id="lab-b",
                                rev=4,
                                k=508.210,
                                t0=4850.20,
                                q=-1.842e-5,
                                sigma_k=0.012,
                                sigma_t0=0.045,
                                sigma_q=6.5e-8,
                                rho_k_t0=0.45,
                                rho_k_q=-0.12,
                                rho_t0_q=0.18,
                                k_units="mDa_per_us2",
                                t0_units="ns",
                                q_units="Da/us^3",
                            )
                        ],
                    ),
                    "runbook.md": note_table(
                        "Contaminant",
                        [
                            cand(
                                candidate_id="lab-out",
                                k=0.511,
                                t0=4.865,
                                q=-1.4e-5,
                                sigma_k=9e-6,
                                sigma_t0=3e-5,
                                sigma_q=5.5e-8,
                            )
                        ],
                    )
                    + note_table(
                        "Non-monotonic",
                        [
                            cand(
                                candidate_id="lab-nm",
                                k=0.508,
                                t0=4.85,
                                q=-0.010,
                                sigma_k=1e-5,
                                sigma_t0=3e-5,
                                sigma_q=1e-7,
                            )
                        ],
                    ),
                },
            )
            out = Path(td) / "report.json"
            r = run_bin(api, "shot-2025-0314", notes, SCHEMA, out)
            assert r.returncode == 0, r.stderr
            got = json.loads(out.read_text())
            assert_report_matches(got, exp)
    finally:
        srv.stop()

    # Wrapper path for production workflow
    subprocess.run(["/app/scripts/start-instrument.sh"], check=True)
    outp = APP / "reports" / "mz-axis-reconcile.json"
    outp.parent.mkdir(parents=True, exist_ok=True)
    r = run_bin(
        "http://127.0.0.1:8791",
        "shot-2025-0314",
        APP / "docs" / "lab-notes",
        SCHEMA,
        outp,
        use_wrapper=True,
    )
    assert r.returncode == 0, r.stderr
    got = json.loads(outp.read_text())
    assert got["axis"]["source"] == "robust_gls"
    assert got["summary"]["accepted"] == 4
    assert got["summary"]["outlier"] == 1
    assert got["summary"]["no_match"] == 1


def _base_api(**overrides):
    c = cand(
        candidate_id="api-active",
        k=0.5082,
        t0=4.85,
        q=-1.85e-5,
        sigma_k=2.0e-5,
        sigma_t0=6.0e-5,
        sigma_q=1.0e-7,
        rho_k_t0=0.4,
        rho_k_q=-0.3,
        rho_t0_q=0.25,
    )
    c.update(overrides)
    return c


def _mini_peaks(run_id="shot-x"):
    return {
        "run_id": run_id,
        "peaks": [
            {"peak_id": "p1", "tof_us": 20.1, "tof_sigma_ns": 0.05},
            {"peak_id": "p2", "tof_us": 30.0, "tof_sigma_ns": 0.05},
        ],
    }


def _mini_catalog():
    return {
        "ions": [
            {"ion_id": "A", "mz_da": 118.09, "sigma_da": 0.001},
            {"ion_id": "B", "mz_da": 322.05, "sigma_da": 0.001},
        ]
    }


def test_correlated_gls_differs_from_diagonal_ivw():
    """Off-diagonal covariance must change the reconciled vector versus scalar IVW."""
    run_id = "corr-gls"
    api = _base_api(sigma_k=3e-5, sigma_t0=8e-5, sigma_q=1.2e-7)
    lab = cand(
        candidate_id="lab1",
        k=0.50835,
        t0=4.851,
        q=-1.80e-5,
        sigma_k=3.5e-5,
        sigma_t0=9e-5,
        sigma_q=1.3e-7,
        rho_k_t0=0.55,
        rho_k_q=-0.4,
        rho_t0_q=0.35,
    )
    cal = {"run_id": run_id, "active": api}
    peaks = _mini_peaks(run_id)
    # Place peaks near masses for this axis roughly
    catalog = _mini_catalog()
    schema_digest = hashlib.sha256(SCHEMA.read_bytes()).hexdigest()
    labs = [{**lab, "key": "n.md::lab1@1"}]
    exp = reconcile_reference(run_id, cal, peaks, catalog, labs, schema_digest)

    # Diagonal-only IVW prediction
    th_api, C_api = canonicalize_candidate(api)
    th_lab, C_lab = canonicalize_candidate(lab)
    ivw = []
    for d in range(3):
        w1 = 1.0 / C_api[d][d]
        w2 = 1.0 / C_lab[d][d]
        ivw.append((w1 * th_api[d] + w2 * th_lab[d]) / (w1 + w2))
    assert not all(_near(exp["axis"][c], ivw[i], atol=1e-12) for i, c in enumerate(["k", "t0", "q"]))

    srv = FixtureServer(cal, peaks, catalog)
    api_url = srv.start()
    try:
        with tempfile.TemporaryDirectory() as td:
            notes = Path(td)
            write_notes(notes, {"n.md": note_table("N", [lab])})
            out = Path(td) / "o.json"
            r = run_bin(api_url, run_id, notes, SCHEMA, out)
            assert r.returncode == 0, r.stderr
            got = json.loads(out.read_text())
            assert_report_matches(got, exp)
    finally:
        srv.stop()


def test_spd_validation_rejects_indefinite_covariance():
    """A covariance with positive diagonals but a negative eigenvalue is rejected."""
    run_id = "spd"
    api = _base_api()
    bad = cand(
        candidate_id="bad",
        k=0.5082,
        t0=4.85,
        q=-1.85e-5,
        sigma_k=2e-5,
        sigma_t0=5e-5,
        sigma_q=1e-7,
        rho_k_t0=0.99,
        rho_k_q=0.99,
        rho_t0_q=-0.99,
    )
    C = cov_from(
        [bad["sigma_k"], bad["sigma_t0"], bad["sigma_q"]],
        [bad["rho_k_t0"], bad["rho_k_q"], bad["rho_t0_q"]],
    )
    assert C[0][0] > 0 and C[1][1] > 0 and C[2][2] > 0
    assert not is_spd(C)

    cal = {"run_id": run_id, "active": api}
    peaks = _mini_peaks(run_id)
    catalog = _mini_catalog()
    schema_digest = hashlib.sha256(SCHEMA.read_bytes()).hexdigest()
    labs = [{**bad, "key": "n.md::bad@1"}]
    exp = reconcile_reference(run_id, cal, peaks, catalog, labs, schema_digest)
    assert any(r["reason"] == "invalid_covariance" for r in exp["provenance"]["rejected_candidates"])

    srv = FixtureServer(cal, peaks, catalog)
    api_url = srv.start()
    try:
        with tempfile.TemporaryDirectory() as td:
            notes = Path(td)
            write_notes(notes, {"n.md": note_table("N", [bad])})
            out = Path(td) / "o.json"
            r = run_bin(api_url, run_id, notes, SCHEMA, out)
            assert r.returncode == 0, r.stderr
            got = json.loads(out.read_text())
            assert any(
                r["reason"] == "invalid_covariance" for r in got["provenance"]["rejected_candidates"]
            )
            assert "n.md::bad@1" not in got["provenance"]["used_candidate_keys"]
    finally:
        srv.stop()


def test_robust_source_rejects_mahalanobis_outlier():
    """One lab vector above the Mahalanobis threshold is removed and GLS recomputed."""
    run_id = "robust"
    api = _base_api(sigma_k=1.5e-5, sigma_t0=4e-5, sigma_q=8e-8)
    good = cand(
        candidate_id="good",
        k=0.50825,
        t0=4.8502,
        q=-1.84e-5,
        sigma_k=2e-5,
        sigma_t0=5e-5,
        sigma_q=1e-7,
        rho_k_t0=0.2,
        rho_k_q=-0.1,
        rho_t0_q=0.1,
    )
    bad = cand(
        candidate_id="far",
        k=0.520,
        t0=4.90,
        q=-1.0e-5,
        sigma_k=1.8e-5,
        sigma_t0=4.5e-5,
        sigma_q=9e-8,
    )
    cal = {"run_id": run_id, "active": api}
    peaks = _mini_peaks(run_id)
    catalog = _mini_catalog()
    schema_digest = hashlib.sha256(SCHEMA.read_bytes()).hexdigest()
    labs = [
        {**good, "key": "g.md::good@1"},
        {**bad, "key": "b.md::far@1"},
    ]
    exp = reconcile_reference(run_id, cal, peaks, catalog, labs, schema_digest)
    assert any(
        r["candidate_key"] == "b.md::far@1" and r["reason"] == "gls_outlier"
        for r in exp["provenance"]["rejected_candidates"]
    )
    assert "b.md::far@1" not in exp["provenance"]["used_candidate_keys"]

    srv = FixtureServer(cal, peaks, catalog)
    api_url = srv.start()
    try:
        with tempfile.TemporaryDirectory() as td:
            notes = Path(td)
            write_notes(
                notes,
                {"g.md": note_table("G", [good]), "b.md": note_table("B", [bad])},
            )
            out = Path(td) / "o.json"
            r = run_bin(api_url, run_id, notes, SCHEMA, out)
            assert r.returncode == 0, r.stderr
            got = json.loads(out.read_text())
            assert_report_matches(got, exp)
    finally:
        srv.stop()


def test_physical_monotonicity_excludes_lab_candidate():
    """A tight but non-monotonic cubic candidate is excluded with non_monotonic."""
    run_id = "mono"
    api = _base_api()
    nm = cand(
        candidate_id="nm",
        k=0.508,
        t0=4.85,
        q=-0.01,
        sigma_k=1e-5,
        sigma_t0=3e-5,
        sigma_q=1e-7,
    )
    cal = {"run_id": run_id, "active": api}
    peaks = {
        "run_id": run_id,
        "peaks": [
            {"peak_id": "lo", "tof_us": 19.5, "tof_sigma_ns": 0.05},
            {"peak_id": "hi", "tof_us": 48.0, "tof_sigma_ns": 0.05},
        ],
    }
    catalog = _mini_catalog()
    schema_digest = hashlib.sha256(SCHEMA.read_bytes()).hexdigest()
    labs = [{**nm, "key": "n.md::nm@1"}]
    exp = reconcile_reference(run_id, cal, peaks, catalog, labs, schema_digest)
    assert any(r["reason"] == "non_monotonic" for r in exp["provenance"]["rejected_candidates"])

    srv = FixtureServer(cal, peaks, catalog)
    api_url = srv.start()
    try:
        with tempfile.TemporaryDirectory() as td:
            notes = Path(td)
            write_notes(notes, {"n.md": note_table("N", [nm])})
            out = Path(td) / "o.json"
            r = run_bin(api_url, run_id, notes, SCHEMA, out)
            assert r.returncode == 0, r.stderr
            got = json.loads(out.read_text())
            assert any(
                r["reason"] == "non_monotonic" for r in got["provenance"]["rejected_candidates"]
            )
    finally:
        srv.stop()


def test_unit_covariance_transform_affects_cross_terms():
    """mDa/ns conversion must scale cross-covariance, not only marginals."""
    run_id = "units"
    api = _base_api(sigma_k=2.5e-5, sigma_t0=7e-5, sigma_q=1.1e-7)
    lab = cand(
        candidate_id="u",
        k=508.30,
        t0=4851.0,
        q=-1.83e-5,
        sigma_k=0.03,
        sigma_t0=0.09,
        sigma_q=1.2e-7,
        rho_k_t0=0.5,
        rho_k_q=-0.25,
        rho_t0_q=0.2,
        k_units="mDa_per_us2",
        t0_units="ns",
        q_units="Da_per_us3",
    )
    th, C = canonicalize_candidate(lab)
    assert _near(th[0], 0.50830)
    assert _near(th[1], 4.851)
    # Cross term C01 = rho*sk*st0 after scale: (0.03/1000)*(0.09/1000)*0.5
    assert _near(C[0][1], 0.5 * (0.03 * 0.001) * (0.09 * 0.001), atol=1e-20)

    cal = {"run_id": run_id, "active": api}
    peaks = _mini_peaks(run_id)
    catalog = _mini_catalog()
    schema_digest = hashlib.sha256(SCHEMA.read_bytes()).hexdigest()
    labs = [{**lab, "key": "n.md::u@1"}]
    exp = reconcile_reference(run_id, cal, peaks, catalog, labs, schema_digest)

    srv = FixtureServer(cal, peaks, catalog)
    api_url = srv.start()
    try:
        with tempfile.TemporaryDirectory() as td:
            notes = Path(td)
            write_notes(notes, {"n.md": note_table("N", [lab])})
            out = Path(td) / "o.json"
            r = run_bin(api_url, run_id, notes, SCHEMA, out)
            assert r.returncode == 0, r.stderr
            got = json.loads(out.read_text())
            assert_report_matches(got, exp)
            # Ensure off-diagonal present in final cov when robust_gls/api_lock uses labs
            assert abs(got["axis"]["covariance"][0][1]) > 0 or got["axis"]["source"] == "api_lock"
    finally:
        srv.stop()


def test_equal_revision_tie_is_order_invariant():
    """Equal-revision selection must not depend on row order."""
    run_id = "tie"
    api = _base_api()
    # Raw mDa sigma_k is smaller than Da sigma_k, but after conversion g(C) is larger.
    row_mda = cand(
        candidate_id="tie",
        rev=5,
        k=508.250,
        t0=4850.40,
        q=-1.860e-5,
        sigma_k=0.00001,
        sigma_t0=500.0,
        sigma_q=1.0e-6,
        rho_k_t0=0.1,
        rho_k_q=0.0,
        rho_t0_q=0.0,
        k_units="mDa_per_us2",
        t0_units="ns",
    )
    row_da = cand(
        candidate_id="tie",
        rev=5,
        k=0.508205,
        t0=4.850100,
        q=-1.849e-5,
        sigma_k=2.0e-5,
        sigma_t0=4.0e-5,
        sigma_q=9.0e-8,
        rho_k_t0=0.1,
        rho_k_q=0.0,
        rho_t0_q=0.0,
    )
    _th1, C1 = canonicalize_candidate(row_mda)
    _th2, C2 = canonicalize_candidate(row_da)
    assert gscale(C2) < gscale(C1)
    assert row_mda["sigma_k"] < row_da["sigma_k"]  # traps pre-conversion ranking

    cal = {"run_id": run_id, "active": api}
    peaks = _mini_peaks(run_id)
    catalog = _mini_catalog()

    digests = []
    for order in ([row_mda, row_da], [row_da, row_mda]):
        srv = FixtureServer(cal, peaks, catalog)
        api_url = srv.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                notes = Path(td)
                write_notes(notes, {"n.md": note_table("N", order)})
                out = Path(td) / "o.json"
                r = run_bin(api_url, run_id, notes, SCHEMA, out)
                assert r.returncode == 0, r.stderr
                got = json.loads(out.read_text())
                digests.append(got["ledger_digest"])
                assert "n.md::tie@5" in got["provenance"]["used_candidate_keys"] or got["axis"]["source"] in (
                    "api_lock",
                    "api_only",
                    "robust_gls",
                    "api_only_after_rejection",
                )
        finally:
            srv.stop()
    assert digests[0] == digests[1]


def test_full_uncertainty_propagation_boundary():
    """Correlations and tof_sigma_ns must alter sigma_corr and a boundary classification."""
    run_id = "prop"
    # Construct so diagonal-only propagation would accept, full cov rejects (or vice versa)
    api = cand(
        candidate_id="api-active",
        k=0.5,
        t0=5.0,
        q=0.0,
        sigma_k=1e-4,
        sigma_t0=1e-4,
        sigma_q=1e-6,
        rho_k_t0=-0.95,
        rho_k_q=0.0,
        rho_t0_q=0.0,
    )
    cal = {"run_id": run_id, "active": api}
    # Single peak near catalog with residual near boundary
    # m = 0.5*(tof-5)^2 ; want ~100 Da => dt=sqrt(200)~14.14, tof~19.14
    # Shift slightly for residual
    catalog = {"ions": [{"ion_id": "X", "mz_da": 100.0, "sigma_da": 0.0001}]}
    peaks = {
        "run_id": run_id,
        "peaks": [{"peak_id": "p", "tof_us": 19.1421356237, "tof_sigma_ns": 0.02}],
    }
    schema_digest = hashlib.sha256(SCHEMA.read_bytes()).hexdigest()
    exp = reconcile_reference(run_id, cal, peaks, catalog, [], schema_digest)

    # Diagonal-only sigma at same point
    th, C = canonicalize_candidate(api)
    tof = 19.1421356237
    sig_us = 0.02 / 1000
    full = sigma_corr(th, C, tof, sig_us)
    Cdiag = [[C[0][0], 0, 0], [0, C[1][1], 0], [0, 0, C[2][2]]]
    diag = sigma_corr(th, Cdiag, tof, sig_us)
    assert abs(full - diag) > 1e-6

    srv = FixtureServer(cal, peaks, catalog)
    api_url = srv.start()
    try:
        with tempfile.TemporaryDirectory() as td:
            notes = Path(td)
            write_notes(notes, {"empty.md": "# no tables\n"})
            out = Path(td) / "o.json"
            r = run_bin(api_url, run_id, notes, SCHEMA, out)
            assert r.returncode == 0, r.stderr
            got = json.loads(out.read_text())
            assert _near(got["peaks"][0]["sigma_corr_da"], full, atol=1e-18, rtol=1e-9)
            assert got["peaks"][0]["accepted"] == exp["peaks"][0]["accepted"]
    finally:
        srv.stop()


def test_global_assignment_beats_greedy():
    """Ambiguous two-peak/two-ion case where greedy nearest is suboptimal."""
    run_id = "assign"
    api = cand(
        candidate_id="api-active",
        k=1.0,
        t0=0.0,
        q=0.0,
        sigma_k=1e-6,
        sigma_t0=1e-6,
        sigma_q=1e-9,
    )
    # m = tof^2. Shared ion is nearest to both; alternate is only reachable for pA.
    # Greedy assigns shared to pA and leaves pB unmatched; global assigns alt+shared.
    peaks = {
        "run_id": run_id,
        "peaks": [
            {"peak_id": "pA", "tof_us": 3.1622776602, "tof_sigma_ns": 0.01},  # m=10.000
            {"peak_id": "pB", "tof_us": 3.1638584035, "tof_sigma_ns": 0.01},  # m=10.010
        ],
    }
    catalog = {
        "ions": [
            {"ion_id": "shared", "mz_da": 10.005, "sigma_da": 0.01},
            {"ion_id": "alt", "mz_da": 9.990, "sigma_da": 0.01},
        ]
    }
    cal = {"run_id": run_id, "active": api}
    schema_digest = hashlib.sha256(SCHEMA.read_bytes()).hexdigest()
    exp = reconcile_reference(run_id, cal, peaks, catalog, [], schema_digest)

    th, C = canonicalize_candidate(api)
    wpeaks = []
    for p in peaks["peaks"]:
        tof = p["tof_us"]
        sc = sigma_corr(th, C, tof, p["tof_sigma_ns"] / 1000)
        wpeaks.append({"peak_id": p["peak_id"], "corrected": mass(th, tof), "sigma": sc})
    ions = [{"ion_id": i["ion_id"], "mz": i["mz_da"], "sigma": i["sigma_da"]} for i in catalog["ions"]]
    ion_used = set()
    greedy_matched = 0
    for wp in sorted(wpeaks, key=lambda x: x["peak_id"]):
        best = None
        for ji, ion in enumerate(ions):
            if ji in ion_used:
                continue
            res = abs(wp["corrected"] - ion["mz"])
            if res > MATCH_WINDOW:
                continue
            cost = res * res / (wp["sigma"] ** 2 + ion["sigma"] ** 2)
            if best is None or cost < best[0]:
                best = (cost, ji)
        if best:
            ion_used.add(best[1])
            greedy_matched += 1
    assert exp["summary"]["matched"] > greedy_matched

    srv = FixtureServer(cal, peaks, catalog)
    api_url = srv.start()
    try:
        with tempfile.TemporaryDirectory() as td:
            notes = Path(td)
            write_notes(notes, {"e.md": "# none\n"})
            out = Path(td) / "o.json"
            r = run_bin(api_url, run_id, notes, SCHEMA, out)
            assert r.returncode == 0, r.stderr
            got = json.loads(out.read_text())
            assert got["summary"]["matched"] == exp["summary"]["matched"]
            gmap = {p["peak_id"]: p["catalog_id"] for p in got["peaks"]}
            emap = {p["peak_id"]: p["catalog_id"] for p in exp["peaks"]}
            assert gmap == emap
    finally:
        srv.stop()


def test_ordering_invariance_of_report_bytes_and_digest():
    """Permuting notes/rows/peaks/catalog/JSON key order must leave digest identical."""
    run_id = "order"
    api = _base_api()
    lab = cand(
        candidate_id="L",
        k=0.50822,
        t0=4.8503,
        q=-1.84e-5,
        sigma_k=2.2e-5,
        sigma_t0=6e-5,
        sigma_q=1.1e-7,
        rho_k_t0=0.2,
    )
    peaks_a = {
        "run_id": run_id,
        "peaks": [
            {"peak_id": "p2", "tof_us": 30.0, "tof_sigma_ns": 0.05, "intensity": 1},
            {"peak_id": "p1", "tof_us": 20.1, "tof_sigma_ns": 0.05, "intensity": 2},
        ],
    }
    peaks_b = {
        "run_id": run_id,
        "peaks": list(reversed(peaks_a["peaks"])),
    }
    cat_a = {
        "ions": [
            {"ion_id": "B", "mz_da": 322.05, "sigma_da": 0.001},
            {"ion_id": "A", "mz_da": 118.09, "sigma_da": 0.001},
        ]
    }
    cat_b = {"ions": list(reversed(cat_a["ions"]))}
    digests = []
    for peaks, catalog, row_order, file_order in [
        (peaks_a, cat_a, [lab], ["a.md", "b.md"]),
        (peaks_b, cat_b, [lab], ["b.md", "a.md"]),
    ]:
        cal = {"run_id": run_id, "active": api}
        srv = FixtureServer(cal, peaks, catalog)
        api_url = srv.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                notes = Path(td)
                files = {
                    "a.md": note_table("N", row_order),
                    "b.md": note_table("Decoy", [lab], decoy=True),
                }
                write_notes(notes, files)
                out = Path(td) / "o.json"
                r = run_bin(api_url, run_id, notes, SCHEMA, out)
                assert r.returncode == 0, r.stderr
                rep = json.loads(out.read_text())
                digests.append(rep["ledger_digest"])
                # api_base embeds the ephemeral port; exclude it from byte identity.
                rep2 = dict(rep)
                rep2["api_base"] = "http://127.0.0.1:PORT"
                # structural identity via digest already covers numerical ledger
                assert rep["provenance"]["used_candidate_keys"] == [
                    "a.md::L@1",
                    "instrument::api-active",
                ] or rep["axis"]["source"] in (
                    "api_lock",
                    "api_only",
                    "robust_gls",
                    "api_only_after_rejection",
                )
        finally:
            srv.stop()
    assert digests[0] == digests[1]


def test_schema_enforcement_preserves_sentinel():
    """Invalid or wrong-version schema fails and leaves an existing report untouched."""
    run_id = "schema"
    api = _base_api()
    cal = {"run_id": run_id, "active": api}
    peaks = _mini_peaks(run_id)
    catalog = _mini_catalog()
    srv = FixtureServer(cal, peaks, catalog)
    api_url = srv.start()
    try:
        with tempfile.TemporaryDirectory() as td:
            notes = Path(td)
            write_notes(notes, {"n.md": "# x\n"})
            out = Path(td) / "o.json"
            sentinel = b'{"sentinel": true, "keep": "me"}\n'
            out.write_bytes(sentinel)
            bad_schema = Path(td) / "bad.json"
            bad_schema.write_text(json.dumps({"x-tofmass-report-version": 1, "title": "nope"}))
            r = run_bin(api_url, run_id, notes, bad_schema, out)
            assert r.returncode != 0
            assert out.read_bytes() == sentinel
            # invalid json
            bad2 = Path(td) / "bad2.json"
            bad2.write_text("{not json")
            r = run_bin(api_url, run_id, notes, bad2, out)
            assert r.returncode != 0
            assert out.read_bytes() == sentinel
    finally:
        srv.stop()


def test_run_binding_mismatch_preserves_sentinel():
    """Mismatched calibration/peaks run_id must fail without replacing output."""
    run_id = "bind"
    api = _base_api()
    cal = {"run_id": "other-run", "active": api}
    peaks = _mini_peaks(run_id)
    catalog = _mini_catalog()
    srv = FixtureServer(cal, peaks, catalog)
    api_url = srv.start()
    try:
        with tempfile.TemporaryDirectory() as td:
            notes = Path(td)
            write_notes(notes, {"n.md": "# x\n"})
            out = Path(td) / "o.json"
            sentinel = b'SENTINEL-BYTES-v1\n'
            out.write_bytes(sentinel)
            r = run_bin(api_url, run_id, notes, SCHEMA, out)
            assert r.returncode != 0
            assert out.read_bytes() == sentinel
    finally:
        srv.stop()


def test_atomic_output_on_malformed_catalog():
    """Malformed catalog must leave no temp artifact and preserve old report bytes."""
    run_id = "atomic"
    api = _base_api()
    cal = {"run_id": run_id, "active": api}
    peaks = _mini_peaks(run_id)
    catalog = {
        "ions": [
            {"ion_id": "A", "mz_da": 118.09},  # missing sigma_da
            {"ion_id": "A", "mz_da": 118.09, "sigma_da": 0.001},  # also duplicate if fixed
        ]
    }
    srv = FixtureServer(cal, peaks, catalog)
    api_url = srv.start()
    try:
        with tempfile.TemporaryDirectory() as td:
            notes = Path(td)
            write_notes(notes, {"n.md": "# x\n"})
            out = Path(td) / "report.json"
            sentinel = b'{"old": true}\n'
            out.write_bytes(sentinel)
            r = run_bin(api_url, run_id, notes, SCHEMA, out)
            assert r.returncode != 0
            assert out.read_bytes() == sentinel
            temps = list(Path(td).glob(".tofmass-report-*"))
            assert temps == []
    finally:
        srv.stop()


def test_digest_sensitivity_to_real_inputs():
    """A covariance or TOF mutation changes the digest; key order does not."""
    run_id = "digest"
    api = _base_api()
    cal = {"run_id": run_id, "active": api}
    peaks = _mini_peaks(run_id)
    catalog = _mini_catalog()
    srv = FixtureServer(cal, peaks, catalog)
    api_url = srv.start()
    try:
        with tempfile.TemporaryDirectory() as td:
            notes = Path(td)
            write_notes(notes, {"n.md": "# x\n"})
            out = Path(td) / "o.json"
            r = run_bin(api_url, run_id, notes, SCHEMA, out)
            assert r.returncode == 0, r.stderr
            d0 = json.loads(out.read_text())["ledger_digest"]
    finally:
        srv.stop()

    api2 = dict(api)
    api2["rho_k_t0"] = 0.55
    cal2 = {"run_id": run_id, "active": api2}
    srv = FixtureServer(cal2, peaks, catalog)
    api_url = srv.start()
    try:
        with tempfile.TemporaryDirectory() as td:
            notes = Path(td)
            write_notes(notes, {"n.md": "# x\n"})
            out = Path(td) / "o.json"
            r = run_bin(api_url, run_id, notes, SCHEMA, out)
            assert r.returncode == 0, r.stderr
            d1 = json.loads(out.read_text())["ledger_digest"]
    finally:
        srv.stop()
    assert d0 != d1

    peaks2 = {
        "run_id": run_id,
        "peaks": [
            {"peak_id": "p1", "tof_us": 20.1000001, "tof_sigma_ns": 0.05},
            {"peak_id": "p2", "tof_us": 30.0, "tof_sigma_ns": 0.05},
        ],
    }
    srv = FixtureServer(cal, peaks2, catalog)
    api_url = srv.start()
    try:
        with tempfile.TemporaryDirectory() as td:
            notes = Path(td)
            write_notes(notes, {"n.md": "# x\n"})
            out = Path(td) / "o.json"
            r = run_bin(api_url, run_id, notes, SCHEMA, out)
            assert r.returncode == 0, r.stderr
            d2 = json.loads(out.read_text())["ledger_digest"]
    finally:
        srv.stop()
    assert d2 != d0


def test_no_notebook_fallback_api_only():
    """With no admissible notebook candidates, API-only behavior remains valid."""
    run_id = "api-only"
    api = _base_api()
    cal = {"run_id": run_id, "active": api}
    peaks = _mini_peaks(run_id)
    catalog = _mini_catalog()
    schema_digest = hashlib.sha256(SCHEMA.read_bytes()).hexdigest()
    exp = reconcile_reference(run_id, cal, peaks, catalog, [], schema_digest)
    assert exp["axis"]["source"] == "api_only"

    srv = FixtureServer(cal, peaks, catalog)
    api_url = srv.start()
    try:
        with tempfile.TemporaryDirectory() as td:
            notes = Path(td)
            write_notes(notes, {"n.md": "# no axis tables\n"})
            out = Path(td) / "o.json"
            r = run_bin(api_url, run_id, notes, SCHEMA, out)
            assert r.returncode == 0, r.stderr
            got = json.loads(out.read_text())
            assert_report_matches(got, exp)
    finally:
        srv.stop()
