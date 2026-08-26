"""Verifier for linkctl cold-start, reload, WAL recovery, and fence/quarantine."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

APP = Path("/app")
OUT = APP / "output"
FIB = OUT / "effective_fib.json"
LINK = OUT / "link_status.json"
JOURNAL = OUT / "reconfigure_journal.jsonl"
STATE = APP / "var" / "state"
WAL = STATE / "wal.jsonl"
SNAP = STATE / "snap.json"
DRIVER_CMD = "/app/scripts/run_link_ops.sh"
LINKCTL_CMD = "/app/bin/linkctl"
ENV = APP / "environment"
TOPO = APP / "data" / "topology_w3"
FEED = APP / "var" / "grant_feed.jsonl"
BROKEN = Path("/tests/fixtures/broken")

CLASS_DYN = 1
CLASS_INJECT = 2
CLASS_CATCH = 3

_PATH_REG = ENV / "reg" / "m7_apply.go"
_PATH_LSE = ENV / "lse" / "w4_epoch.go"
_SRC_PATHS = (_PATH_REG, _PATH_LSE)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_feed() -> list[dict[str, Any]]:
    lines = FEED.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _feed_state(
    events: list[dict[str, Any]], upto: int
) -> tuple[int, int, dict[str, bool]]:
    epoch = 0
    fence = 0
    active: dict[str, bool] = {}
    for ev in events:
        if ev["seq"] > upto:
            continue
        if ev["kind"] == "G":
            epoch += 1
            fence += 1
            active[ev["prefix"]] = True
        elif ev["kind"] == "W":
            epoch += 1
            fence += 1
            active.pop(ev["prefix"], None)
    return epoch, fence, active


def _rows_for_profile(profile: str, upto: int) -> list[dict[str, Any]]:
    prof = _load_json(TOPO / f"{profile}.json")
    foreign = _load_json(TOPO / "foreign_rows.json")["rows"]
    _, fence, active = _feed_state(_load_feed(), upto)
    rows: list[dict[str, Any]] = []
    for raw in foreign:
        admit = int(raw.get("admit_fence", fence))
        if fence < admit:
            continue
        rows.append(
            {
                "key": raw["key"],
                "prefix": raw["prefix"],
                "via": raw["via"],
                "class": CLASS_INJECT,
            }
        )
    for raw in prof["catch_rows"]:
        rows.append(
            {
                "key": raw["key"],
                "prefix": raw["prefix"],
                "via": raw["via"],
                "class": CLASS_CATCH,
            }
        )
    for raw in prof["manager_rows"]:
        if not active.get(raw["prefix"]):
            continue
        rows.append(
            {
                "key": raw["key"],
                "prefix": raw["prefix"],
                "via": raw["via"],
                "class": CLASS_DYN,
            }
        )
    return rows


def fingerprint(rows: list[dict[str, Any]]) -> str:
    wire = [{"p": r["prefix"], "v": r["via"], "c": r["class"]} for r in rows]
    wire.sort(key=lambda item: (item["p"], item["v"]))
    payload = json.dumps(wire, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def cold_fingerprint(profile: str) -> str:
    rows = _rows_for_profile(profile, upto=999)
    return fingerprint(rows)


def reconfigure_rows(
    profile: str, prior: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    prof = _load_json(TOPO / f"{profile}.json")
    want = _rows_for_profile(profile, upto=prof["churn_seq"])
    if prior is None:
        prior = _rows_for_profile("alpha", upto=999)
    kept = [r for r in prior if r["class"] == CLASS_INJECT]
    catch_keys = {r["key"] for r in want if r["class"] == CLASS_CATCH}
    for r in prior:
        if r["class"] == CLASS_CATCH and r["key"] not in catch_keys:
            kept.append(r)
    for r in want:
        if r["class"] == CLASS_CATCH:
            kept.append(r)
    kept.extend(r for r in want if r["class"] == CLASS_DYN)
    dedup: dict[str, dict[str, Any]] = {}
    for r in kept:
        dedup[r["key"]] = r
    return list(dedup.values())


def reconfigure_fingerprint(
    profile: str, prior: list[dict[str, Any]] | None = None
) -> str:
    return fingerprint(reconfigure_rows(profile, prior=prior))


def _snapshot_sources() -> dict[str, str]:
    return {str(path): path.read_text(encoding="utf-8") for path in _SRC_PATHS}


def _restore_snapshot(snap: dict[str, str]) -> None:
    for path in _SRC_PATHS:
        path.write_text(snap[str(path)], encoding="utf-8")


def _build() -> None:
    subprocess.run(
        ["bash", str(ENV / "scripts" / "build_linkctl.sh")],
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )


def _wipe_outputs() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)


def _wipe_state() -> None:
    if STATE.exists():
        shutil.rmtree(STATE)
    STATE.mkdir(parents=True, exist_ok=True)


def _run_driver(profile: str = "alpha") -> None:
    _wipe_outputs()
    _build()
    subprocess.run(
        ["bash", DRIVER_CMD, profile],
        check=True,
        capture_output=True,
        text=True,
        timeout=300,
    )


def _run_boot(profile: str) -> None:
    _wipe_state()
    subprocess.run(
        [LINKCTL_CMD, "boot", "--profile", profile],
        check=True,
        capture_output=True,
        timeout=120,
    )


def _run_reconfigure(profile: str) -> None:
    subprocess.run(
        [LINKCTL_CMD, "reconfigure", "--profile", profile],
        check=True,
        capture_output=True,
        timeout=120,
    )


def _run_recover(profile: str = "beta") -> None:
    subprocess.run(
        [
            LINKCTL_CMD,
            "recover",
            "--root",
            "/app/var/state",
            "--out",
            "/app/output",
            "--profile",
            profile,
        ],
        check=True,
        capture_output=True,
        timeout=120,
    )


def _load_fib() -> dict:
    return json.loads(FIB.read_text(encoding="utf-8"))


def _load_link() -> dict:
    return json.loads(LINK.read_text(encoding="utf-8"))


def _journal_lines() -> list[dict]:
    if not JOURNAL.exists():
        return []
    out = []
    for line in JOURNAL.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _fp_from_doc(doc: dict) -> str:
    return fingerprint(doc["rows"])


def _last_sealed_gen() -> int:
    sealed = 0
    for line in WAL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        fr = json.loads(line)
        if fr.get("sealed"):
            sealed = fr["gen"]
    return sealed


# --- preserved tests ---


def test_n2_full_cold_baseline() -> None:
    """Cold restart converges effective FIB fingerprint."""
    _wipe_outputs()
    _build()
    _wipe_state()
    _run_boot("alpha")
    doc = _load_fib()
    assert doc["fingerprint"] == cold_fingerprint("alpha")
    assert doc["fingerprint"] == _fp_from_doc(doc)


def test_w9_cycle_parity() -> None:
    """Second reconfigure pass matches cold-start reachability set."""
    _run_driver("alpha")
    doc = _load_fib()
    assert doc["fingerprint"] == reconfigure_fingerprint("beta")


def test_m3_perm_load_order() -> None:
    """FIB invariant when profile fixture load order permutes."""
    seed = int.from_bytes(hashlib.sha256(b"m3").digest()[:4], "big")
    names = ["gamma", "alpha", "beta"]
    order = names[:]
    for i in range(len(order) - 1, 0, -1):
        seed = (1103515245 * seed + 12345) & 0x7FFFFFFF
        j = seed % (i + 1)
        order[i], order[j] = order[j], order[i]
    _wipe_outputs()
    _build()
    for name in order:
        _wipe_state()
        _run_boot(name)
        doc = _load_fib()
        assert doc["fingerprint"] == cold_fingerprint(name)


def test_k1_second_pass_green_trap() -> None:
    """Probe-green status must not pass when effective FIB diverges."""
    _run_driver("alpha")
    link = _load_link()
    assert all(p["carrier_up"] for p in link["probes"])
    doc = _load_fib()
    assert doc["fingerprint"] == reconfigure_fingerprint("beta")


# --- replaced hard tests ---


def test_h1_recover_idempotent() -> None:
    """Two recover passes match oracle fingerprint and keep the same tip."""
    _wipe_outputs()
    _build()
    _wipe_state()
    _run_boot("alpha")
    _run_reconfigure("beta")
    expect = reconfigure_fingerprint("beta")
    assert _load_fib()["fingerprint"] == expect
    _run_recover("beta")
    first = _load_fib()["fingerprint"]
    first_recover = [ln for ln in _journal_lines() if ln["phase"] == "recover"][-1]
    _run_recover("beta")
    second = _load_fib()["fingerprint"]
    second_recover = [ln for ln in _journal_lines() if ln["phase"] == "recover"][-1]
    assert first == second == expect
    assert first_recover["gen_committed"] == second_recover["gen_committed"]


def test_h2_snap_corruption_recover() -> None:
    """Corrupt snap.json; recover rebuilds sealed WAL tip FIB."""
    _wipe_outputs()
    _build()
    _wipe_state()
    _run_boot("alpha")
    _run_reconfigure("beta")
    expected = reconfigure_fingerprint("beta")
    assert _load_fib()["fingerprint"] == expected
    SNAP.write_text("{not-json", encoding="utf-8")
    _run_recover("beta")
    doc = _load_fib()
    assert doc["fingerprint"] == expected


def test_h3_gamma_chain_ordering() -> None:
    """Boot alpha, reconfigure beta, recover, reconfigure gamma chain."""
    _wipe_outputs()
    _build()
    _wipe_state()
    _run_boot("alpha")
    _run_reconfigure("beta")
    beta_fp = reconfigure_fingerprint("beta")
    beta_rows = reconfigure_rows("beta")
    assert _load_fib()["fingerprint"] == beta_fp
    _run_recover("beta")
    assert _load_fib()["fingerprint"] == beta_fp
    _run_reconfigure("gamma")
    expected = reconfigure_fingerprint("gamma", prior=beta_rows)
    assert _load_fib()["fingerprint"] == expected


def test_h4_stale_fence_quarantine() -> None:
    """Withdrawn manager prefixes absent; deferred hold stays out of FIB."""
    _run_driver("alpha")
    keys = {r["key"] for r in _load_fib()["rows"]}
    assert "m-alpha-2" not in keys
    assert "f-shim-9" in keys and "f-shim-10" in keys
    assert "f-shim-hold" not in keys
    _run_recover("beta")
    _run_reconfigure("beta")
    keys2 = {r["key"] for r in _load_fib()["rows"]}
    assert "m-alpha-2" not in keys2
    assert "f-shim-9" in keys2 and "f-shim-10" in keys2
    assert "f-shim-hold" not in keys2


def test_h5_unsealed_wal_ignored() -> None:
    """Fake unsealed WAL frame must not become recovery tip."""
    _wipe_outputs()
    _build()
    _wipe_state()
    _run_boot("alpha")
    _run_reconfigure("beta")
    sealed_fp = _load_fib()["fingerprint"]
    sealed_gen = _last_sealed_gen()
    bogus_rows = [{"key": "bogus-x", "prefix": "192.0.2.0/24", "via": "0.0.0.0", "class": 1}]
    fake = {"gen": sealed_gen + 99, "sealed": False, "rows": bogus_rows}
    with WAL.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(fake) + "\n")
    SNAP.write_text("{}", encoding="utf-8")
    _run_recover("beta")
    assert _load_fib()["fingerprint"] == sealed_fp
    assert "bogus-x" not in {r["key"] for r in _load_fib()["rows"]}


def test_h6_cross_command_consistency() -> None:
    """Cold, driver, and probe generations align with contract."""
    _wipe_outputs()
    _build()
    _wipe_state()
    _run_boot("alpha")
    boot_fp = _load_fib()["fingerprint"]
    assert boot_fp == cold_fingerprint("alpha")
    _run_reconfigure("alpha")
    _run_reconfigure("beta")
    driver_fp = _load_fib()["fingerprint"]
    assert driver_fp == reconfigure_fingerprint("beta")
    lines = _journal_lines()
    last_commit = [ln for ln in lines if ln["phase"] == "commit"][-1]
    gen_committed = last_commit["gen_committed"]
    for probe in _load_link()["probes"]:
        assert probe["mirror_gen"] == gen_committed


def test_h7_beta_idempotent_after_recover() -> None:
    """Recover then repeat beta reconfigure keeps fingerprint stable."""
    _wipe_outputs()
    _build()
    _wipe_state()
    _run_boot("alpha")
    _run_reconfigure("beta")
    first_fp = _load_fib()["fingerprint"]
    _run_recover("beta")
    _run_reconfigure("beta")
    second_fp = _load_fib()["fingerprint"]
    assert first_fp == second_fp == reconfigure_fingerprint("beta")


# --- ablation tests ---


def test_v7_loc_a_ablation() -> None:
    """Revert registry merge fix leaves reload parity subset red."""
    snap = _snapshot_sources()
    try:
        _PATH_REG.write_text((BROKEN / "loc_a.go").read_text(encoding="utf-8"))
        _run_driver("alpha")
        assert _load_fib()["fingerprint"] != reconfigure_fingerprint("beta")
    finally:
        _restore_snapshot(snap)


def test_v8_loc_b_ablation() -> None:
    """Revert feed withdraw fix leaves active_pref superset inflated."""
    snap = _snapshot_sources()
    try:
        _PATH_LSE.write_text((BROKEN / "loc_b.go").read_text(encoding="utf-8"))
        _run_driver("alpha")
        broken_count = len(
            json.loads(SNAP.read_text(encoding="utf-8"))["Feed"]["active_pref"]
        )
        _restore_snapshot(snap)
        _run_driver("alpha")
        fixed_count = len(
            json.loads(SNAP.read_text(encoding="utf-8"))["Feed"]["active_pref"]
        )
        assert broken_count > fixed_count
    finally:
        _restore_snapshot(snap)
