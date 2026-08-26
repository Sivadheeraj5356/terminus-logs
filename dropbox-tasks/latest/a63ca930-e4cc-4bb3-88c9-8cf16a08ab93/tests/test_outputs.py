"""Verification for quantum state-vector simulation benchmark."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPORT_PATH = Path("/app/build/statevec_benchmark_report.json")
BINARY_PATH = Path("/app/build/qwavectl")
REPORT_FIRST = Path("/logs/verifier/report_first.json")
VERIFIER_DIR = Path("/logs/verifier")
PROTECTED_DIR = Path("/tests/protected")
PROTECTED_HASHES_PATH = PROTECTED_DIR / "sha256sums.json"
SRC_GRADE_DIR = VERIFIER_DIR / "src_grade"
GRADE_BUILD_DIR = Path("/home/model/grade_src")
CORPUS_DIR = Path("/app/wavefn_corpus")
ROSTER_PATH = CORPUS_DIR / "roster.json"
APP_DIR = Path("/app")
MAIN_GO = APP_DIR / "qwavectl" / "cmd" / "qwavectl" / "main.go"
BUILD_DIR = APP_DIR / "build"
CONTRACT_PATH = APP_DIR / "engine_spec" / "statevec_sim_contract.json"
AGENT_USER = "model"
EDITABLE_PACKAGES = ("qwavectl", "ampstore", "gatekron", "circexec", "numpolicy")

IMMUTABLE_SHA256: dict[str, str] = {}

S2 = 1 / math.sqrt(2)
PHASE_EPS = 1e-15
FUSABLE = {"I", "X", "Y", "Z", "H", "S", "T", "Sdg", "Tdg"}
KNOWN = FUSABLE | {"RX", "RZ", "CNOT", "CZ", "CPHASE", "SWAP", "CSWAP", "REWIND"}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fmt10(v: float) -> str:
    if v == 0.0:
        v = 0.0
    return f"{v:.10f}"


def _mat(op: str) -> tuple[complex, complex, complex, complex]:
    if op == "I":
        return (1 + 0j, 0j, 0j, 1 + 0j)
    if op == "X":
        return (0j, 1 + 0j, 1 + 0j, 0j)
    if op == "Y":
        return (0j, -1j, 1j, 0j)
    if op == "Z":
        return (1 + 0j, 0j, 0j, -1 + 0j)
    if op == "H":
        return (S2 + 0j, S2 + 0j, S2 + 0j, -S2 + 0j)
    if op == "S":
        return (1 + 0j, 0j, 0j, 1j)
    if op == "Sdg":
        return (1 + 0j, 0j, 0j, -1j)
    if op == "T":
        return (1 + 0j, 0j, 0j, complex(math.cos(math.pi / 4), math.sin(math.pi / 4)))
    if op == "Tdg":
        return (1 + 0j, 0j, 0j, complex(math.cos(-math.pi / 4), math.sin(-math.pi / 4)))
    raise KeyError(op)


def _rx_mat(theta: float) -> tuple[complex, complex, complex, complex]:
    c = math.cos(theta / 2)
    s = math.sin(theta / 2)
    return (complex(c, 0), complex(0, -s), complex(0, -s), complex(c, 0))


def _rz_mat(theta: float) -> tuple[complex, complex, complex, complex]:
    return (
        complex(math.cos(-theta / 2), math.sin(-theta / 2)),
        0j,
        0j,
        complex(math.cos(theta / 2), math.sin(theta / 2)),
    )


def _adjoint(
    m: tuple[complex, complex, complex, complex]
) -> tuple[complex, complex, complex, complex]:
    m00, m01, m10, m11 = m
    return (m00.conjugate(), m10.conjugate(), m01.conjugate(), m11.conjugate())


def _mul(
    a: tuple[complex, complex, complex, complex],
    b: tuple[complex, complex, complex, complex],
) -> tuple[complex, complex, complex, complex]:
    a00, a01, a10, a11 = a
    b00, b01, b10, b11 = b
    return (
        a00 * b00 + a01 * b10,
        a00 * b01 + a01 * b11,
        a10 * b00 + a11 * b10,
        a10 * b01 + a11 * b11,
    )


def _apply1(st: list[complex], q: int, m: tuple[complex, complex, complex, complex]) -> None:
    u00, u01, u10, u11 = m
    mask = 1 << q
    for i in range(len(st)):
        if i & mask:
            continue
        j = i | mask
        a0, a1 = st[i], st[j]
        st[i] = u00 * a0 + u01 * a1
        st[j] = u10 * a0 + u11 * a1


def _apply_cnot(st: list[complex], c: int, t: int) -> None:
    cm, tm = 1 << c, 1 << t
    for i in range(len(st)):
        if not (i & cm):
            continue
        j = i ^ tm
        if i < j:
            st[i], st[j] = st[j], st[i]


def _apply_cz(st: list[complex], c: int, t: int) -> None:
    cm, tm = 1 << c, 1 << t
    for i in range(len(st)):
        if (i & cm) and (i & tm):
            st[i] = -st[i]


def _apply_cphase(st: list[complex], c: int, t: int, phi: float) -> None:
    phase = complex(math.cos(phi), math.sin(phi))
    cm, tm = 1 << c, 1 << t
    for i in range(len(st)):
        if (i & cm) and (i & tm):
            st[i] *= phase


def _apply_swap(st: list[complex], a: int, b: int) -> None:
    if a == b:
        return
    am, bm = 1 << a, 1 << b
    for i in range(len(st)):
        ba = bool(i & am)
        bb = bool(i & bm)
        if ba == bb:
            continue
        j = i ^ am ^ bm
        if i < j:
            st[i], st[j] = st[j], st[i]


def _apply_cswap(st: list[complex], c: int, a: int, b: int) -> None:
    cm, am, bm = 1 << c, 1 << a, 1 << b
    for i in range(len(st)):
        if not (i & cm):
            continue
        ba = bool(i & am)
        bb = bool(i & bm)
        if ba == bb:
            continue
        j = i ^ am ^ bm
        if i < j:
            st[i], st[j] = st[j], st[i]


def _apply_inverse(st: list[complex], entry: tuple) -> None:
    kind = entry[0]
    if kind == "one":
        _apply1(st, entry[1], _adjoint(entry[2]))
    elif kind == "cnot":
        _apply_cnot(st, entry[1], entry[2])
    elif kind == "cz":
        _apply_cz(st, entry[1], entry[2])
    elif kind == "swap":
        _apply_swap(st, entry[1], entry[2])
    elif kind == "cphase":
        _apply_cphase(st, entry[1], entry[2], -entry[3])
    elif kind == "cswap":
        _apply_cswap(st, entry[1], entry[2], entry[3])


def _resolve_policy(sc: dict[str, Any]) -> tuple[float, float, bool, bool, float]:
    norm_eps = float(sc.get("norm_eps", 1e-9))
    fid_eps = float(sc.get("fidelity_eps", 1e-9))
    fuse = bool(sc.get("fuse_adjacent", True))
    check_u = bool(sc.get("check_unitary", True))
    ghost_eps = float(sc.get("ghost_eps", 0.0))
    overrides = sc.get("policy_overrides") or {}
    if "norm_eps" in overrides and float(overrides["norm_eps"]) > 0:
        norm_eps = float(overrides["norm_eps"])
    if "fidelity_eps" in overrides and float(overrides["fidelity_eps"]) > 0:
        fid_eps = float(overrides["fidelity_eps"])
    if "fuse_adjacent" in overrides:
        fuse = bool(overrides["fuse_adjacent"])
    if "check_unitary" in overrides:
        check_u = bool(overrides["check_unitary"])
    if "ghost_eps" in overrides:
        ghost_eps = float(overrides["ghost_eps"])
    return norm_eps, fid_eps, fuse, check_u, ghost_eps


def analyze_circuit(sc: dict[str, Any]) -> dict[str, Any]:
    """Python reference matching corrected Go engine semantics."""
    qubits = int(sc["qubits"])
    gates = sc["gates"]
    norm_eps, fid_eps, fuse, check_u, ghost_eps = _resolve_policy(sc)

    st: list[complex] = [0j] * (1 << qubits)
    st[0] = 1 + 0j
    anomalies: list[dict[str, Any]] = []
    fused = 0
    history: list[tuple] = []

    i = 0
    steps: list[tuple] = []
    while i < len(gates):
        g = gates[i]
        if (
            fuse
            and g["op"] in FUSABLE
            and i + 1 < len(gates)
            and gates[i + 1]["op"] == g["op"]
            and gates[i + 1].get("qubit") == g.get("qubit")
            and g.get("qubit") is not None
        ):
            if g.get("block_fuse") is True:
                anomalies.append({"kind": "FUSION_SKIP", "gate_index": i, "detail": g["op"]})
                steps.append(("gate", g, i))
                steps.append(("gate", gates[i + 1], i + 1))
                i += 2
                continue
            m = _mul(_mat(gates[i + 1]["op"]), _mat(g["op"]))
            steps.append(("mat", g.get("qubit"), m, i, g["op"]))
            fused += 1
            i += 2
            continue
        steps.append(("gate", g, i))
        i += 1

    structural_stop = False
    for step in steps:
        if step[0] == "mat":
            _, q, m, gi, opname = step
            if q < 0 or q >= qubits:
                anomalies.append({"kind": "QUBIT_OUT_OF_RANGE", "gate_index": gi, "detail": opname})
                structural_stop = True
                break
            _apply1(st, q, m)
            history.append(("one", q, m))
            continue
        g, gi = step[1], step[2]
        op = g["op"]
        if op == "REWIND":
            depth = g.get("depth")
            if depth is None or float(depth) < 0:
                anomalies.append({"kind": "UNKNOWN_GATE", "gate_index": gi, "detail": "REWIND"})
                structural_stop = True
                break
            d = int(depth)
            if d == 0:
                continue
            if d > len(history):
                anomalies.append(
                    {"kind": "REWIND_OVERFLOW", "gate_index": gi, "detail": "overflow"}
                )
                structural_stop = True
                break
            for _ in range(d):
                _apply_inverse(st, history.pop())
            continue
        if op not in KNOWN:
            anomalies.append({"kind": "UNKNOWN_GATE", "gate_index": gi, "detail": op})
            structural_stop = True
            break
        if op == "CNOT":
            c, t = g["control"], g["target"]
            if c == t or min(c, t) < 0 or max(c, t) >= qubits:
                anomalies.append({"kind": "QUBIT_OUT_OF_RANGE", "gate_index": gi, "detail": "cnot"})
                structural_stop = True
                break
            _apply_cnot(st, c, t)
            history.append(("cnot", c, t))
        elif op == "CZ":
            c, t = g["control"], g["target"]
            if c == t or min(c, t) < 0 or max(c, t) >= qubits:
                anomalies.append({"kind": "QUBIT_OUT_OF_RANGE", "gate_index": gi, "detail": "cz"})
                structural_stop = True
                break
            _apply_cz(st, c, t)
            history.append(("cz", c, t))
        elif op == "CPHASE":
            c, t = g["control"], g["target"]
            phi = float(g["phi"])
            if c == t or min(c, t) < 0 or max(c, t) >= qubits:
                anomalies.append(
                    {"kind": "QUBIT_OUT_OF_RANGE", "gate_index": gi, "detail": "cphase"}
                )
                structural_stop = True
                break
            _apply_cphase(st, c, t, phi)
            history.append(("cphase", c, t, phi))
        elif op == "SWAP":
            a, b = g["a"], g["b"]
            if a == b or min(a, b) < 0 or max(a, b) >= qubits:
                anomalies.append({"kind": "QUBIT_OUT_OF_RANGE", "gate_index": gi, "detail": "swap"})
                structural_stop = True
                break
            _apply_swap(st, a, b)
            history.append(("swap", a, b))
        elif op == "CSWAP":
            c, a, b = g["control"], g["a"], g["b"]
            idxs = [c, a, b]
            if c == a or c == b or a == b or min(idxs) < 0 or max(idxs) >= qubits:
                anomalies.append(
                    {"kind": "QUBIT_OUT_OF_RANGE", "gate_index": gi, "detail": "cswap"}
                )
                structural_stop = True
                break
            _apply_cswap(st, c, a, b)
            history.append(("cswap", c, a, b))
        elif op == "RX":
            if "theta" not in g or g["theta"] is None:
                anomalies.append({"kind": "UNKNOWN_GATE", "gate_index": gi, "detail": "RX"})
                structural_stop = True
                break
            q = g["qubit"]
            theta = float(g["theta"])
            if q < 0 or q >= qubits:
                anomalies.append({"kind": "QUBIT_OUT_OF_RANGE", "gate_index": gi, "detail": "RX"})
                structural_stop = True
                break
            m = _rx_mat(theta)
            _apply1(st, q, m)
            history.append(("one", q, m))
        elif op == "RZ":
            if "theta" not in g or g["theta"] is None:
                anomalies.append({"kind": "UNKNOWN_GATE", "gate_index": gi, "detail": "RZ"})
                structural_stop = True
                break
            q = g["qubit"]
            theta = float(g["theta"])
            if q < 0 or q >= qubits:
                anomalies.append({"kind": "QUBIT_OUT_OF_RANGE", "gate_index": gi, "detail": "RZ"})
                structural_stop = True
                break
            m = _rz_mat(theta)
            _apply1(st, q, m)
            history.append(("one", q, m))
        else:
            q = g["qubit"]
            if q < 0 or q >= qubits:
                anomalies.append({"kind": "QUBIT_OUT_OF_RANGE", "gate_index": gi, "detail": op})
                structural_stop = True
                break
            m = _mat(op)
            _apply1(st, q, m)
            history.append(("one", q, m))

    rev_clone = st[:]

    if ghost_eps > 0:
        zeroed = False
        for k in range(len(st)):
            if st[k] != 0 and abs(st[k]) < ghost_eps:
                st[k] = 0j
                zeroed = True
        if zeroed:
            nrm = math.sqrt(sum((z.real * z.real + z.imag * z.imag) for z in st))
            if nrm > 0:
                st = [z / nrm for z in st]

    norm = math.sqrt(sum((z.real * z.real + z.imag * z.imag) for z in st))
    rev_fid = 0.0
    if not structural_stop:
        for entry in reversed(history):
            _apply_inverse(rev_clone, entry)
        rev_fid = rev_clone[0].real * rev_clone[0].real + rev_clone[0].imag * rev_clone[0].imag
        if abs(norm - 1.0) > norm_eps:
            anomalies.append({"kind": "NORM_DRIFT", "gate_index": -1, "detail": _fmt10(norm)})
        if check_u and abs(rev_fid - 1.0) > fid_eps:
            anomalies.append(
                {"kind": "UNITARY_DRIFT", "gate_index": -1, "detail": _fmt10(rev_fid)}
            )

    lead = -1
    for k in range(len(st)):
        if abs(st[k]) > PHASE_EPS:
            lead = k
            break
    if lead >= 0:
        mag = abs(st[lead])
        factor = st[lead].conjugate() / mag
        st = [z * factor for z in st]

    anomalies.sort(key=lambda a: (a["kind"], a["gate_index"], a["detail"]))
    amps = [{"re": _fmt10(a.real), "im": _fmt10(a.imag)} for a in st]
    status = "INVALID" if anomalies else "VALID"
    return {
        "circuit_id": sc["circuit_id"],
        "qubits": qubits,
        "status": status,
        "gate_count": len(gates),
        "fused_pairs": fused,
        "norm": _fmt10(norm),
        "reverse_fidelity": _fmt10(rev_fid),
        "amplitudes": amps,
        "anomalies": anomalies,
    }


def _build_expected_report() -> dict[str, Any]:
    roster = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))
    return {
        "circuits": [
            analyze_circuit(json.loads((CORPUS_DIR / f"{cid}.json").read_text(encoding="utf-8")))
            for cid in roster["circuits"]
        ]
    }


def _agent_env() -> dict[str, str]:
    env = dict(os.environ)
    env["HOME"] = "/home/model"
    env["GOTMPDIR"] = "/home/model/tmp"
    env["GOCACHE"] = "/home/model/go/cache"
    env["GOPATH"] = "/home/model/go"
    return env


def _run_as_agent(
    argv: list[str],
    *,
    log_name: str | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run build/binary as the restricted model user away from protected mounts."""
    VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["runuser", "-u", AGENT_USER, "--", *argv],
        cwd=str(cwd or GRADE_BUILD_DIR),
        capture_output=True,
        text=True,
        env=_agent_env(),
    )
    if log_name is not None:
        (VERIFIER_DIR / log_name).write_text(proc.stdout + proc.stderr, encoding="utf-8")
    return proc


def _assert_regular_editable_sources() -> None:
    """Reject source links and mirror regular sources into verifier-owned staging."""
    if SRC_GRADE_DIR.exists():
        shutil.rmtree(SRC_GRADE_DIR)
    SRC_GRADE_DIR.mkdir(parents=True, exist_ok=True)

    go_mod = APP_DIR / "go.mod"
    assert go_mod.is_file() and not go_mod.is_symlink(), "go.mod must be a regular file"
    shutil.copy2(go_mod, SRC_GRADE_DIR / "go.mod")

    for name in EDITABLE_PACKAGES:
        src_root = APP_DIR / name
        assert src_root.is_dir(), f"missing editable package {name}"
        assert not src_root.is_symlink(), f"source link rejected: {src_root}"
        for path in src_root.rglob("*"):
            assert not path.is_symlink(), f"source link rejected: {path}"
        dest = SRC_GRADE_DIR / name
        shutil.copytree(src_root, dest, symlinks=False)
        for path in dest.rglob("*.go"):
            assert path.is_file() and not path.is_symlink(), f"staged source must be regular: {path}"

    # Model-readable build tree has only staged packages + go.mod (no /tests or /solution).
    if GRADE_BUILD_DIR.exists():
        shutil.rmtree(GRADE_BUILD_DIR)
    shutil.copytree(SRC_GRADE_DIR, GRADE_BUILD_DIR, symlinks=False)
    for path in [GRADE_BUILD_DIR, *GRADE_BUILD_DIR.rglob("*")]:
        shutil.chown(path, user=AGENT_USER, group=AGENT_USER)
    assert not (GRADE_BUILD_DIR / "tests").exists()
    assert not (GRADE_BUILD_DIR / "solution").exists()
    assert (GRADE_BUILD_DIR / "go.mod").is_file()


def _run_make(target: str, log_name: str) -> None:
    """Compile only verifier-owned staged sources, then optionally run the binary as model."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    _chown_model(BUILD_DIR)
    _assert_regular_editable_sources()

    if target not in ("build", "run"):
        pytest.fail(f"unsupported make target for staged grading: {target}")

    build_log = log_name if target == "build" else f"build_for_{log_name}"
    build_proc = _run_as_agent(
        ["go", "build", "-o", str(BINARY_PATH), "./qwavectl/cmd/qwavectl"],
        log_name=build_log,
        cwd=GRADE_BUILD_DIR,
    )
    if build_proc.returncode != 0:
        pytest.fail(f"staged go build failed; see /logs/verifier/{build_log}")

    if target == "build":
        return

    run_proc = _run_as_agent(
        [str(BINARY_PATH)],
        log_name=log_name,
        cwd=APP_DIR,
    )
    if run_proc.returncode != 0:
        pytest.fail(f"staged binary run failed; see /logs/verifier/{log_name}")


def _load_verifier_owned_hashes() -> dict[str, str]:
    assert PROTECTED_HASHES_PATH.is_file(), f"missing verifier-owned hashes at {PROTECTED_HASHES_PATH}"
    raw = json.loads(PROTECTED_HASHES_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw, dict) and raw, "protected sha256sums.json must be a non-empty object"
    return {str(k): str(v) for k, v in raw.items()}


def _assert_app_matches_protected(hashes: dict[str, str], *, when: str) -> None:
    for rel, expected in hashes.items():
        path = APP_DIR / rel
        assert path.is_file(), f"{when}: missing protected path {rel}"
        assert not path.is_symlink(), f"{when}: protected path must be a regular file: {rel}"
        assert _sha256_file(path) == expected, f"{when}: modified {rel}"


def _assert_regular_build_artifacts() -> None:
    assert BINARY_PATH.is_file() and not BINARY_PATH.is_symlink(), "qwavectl must be a regular file"
    assert REPORT_PATH.is_file() and not REPORT_PATH.is_symlink(), "report must be a regular file"


def _chown_model(path: Path) -> None:
    shutil.chown(path, user=AGENT_USER, group=AGENT_USER)


def _circuit(report: dict[str, Any], circuit_id: str) -> dict[str, Any]:
    for row in report["circuits"]:
        if row["circuit_id"] == circuit_id:
            return row
    raise KeyError(circuit_id)


def _amp(row: dict[str, Any], index: int) -> tuple[str, str]:
    a = row["amplitudes"][index]
    return a["re"], a["im"]


def _perturb_circ_03() -> None:
    path = CORPUS_DIR / "circ_03.json"
    obj = json.loads(path.read_text(encoding="utf-8"))
    shutil.copy(path, VERIFIER_DIR / "circ_03_clean.json")
    obj["gates"] = [{"op": "X", "qubit": 0}]
    path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
    _chown_model(path)


@pytest.fixture(scope="session", autouse=True)
def _verifier_grading_setup() -> None:
    """Lock verifier-owned hashes, reject source links, then build/run as model."""
    VERIFIER_DIR.mkdir(parents=True, exist_ok=True)
    for name in ("circ_03_clean.json", "report_first.json"):
        (VERIFIER_DIR / name).unlink(missing_ok=True)
    for path in VERIFIER_DIR.glob("*.log"):
        path.unlink()

    protected = _load_verifier_owned_hashes()
    _assert_app_matches_protected(protected, when="before submitted build")
    IMMUTABLE_SHA256.clear()
    IMMUTABLE_SHA256.update(protected)

    _perturb_circ_03()
    REPORT_PATH.unlink(missing_ok=True)
    _run_make("build", "build.log")
    _run_make("run", "run_perturbed.log")
    _assert_regular_build_artifacts()
    shutil.copy(REPORT_PATH, REPORT_FIRST)
    _run_make("run", "run_perturbed2.log")
    if REPORT_PATH.read_bytes() != REPORT_FIRST.read_bytes():
        pytest.fail("perturbed circ_03 rerun not byte-identical")
    perturbed = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    row = _circuit(perturbed, "circ_03")
    assert _amp(row, 1) == ("1.0000000000", "0.0000000000")

    shutil.copy(VERIFIER_DIR / "circ_03_clean.json", CORPUS_DIR / "circ_03.json")
    _chown_model(CORPUS_DIR / "circ_03.json")
    REPORT_PATH.unlink(missing_ok=True)
    _run_make("run", "run_clean.log")
    shutil.copy(REPORT_PATH, REPORT_FIRST)
    _run_make("run", "run_clean2.log")
    if REPORT_PATH.read_bytes() != REPORT_FIRST.read_bytes():
        pytest.fail("clean rerun not byte-identical")

    _assert_app_matches_protected(IMMUTABLE_SHA256, when="after submitted runs")
    _assert_regular_build_artifacts()


@pytest.fixture(scope="module")
def report() -> dict[str, Any]:
    assert REPORT_PATH.is_file(), f"missing {REPORT_PATH}"
    return json.loads(REPORT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def expected_report() -> dict[str, Any]:
    return _build_expected_report()


def test_report_contract_immutability(report: dict[str, Any]) -> None:
    """Roster order immutability compact JSON and ten decimal metrics for 42 circuits."""
    expected_ids = [f"circ_{i:02d}" for i in range(1, 43)]
    roster = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))
    assert roster["circuits"] == expected_ids
    assert [row["circuit_id"] for row in report["circuits"]] == expected_ids
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert contract["circuit_count"] == 42
    _assert_app_matches_protected(IMMUTABLE_SHA256, when="report contract check")
    _assert_regular_build_artifacts()
    raw = REPORT_PATH.read_bytes()
    assert raw.endswith(b"\n") and b": " not in raw and b", " not in raw
    canonical = json.dumps(report, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
    assert raw == canonical
    assert REPORT_FIRST.is_file() and raw == REPORT_FIRST.read_bytes()
    for row in report["circuits"]:
        assert isinstance(row["norm"], str)
        assert isinstance(row["reverse_fidelity"], str)
        assert row["norm"].count(".") == 1 and len(row["norm"].split(".")[1]) == 10
        assert row["reverse_fidelity"].count(".") == 1 and len(row["reverse_fidelity"].split(".")[1]) == 10
        for amp in row["amplitudes"]:
            assert isinstance(amp["re"], str) and isinstance(amp["im"], str)
            assert len(amp["re"].split(".")[1]) == 10
            assert len(amp["im"].split(".")[1]) == 10
            assert not amp["re"].startswith("-0.0000000000")
            assert not amp["im"].startswith("-0.0000000000")


def test_restricted_user_cannot_read_protected_mounts() -> None:
    """Restricted model user must not read /tests or /solution during grading.

    Note: /logs/verifier is a Harbor bind mount; Docker Desktop often ignores chmod
    on that mount, so we only assert locks that the verifier can reliably enforce.
    """
    for path in ("/tests", "/tests/test_outputs.py"):
        assert Path(path).exists()
        proc = _run_as_agent(["test", "-r", path], log_name=None, cwd=APP_DIR)
        assert proc.returncode != 0, f"{AGENT_USER} must not read {path}"
    proc = _run_as_agent(["ls", "/tests"], log_name=None, cwd=APP_DIR)
    assert proc.returncode != 0, f"{AGENT_USER} must not list /tests"
    if Path("/solution").exists():
        proc = _run_as_agent(["ls", "/solution"], log_name=None, cwd=APP_DIR)
        assert proc.returncode != 0, f"{AGENT_USER} must not list /solution"


def test_full_report_equivalence(report: dict[str, Any], expected_report: dict[str, Any]) -> None:
    """Entire benchmark report must match the Python reference simulator."""
    assert report == expected_report


def test_structural_anomalies(report: dict[str, Any]) -> None:
    """Unknown gate and out-of-range qubit remain INVALID with correct details."""
    unk = _circuit(report, "circ_13")
    assert unk["status"] == "INVALID"
    assert unk["anomalies"][0] == {"kind": "UNKNOWN_GATE", "gate_index": 0, "detail": "FOO"}
    oor = _circuit(report, "circ_14")
    assert oor["status"] == "INVALID"
    assert oor["anomalies"][0]["kind"] == "QUBIT_OUT_OF_RANGE"
    assert oor["anomalies"][0]["detail"] == "X"


def test_rz_after_hadamard_phase_locked(report: dict[str, Any]) -> None:
    """circ_22 RZ(pi/2) after H is canonicalized by phase-lock to a real leading amplitude."""
    row = _circuit(report, "circ_22")
    assert row["status"] == "VALID"
    assert _amp(row, 0) == ("0.7071067812", "0.0000000000")
    assert _amp(row, 1) == ("0.0000000000", "0.7071067812")
    assert row["reverse_fidelity"] == "1.0000000000"


def test_cphase_pi_matches_cz_pattern(report: dict[str, Any]) -> None:
    """circ_23 CPHASE(pi) after HH matches CZ amplitude pattern."""
    row = _circuit(report, "circ_23")
    cz = _circuit(report, "circ_06")
    assert row["status"] == "VALID"
    assert row["amplitudes"] == cz["amplitudes"]


def test_cnot_control_equals_target(report: dict[str, Any]) -> None:
    """circ_24 CNOT with control==target is QUBIT_OUT_OF_RANGE detail cnot."""
    row = _circuit(report, "circ_24")
    assert row["status"] == "INVALID"
    assert row["anomalies"] == [{"kind": "QUBIT_OUT_OF_RANGE", "gate_index": 0, "detail": "cnot"}]


def test_phase_lock_after_y(report: dict[str, Any]) -> None:
    """circ_08 Y|0> = i|1> is phase-locked to the real state |1>."""
    row = _circuit(report, "circ_08")
    assert row["status"] == "VALID"
    assert _amp(row, 0) == ("0.0000000000", "0.0000000000")
    assert _amp(row, 1) == ("1.0000000000", "0.0000000000")
    assert row["reverse_fidelity"] == "1.0000000000"


def test_phase_lock_removes_global_phase(report: dict[str, Any]) -> None:
    """circ_42 RZ(pi/2) then H carries a global phase removed by phase-lock."""
    row = _circuit(report, "circ_42")
    assert row["status"] == "VALID"
    assert _amp(row, 0) == ("0.7071067812", "0.0000000000")
    assert _amp(row, 1) == ("0.7071067812", "0.0000000000")
    assert row["reverse_fidelity"] == "1.0000000000"


def test_ghost_prune_zeroes_tiny_amplitude(report: dict[str, Any]) -> None:
    """circ_38 ghost_eps override zeroes the tiny RX amplitude then renormalizes to |0>."""
    row = _circuit(report, "circ_38")
    assert row["status"] == "VALID"
    assert _amp(row, 0) == ("1.0000000000", "0.0000000000")
    assert _amp(row, 1) == ("0.0000000000", "0.0000000000")
    assert row["norm"] == "1.0000000000"
    assert row["reverse_fidelity"] == "1.0000000000"


def test_cswap_controlled_swap(report: dict[str, Any]) -> None:
    """circ_37 CSWAP with control set swaps qubits 1 and 2 sending |011> to |101>."""
    row = _circuit(report, "circ_37")
    assert row["status"] == "VALID"
    assert len(row["amplitudes"]) == 8
    for idx in range(8):
        expected = (
            ("1.0000000000", "0.0000000000")
            if idx == 5
            else ("0.0000000000", "0.0000000000")
        )
        assert _amp(row, idx) == expected
    assert row["reverse_fidelity"] == "1.0000000000"


def test_rewind_restores_state(report: dict[str, Any]) -> None:
    """circ_39 X then REWIND depth 1 undoes the X and returns to |0>."""
    row = _circuit(report, "circ_39")
    assert row["status"] == "VALID"
    assert row["gate_count"] == 2
    assert _amp(row, 0) == ("1.0000000000", "0.0000000000")
    assert _amp(row, 1) == ("0.0000000000", "0.0000000000")
    assert row["reverse_fidelity"] == "1.0000000000"


def test_rewind_overflow(report: dict[str, Any]) -> None:
    """circ_40 REWIND depth 2 with one history entry emits REWIND_OVERFLOW and keeps the post-H state."""
    row = _circuit(report, "circ_40")
    assert row["status"] == "INVALID"
    assert row["anomalies"] == [
        {"kind": "REWIND_OVERFLOW", "gate_index": 1, "detail": "overflow"}
    ]
    assert _amp(row, 0) == ("0.7071067812", "0.0000000000")
    assert _amp(row, 1) == ("0.7071067812", "0.0000000000")
    assert row["reverse_fidelity"] == "0.0000000000"


def test_rewind_after_fusion(report: dict[str, Any]) -> None:
    """circ_41 XXX fuses one pair, REWIND depth 1 pops only the trailing X history entry to reach |0>."""
    row = _circuit(report, "circ_41")
    assert row["status"] == "VALID"
    assert row["gate_count"] == 4
    assert row["fused_pairs"] == 1
    assert _amp(row, 0) == ("1.0000000000", "0.0000000000")
    assert _amp(row, 1) == ("0.0000000000", "0.0000000000")
    assert row["reverse_fidelity"] == "1.0000000000"


def test_block_fuse_fusion_skip(report: dict[str, Any]) -> None:
    """circ_29 block_fuse on first XX emits FUSION_SKIP, fused_pairs 0, state |0>, INVALID."""
    row = _circuit(report, "circ_29")
    assert row["status"] == "INVALID"
    assert row["fused_pairs"] == 0
    assert row["anomalies"] == [{"kind": "FUSION_SKIP", "gate_index": 0, "detail": "X"}]
    assert _amp(row, 0) == ("1.0000000000", "0.0000000000")
    assert row["reverse_fidelity"] == "1.0000000000"


def test_rx_missing_theta_unknown(report: dict[str, Any]) -> None:
    """circ_30 RX without theta is UNKNOWN_GATE detail RX; decoy angle ignored."""
    row = _circuit(report, "circ_30")
    assert row["status"] == "INVALID"
    assert row["anomalies"] == [{"kind": "UNKNOWN_GATE", "gate_index": 0, "detail": "RX"}]
    assert _amp(row, 0) == ("1.0000000000", "0.0000000000")


def test_swap_a_equals_b(report: dict[str, Any]) -> None:
    """circ_31 SWAP with a==b is QUBIT_OUT_OF_RANGE detail swap."""
    row = _circuit(report, "circ_31")
    assert row["status"] == "INVALID"
    assert row["anomalies"] == [{"kind": "QUBIT_OUT_OF_RANGE", "gate_index": 0, "detail": "swap"}]


def test_unknown_before_oor_corpus(report: dict[str, Any]) -> None:
    """circ_32 FOO on qubit 99 is UNKNOWN_GATE, not QUBIT_OUT_OF_RANGE."""
    row = _circuit(report, "circ_32")
    assert row["status"] == "INVALID"
    assert row["anomalies"] == [{"kind": "UNKNOWN_GATE", "gate_index": 0, "detail": "FOO"}]


def test_triple_x_left_associative_fusion(report: dict[str, Any]) -> None:
    """circ_33 XXX left-associative fusion yields fused_pairs 1 and |1>."""
    row = _circuit(report, "circ_33")
    assert row["status"] == "VALID"
    assert row["fused_pairs"] == 1
    assert _amp(row, 0) == ("0.0000000000", "0.0000000000")
    assert _amp(row, 1) == ("1.0000000000", "0.0000000000")


def test_cz_control_eq_target_after_h(report: dict[str, Any]) -> None:
    """circ_36 CZ control==target after H stops; amplitudes are post-H only."""
    row = _circuit(report, "circ_36")
    assert row["status"] == "INVALID"
    assert row["anomalies"] == [{"kind": "QUBIT_OUT_OF_RANGE", "gate_index": 1, "detail": "cz"}]
    assert _amp(row, 0) == ("0.7071067812", "0.0000000000")
    assert _amp(row, 1) == ("0.7071067812", "0.0000000000")
    assert row["reverse_fidelity"] == "0.0000000000"


def test_strict_threshold_equality_no_drift() -> None:
    """NORM_DRIFT/UNITARY_DRIFT fire only when abs(metric-1) is strictly greater than eps."""
    sc = {
        "circuit_id": "synth_eq",
        "qubits": 1,
        "gates": [{"op": "I", "qubit": 0}],
        "norm_eps": 0.0,
        "fidelity_eps": 0.0,
        "check_unitary": True,
    }
    row = analyze_circuit(sc)
    assert row["status"] == "VALID"
    assert row["anomalies"] == []

    sc2 = {
        "circuit_id": "synth_misspell",
        "qubits": 1,
        "gates": [{"op": "X", "qubit": 0}, {"op": "X", "qubit": 0}],
        "policy_overrides": {"fuse_Adjacent": False, "fidelity_Eps": 1e-30, "Fuse_adjacent": False},
    }
    row2 = analyze_circuit(sc2)
    assert row2["fused_pairs"] == 1
    assert row2["status"] == "VALID"


def test_synthetic_control_eq_target_cz_cphase() -> None:
    """CZ/CPHASE with control==target must also be QUBIT_OUT_OF_RANGE."""
    cz = analyze_circuit(
        {
            "circuit_id": "synth_cz",
            "qubits": 2,
            "gates": [{"op": "CZ", "control": 0, "target": 0}],
        }
    )
    assert cz["anomalies"][0] == {"kind": "QUBIT_OUT_OF_RANGE", "gate_index": 0, "detail": "cz"}
    cp = analyze_circuit(
        {
            "circuit_id": "synth_cp",
            "qubits": 2,
            "gates": [{"op": "CPHASE", "control": 1, "target": 1, "phi": 0.5}],
        }
    )
    assert cp["anomalies"][0] == {"kind": "QUBIT_OUT_OF_RANGE", "gate_index": 0, "detail": "cphase"}


def test_synthetic_unknown_before_oor() -> None:
    """Unknown op with out-of-range qubit must emit UNKNOWN_GATE, not OOR."""
    row = analyze_circuit(
        {
            "circuit_id": "synth_unk_oor",
            "qubits": 1,
            "gates": [{"op": "BAR", "qubit": 99}],
        }
    )
    assert row["anomalies"] == [{"kind": "UNKNOWN_GATE", "gate_index": 0, "detail": "BAR"}]


def test_synthetic_cswap_degenerate_indices() -> None:
    """CSWAP with control==a or a==b is QUBIT_OUT_OF_RANGE detail cswap before any swap."""
    same_ctrl = analyze_circuit(
        {
            "circuit_id": "synth_cswap_ctrl",
            "qubits": 3,
            "gates": [{"op": "CSWAP", "control": 1, "a": 1, "b": 2}],
        }
    )
    assert same_ctrl["anomalies"] == [
        {"kind": "QUBIT_OUT_OF_RANGE", "gate_index": 0, "detail": "cswap"}
    ]
    same_ab = analyze_circuit(
        {
            "circuit_id": "synth_cswap_ab",
            "qubits": 3,
            "gates": [{"op": "CSWAP", "control": 0, "a": 2, "b": 2}],
        }
    )
    assert same_ab["anomalies"] == [
        {"kind": "QUBIT_OUT_OF_RANGE", "gate_index": 0, "detail": "cswap"}
    ]


def test_synthetic_rewind_bad_depth() -> None:
    """REWIND with missing, null, or negative depth emits UNKNOWN_GATE detail REWIND."""
    for gates in (
        [{"op": "X", "qubit": 0}, {"op": "REWIND"}],
        [{"op": "X", "qubit": 0}, {"op": "REWIND", "depth": None}],
        [{"op": "X", "qubit": 0}, {"op": "REWIND", "depth": -1}],
    ):
        row = analyze_circuit({"circuit_id": "synth_rw", "qubits": 1, "gates": gates})
        assert row["status"] == "INVALID"
        assert row["anomalies"] == [{"kind": "UNKNOWN_GATE", "gate_index": 1, "detail": "REWIND"}]
        assert row["reverse_fidelity"] == "0.0000000000"


def test_main_go_absolute_paths_and_prune_call() -> None:
    """main.go must use corpusDir literal, absolute report path, and call pruneBuildStaging."""
    text = MAIN_GO.read_text(encoding="utf-8")
    assert 'corpusDir := "/app/wavefn_corpus"' in text
    assert '"/app/build/statevec_benchmark_report.json"' in text
    assert "pruneBuildStaging" in text
    assert "pruneBuildStaging(" in text or "pruneBuildStaging (" in text
    assert "filepath.Join(\"/app\", \"wavefn_corpus\")" not in text
    assert "filepath.Join(\"/app\", \"build\"" not in text


def test_make_run_prunes_stale_build_files_and_subdirs() -> None:
    """pruneBuildStaging must leave only qwavectl and the report under /app/build."""
    stale = BUILD_DIR / "stale_noise.txt"
    nested = BUILD_DIR / "nested_dir" / "junk.bin"
    nested.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("noise", encoding="utf-8")
    nested.write_bytes(b"\x00\x01")
    _chown_model(BUILD_DIR)
    for path in BUILD_DIR.rglob("*"):
        _chown_model(path)
    _run_make("run", "prune_run.log")
    names = sorted(p.name for p in BUILD_DIR.iterdir())
    assert names == ["qwavectl", "statevec_benchmark_report.json"]
    assert not stale.exists() and not nested.exists()
    _assert_regular_build_artifacts()


def test_anti_cheat_perturb_restore(report: dict[str, Any]) -> None:
    """Perturbing a corpus fixture must change the report; restore recovers byte identity."""
    baseline = REPORT_PATH.read_bytes()
    path = CORPUS_DIR / "circ_05.json"
    clean = VERIFIER_DIR / "circ_05_clean.json"
    shutil.copy(path, clean)
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        obj["gates"] = [{"op": "X", "qubit": 0}]
        path.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
        _chown_model(path)
        REPORT_PATH.unlink(missing_ok=True)
        _run_make("run", "perturb_circ05.log")
        assert REPORT_PATH.read_bytes() != baseline
    finally:
        shutil.copy(clean, path)
        _chown_model(path)
        REPORT_PATH.unlink(missing_ok=True)
        _run_make("run", "restore_circ05.log")
        assert REPORT_PATH.read_bytes() == baseline
        _assert_app_matches_protected(IMMUTABLE_SHA256, when="after anti-cheat restore")
