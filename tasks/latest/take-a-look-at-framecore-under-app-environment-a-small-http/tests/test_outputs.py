from __future__ import annotations

import random
import re
import subprocess
import uuid
from pathlib import Path

import pytest

ENV = Path("/app/environment")
BIN = "/tmp/framecore-bin"

HEADER_OVERHEAD = 32

INT_FIELDS = {
    "memory",
    "header_count",
    "max_memory",
    "max_header_count",
    "id",
    "headers_length",
    "name_len",
    "value_len",
    "charge",
    "local_length",
    "count",
}


def _parse_output(stdout: str) -> list[dict]:
    events = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        d: dict = {"tag": parts[0]}
        for kv in parts[1:]:
            key, _, value = kv.partition("=")
            d[key] = int(value) if key in INT_FIELDS else value
        events.append(d)
    return events


def _token(value: str) -> str:
    return "-" if value == "" else value


def _serialize_ops(ops: list[tuple]) -> str:
    lines = []
    for op in ops:
        kind = op[0]
        if kind == "session":
            lines.append(f"session {op[1]} {op[2]}")
        elif kind == "stream":
            lines.append(f"stream {op[1]}")
        elif kind == "start_headers":
            lines.append(f"start_headers {op[1]} {op[2]}")
        elif kind == "add_header":
            lines.append(f"add_header {op[1]} {_token(op[2])} {_token(op[3])}")
        elif kind == "flush":
            lines.append(f"flush {op[1]}")
        elif kind == "destroy":
            lines.append(f"destroy {op[1]}")
        else:
            raise ValueError(f"unknown op kind {kind}")
    return "\n".join(lines) + "\n"


def _parse_script_text(text: str) -> list[tuple]:
    ops = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split()
        cmd = parts[0]
        if cmd == "session":
            ops.append(("session", int(parts[1]), int(parts[2])))
        elif cmd == "stream":
            ops.append(("stream", int(parts[1])))
        elif cmd == "start_headers":
            ops.append(("start_headers", int(parts[1]), parts[2]))
        elif cmd == "add_header":
            name = "" if parts[2] == "-" else parts[2]
            value = "" if parts[3] == "-" else parts[3]
            ops.append(("add_header", int(parts[1]), name, value))
        elif cmd == "flush":
            ops.append(("flush", int(parts[1])))
        elif cmd == "destroy":
            ops.append(("destroy", int(parts[1])))
        else:
            raise ValueError(f"unknown script command {cmd!r}")
    return ops


_LEGAL_PHASE_TRANSITIONS = {
    "informational": {"informational", "headers"},
    "headers": {"trailers"},
    "trailers": set(),
}


def _is_legal_phase_transition(from_category: str, to_category: str) -> bool:
    """Mirror Stream's IsLegalPhaseTransition: informational may repeat or
    advance to headers, headers may only advance to trailers, and trailers
    is terminal."""
    return to_category in _LEGAL_PHASE_TRANSITIONS[from_category]


class _OracleStream:
    def __init__(self):
        self.category = "headers"
        self.phase_started = False
        self.local_length = 0
        self.headers: list[tuple[str, str]] = []


class _OracleSession:
    def __init__(self, max_bytes: int, max_headers: int):
        self.max_bytes = max_bytes
        self.max_headers = max_headers
        self.memory = 0
        self.header_count = 0
        self.streams: dict[int, _OracleStream] = {}


def oracle_events(ops: list[tuple]) -> list[dict]:
    """Independently recompute the expected tagged event stream for ops using
    the correct charge/refund accounting contract, never reading the binary."""
    session: _OracleSession | None = None
    events: list[dict] = []
    for op in ops:
        kind = op[0]
        if kind == "session":
            _, max_bytes, max_headers = op
            session = _OracleSession(max_bytes, max_headers)
            events.append(
                {
                    "tag": "SESSION",
                    "memory": 0,
                    "header_count": 0,
                    "max_memory": max_bytes,
                    "max_header_count": max_headers,
                }
            )
        elif kind == "stream":
            _, sid = op
            session.streams[sid] = _OracleStream()
            events.append(
                {
                    "tag": "STREAM",
                    "id": sid,
                    "headers_length": 0,
                    "header_count": 0,
                    "category": "headers",
                }
            )
        elif kind == "start_headers":
            _, sid, category = op
            s = session.streams[sid]
            if s.phase_started and not _is_legal_phase_transition(s.category, category):
                status = "rejected"
            else:
                status = "ok"
                if s.local_length > 0:
                    session.memory -= s.local_length
                    session.header_count -= len(s.headers)
                s.local_length = 0
                s.headers = []
                s.phase_started = True
                s.category = category
            events.append(
                {
                    "tag": "START",
                    "id": sid,
                    "status": status,
                    "category": s.category,
                    "memory": session.memory,
                    "header_count": session.header_count,
                }
            )
        elif kind == "add_header":
            _, sid, name, value = op
            s = session.streams[sid]
            before = session.memory
            if name == "":
                status = "ignored"
            else:
                charge = len(name) + len(value) + HEADER_OVERHEAD
                fits_bytes = session.memory + charge <= session.max_bytes
                fits_count = session.header_count + 1 <= session.max_headers
                if fits_bytes and fits_count:
                    session.memory += charge
                    session.header_count += 1
                    s.local_length += charge
                    s.headers.append((name, value))
                    status = "ok"
                else:
                    status = "rejected"
            events.append(
                {
                    "tag": "ADD",
                    "id": sid,
                    "status": status,
                    "name_len": len(name),
                    "value_len": len(value),
                    "charge": session.memory - before,
                    "memory": session.memory,
                    "header_count": session.header_count,
                    "local_length": s.local_length,
                }
            )
        elif kind == "flush":
            _, sid = op
            s = session.streams[sid]
            count = len(s.headers)
            session.memory -= s.local_length
            session.header_count -= count
            s.local_length = 0
            s.headers = []
            events.append(
                {
                    "tag": "FLUSH",
                    "id": sid,
                    "count": count,
                    "memory": session.memory,
                    "header_count": session.header_count,
                    "local_length": 0,
                }
            )
        elif kind == "destroy":
            _, sid = op
            s = session.streams.pop(sid)
            if s.local_length > 0:
                session.memory -= s.local_length
                session.header_count -= len(s.headers)
            events.append(
                {
                    "tag": "DESTROY",
                    "id": sid,
                    "destroyed": "true",
                    "memory": session.memory,
                    "header_count": session.header_count,
                }
            )
        else:
            raise ValueError(f"unknown op kind {kind}")
    events.append(
        {
            "tag": "FINAL",
            "memory": session.memory,
            "header_count": session.header_count,
            "max_memory": session.max_bytes,
            "max_header_count": session.max_headers,
        }
    )
    return events


def assert_no_crash(result: subprocess.CompletedProcess) -> None:
    assert result.returncode >= 0, (
        f"framecore terminated by signal {-result.returncode}, expected a clean exit\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def run_script_file(
    binary: str, path: Path, timeout: int = 60
) -> subprocess.CompletedProcess:
    result = subprocess.run(
        [binary, "script", str(path)],
        cwd=str(ENV),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    assert_no_crash(result)
    return result


def run_ops(
    binary: str, ops: list[tuple], tmp_path: Path, timeout: int = 120
) -> subprocess.CompletedProcess:
    script_path = tmp_path / f"script-{uuid.uuid4().hex[:8]}.txt"
    script_path.write_text(_serialize_ops(ops))
    return run_script_file(binary, script_path, timeout=timeout)


def assert_matches_oracle(
    result: subprocess.CompletedProcess, ops: list[tuple]
) -> list[dict]:
    expected = oracle_events(ops)
    actual = _parse_output(result.stdout)
    assert actual == expected, (
        f"framecore's printed accounting state diverged from the independently "
        f"recomputed expected state.\nexpected: {expected}\nactual:   {actual}\n"
        f"stderr:\n{result.stderr}"
    )
    return actual


@pytest.fixture(scope="session")
def binary():
    clean = subprocess.run(
        ["make", "clean"], cwd=str(ENV), text=True, capture_output=True, timeout=60
    )
    assert clean.returncode == 0, f"make clean failed:\n{clean.stdout}\n{clean.stderr}"
    build = subprocess.run(
        ["make"], cwd=str(ENV), text=True, capture_output=True, timeout=300
    )
    assert build.returncode == 0, f"make failed:\n{build.stdout}\n{build.stderr}"
    assert (ENV / "framecore").exists(), "framecore binary was not produced by make"
    return str(ENV / "framecore")


_HARNESS_SRC = r"""
#include <cstdio>
#include <cstdlib>
#include <string>

#include "framecore/transport/session.h"
#include "framecore/transport/stream.h"

using namespace framecore;

namespace {

const char* StatusName(const Status& st) {
  if (st.ok()) return "ok";
  if (st.ignored()) return "ignored";
  return "rejected";
}

int ScenarioEmptyNameNotCharged() {
  Session session(4096, 100);
  Stream* s = session.CreateStream(1);
  Status st = s->AddHeader("", "somevalue");
  std::printf("status=%s memory=%zu header_count=%zu local_length=%zu\n",
              StatusName(st), session.current_session_memory(),
              session.current_header_count(), s->current_headers_length());
  return 0;
}

int ScenarioFlushRefunds() {
  Session session(4096, 100);
  Stream* s = session.CreateStream(1);
  s->AddHeader("name", "value");
  size_t charged_memory = session.current_session_memory();
  size_t charged_count = session.current_header_count();
  s->FlushHeaders();
  std::printf(
      "charged_memory=%zu charged_count=%zu memory=%zu "
      "header_count=%zu local_length=%zu\n",
      charged_memory, charged_count, session.current_session_memory(),
      session.current_header_count(), s->current_headers_length());
  return 0;
}

int ScenarioDestroyRefunds() {
  Session session(4096, 100);
  session.CreateStream(1);
  session.FindStream(1)->AddHeader("name", "value");
  size_t charged_memory = session.current_session_memory();
  session.DestroyStream(1);
  std::printf("charged_memory=%zu memory=%zu header_count=%zu\n", charged_memory,
              session.current_session_memory(), session.current_header_count());
  return 0;
}

int ScenarioStartHeadersRefunds() {
  Session session(4096, 100);
  Stream* s = session.CreateStream(1);
  s->AddHeader("name", "value");
  size_t charged_memory = session.current_session_memory();
  s->StartHeaders(HeaderCategory::kTrailers);
  std::printf("charged_memory=%zu memory=%zu header_count=%zu local_length=%zu\n",
              charged_memory, session.current_session_memory(),
              session.current_header_count(), s->current_headers_length());
  return 0;
}

int ScenarioHeaderCountCapEnforced() {
  Session session(1000000, 2);
  Stream* s = session.CreateStream(1);
  Status st1 = s->AddHeader("a", "1");
  Status st2 = s->AddHeader("b", "2");
  Status st3 = s->AddHeader("c", "3");
  std::printf("status1=%s status2=%s status3=%s header_count=%zu\n", StatusName(st1),
              StatusName(st2), StatusName(st3), session.current_header_count());
  return 0;
}

const char* CategoryName(HeaderCategory category) {
  switch (category) {
    case HeaderCategory::kHeaders:
      return "headers";
    case HeaderCategory::kInformational:
      return "informational";
    case HeaderCategory::kTrailers:
      return "trailers";
  }
  return "unknown";
}

int ScenarioPhaseRejectsInformationalAfterHeaders() {
  Session session(4096, 100);
  Stream* s = session.CreateStream(1);
  Status st1 = s->StartHeaders(HeaderCategory::kHeaders);
  Status st2 = s->StartHeaders(HeaderCategory::kInformational);
  std::printf("status1=%s status2=%s category=%s\n", StatusName(st1), StatusName(st2),
              CategoryName(s->category()));
  return 0;
}

int ScenarioPhaseRejectsAnythingAfterTrailers() {
  Session session(4096, 100);
  Stream* s = session.CreateStream(1);
  Status st1 = s->StartHeaders(HeaderCategory::kTrailers);
  Status st2 = s->StartHeaders(HeaderCategory::kHeaders);
  std::printf("status1=%s status2=%s category=%s\n", StatusName(st1), StatusName(st2),
              CategoryName(s->category()));
  return 0;
}

int ScenarioPhaseAllowsInformationalThenHeadersThenTrailers() {
  Session session(4096, 100);
  Stream* s = session.CreateStream(1);
  Status st1 = s->StartHeaders(HeaderCategory::kInformational);
  Status st2 = s->StartHeaders(HeaderCategory::kHeaders);
  Status st3 = s->StartHeaders(HeaderCategory::kTrailers);
  std::printf("status1=%s status2=%s status3=%s category=%s\n", StatusName(st1),
              StatusName(st2), StatusName(st3), CategoryName(s->category()));
  return 0;
}

}  // namespace

int main(int argc, char** argv) {
  if (argc != 2) {
    std::fprintf(stderr, "behavior_harness: expected exactly one scenario name\n");
    return 2;
  }
  const std::string scenario = argv[1];
  if (scenario == "empty_name_not_charged") return ScenarioEmptyNameNotCharged();
  if (scenario == "flush_refunds") return ScenarioFlushRefunds();
  if (scenario == "destroy_refunds") return ScenarioDestroyRefunds();
  if (scenario == "start_headers_refunds") return ScenarioStartHeadersRefunds();
  if (scenario == "header_count_cap_enforced") return ScenarioHeaderCountCapEnforced();
  if (scenario == "phase_rejects_informational_after_headers") {
    return ScenarioPhaseRejectsInformationalAfterHeaders();
  }
  if (scenario == "phase_rejects_anything_after_trailers") {
    return ScenarioPhaseRejectsAnythingAfterTrailers();
  }
  if (scenario == "phase_allows_informational_then_headers_then_trailers") {
    return ScenarioPhaseAllowsInformationalThenHeadersThenTrailers();
  }
  std::fprintf(stderr, "behavior_harness: unknown scenario %s\n", scenario.c_str());
  return 2;
}
"""


@pytest.fixture(scope="session")
def behavior_harness(binary, tmp_path_factory):
    """Compile a verifier-owned C++ program that links directly against the
    agent's compiled Session and Stream and drives each through its public
    API only, so any internally equivalent implementation (shared helpers,
    differently named locals, and so on) is exercised identically."""
    work_dir = tmp_path_factory.mktemp("behavior_harness")
    harness_src = work_dir / "harness.cc"
    harness_src.write_text(_HARNESS_SRC)
    objects = sorted(str(p) for p in ENV.glob("src/**/*.o"))
    assert objects, "no compiled object files found; the binary fixture must run first"
    harness_bin = work_dir / "harness"
    compile_cmd = [
        "g++",
        "-std=c++17",
        "-O0",
        "-g",
        f"-I{ENV / 'include'}",
        str(harness_src),
        *objects,
        "-o",
        str(harness_bin),
    ]
    result = subprocess.run(compile_cmd, text=True, capture_output=True, timeout=120)
    assert result.returncode == 0, (
        f"behavior harness failed to compile:\n{result.stderr}"
    )
    return str(harness_bin)


def _run_harness_scenario(behavior_harness: str, scenario: str) -> dict:
    result = subprocess.run(
        [behavior_harness, scenario],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"{scenario}: harness exited {result.returncode}\n{result.stderr}"
    )
    fields: dict = {}
    for kv in result.stdout.strip().split():
        key, _, value = kv.partition("=")
        fields[key] = int(value) if value.lstrip("-").isdigit() else value
    return fields


def test_binary_builds_and_prints_usage(binary):
    """A bare invocation with no subcommand must print usage and exit 2."""
    r = subprocess.run([binary], text=True, capture_output=True, timeout=10)
    assert r.returncode == 2, (
        f"expected exit 2 with no args, got {r.returncode}\n{r.stderr}"
    )
    assert "usage" in r.stderr.lower(), r.stderr


def test_config_check_reports_positive_limits(binary):
    """config-check must report every resource limit as a positive integer."""
    r = subprocess.run(
        [binary, "config-check"], text=True, capture_output=True, timeout=10
    )
    assert r.returncode == 0, f"config-check failed:\n{r.stderr}"
    values = dict(re.findall(r"(config\.\w+)=(\d+)", r.stdout))
    expected_keys = {
        "config.max_session_memory",
        "config.max_header_count",
        "config.max_concurrent_streams",
        "config.initial_window_size",
        "config.max_frame_size",
    }
    assert expected_keys.issubset(values.keys()), r.stdout
    for key in expected_keys:
        assert int(values[key]) > 0, f"{key} must be positive, got {values[key]}"


@pytest.mark.parametrize(
    "capture_name,expected_type",
    [
        ("ping.bin", "ping"),
        ("window_update.bin", "window_update"),
        ("headers.bin", "headers"),
    ],
)
def test_replay_accepts_valid_wire_captures(binary, capture_name, expected_type):
    """Every committed wire capture must replay cleanly as exactly one frame."""
    path = ENV / "testdata" / "wire" / "valid" / capture_name
    r = subprocess.run(
        [binary, "replay", str(path)], text=True, capture_output=True, timeout=10
    )
    assert_no_crash(r)
    assert r.returncode == 0, (
        f"replay of {capture_name} failed:\n{r.stdout}\n{r.stderr}"
    )
    assert f"type={expected_type}" in r.stdout, r.stdout
    assert "REPLAY frames=1" in r.stdout, r.stdout


def _valid_script_paths() -> list[Path]:
    return sorted((ENV / "testdata" / "scripts" / "valid").glob("*.script"))


def _boundary_script_paths() -> list[Path]:
    return sorted((ENV / "testdata" / "scripts" / "boundary").glob("*.script"))


@pytest.mark.parametrize("script_path", _valid_script_paths(), ids=lambda p: p.stem)
def test_valid_script_matches_oracle(binary, script_path):
    """Every committed valid-traffic script's printed state must match the
    independently recomputed expected accounting exactly."""
    ops = _parse_script_text(script_path.read_text())
    result = run_script_file(binary, script_path)
    assert result.returncode == 0, f"{script_path.name} was rejected:\n{result.stderr}"
    assert_matches_oracle(result, ops)


@pytest.mark.parametrize("script_path", _boundary_script_paths(), ids=lambda p: p.stem)
def test_boundary_script_matches_oracle(binary, script_path):
    """Every committed boundary script (at-limit accepts, over-limit rejects,
    zero-length-value headers, clean empty teardown) must match the oracle."""
    ops = _parse_script_text(script_path.read_text())
    result = run_script_file(binary, script_path)
    assert result.returncode == 0, (
        f"{script_path.name} exited nonzero:\n{result.stderr}"
    )
    assert_matches_oracle(result, ops)


def test_bug_empty_name_header_is_ignored_not_charged(binary, tmp_path):
    """A header with an empty name must be ignored: no charge, not stored."""
    ops = [
        ("session", 65536, 500),
        ("stream", 1),
        ("add_header", 1, "", "some-value"),
        ("flush", 1),
    ]
    result = run_ops(binary, ops, tmp_path)
    assert result.returncode == 0
    events = assert_matches_oracle(result, ops)
    add_event = [e for e in events if e["tag"] == "ADD"][0]
    assert add_event["status"] == "ignored", events
    assert add_event["charge"] == 0, events
    flush_event = [e for e in events if e["tag"] == "FLUSH"][0]
    assert flush_event["count"] == 0, events


def test_bug_flush_refunds_session_budget(binary, tmp_path):
    """Flushing a header block must return its exact charge to the session."""
    ops = [
        ("session", 65536, 500),
        ("stream", 1),
        ("add_header", 1, "content-type", "application/json"),
        ("add_header", 1, "x-request-id", "abcd1234"),
        ("flush", 1),
    ]
    result = run_ops(binary, ops, tmp_path)
    assert result.returncode == 0
    events = assert_matches_oracle(result, ops)
    flush_event = [e for e in events if e["tag"] == "FLUSH"][0]
    assert flush_event["memory"] == 0, events
    assert flush_event["header_count"] == 0, events
    assert flush_event["local_length"] == 0, events


def test_bug_destroy_mid_block_refunds_outstanding_charge(binary, tmp_path):
    """Destroying a stream with a partially charged, never-flushed block must
    release that outstanding charge back to the session."""
    ops = [
        ("session", 65536, 500),
        ("stream", 1),
        ("add_header", 1, "x-partial", "not-yet-flushed"),
        ("destroy", 1),
    ]
    result = run_ops(binary, ops, tmp_path)
    assert result.returncode == 0
    events = assert_matches_oracle(result, ops)
    destroy_event = [e for e in events if e["tag"] == "DESTROY"][0]
    assert destroy_event["memory"] == 0, events
    assert destroy_event["header_count"] == 0, events


def test_no_double_refund_after_clean_flush_then_destroy(binary, tmp_path):
    """A stream flushed cleanly and then destroyed must refund nothing a
    second time; the unsigned session counters must not underflow."""
    ops = [
        ("session", 65536, 500),
        ("stream", 1),
        ("add_header", 1, "x-once", "charged-once"),
        ("flush", 1),
        ("destroy", 1),
    ]
    result = run_ops(binary, ops, tmp_path)
    assert result.returncode == 0
    events = assert_matches_oracle(result, ops)
    destroy_event = [e for e in events if e["tag"] == "DESTROY"][0]
    assert destroy_event["memory"] == 0, events
    assert destroy_event["memory"] <= 65536, events


def test_bug_start_headers_phase_restart_refunds_previous_phase(binary, tmp_path):
    """Starting a second header phase on a live stream must refund the first
    phase's outstanding charge before local state resets for the new phase."""
    ops = [
        ("session", 65536, 500),
        ("stream", 1),
        ("add_header", 1, "x-first-phase", "value-one"),
        ("start_headers", 1, "trailers"),
        ("add_header", 1, "x-second-phase", "value-two"),
        ("flush", 1),
    ]
    result = run_ops(binary, ops, tmp_path)
    assert result.returncode == 0
    events = assert_matches_oracle(result, ops)
    start_event = [e for e in events if e["tag"] == "START"][0]
    assert start_event["memory"] == 0, events
    assert start_event["header_count"] == 0, events


def test_bug_repeated_phase_restarts_do_not_leak_across_many_cycles(binary, tmp_path):
    """Many phase restarts on one never-flushed stream must never accumulate
    more than the single most recent phase's charge."""
    ops = [("session", 1_000_000, 5000), ("stream", 1)]
    for i in range(60):
        ops.append(("start_headers", 1, "informational"))
        ops.append(("add_header", 1, f"x-cycle-{i}", f"value-{i}"))
    result = run_ops(binary, ops, tmp_path)
    assert result.returncode == 0
    events = assert_matches_oracle(result, ops)
    last_add = [e for e in events if e["tag"] == "ADD"][-1]
    assert last_add["memory"] == last_add["charge"], events


def test_bug_header_count_cap_enforced_independent_of_byte_cap(binary, tmp_path):
    """A header-count cap must reject once exceeded even though the byte
    budget has ample headroom left, and the exact-at-cap count must pass."""
    ops = [("session", 10_000_000, 5), ("stream", 1)]
    for i in range(5):
        ops.append(("add_header", 1, f"h{i}", "v"))
    ops.append(("add_header", 1, "h5", "v"))
    result = run_ops(binary, ops, tmp_path)
    assert result.returncode == 0
    events = assert_matches_oracle(result, ops)
    adds = [e for e in events if e["tag"] == "ADD"]
    assert all(e["status"] == "ok" for e in adds[:5]), events
    assert adds[5]["status"] == "rejected", events
    assert adds[5]["header_count"] == 5, events


def test_composition_flush_then_new_phase_then_destroy_no_double_refund(
    binary, tmp_path
):
    """Flush-refund and destroy-refund must not double-count each other's
    territory when a stream is flushed once, restarts, and is then destroyed
    mid second phase."""
    ops = [
        ("session", 65536, 500),
        ("stream", 1),
        ("add_header", 1, "x-phase-one-a", "aaa"),
        ("add_header", 1, "x-phase-one-b", "bbb"),
        ("flush", 1),
        ("start_headers", 1, "trailers"),
        ("add_header", 1, "x-phase-two", "ccc"),
        ("destroy", 1),
    ]
    result = run_ops(binary, ops, tmp_path)
    assert result.returncode == 0
    events = assert_matches_oracle(result, ops)
    destroy_event = [e for e in events if e["tag"] == "DESTROY"][0]
    assert destroy_event["memory"] == 0, events
    assert destroy_event["header_count"] == 0, events


def test_dos_scale_many_streams_many_phases_matches_oracle_and_bounded(
    binary, tmp_path
):
    """A large, freshly generated multi-stream, multi-phase workload must
    match the independent oracle exactly and settle back to zero once every
    stream is resolved, defeating both a leak and a raised-cap non-fix."""
    rng = random.Random()
    stream_count = rng.randint(150, 250)
    ops: list[tuple] = [("session", 10_000_000, 500_000)]
    stream_ids = [sid * 2 + 1 for sid in range(stream_count)]
    for sid in stream_ids:
        ops.append(("stream", sid))
        phase_count = rng.randint(1, 3)
        for phase in range(phase_count):
            if phase > 0:
                category = rng.choice(["headers", "informational", "trailers"])
                ops.append(("start_headers", sid, category))
            header_count = rng.randint(1, 5)
            for h in range(header_count):
                ops.append(
                    (
                        "add_header",
                        sid,
                        f"x-s{sid}-p{phase}-h{h}",
                        uuid.uuid4().hex[:12],
                    )
                )
        if rng.random() < 0.5:
            ops.append(("flush", sid))
        ops.append(("destroy", sid))

    result = run_ops(binary, ops, tmp_path, timeout=180)
    assert result.returncode == 0
    events = assert_matches_oracle(result, ops)
    final_event = [e for e in events if e["tag"] == "FINAL"][0]
    assert final_event["memory"] == 0, (
        "budget leaked across a large multi-phase workload"
    )
    assert final_event["header_count"] == 0, (
        "header count leaked across a large multi-phase workload"
    )


def test_generated_fresh_empty_name_flood_rejected_cheaply(binary, tmp_path):
    """A freshly sized flood of empty-name headers, regenerated every run,
    must all be ignored with zero cumulative charge to the session."""
    rng = random.Random()
    flood_size = rng.randint(500, 900)
    ops: list[tuple] = [("session", 4096, 100_000), ("stream", 1)]
    for _ in range(flood_size):
        ops.append(("add_header", 1, "", uuid.uuid4().hex[:8]))
    ops.append(("flush", 1))
    result = run_ops(binary, ops, tmp_path, timeout=120)
    assert result.returncode == 0
    events = _parse_output(result.stdout)
    add_events = [e for e in events if e["tag"] == "ADD"]
    assert len(add_events) == flood_size, len(add_events)
    non_ignored = [e for e in add_events if e["status"] != "ignored"]
    assert not non_ignored, non_ignored[:5]
    final_event = [e for e in events if e["tag"] == "FINAL"][0]
    assert final_event["memory"] == 0, final_event
    assert final_event["header_count"] == 0, final_event


def test_script_runner_rejects_malformed_script_cleanly(binary, tmp_path):
    """An unrecognized script command must exit non-zero with a script_runner
    prefixed message on stderr, never a crash."""
    script_path = tmp_path / "malformed.txt"
    script_path.write_text("session 65536 500\nnot_a_real_command 1 2 3\n")
    result = run_script_file(binary, script_path)
    assert result.returncode != 0
    assert "script_runner" in result.stderr.lower(), result.stderr


def test_stream_behavior_add_header_ignores_empty_name_before_charging(
    behavior_harness,
):
    """An empty-name header, added directly through the public API, must be
    reported ignored and must not be charged to the session's byte or
    header-count budget, regardless of how the fix is internally structured."""
    fields = _run_harness_scenario(behavior_harness, "empty_name_not_charged")
    assert fields["status"] == "ignored", fields
    assert fields["memory"] == 0, fields
    assert fields["header_count"] == 0, fields
    assert fields["local_length"] == 0, fields


def test_stream_behavior_flush_headers_refunds_session(behavior_harness):
    """Flushing a header block through the public API must return its exact
    charge to the session and leave the stream's own accumulator at zero."""
    fields = _run_harness_scenario(behavior_harness, "flush_refunds")
    assert fields["charged_memory"] > 0, fields
    assert fields["charged_count"] > 0, fields
    assert fields["memory"] == 0, fields
    assert fields["header_count"] == 0, fields
    assert fields["local_length"] == 0, fields


def test_stream_behavior_destructor_refunds_outstanding_charge(behavior_harness):
    """Destroying a stream that still holds an uncommitted header block must
    return that block's charge to the session rather than leaking it."""
    fields = _run_harness_scenario(behavior_harness, "destroy_refunds")
    assert fields["charged_memory"] > 0, fields
    assert fields["memory"] == 0, fields
    assert fields["header_count"] == 0, fields


def test_stream_behavior_start_headers_refunds_previous_phase(behavior_harness):
    """Starting a new header phase on a still-live stream must refund the
    outgoing phase's charge to the session, not just reset the stream's own
    local accumulator."""
    fields = _run_harness_scenario(behavior_harness, "start_headers_refunds")
    assert fields["charged_memory"] > 0, fields
    assert fields["memory"] == 0, fields
    assert fields["header_count"] == 0, fields
    assert fields["local_length"] == 0, fields


def test_session_behavior_header_count_cap_is_enforced(behavior_harness):
    """A session configured with a small header-count cap must reject a
    header once that count is exceeded, independent of how much byte budget
    remains, when driven directly through the public API."""
    fields = _run_harness_scenario(behavior_harness, "header_count_cap_enforced")
    assert fields["status1"] == "ok", fields
    assert fields["status2"] == "ok", fields
    assert fields["status3"] == "rejected", fields
    assert fields["header_count"] == 2, fields


def test_stream_behavior_phase_rejects_informational_after_headers(behavior_harness):
    """Once a stream has entered the main headers phase, starting an
    informational phase must be rejected and must leave the stream's
    category unchanged."""
    fields = _run_harness_scenario(
        behavior_harness, "phase_rejects_informational_after_headers"
    )
    assert fields["status1"] == "ok", fields
    assert fields["status2"] == "rejected", fields
    assert fields["category"] == "headers", fields


def test_stream_behavior_phase_rejects_anything_after_trailers(behavior_harness):
    """Trailers must be a stream's terminal phase: once entered, starting
    any further phase must be rejected and must leave the category at
    trailers."""
    fields = _run_harness_scenario(
        behavior_harness, "phase_rejects_anything_after_trailers"
    )
    assert fields["status1"] == "ok", fields
    assert fields["status2"] == "rejected", fields
    assert fields["category"] == "trailers", fields


def test_stream_behavior_phase_allows_legal_informational_headers_trailers_sequence(
    behavior_harness,
):
    """The one legal full sequence, informational then headers then
    trailers, must be admitted at every step."""
    fields = _run_harness_scenario(
        behavior_harness, "phase_allows_informational_then_headers_then_trailers"
    )
    assert fields["status1"] == "ok", fields
    assert fields["status2"] == "ok", fields
    assert fields["status3"] == "ok", fields
    assert fields["category"] == "trailers", fields


def test_security_notes_covers_all_five_themes():
    """security_notes.md must name every subsystem, the CWE class, and the
    upstream attribution the instructions asked for."""
    notes_path = ENV / "security_notes.md"
    assert notes_path.exists(), (
        "security_notes.md was not written to /app/environment; instruction.md "
        "asks for it as a deliverable."
    )
    body = notes_path.read_text().lower()
    for theme in (
        "session",
        "stream",
        "empty",
        "flush",
        "phase",
        "count",
    ):
        assert theme in body, f"security_notes.md missing theme keyword '{theme}'"
    assert re.search(r"destr\w*|tear\w*.?down", body), (
        "security_notes.md must describe the stream-teardown refund (any "
        "wording built on 'destroy'/'destruction' or 'teardown'/'tear down')"
    )
    assert re.search(r"\border\w*", body), (
        "security_notes.md must describe the header-phase ordering rule"
    )
    for kw in ("cwe-770", "cwe-841", "http/2", "mit"):
        assert kw in body, f"security_notes.md missing keyword '{kw}'"
