import json
import os
import shutil
import subprocess
import tempfile

import pytest

INTEGRATOR = "/app/bin/integrate"
BENCH = "/app/bench/bench"
CALIBRATION_DIR = "/app/calibration"
REF_SRC = "/tests/_kinref"

# The graded workload is synthesised at grade time from this seed. The networks
# it produces exist nowhere in the agent image.
ASSAY_SEED = "8675309"
ASSAY_COUNT = "16"

# Calibration is graded EXACTLY: the twelve systems are compiled into the bench,
# so the agent can drive it and verify a byte-for-byte reproduction before it
# commits. This is where an exact recovery of the protocol is enforced.
CAL_STATE_RTOL = 1.0e-10
CAL_STATE_ATOL = 1.0e-12
CAL_TIME_RTOL = 1.0e-10

# Held-out assays are graded at the robustness a faithful reconstruction reaches
# WITHOUT reproducing C++ double-precision arithmetic bit for bit. A correct
# recovery of the protocol lands well inside these bands; a naive or generic
# integrator misses the step-count transfer and the stop verdict by a wide
# margin (see tests/_kinref for the reference and the fix calibration notes).
STATE_RTOL = 1.0e-5
STATE_ATOL = 1.0e-6
TIME_RTOL = 1.0e-6
STEP_RTOL = 0.05
STEP_ATOL = 4

REQUIRED_KEYS = {
    "network",
    "verdict",
    "stop_time",
    "accepted",
    "rejected",
    "derivative_evals",
    "final",
}


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def _close(a, b, rtol, atol):
    return abs(a - b) <= atol + rtol * abs(b)


def _step_close(got, want):
    """An integer step statistic transfers within a small relative band."""
    return abs(got - want) <= max(STEP_ATOL, STEP_RTOL * abs(want))


def _by_name(rows):
    return {r["network"]: r for r in rows}


def _converged(rows):
    return [r for r in rows if r["verdict"] == "converged"]


def _slack(n):
    """How many held-out networks a correct recovery may miss on a state or
    step-count check before the transfer is judged broken."""
    return max(1, n // 5)


@pytest.fixture(scope="session")
def workdir():
    d = tempfile.mkdtemp(prefix="halvard_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(scope="session")
def reference(workdir):
    """Compile the held-out reference and synthesise the graded assay set."""
    build = os.path.join(workdir, "ref")
    shutil.copytree(REF_SRC, build)
    r = _run(["make", "-C", build], timeout=300)
    assert r.returncode == 0, f"reference build failed:\n{r.stdout}\n{r.stderr}"

    assays = os.path.join(workdir, "assays")
    os.makedirs(assays)
    r = _run(
        [os.path.join(build, "genassays"), ASSAY_SEED, ASSAY_COUNT, assays, "assay"],
        timeout=120,
    )
    assert r.returncode == 0, f"assay synthesis failed: {r.stderr}"

    ref_out = os.path.join(workdir, "reference.jsonl")
    r = _run(
        [
            os.path.join(build, "kinref"),
            assays,
            os.path.join(build, "stage_weights.tsv"),
            ref_out,
        ],
        timeout=600,
    )
    assert r.returncode == 0, f"reference integration failed: {r.stderr}"

    rows = [json.loads(line) for line in open(ref_out) if line.strip()]
    assert len(rows) == int(ASSAY_COUNT)
    return {"assays": assays, "rows": rows, "build": build}


@pytest.fixture(scope="session")
def agent_rows(workdir, reference):
    """Run the agent's integrator on the held-out assay set."""
    assert os.path.isfile(INTEGRATOR), f"no integrator at {INTEGRATOR}"
    assert os.access(INTEGRATOR, os.X_OK), f"{INTEGRATOR} is not executable"

    out = os.path.join(workdir, "agent.jsonl")
    r = _run([INTEGRATOR, reference["assays"], out], timeout=900)
    assert r.returncode == 0, (
        f"integrator exited {r.returncode}:\n{r.stdout}\n{r.stderr}"
    )
    assert os.path.isfile(out), "integrator wrote no output file"

    rows = []
    for line in open(out):
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_integrator_is_present_and_executable():
    """The deliverable exists at the required path and is runnable."""
    assert os.path.isfile(INTEGRATOR), f"no integrator at {INTEGRATOR}"
    assert os.access(INTEGRATOR, os.X_OK), f"{INTEGRATOR} is not executable"


def test_output_schema_is_well_formed(agent_rows, reference):
    """One record per network, carrying every certified field with the right type."""
    assert len(agent_rows) == len(reference["rows"]), (
        f"expected {len(reference['rows'])} records, got {len(agent_rows)}"
    )
    for row in agent_rows:
        missing = REQUIRED_KEYS - set(row)
        assert not missing, (
            f"record {row.get('network')} is missing keys: {sorted(missing)}"
        )
        assert isinstance(row["verdict"], str)
        assert isinstance(row["accepted"], int)
        assert isinstance(row["rejected"], int)
        assert isinstance(row["derivative_evals"], int)
        assert isinstance(row["final"], dict) and row["final"]


def test_calibration_runs_reproduce_the_bench(workdir):
    """The integrator must reproduce the bench EXACTLY on the twelve calibration
    networks. The bench is present, so the agent can drive it and confirm this
    recovery before committing; it is the exact-reproduction gate for the
    protocol's structure and constants."""
    out = os.path.join(workdir, "calibration.jsonl")
    r = _run([INTEGRATOR, CALIBRATION_DIR, out], timeout=900)
    assert r.returncode == 0, f"integrator failed on the calibration suite: {r.stderr}"
    produced = _by_name([json.loads(ln) for ln in open(out) if ln.strip()])

    listing = _run([BENCH, "list"], timeout=60)
    assert listing.returncode == 0
    names = [
        line.split("\t")[0] for line in listing.stdout.splitlines() if line.strip()
    ]
    assert len(names) == 12

    for name in names:
        b = _run([BENCH, "run", "--system", name], timeout=300)
        assert b.returncode == 0, f"bench failed on {name}"
        certified = {}
        final = {}
        for line in b.stdout.splitlines():
            parts = line.split("\t")
            if parts[0] == "final":
                final[parts[1]] = float(parts[2])
            elif len(parts) >= 2:
                certified[parts[0]] = parts[1]

        assert name in produced, f"no record produced for calibration system {name}"
        got = produced[name]
        assert got["verdict"] == certified["verdict"], f"{name}: verdict"
        assert got["accepted"] == int(certified["accepted"]), f"{name}: accepted steps"
        assert got["rejected"] == int(certified["rejected"]), f"{name}: rejected steps"
        assert got["derivative_evals"] == int(certified["derivative_evals"]), (
            f"{name}: derivative evaluations"
        )
        assert _close(
            got["stop_time"],
            float(certified["stop_time"]),
            CAL_TIME_RTOL,
            CAL_STATE_ATOL,
        ), f"{name}: stop time"
        for species, value in final.items():
            assert _close(
                got["final"][species], value, CAL_STATE_RTOL, CAL_STATE_ATOL
            ), f"{name}: concentration of {species}"


def test_certified_final_state_on_heldout_assays(agent_rows, reference):
    """Concentrations at the horizon must match what the bench certifies for the
    networks that reach it. Graded at physical accuracy, not bit reproduction."""
    produced = _by_name(agent_rows)
    conv = _converged(reference["rows"])
    assert conv, "the held-out set must contain networks that reach the horizon"
    misses = []
    for want in conv:
        name = want["network"]
        assert name in produced, f"no record for held-out network {name}"
        got = produced[name]
        ok = all(
            species in got["final"]
            and _close(got["final"][species], value, STATE_RTOL, STATE_ATOL)
            for species, value in want["final"].items()
        )
        if not ok:
            misses.append(name)
    assert len(misses) <= _slack(len(conv)), (
        f"final concentrations diverge from the bench on {misses}"
    )


def test_heldout_step_statistics_match_certified(agent_rows, reference):
    """Accepted, rejected and derivative-evaluation counts must transfer for the
    networks that reach the horizon. A faithful reconstruction lands inside a
    small relative band; a naive or generic integrator is off by tens of
    percent."""
    produced = _by_name(agent_rows)
    conv = _converged(reference["rows"])
    assert conv, "the held-out set must contain networks that reach the horizon"
    misses = []
    for want in conv:
        name = want["network"]
        assert name in produced, f"no record for held-out network {name}"
        got = produced[name]
        ok = (
            _step_close(got["accepted"], want["accepted"])
            and _step_close(got["derivative_evals"], want["derivative_evals"])
            and abs(got["rejected"] - want["rejected"])
            <= max(STEP_ATOL, want["rejected"])
        )
        if not ok:
            misses.append(
                f"{name}: got acc={got['accepted']} rej={got['rejected']} "
                f"dev={got['derivative_evals']}, certified acc={want['accepted']} "
                f"rej={want['rejected']} dev={want['derivative_evals']}"
            )
    assert len(misses) <= _slack(len(conv)), (
        "step statistics diverge from the certified protocol:\n" + "\n".join(misses)
    )


def test_heldout_stop_verdicts_and_stop_times(agent_rows, reference):
    """The verdict must match the bench on every network, and networks that reach
    the horizon must report the time they reached it. The verdict separates a
    faithful protocol from a generic solver, which converges the stiff networks
    the protocol gives up on."""
    produced = _by_name(agent_rows)
    verdict_misses = []
    for want in reference["rows"]:
        name = want["network"]
        assert name in produced, f"no record for held-out network {name}"
        got = produced[name]
        if got["verdict"] != want["verdict"]:
            verdict_misses.append(
                f"{name}: verdict {got['verdict']!r}, bench certifies {want['verdict']!r}"
            )
    assert len(verdict_misses) <= 1, "verdicts diverge:\n" + "\n".join(verdict_misses)

    for want in _converged(reference["rows"]):
        got = produced[want["network"]]
        assert _close(got["stop_time"], want["stop_time"], TIME_RTOL, STATE_ATOL), (
            f"{want['network']}: stop time {got['stop_time']!r}, "
            f"the bench certifies {want['stop_time']!r}"
        )


def test_no_certified_result_where_the_protocol_stops(agent_rows, reference):
    """An integration the protocol halts must not be reported as reaching the
    horizon."""
    stopped = [r for r in reference["rows"] if r["verdict"] != "converged"]
    assert stopped, "the held-out set must exercise the protocol's stop branch"
    produced = _by_name(agent_rows)
    wrong = []
    for want in stopped:
        name = want["network"]
        got = produced[name]
        if got["verdict"] == "converged":
            wrong.append(name)
    assert len(wrong) <= _slack(len(stopped)), (
        f"networks the protocol stops were reported as reaching the horizon: {wrong}"
    )


def test_total_concentration_is_conserved(agent_rows, reference):
    """Every network conserves total concentration; the reported state must too,
    for the networks that reach the horizon."""
    produced = _by_name(agent_rows)
    conv = _converged(reference["rows"])
    misses = []
    for want in conv:
        name = want["network"]
        got = produced[name]
        want_total = sum(want["final"].values())
        got_total = sum(got["final"].values())
        if not _close(got_total, want_total, 1.0e-6, 1.0e-8):
            misses.append(f"{name}: total {got_total!r} vs certified {want_total!r}")
    assert len(misses) <= _slack(len(conv)), (
        "total concentration diverges:\n" + "\n".join(misses)
    )


SECOND_SEED = "31415926"
SECOND_COUNT = "8"


@pytest.fixture(scope="session")
def second_workload(workdir, reference):
    """A second held-out batch, from a different private seed."""
    assays = os.path.join(workdir, "assays2")
    os.makedirs(assays)
    r = _run(
        [
            os.path.join(reference["build"], "genassays"),
            SECOND_SEED,
            SECOND_COUNT,
            assays,
            "batch",
        ],
        timeout=120,
    )
    assert r.returncode == 0, f"second assay synthesis failed: {r.stderr}"

    ref_out = os.path.join(workdir, "reference2.jsonl")
    r = _run(
        [
            os.path.join(reference["build"], "kinref"),
            assays,
            os.path.join(reference["build"], "stage_weights.tsv"),
            ref_out,
        ],
        timeout=600,
    )
    assert r.returncode == 0, f"second reference integration failed: {r.stderr}"
    want = [json.loads(line) for line in open(ref_out) if line.strip()]

    out = os.path.join(workdir, "agent2.jsonl")
    r = _run([INTEGRATOR, assays, out], timeout=900)
    assert r.returncode == 0, f"integrator failed on the second workload: {r.stderr}"
    got = [json.loads(line) for line in open(out) if line.strip()]
    return want, got


def test_integrator_generalises_to_a_second_workload(second_workload):
    """The protocol must transfer to networks drawn from a different seed: the
    right verdict on every network, and the certified concentrations and step
    counts on the ones that reach the horizon."""
    want_rows, got_rows = second_workload
    produced = _by_name(got_rows)

    verdict_misses = []
    for want in want_rows:
        name = want["network"]
        assert name in produced, f"no record for held-out network {name}"
        if produced[name]["verdict"] != want["verdict"]:
            verdict_misses.append(name)
    assert len(verdict_misses) <= 1, (
        f"verdicts diverge on the second workload: {verdict_misses}"
    )

    conv = _converged(want_rows)
    assert conv, "the second workload must contain networks that reach the horizon"
    misses = []
    for want in conv:
        got = produced[want["network"]]
        step_ok = _step_close(got["accepted"], want["accepted"]) and _step_close(
            got["derivative_evals"], want["derivative_evals"]
        )
        state_ok = all(
            species in got["final"]
            and _close(got["final"][species], value, STATE_RTOL, STATE_ATOL)
            for species, value in want["final"].items()
        )
        if not (step_ok and state_ok):
            misses.append(want["network"])
    assert len(misses) <= _slack(len(conv)), (
        f"the recovered protocol does not transfer to the second workload: {misses}"
    )
