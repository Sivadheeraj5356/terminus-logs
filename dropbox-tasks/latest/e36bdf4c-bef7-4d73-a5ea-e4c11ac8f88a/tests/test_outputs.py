"""Verifier for openssl-engine-provider-migration graded ov_trace suite (q01–q21)."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ENV = Path("/app/environment")
OUT = Path("/app/output/ov_trace.json")
SMOKE = Path("/app/output/smoke_trace.json")
CONF = ENV / "conf" / "workspace.conf"
CASES = ENV / "cases"
PERSIST = Path("/app/output/.ov_persist")
MASK_F = ENV / "var" / "mig" / "epoch_mask.json"
IDX_F = CASES / "idx.json"
STAMP_F = ENV / "var" / "mig" / "seal_stamp.json"
GEN_F = ENV / "var" / "mig" / "suite_gen"
BIND_F = PERSIST / "bind_stamp.json"
ORD_SRC = ENV / "r4" / "ord.go"
BIND_SRC = ENV / "t6" / "bind.go"
BLOBS = ENV / "share" / "ref_blobs"
BLOB_NAMES = ("ord.go", "bind.go")
PROBE = "/app/environment/tools/ov_probe/ov_probe"
AGENT = "agent"
GUARD = Path("/opt/verifier/guard")
G_CONF = GUARD / "conf" / "workspace.conf"
G_CASES = GUARD / "cases"
G_IDX = G_CASES / "idx.json"
G_MASK = GUARD / "var" / "mig" / "epoch_mask.json"
G_BLOBS = Path("/opt/verifier/ref_blobs")
G_BLOB_HASHES = Path("/opt/verifier/ref_blobs.sha256")


def _as_agent(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(["runuser", "-u", AGENT, "--", *args], **kwargs)


def _agent_own(*paths: Path) -> None:
    for path in paths:
        if path.exists():
            subprocess.run(["chown", "-R", f"{AGENT}:{AGENT}", str(path)], check=False)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _protected_blob_hashes() -> dict[str, str]:
    """Parse root-owned sha256sum manifest written at image build."""
    assert G_BLOB_HASHES.is_file(), f"missing protected hash manifest {G_BLOB_HASHES}"
    out: dict[str, str] = {}
    for line in G_BLOB_HASHES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        assert len(parts) >= 2, f"bad hash manifest line: {line!r}"
        digest = parts[0]
        name = Path(parts[1].lstrip("*")).name
        out[name] = digest
    assert set(BLOB_NAMES) <= set(out), f"hash manifest missing blobs: {out}"
    return out


def _assert_ref_blobs_intact() -> None:
    """Live ref_blobs must match root-owned protected copies and hash manifest."""
    expected = _protected_blob_hashes()
    for name in BLOB_NAMES:
        live = BLOBS / name
        prot = G_BLOBS / name
        assert prot.is_file(), f"missing protected baseline {prot}"
        assert live.is_file(), f"missing live baseline {live}"
        live_bytes = live.read_bytes()
        prot_bytes = prot.read_bytes()
        assert live_bytes == prot_bytes, f"ref_blobs/{name} mutated vs protected copy"
        digest = hashlib.sha256(live_bytes).hexdigest()
        assert digest == expected[name], f"ref_blobs/{name} hash drift vs manifest"
        assert hashlib.sha256(prot_bytes).hexdigest() == expected[name]


@pytest.fixture(autouse=True)
def _ref_blobs_before_after_each_test() -> None:
    """Compare both frozen baselines before and after every graded test."""
    _assert_ref_blobs_intact()
    yield
    _assert_ref_blobs_intact()


def _refresh_guard() -> None:
    """Snapshot live fixture inputs before probe execution (root-owned, agent-readable)."""
    shutil.rmtree(GUARD, ignore_errors=True)
    (GUARD / "conf").mkdir(parents=True, exist_ok=True)
    (GUARD / "cases").mkdir(parents=True, exist_ok=True)
    (GUARD / "var" / "mig").mkdir(parents=True, exist_ok=True)
    shutil.copy2(CONF, G_CONF)
    shutil.copy2(MASK_F, G_MASK)
    shutil.copy2(IDX_F, G_IDX)
    for name in json.loads(IDX_F.read_text(encoding="utf-8")):
        shutil.copy2(CASES / name, G_CASES / name)
    for lane in ("arm_a", "arm_b"):
        src = ENV / "conf" / f"{lane}.conf"
        shutil.copy2(src, GUARD / "conf" / f"{lane}.conf")
    for path in GUARD.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
    GUARD.chmod(0o755)


@pytest.fixture(scope="session", autouse=True)
def session_workspace():
    conf_bak = CONF.read_text(encoding="utf-8")
    mask_bak = MASK_F.read_text(encoding="utf-8")
    idx_bak = IDX_F.read_text(encoding="utf-8")

    CONF.write_text(
        "# Workspace activation order\n"
        "slot=1\nslot=0\nslot=1\nslot=2\nslot=3\n",
        encoding="utf-8",
    )
    MASK_F.write_text('{"mask": 10}\n', encoding="utf-8")

    c04 = CASES / "case_04.json"
    c05 = CASES / "case_05.json"
    c04.write_text(
        '{\n  "unit_id": "c04",\n  "query": "mode=strict",\n'
        '  "uri": "eng://fallback-delta",\n  "alg": "dig-d"\n}\n',
        encoding="utf-8",
    )
    c05.write_text(
        '{\n  "unit_id": "c05",\n  "query": "mode=strict",\n'
        '  "uri": "file:///delta-override",\n  "alg": "dig-e"\n}\n',
        encoding="utf-8",
    )
    IDX_F.write_text(
        '[\n  "case_01.json",\n  "case_02.json",\n'
        '  "case_03.json",\n  "case_04.json",\n  "case_05.json"\n]\n',
        encoding="utf-8",
    )
    _agent_own(ENV, Path("/app/output"))
    _as_agent(["bash", "/app/environment/scripts/build_workspace.sh"], check=True)
    _refresh_guard()
    _assert_ref_blobs_intact()

    yield

    _assert_ref_blobs_intact()
    CONF.write_text(conf_bak, encoding="utf-8")
    MASK_F.write_text(mask_bak, encoding="utf-8")
    IDX_F.write_text(idx_bak, encoding="utf-8")
    for p in (c04, c05):
        if p.exists():
            p.unlink()


def _sha(s: str) -> str:
    proc = subprocess.run(
        ["openssl", "dgst", "-sha256"],
        input=s.encode("utf-8"),
        capture_output=True,
        check=True,
    )
    return proc.stdout.decode("utf-8").strip().split()[-1]


def _repair() -> None:
    _as_agent(["bash", "/app/environment/migrations/rst9.sh", "--repair"], check=True)


def _build() -> None:
    _as_agent(["bash", "/app/environment/scripts/build_workspace.sh"], check=True)


def _probe(trace: Path | None = None) -> subprocess.CompletedProcess:
    return _as_agent(
        [PROBE, "--suite", "all", "--trace-out", str(trace or OUT)],
        capture_output=True,
    )


def _rebuild() -> subprocess.CompletedProcess:
    return _as_agent([PROBE, "--suite", "rebuild"], capture_output=True)


def _prop() -> subprocess.CompletedProcess:
    return _as_agent([PROBE, "--suite", "prop"], capture_output=True)


def _prepare() -> subprocess.CompletedProcess:
    return _as_agent([PROBE, "--suite", "prepare"], capture_output=True)


def _finalize(trace: Path | None = None) -> subprocess.CompletedProcess:
    return _as_agent(
        [PROBE, "--suite", "finalize", "--trace-out", str(trace or OUT)],
        capture_output=True,
    )


def _load(path: Path | None = None) -> list:
    return json.loads((path or OUT).read_text(encoding="utf-8"))


def _row(trace: list, uid: str, lane: str) -> dict:
    for r in trace:
        if r["unit_id"] == uid and r["arm"] == lane:
            return r
    raise AssertionError(f"missing {uid}/{lane}")


def _cases() -> list[dict]:
    idx = json.loads(G_IDX.read_text(encoding="utf-8"))
    return [json.loads((G_CASES / n).read_text(encoding="utf-8")) for n in idx]


def _slots_raw() -> list[int]:
    out: list[int] = []
    for line in G_CONF.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("slot="):
            out.append(int(line.split("=", 1)[1]))
    return out


def _weight() -> int:
    return len(_slots_raw())


def _first_wins() -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for v in _slots_raw():
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def _slot_a(lane: str) -> bool:
    text = (GUARD / "conf" / f"{lane}.conf").read_text(encoding="utf-8")
    return any(ln.strip().startswith("slot=A") for ln in text.splitlines())


def _sel(query: str, lane: str) -> str:
    if "strict" in query and _slot_a(lane):
        return "slotA"
    return "def"


def _uri_only(uri: str) -> str:
    if uri.startswith("prv:"):
        return "prv"
    if uri.startswith("file:"):
        return "file"
    return "eng"


def _scheme(uri: str, sel: str) -> str:
    if sel == "slotA":
        if uri.startswith("file:"):
            return "file"
        return "prv"
    return _uri_only(uri)


def _epoch() -> int:
    mask = json.loads(G_MASK.read_text(encoding="utf-8"))["mask"]
    return sum(_slots_raw()) ^ int(mask)


def _cycle() -> int:
    if not GEN_F.exists():
        return 0
    return int(GEN_F.read_text(encoding="utf-8").strip() or "0")


def _auth_gen() -> int:
    if not BIND_F.exists():
        return 0
    return int(json.loads(BIND_F.read_text(encoding="utf-8"))["auth_gen"])


def _digest(case: dict, lane: str, cycle: int) -> str:
    sel = _sel(case["query"], lane)
    sch = _scheme(case["uri"], sel)
    seq = ",".join(str(x) for x in _first_wins())
    row = (
        f"{case['unit_id']}|{lane}|{sel}|{seq}|{sch}|{_epoch()}|{cycle}|{_weight()}"
    )
    return _sha(row)


def _guard_nonce(auth_gen: int | None = None) -> str:
    ag = _auth_gen() if auth_gen is None else auth_gen
    ep = str(_epoch())
    idx_b = G_IDX.read_bytes().decode("utf-8")
    mask_b = G_MASK.read_bytes().decode("utf-8")
    raw = f"{ep}|{idx_b}|{mask_b}|{_weight()}|{ag}"
    return _sha(raw)[:16]


def _expect_trace(cycle: int) -> list[dict]:
    rows = []
    for case in _cases():
        for lane in ("arm_a", "arm_b"):
            sel = _sel(case["query"], lane)
            sch = _scheme(case["uri"], sel)
            rows.append(
                {
                    "unit_id": case["unit_id"],
                    "arm": lane,
                    "sel_id": sel,
                    "fetch_seq": _first_wins(),
                    "scheme": sch,
                    "uri_scheme": _uri_only(case["uri"]),
                    "digest": _digest(case, lane, cycle),
                    "status": "WIT_FRESH",
                }
            )
    return rows


def _assert_coherent(trace: list, cycle: int) -> None:
    expected = _expect_trace(cycle)
    assert len(trace) == len(expected)
    for got, exp in zip(trace, expected):
        for k in (
            "unit_id",
            "arm",
            "sel_id",
            "fetch_seq",
            "scheme",
            "uri_scheme",
            "digest",
            "status",
        ):
            assert got[k] == exp[k], f"{got['unit_id']}/{got['arm']} {k}"


def _cold() -> list:
    _repair()
    _build()
    _refresh_guard()
    proc = _probe()
    assert proc.returncode == 0, (proc.stdout or b"").decode() + (proc.stderr or b"").decode()
    return _load()


def test_q01_cold_coherent_ten_rows() -> None:
    """Cold repair plus graded suite yields ten WIT_FRESH rows at cycle zero."""
    trace = _cold()
    assert len(trace) == 10
    assert _cycle() == 1
    _assert_coherent(trace, 0)
    latch = PERSIST / "pref_latch"
    assert latch.is_file()
    assert latch.read_text(encoding="utf-8").strip() == "sealed"


def test_q02_second_suite_digest_drift() -> None:
    """Second suite digests differ while auth_gen advances with cycle one."""
    t0 = _cold()
    d0 = [r["digest"] for r in t0]
    assert _auth_gen() == 1
    latch = PERSIST / "pref_latch"
    assert latch.is_file()
    assert latch.read_text(encoding="utf-8").strip() == "sealed"
    _refresh_guard()
    assert _probe().returncode == 0
    t1 = _load()
    d1 = [r["digest"] for r in t1]
    assert d0 != d1
    _assert_coherent(t1, 1)
    assert _auth_gen() == 2
    assert latch.read_text(encoding="utf-8").strip() == "sealed"


def test_q03_leftover_arm_token_rejects() -> None:
    """Prepare rejects a pre-existing arm_token from a prior incomplete run."""
    _cold()
    PERSIST.mkdir(parents=True, exist_ok=True)
    tok = PERSIST / "arm_token"
    tok.write_text("stale", encoding="utf-8")
    _agent_own(tok)
    _refresh_guard()
    assert _probe().returncode != 0


def test_q04_midcycle_nonce_tamper_rejects_finalize() -> None:
    """Prepare writes the contract nonce; tampering before finalize must fail consume."""
    _assert_ref_blobs_intact()
    _repair()
    _build()
    _refresh_guard()
    assert _prepare().returncode == 0
    tok = PERSIST / "arm_token"
    assert tok.is_file()
    created = tok.read_text(encoding="utf-8").strip()
    expected = _guard_nonce(auth_gen=0)
    assert created == expected
    assert len(created) == 16
    assert all(c in "0123456789abcdef" for c in created)
    # Tamper between prepare and finalize — wrong binders must fail consume.
    bad = _sha(f"{_epoch()}|{G_IDX.read_bytes().decode('utf-8')}|{G_MASK.read_bytes().decode('utf-8')}|{_weight()}")[:16]
    assert bad != created
    tok.write_text(bad, encoding="utf-8")
    _agent_own(tok)
    assert _finalize().returncode != 0
    assert tok.is_file()
    _assert_ref_blobs_intact()


def test_q04b_nonce_bind_stamp_after_cycle_and_mid_mutate() -> None:
    """After a completed cycle, prepare binds bind_stamp auth_gen (not suite_gen/zero).

    Changing bind_stamp between prepare and finalize must make finalize reject.
    Always-zero or suite_gen-sourced nonces must not match the live-bound token.
    """
    _assert_ref_blobs_intact()
    _cold()
    assert BIND_F.is_file()
    assert _auth_gen() == 1
    assert _cycle() == 1
    # Diverge suite_gen from bind_stamp.auth_gen so always-zero or suite_gen reads fail.
    GEN_F.write_text("99\n", encoding="utf-8")
    _agent_own(GEN_F)
    assert _auth_gen() == 1
    assert _cycle() == 99
    _refresh_guard()
    assert _prepare().returncode == 0
    tok = PERSIST / "arm_token"
    assert tok.is_file()
    created = tok.read_text(encoding="utf-8").strip()
    expected = _guard_nonce(auth_gen=1)
    assert created == expected
    assert created != _guard_nonce(auth_gen=0)
    assert created != _guard_nonce(auth_gen=99)
    assert created != _guard_nonce(auth_gen=_cycle())
    # Mutate live bind_stamp auth_gen between prepare and finalize.
    BIND_F.write_text(
        json.dumps({"auth_gen": 7, "epoch": _epoch()}) + "\n",
        encoding="utf-8",
    )
    _agent_own(BIND_F)
    assert _auth_gen() == 7
    assert _finalize().returncode != 0
    assert tok.is_file()
    _assert_ref_blobs_intact()


def test_q05_poison_residue_cleared_coherent() -> None:
    """Matching stamp still clears planted poison-residue-hex before eight-segment hashing."""
    _repair()
    _build()
    _refresh_guard()
    STAMP_F.write_text(json.dumps({"epoch": _epoch()}) + "\n", encoding="utf-8")
    PERSIST.mkdir(parents=True, exist_ok=True)
    res = PERSIST / "rim_residue"
    res.write_text("poison-residue-hex", encoding="utf-8")
    _agent_own(STAMP_F, res)
    assert _probe().returncode == 0
    _assert_coherent(_load(), 0)
    if res.exists():
        assert res.read_text(encoding="utf-8").strip() == ""


def test_q06_stamp_mismatch_bytes_preserved() -> None:
    """Seal stamp bytes are preserved on epoch mismatch while hygiene still runs."""
    _repair()
    _build()
    _refresh_guard()
    STAMP_F.write_text('{"epoch": 9999}\n', encoding="utf-8")
    _agent_own(STAMP_F)
    before = STAMP_F.read_text(encoding="utf-8")
    assert _probe().returncode == 0
    assert STAMP_F.read_text(encoding="utf-8") == before
    _assert_coherent(_load(), 0)


def test_q07_fetch_seq_first_wins() -> None:
    """fetch_seq applies first-wins dedupe yielding [1, 0, 2, 3]."""
    trace = _cold()
    for r in trace:
        assert r["fetch_seq"] == [1, 0, 2, 3]


def test_q08_digests_are_eight_segment() -> None:
    """Graded digests use eight segments including weight, not seven."""
    trace = _cold()
    for r in trace:
        assert r["status"] == "WIT_FRESH"
        seven = _sha(
            "|".join(
                [
                    r["unit_id"],
                    r["arm"],
                    r["sel_id"],
                    ",".join(str(x) for x in r["fetch_seq"]),
                    r["scheme"],
                    str(_epoch()),
                    str(0),
                ]
            )
        )
        assert r["digest"] != seven
        assert len(r["digest"]) == 64


def test_q09_scheme_ternary_matrix() -> None:
    """Joint scheme and uri_scheme disagree on slotA eng URI; file override holds."""
    trace = _cold()
    r = _row(trace, "c01", "arm_a")
    assert r["sel_id"] == "slotA"
    assert r["scheme"] == "prv"
    assert r["uri_scheme"] == "prv"
    r4 = _row(trace, "c04", "arm_a")
    assert r4["sel_id"] == "slotA"
    assert r4["scheme"] == "prv"
    assert r4["uri_scheme"] == "eng"
    assert r4["scheme"] != r4["uri_scheme"]
    r5 = _row(trace, "c05", "arm_a")
    assert r5["scheme"] == "file"
    assert r5["uri_scheme"] == "file"


def test_q10_rebuild_dual_parity() -> None:
    """Rebuild agrees with a fresh full suite at the advanced cycle."""
    _cold()
    _refresh_guard()
    assert _rebuild().returncode == 0
    _assert_coherent(_load(), 1)


def test_q11_triple_cycle_oscillation() -> None:
    """Three consecutive suites produce distinct digest sets per cycle."""
    digests = []
    _repair()
    _build()
    for cy in range(3):
        _refresh_guard()
        assert _probe().returncode == 0
        t = _load()
        _assert_coherent(t, cy)
        digests.append([r["digest"] for r in t])
    assert digests[0] != digests[1] != digests[2]
    assert digests[0] != digests[2]


def test_q12_repair_wipe_cold_coherent() -> None:
    """Repair wipe drops trace and suite_gen; next cold suite is coherent."""
    _cold()
    assert OUT.exists() and GEN_F.exists()
    _repair()
    assert not OUT.exists()
    assert not GEN_F.exists()
    _build()
    _refresh_guard()
    assert _probe().returncode == 0
    _assert_coherent(_load(), 0)


def test_q13_journal_prefixes_match_digest() -> None:
    """Journal lines are sixteen-hex digest prefixes in row order."""
    trace = _cold()
    jnl = (PERSIST / "mig.jnl").read_text(encoding="utf-8").splitlines()
    assert len(jnl) == len(trace)
    for line, row in zip(jnl, trace):
        assert line == row["digest"][:16]
        assert all(c in "0123456789abcdef" for c in line)


def test_q14_smoke_partial_then_graded() -> None:
    """Prop smoke emits PARTIAL_OK without waiving a subsequent graded suite."""
    _repair()
    _build()
    _refresh_guard()
    assert _prop().returncode == 0
    smoke = _load(SMOKE)
    assert smoke[0]["status"] == "PARTIAL_OK"
    assert _probe().returncode == 0
    _assert_coherent(_load(), 0)


def test_q15_stock_ord_ablation_breaks_first_wins() -> None:
    """Stock ord reference blob breaks first-wins fetch_seq ordering."""
    _assert_ref_blobs_intact()
    bak = ORD_SRC.read_text(encoding="utf-8")
    try:
        ORD_SRC.write_text((BLOBS / "ord.go").read_text(encoding="utf-8"), encoding="utf-8")
        _agent_own(ORD_SRC)
        _repair()
        _build()
        _refresh_guard()
        rc = _probe().returncode
        if rc == 0:
            trace = _load()
            assert any(r["fetch_seq"] != [1, 0, 2, 3] for r in trace)
    finally:
        ORD_SRC.write_text(bak, encoding="utf-8")
        _agent_own(ORD_SRC)
        _build()
        _assert_ref_blobs_intact()


def test_q16_stock_bind_ablation_breaks_scheme() -> None:
    """Stock bind reference blob forces eng scheme on slotA rows."""
    _assert_ref_blobs_intact()
    bak = BIND_SRC.read_text(encoding="utf-8")
    try:
        BIND_SRC.write_text((BLOBS / "bind.go").read_text(encoding="utf-8"), encoding="utf-8")
        _agent_own(BIND_SRC)
        _repair()
        _build()
        _refresh_guard()
        rc = _probe().returncode
        if rc == 0:
            trace = _load()
            r = _row(trace, "c01", "arm_a")
            assert r["scheme"] == "eng" or r["status"] != "WIT_FRESH"
    finally:
        BIND_SRC.write_text(bak, encoding="utf-8")
        _agent_own(BIND_SRC)
        _build()
        _assert_ref_blobs_intact()


def test_q17_cross_suite_latch_cleared_slotA_prv() -> None:
    """Sticky latch before second suite does not remap slotA prv selection."""
    _cold()
    PERSIST.mkdir(parents=True, exist_ok=True)
    latch = PERSIST / "pref_latch"
    latch.write_text("sticky", encoding="utf-8")
    _agent_own(latch)
    _refresh_guard()
    assert _probe().returncode == 0
    trace = _load()
    r = _row(trace, "c01", "arm_a")
    assert r["sel_id"] == "slotA"
    assert r["scheme"] == "prv"
    assert _auth_gen() == 2


def test_q18_metamorphic_conf_change() -> None:
    """Live workspace.conf edits change epoch and weight authoritatively."""
    _cold()
    conf_bak = CONF.read_text(encoding="utf-8")
    try:
        CONF.write_text("slot=9\nslot=9\n", encoding="utf-8")
        _agent_own(CONF)
        _refresh_guard()
        r = _probe()
        if r.returncode == 0:
            _assert_coherent(_load(), _cycle() - 1)
        _repair()
        _build()
        CONF.write_text("slot=9\nslot=9\n", encoding="utf-8")
        _agent_own(CONF)
        _refresh_guard()
        assert _probe().returncode == 0
        assert _epoch() == (9 + 9) ^ 10
        assert _weight() == 2
        _assert_coherent(_load(), 0)
    finally:
        CONF.write_text(conf_bak, encoding="utf-8")
        _agent_own(CONF)
        _refresh_guard()


def test_q19_continue_bind_stamp_auth_gen_matches_gen() -> None:
    """After two probes bind_stamp auth_gen equals suite_gen with empty residue."""
    _cold()
    _refresh_guard()
    assert _probe().returncode == 0
    assert BIND_F.exists()
    bind = json.loads(BIND_F.read_text(encoding="utf-8"))
    assert bind["auth_gen"] == _cycle()
    assert bind["epoch"] == _epoch()
    res = PERSIST / "rim_residue"
    if res.exists():
        assert res.read_text(encoding="utf-8").strip() == ""


def test_q20_odd_epoch_latch_inert_before_first_probe() -> None:
    """Odd epoch with planted latch still yields slotA prv on first graded probe."""
    assert _epoch() % 2 == 1
    _repair()
    _build()
    PERSIST.mkdir(parents=True, exist_ok=True)
    latch = PERSIST / "pref_latch"
    latch.write_text("sticky", encoding="utf-8")
    _agent_own(latch)
    _refresh_guard()
    assert _probe().returncode == 0
    trace = _load()
    r = _row(trace, "c01", "arm_a")
    assert r["sel_id"] == "slotA"
    assert r["scheme"] == "prv"


def test_q21_ref_blobs_match_protected_baselines() -> None:
    """Both share/ref_blobs files stay byte-identical to protected copies and hashes."""
    _assert_ref_blobs_intact()
    expected = _protected_blob_hashes()
    for name in BLOB_NAMES:
        assert _file_sha256(BLOBS / name) == expected[name]
        assert _file_sha256(G_BLOBS / name) == expected[name]
    _cold()
    _assert_ref_blobs_intact()
    for name in BLOB_NAMES:
        assert _file_sha256(BLOBS / name) == expected[name]
        assert _file_sha256(G_BLOBS / name) == expected[name]
