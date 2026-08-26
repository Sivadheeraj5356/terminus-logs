#!/usr/bin/env python3
"""Verifier for lvm-cache-pvmove-origin-split."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ENV_ROOT = Path("/app/environment")
CVCTL = Path("/tmp/cvctl")


def _build_cvctl() -> None:
    if CVCTL.exists():
        CVCTL.unlink()
    go_root = Path("/usr") / "local" / "go" / "bin"
    local_bin = Path("/usr") / "local" / "bin"
    path = os.pathsep.join(
        [str(go_root), str(local_bin), os.environ.get("PATH", "")]
    )
    gocache = Path(os.environ.get("GOCACHE", "/var/cache/cv-go"))
    gomodcache = Path(os.environ.get("GOMODCACHE", "/var/cache/cv-gomod"))
    gocache.mkdir(parents=True, exist_ok=True)
    gomodcache.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["go", "build", "-o", str(CVCTL), str(ENV_ROOT / "cmd" / "cvctl")],
        cwd=str(ENV_ROOT),
        check=True,
        env={
            **os.environ,
            "CVCTL_ROOT": str(ENV_ROOT),
            "GOCACHE": str(gocache),
            "GOMODCACHE": str(gomodcache),
            "GOTOOLCHAIN": "local",
            "PATH": path,
        },
    )


def _fresh_workspace() -> Path:
    ws = Path("/tmp") / f"cvws-{os.urandom(5).hex()}"
    if ws.exists():
        shutil.rmtree(ws)
    return ws


def _run_cvctl(*args: str) -> None:
    env = {**os.environ, "CVCTL_ROOT": str(ENV_ROOT)}
    subprocess.run([str(CVCTL), *args], check=True, env=env)


def _copy_sample(sample: str) -> Path:
    ws = _fresh_workspace()
    _run_cvctl("copy", f"--sample={sample}", f"--dest={ws}")
    return ws


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _foreign_payload(ws: Path, slot: int) -> str:
    return _read_json(ws / "foreign" / f"{slot}.json")["payload"]


def _slow_payload(ws: Path, slot: int) -> str:
    return _read_json(ws / "lanes" / "slow" / f"{slot}.json")["payload"]


def _fast_payload(ws: Path, slow_slot: int) -> str:
    return _fast_by_bind(ws, slow_slot)["payload"]


def _fast_by_bind(ws: Path, slow_slot: int) -> dict:
    for path in (ws / "lanes" / "fast").glob("*.json"):
        data = _read_json(path)
        if int(data.get("bind", -1)) == slow_slot:
            return data
    raise AssertionError(f"no fast lane bound to slow slot {slow_slot}")


def _expected_fprint(tag: str, rev: int, move: int) -> str:
    raw = f"{tag}:{rev}:{move}".encode()
    proc = subprocess.run(
        ["sha256sum"],
        input=raw,
        check=True,
        capture_output=True,
    )
    return proc.stdout.decode().split()[0][:16]


def _digest_ref_fprint(tag: str, rev: int, move: int) -> str:
    proc = subprocess.run(
        [
            sys.executable,
            str(ENV_ROOT / "docs" / "digest_ref.py"),
            tag,
            str(rev),
            str(move),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _assert_fprint_matches(hash_view: dict) -> None:
    tag = hash_view["tag"]
    rev = int(hash_view["rev"])
    move = int(hash_view["move"])
    expected = _expected_fprint(tag, rev, move)
    assert hash_view["fprint"] == expected
    assert _digest_ref_fprint(tag, rev, move) == expected


def _fast_bind_snapshot(ws: Path) -> dict[str, int]:
    snap: dict[str, int] = {}
    for path in sorted((ws / "lanes" / "fast").glob("*.json")):
        data = _read_json(path)
        assert "bind" in data and int(data["bind"]) > 0, f"fast lane {path.name} missing bind"
        snap[path.name] = int(data["bind"])
    return snap


def _workflow(ws: Path, events_rel: str) -> None:
    _run_cvctl("status", f"--workspace={ws}")
    _run_cvctl("invariant", f"--workspace={ws}")
    _run_cvctl("recover", f"--workspace={ws}")
    events = ENV_ROOT / "samples" / events_rel / "events.jsonl"
    _run_cvctl("read-replay", f"--workspace={ws}", f"--events={events}")


@pytest.fixture(scope="session", autouse=True)
def build_once() -> None:
    _build_cvctl()


class TestCacheTierSplit:
    """Operator contracts for stacked-volume relocation recovery."""

    def test_barrier_quorum_and_seal_lag(self) -> None:
        """Barrier at move_gen with seal lag keeps window open until quorum converges."""
        ws = _copy_sample("case_g")
        events = ENV_ROOT / "samples" / "run_g" / "events.jsonl"
        _run_cvctl("invariant", f"--workspace={ws}")
        probe = (ws / "out" / "probe_view.txt").read_text()
        assert "window=open" in probe
        vault = _read_json(ws / "state" / "vault.json")
        assert int(vault["seal"]) == 0
        assert int(vault["move_gen"]) == 6
        dirty = vault["dirty"]
        assert int(dirty["barrier"]) >= int(vault["move_gen"])
        alias_pre = _read_json(ws / "maps" / "origin_alias.json")
        assert alias_pre["path"] == "refs/pre_move.json"
        _run_cvctl("read-replay", f"--workspace={ws}", f"--events={events}")
        pre = _read_jsonl(ws / "out" / "tap_rows.jsonl")
        assert pre
        assert all(r["tally"] == 0 for r in pre)
        assert pre[0]["payload"] == _fast_by_bind(ws, 8)["payload"]
        keeper = _foreign_payload(ws, 33)
        _workflow(ws, "run_g")
        hash_view = _read_json(ws / "out" / "hash_view.json")
        assert hash_view["tag"] == "settled"
        _assert_fprint_matches(hash_view)
        assert _foreign_payload(ws, 33) == keeper
        assert _fast_by_bind(ws, 8)["payload"] == _slow_payload(ws, 8)
        tap = _read_jsonl(ws / "out" / "tap_rows.jsonl")
        assert any(r["tally"] > 0 for r in tap)
        traces = _read_jsonl(ws / "out" / "row_trace.jsonl")
        bind = [r for r in traces if r.get("kind") == "bind" and r.get("slot") == 8]
        assert bind and "off=49152" in bind[0].get("note", "")
        _run_cvctl("invariant", f"--workspace={ws}")
        post_probe = (ws / "out" / "probe_view.txt").read_text()
        assert "window=closed" in post_probe

    def test_quorum_surfaces_seal_and_binds(self) -> None:
        """Recover closes all authority surfaces, promotes seal, emits bind notes."""
        ws = _copy_sample("case_a")
        keeper = _foreign_payload(ws, 99)
        _workflow(ws, "run_a")
        vault = _read_json(ws / "state" / "vault.json")
        alias = _read_json(ws / "maps" / "origin_alias.json")
        active = _read_json(ws / "refs" / "active.json")
        assert vault["ptr_path"] == "refs/post_move.json"
        assert int(vault["ptr_rev"]) >= 4
        assert int(vault["seal"]) == int(vault["move_gen"]) == 4
        assert alias["path"] == "refs/post_move.json"
        assert int(alias["rev"]) >= 4
        assert active["path"] == "refs/post_move.json"
        assert int(active["rev"]) >= 4
        traces = _read_jsonl(ws / "out" / "row_trace.jsonl")
        bind1 = [r for r in traces if r.get("kind") == "bind" and r.get("slot") == 1]
        bind2 = [r for r in traces if r.get("kind") == "bind" and r.get("slot") == 2]
        assert bind1 and "off=0" in bind1[0].get("note", "")
        assert bind2 and "off=4096" in bind2[0].get("note", "")
        hash_view = _read_json(ws / "out" / "hash_view.json")
        assert hash_view["tag"] == "settled"
        assert hash_view["rev"] >= 4
        _assert_fprint_matches(hash_view)
        assert _foreign_payload(ws, 99) == keeper
        post = _read_jsonl(ws / "out" / "tap_rows.jsonl")
        slow = _slow_payload(ws, 1)
        assert any(r["slot"] == 1 and r["payload"] == slow for r in post)
        assert any(r["tally"] > 0 for r in post)

    def test_replay_preserves_clash_and_idempotent_fprint(self) -> None:
        """read-replay keeps clash/hash; second recover leaves fprint unchanged."""
        ws = _copy_sample("case_a")
        _workflow(ws, "run_b")
        clash = _read_jsonl(ws / "out" / "clash_rows.jsonl")
        assert clash, "clash rows must survive read-replay"
        first = _read_json(ws / "out" / "hash_view.json")["fprint"]
        events = ENV_ROOT / "samples" / "run_b" / "events.jsonl"
        _run_cvctl("read-replay", f"--workspace={ws}", f"--events={events}")
        assert (ws / "out" / "hash_view.json").exists()
        mid = _read_json(ws / "out" / "hash_view.json")["fprint"]
        assert first == mid
        assert _read_jsonl(ws / "out" / "clash_rows.jsonl"), "clash must remain after second replay"
        _run_cvctl("recover", f"--workspace={ws}")
        second = _read_json(ws / "out" / "hash_view.json")["fprint"]
        assert first == second

    def test_foreign_and_dirty_reconcile(self) -> None:
        """Foreign payloads survive; dirty fast lanes reconcile to slow payloads."""
        ws = _copy_sample("case_b")
        before = _foreign_payload(ws, 88)
        before_fast = _fast_bind_snapshot(ws)
        _workflow(ws, "run_b")
        assert _foreign_payload(ws, 88) == before == "orphan-keep"
        assert _fast_bind_snapshot(ws) == before_fast
        fast1 = _fast_by_bind(ws, 1)
        assert fast1["payload"] == _slow_payload(ws, 1)
        tap = _read_jsonl(ws / "out" / "tap_rows.jsonl")
        assert any(r["payload"] == _slow_payload(ws, 1) for r in tap if r["slot"] == 1)
        assert any(r["tally"] > 0 for r in tap)

    def test_dual_clash_fields(self) -> None:
        """Clash archaeology covers pointer revision and origin path."""
        ws = _copy_sample("case_b")
        _workflow(ws, "run_b")
        clash = _read_jsonl(ws / "out" / "clash_rows.jsonl")
        assert clash, "clash rows required"
        fields = {row["field"] for row in clash}
        assert "ptr" in fields
        assert "origin" in fields
        ptr = next(r for r in clash if r["field"] == "ptr")
        origin = next(r for r in clash if r["field"] == "origin")
        for key in ("field", "was", "now", "rev"):
            assert key in ptr and key in origin
        assert ptr["was"] == "1"
        assert ptr["now"] == "5"
        assert ptr["rev"] >= 5
        assert origin["was"] == "refs/pre_move.json"
        assert origin["now"] == "refs/post_move.json"

    def test_alternate_topology(self) -> None:
        """Alternate sample converges under the same operator workflow."""
        ws = _copy_sample("case_c")
        keeper = _foreign_payload(ws, 77)
        _workflow(ws, "run_c")
        hash_view = _read_json(ws / "out" / "hash_view.json")
        assert hash_view["move"] == 5
        assert hash_view["tag"] == "settled"
        _assert_fprint_matches(hash_view)
        assert _foreign_payload(ws, 77) == keeper
        traces = _read_jsonl(ws / "out" / "row_trace.jsonl")
        bind4 = [r for r in traces if r.get("kind") == "bind" and r.get("slot") == 4]
        assert bind4 and "off=2048" in bind4[0].get("note", "")
        tap = _read_jsonl(ws / "out" / "tap_rows.jsonl")
        assert any(r["tally"] > 0 for r in tap)
        assert _fast_by_bind(ws, 3)["payload"] == _slow_payload(ws, 3)
        vault = _read_json(ws / "state" / "vault.json")
        assert int(vault["seal"]) == 5

    def test_epoch_tie_prefers_origin(self) -> None:
        """Empty dirty writeback settle keeps equal-epoch slow payload over fast cache."""
        ws = _copy_sample("case_d")
        keeper = _foreign_payload(ws, 55)
        before = _fast_bind_snapshot(ws)
        _workflow(ws, "run_d")
        assert _fast_bind_snapshot(ws) == before
        assert _foreign_payload(ws, 55) == keeper
        hash_view = _read_json(ws / "out" / "hash_view.json")
        assert hash_view["tag"] == "settled"
        _assert_fprint_matches(hash_view)
        assert _fast_by_bind(ws, 5)["payload"] == "theta-cache"
        tap = _read_jsonl(ws / "out" / "tap_rows.jsonl")
        assert tap
        assert all(r["payload"] == "theta-origin" for r in tap if r["slot"] == 5)
        assert any(r["tally"] > 0 for r in tap)
        traces = _read_jsonl(ws / "out" / "row_trace.jsonl")
        bind = [r for r in traces if r.get("kind") == "bind" and r.get("slot") == 5]
        assert bind and "off=16384" in bind[0].get("note", "")

    def test_staggered_surfaces_require_seal(self) -> None:
        """Vault already on post-move still lags until alias, active, seal, and quorum join."""
        ws = _copy_sample("case_e")
        events = ENV_ROOT / "samples" / "run_e" / "events.jsonl"
        _run_cvctl("read-replay", f"--workspace={ws}", f"--events={events}")
        pre = _read_jsonl(ws / "out" / "tap_rows.jsonl")
        assert pre
        assert all(r["tally"] == 0 for r in pre)
        assert pre[0]["payload"] == _fast_by_bind(ws, 7)["payload"]
        vault_pre = _read_json(ws / "state" / "vault.json")
        assert vault_pre["ptr_path"] == "refs/post_move.json"
        assert int(vault_pre["seal"]) == 0
        alias_pre = _read_json(ws / "maps" / "origin_alias.json")
        assert alias_pre["path"] == "refs/pre_move.json"
        keeper = _foreign_payload(ws, 66)
        _workflow(ws, "run_e")
        vault = _read_json(ws / "state" / "vault.json")
        alias = _read_json(ws / "maps" / "origin_alias.json")
        active = _read_json(ws / "refs" / "active.json")
        assert int(vault["seal"]) == 6
        assert alias["path"] == "refs/post_move.json"
        assert active["path"] == "refs/post_move.json"
        hash_view = _read_json(ws / "out" / "hash_view.json")
        assert hash_view["tag"] == "settled"
        _assert_fprint_matches(hash_view)
        assert _foreign_payload(ws, 66) == keeper
        assert _fast_by_bind(ws, 7)["payload"] == _slow_payload(ws, 7)
        tap = _read_jsonl(ws / "out" / "tap_rows.jsonl")
        assert any(r["tally"] > 0 for r in tap)
        traces = _read_jsonl(ws / "out" / "row_trace.jsonl")
        bind = [r for r in traces if r.get("kind") == "bind" and r.get("slot") == 7]
        assert bind and "off=32768" in bind[0].get("note", "")

    def test_writethrough_keeps_origin(self) -> None:
        """Writethrough mode serves origin after settle even when cache epoch is newer."""
        ws = _copy_sample("case_f")
        keeper = _foreign_payload(ws, 44)
        before = _fast_bind_snapshot(ws)
        _workflow(ws, "run_f")
        assert _fast_bind_snapshot(ws) == before
        assert _foreign_payload(ws, 44) == keeper
        vault = _read_json(ws / "state" / "vault.json")
        assert vault["mode"] == "writethrough"
        assert int(vault["seal"]) == 2
        assert _fast_by_bind(ws, 9)["payload"] == "wt-cache-hot"
        assert int(_fast_by_bind(ws, 9)["epoch"]) == 9
        hash_view = _read_json(ws / "out" / "hash_view.json")
        assert hash_view["tag"] == "settled"
        _assert_fprint_matches(hash_view)
        tap = _read_jsonl(ws / "out" / "tap_rows.jsonl")
        assert tap
        assert all(r["payload"] == "wt-origin" for r in tap if r["slot"] == 9)
        assert any(r["tally"] > 0 for r in tap)
        traces = _read_jsonl(ws / "out" / "row_trace.jsonl")
        bind = [r for r in traces if r.get("kind") == "bind" and r.get("slot") == 9]
        assert bind and "off=65536" in bind[0].get("note", "")

    def test_partial_dirty_scope_reconcile(self) -> None:
        """Only dirty-listed slots are rewritten on disk; read-replay serves origin for others."""
        ws = _copy_sample("case_h")
        keeper = _foreign_payload(ws, 50)
        before_binds = _fast_bind_snapshot(ws)
        _workflow(ws, "run_h")
        assert _foreign_payload(ws, 50) == keeper == "partial-keep"
        assert _fast_bind_snapshot(ws) == before_binds
        assert _fast_by_bind(ws, 1)["payload"] == _slow_payload(ws, 1) == "slot1-origin"
        assert _fast_payload(ws, 2) == "slot2-stale"
        tap = _read_jsonl(ws / "out" / "tap_rows.jsonl")
        slot2 = [r for r in tap if r["slot"] == 2]
        assert slot2 and slot2[0]["payload"] == "slot2-origin"
        assert any(r["tally"] > 0 for r in tap)
        traces = _read_jsonl(ws / "out" / "row_trace.jsonl")
        bind2 = [r for r in traces if r.get("kind") == "bind" and r.get("slot") == 2]
        assert bind2 and "off=8192" in bind2[0].get("note", "")
        hash_view = _read_json(ws / "out" / "hash_view.json")
        assert hash_view["tag"] == "settled"
        _assert_fprint_matches(hash_view)

    def test_double_replay_while_window_open(self) -> None:
        """Repeated read-replay before recover keeps tally zero and fprint absent."""
        ws = _copy_sample("case_e")
        events = ENV_ROOT / "samples" / "run_e" / "events.jsonl"
        _run_cvctl("read-replay", f"--workspace={ws}", f"--events={events}")
        first = _read_jsonl(ws / "out" / "tap_rows.jsonl")
        assert all(r["tally"] == 0 for r in first)
        _run_cvctl("read-replay", f"--workspace={ws}", f"--events={events}")
        second = _read_jsonl(ws / "out" / "tap_rows.jsonl")
        assert all(r["tally"] == 0 for r in second)
        assert not (ws / "out" / "hash_view.json").exists()
        _run_cvctl("recover", f"--workspace={ws}")
        _run_cvctl("read-replay", f"--workspace={ws}", f"--events={events}")
        tap = _read_jsonl(ws / "out" / "tap_rows.jsonl")
        assert any(r["tally"] > 0 for r in tap)
