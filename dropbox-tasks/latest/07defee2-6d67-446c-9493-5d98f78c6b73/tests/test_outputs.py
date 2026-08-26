"""Byte-exact verifier for the Chan (bi tu, 100-card) winning account.

Records and expected accounts are produced outside the candidate jail by an
independent Python referee.  The candidate is compiled as a static Go binary,
copied alone into a chroot, and fed one record on standard input.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ref"))

import channgen as gen  # noqa: E402
import channref as ref  # noqa: E402

CASE_COUNT = 300
SEED_BASE = 1_700_000_003
SEED_STEP = 104_729
CASES = [(SEED_BASE + index * SEED_STEP, index) for index in range(CASE_COUNT)]


@pytest.fixture(scope="session")
def tool_binary(tmp_path_factory):
    """Build the candidate statically from candidate-visible Go sources."""
    output = tmp_path_factory.mktemp("bin") / "chandeck"
    process = subprocess.run(
        ["go", "build", "-trimpath", "-o", str(output), "./cmd/chandeck"],
        cwd="/app",
        capture_output=True,
        text=True,
        env={**os.environ, "CGO_ENABLED": "0"},
        timeout=120,
        check=False,
    )
    assert process.returncode == 0, "/app failed to build:\n" + process.stderr
    return str(output)


def _run_isolated(binary: str, record: bytes, timeout: int = 30) -> bytes:
    """Run one record in a chroot that contains only the static candidate."""
    jail = tempfile.mkdtemp(prefix="chandeck_jail_")
    shutil.copy2(binary, os.path.join(jail, "tool"))
    os.chmod(os.path.join(jail, "tool"), 0o755)

    def _enter() -> None:
        os.chroot(jail)
        os.chdir("/")

    try:
        process = subprocess.run(
            ["/tool"],
            input=record,
            capture_output=True,
            env={},
            timeout=timeout,
            preexec_fn=_enter,
            check=False,
        )
    finally:
        shutil.rmtree(jail, ignore_errors=True)
    assert process.returncode == 0, process.stderr.decode("utf-8", "replace")[:500]
    assert process.stderr == b""
    return process.stdout


def _assert_record(binary: str, record: bytes) -> str:
    """Require the candidate and the reference to agree byte for byte."""
    expected = ref.trace(record).encode("ascii")
    actual = _run_isolated(binary, record)
    assert actual == expected
    return expected.decode("ascii")


@pytest.mark.parametrize("case_index", range(len(CASES)))
def test_indexed_replay(tool_binary, case_index):
    """A neutral indexed record matches the live reference byte for byte."""
    seed, schedule_index = CASES[case_index]
    record = gen.build(seed, schedule_index)
    expected = ref.trace(record).encode("ascii")
    actual = _run_isolated(tool_binary, record)
    assert actual == expected, "seed %d index %d mode %s" % (
        seed,
        schedule_index,
        gen.MODE_NAMES[gen.mode_for_index(schedule_index)],
    )


def test_defining_schedule_covers_every_branch(tool_binary):
    """One record per mode reaches every honour, fine, fault, and terminal line."""
    traces: list[str] = []
    for index in range(len(gen.MODE_NAMES)):
        record = gen.build(2_000_000_033 + index * 65_537, index)
        traces.append(_assert_record(tool_binary, record))
    corpus = "\n".join(traces)
    for token in (
        "thienu", "diau", "thong", "chi", "banthu", "tom", "leo",
        "bachdinh", "tamdo", "kinhtuchi", "thienkhai", "xuong",
    ):
        assert re.search(r"^Cuoc = .*\b%s\b" % re.escape(token), corpus, re.MULTILINE), token
    for fine in ("treo-tranh", "tra-cua", "lot-song"):
        assert "Phat = " + fine in corpus, fine
    for reason in ("malformed", "bad-hand", "bad-layout", "bad-log"):
        assert "reason:" + reason in corpus, reason
    for token in (
        "Result = uu", "Result = void", "Phat = none",
        "Wait = banthu", "Wait = thuong",
    ):
        assert token in corpus, token


def _split(record: bytes) -> list[str]:
    return record.decode("ascii").splitlines()


def _join(lines: list[str]) -> bytes:
    return ("\n".join(lines) + "\n").encode("ascii")


def test_winning_unit_must_lead_the_layout(tool_binary):
    """Moving a non-winning unit to the front is a bad-layout, not a re-sort."""
    record = gen.build(3_000_000_019, gen.MODE_NAMES.index("banthu"))
    lines = _split(record)
    uu = lines[2].split(" ")[1]
    units = lines[4][len("layout "):].split(";")
    swap = next(i for i, u in enumerate(units) if i > 0 and uu not in u.split("("))
    inside = units[swap][units[swap].index("(") + 1:-1].split(",")
    assert uu not in inside
    units[0], units[swap] = units[swap], units[0]
    lines[4] = "layout " + ";".join(units)
    trace = ref.trace(_join(lines))
    actual = _run_isolated(tool_binary, _join(lines)).decode("ascii")
    assert actual == trace
    assert "reason:bad-layout" in trace


def test_fine_settlement_is_zero_sum(tool_binary):
    """A fined hand still settles to nothing across the four seats."""
    record = gen.build(3_100_000_021, gen.MODE_NAMES.index("tra-cua"))
    trace = _assert_record(tool_binary, record)
    nets = [int(m) for m in re.findall(r"^Settle [ABCD] = (-?\d+)$", trace, re.MULTILINE)]
    assert len(nets) == 4
    assert sum(nets) == 0
    assert any(line.startswith("Phat = tra-cua:") for line in trace.splitlines())


def test_eight_reds_score_tamdo(tool_binary):
    """A hand of exactly eight red cards is scored tamdo for eight extra diem."""
    record = gen.build(3_200_000_033, gen.MODE_NAMES.index("tamdo"))
    trace = _assert_record(tool_binary, record)
    assert "Reds = 8" in trace
    cuoc = next(line for line in trace.splitlines() if line.startswith("Cuoc = "))
    assert "tamdo" in cuoc
    diem = int(next(line for line in trace.splitlines() if line.startswith("Diem = ")).split(" = ")[1])
    assert diem >= 11


def test_candidate_is_native_and_reference_is_not_shipped():
    """Candidate Go sources cannot invoke helpers or contain verifier assets."""
    forbidden = re.compile(r"os/exec|exec\.Command|syscall|plugin\.Open|StartProcess")
    for directory, _, files in os.walk("/app"):
        for name in files:
            if name.endswith(".go"):
                with open(os.path.join(directory, name), encoding="utf-8") as source:
                    assert not forbidden.search(source.read())
    assert not os.path.exists("/app/tests")
    assert not os.path.exists("/app/solution")
