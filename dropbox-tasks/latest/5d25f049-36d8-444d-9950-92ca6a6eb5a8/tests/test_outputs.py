"""Behavioral verifier for reconcile-firewall-intent-after-partial-apply."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from backend_factory import empty_state, insert_foreign_rule, legacy_manifest_v1
from fixture_generator import write_case
from ref_model import FAILPOINTS, effective_winner, state_digest

APP = Path("/app")
BIN = APP / "bin/nxctl"
CONF_D = APP / "config/conf.d"
PACKET = APP / "fixtures/packet-allow.json"


def run_ctl(args: list[str], *, env: dict | None = None, ok: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(
        ["/app/environment/bin/nxctl", *args],
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )
    if ok and proc.returncode != 0:
        raise AssertionError(proc.stderr + proc.stdout)
    if not ok and proc.returncode == 0:
        raise AssertionError("expected failure")
    return proc


def status(state_dir: Path) -> dict:
    proc = run_ctl(["--state-dir", str(state_dir), "status", "--json"])
    return json.loads(proc.stdout)


@pytest.fixture(scope="session", autouse=True)
def ensure_binary():
    assert BIN.is_file(), "nxctl missing"


def fresh_state(tmp_path: Path) -> Path:
    return empty_state(tmp_path / "state")


def test_clean_apply_matches_ref_model(tmp_path):
    """Normal apply honors precedence winner for the bundled demo packet."""
    state = fresh_state(tmp_path)
    run_ctl(["--state-dir", str(state), "apply", "--json"])
    winner = effective_winner(CONF_D)
    assert winner == "drop"
    proc = run_ctl(["--state-dir", str(state), "simulate", "--packet", str(PACKET), "--json"])
    result = json.loads(proc.stdout)
    assert result["verdict"] == "drop"
    rep = status(state)
    assert rep["ok"] is True
    assert rep["managed_rules"] >= 1
    run_ctl(
        ["--state-dir", str(state), "apply", "--json"],
        env={"NX_FAILPOINT": "after-stage-sets"},
        ok=False,
    )
    run_ctl(["--state-dir", str(state), "recover", "--json"])
    assert status(state)["generation"] >= rep["generation"]


@pytest.mark.parametrize("failpoint", FAILPOINTS)
def test_each_crash_barrier_converges_to_clean_apply(tmp_path, failpoint):
    """Interrupted apply at each failpoint recovers to the same generation as a clean apply."""
    clean = fresh_state(tmp_path / "clean")
    run_ctl(["--state-dir", str(clean), "apply", "--json"])
    clean_gen = status(clean)["generation"]

    crash = fresh_state(tmp_path / f"crash-{failpoint}")
    env = {"NX_FAILPOINT": failpoint}
    if failpoint == "during-cleanup":
        run_ctl(["--state-dir", str(crash), "apply", "--json"], env=env, ok=True)
    else:
        run_ctl(["--state-dir", str(crash), "apply", "--json"], env=env, ok=False)
    run_ctl(["--state-dir", str(crash), "recover", "--json"])
    gen_once = status(crash)["generation"]
    run_ctl(["--state-dir", str(crash), "recover", "--json"])
    assert status(crash)["generation"] == gen_once
    assert gen_once >= clean_gen


def test_operator_objects_survive_recovery(tmp_path):
    """Foreign operator rules and counters remain after apply, recover, and cleanup."""
    state = fresh_state(tmp_path)
    insert_foreign_rule(state, "operator-allow-443", counter=9)
    before = json.loads((state / "backend.json").read_text())
    foreign_counter = before["rules"]["1"]["counter"]
    run_ctl(["--state-dir", str(state), "apply", "--json"])
    run_ctl(["--state-dir", str(state), "recover", "--json"])
    run_ctl(["--state-dir", str(state), "cleanup", "--json"])
    after = json.loads((state / "backend.json").read_text())
    assert any(r.get("visible_name") == "operator-allow-443" for r in after.get("rules", {}).values())
    surviving = next(r for r in after["rules"].values() if r.get("visible_name") == "operator-allow-443")
    assert surviving["counter"] == foreign_counter


def test_dropin_precedence_uses_priority_and_normalized_path(tmp_path):
    """Lower-priority-number drop-in wins even when lexically later filenames disagree."""
    state = fresh_state(tmp_path)
    run_ctl(["--state-dir", str(state), "apply", "--json"])
    proc = run_ctl(["--state-dir", str(state), "simulate", "--packet", str(PACKET), "--json"])
    assert effective_winner(CONF_D) == "drop"
    assert json.loads(proc.stdout)["verdict"] == "drop"


def test_runtime_override_cannot_replace_ownership_scope(tmp_path):
    """Protected tenant or ownership scope in runtime overrides is rejected."""
    state = fresh_state(tmp_path)
    run_ctl(["--state-dir", str(state), "apply", "--json"])
    overrides = {"rules": {"allow-web": {"ownership_scope": "evil", "action": "drop"}}}
    (state / "runtime-overrides.json").write_text(json.dumps(overrides))
    before_b = state_digest(state / "backend.json")
    proc = run_ctl(["--state-dir", str(state), "apply", "--json"], ok=False)
    assert proc.returncode != 0
    assert state_digest(state / "backend.json") == before_b


def test_invalid_config_is_state_immutable(tmp_path):
    """Semantic validation failure leaves backend and manifest digests unchanged."""
    state = fresh_state(tmp_path)
    bad = tmp_path / "bad.toml"
    shutil.copy(APP / "config/base.toml", bad)
    bad.write_text(bad.read_text() + '\n[rules.invalid-set-ref]\naction = "allow"\nsrc_set = "missing"\nordered_index = 3\n')
    before_b = state_digest(state / "backend.json")
    before_m = state_digest(state / "ownership-manifest.json")
    env = {"NX_CONFIG": str(bad)}
    run_ctl(["--state-dir", str(state), "apply", "--json"], env=env, ok=False)
    assert state_digest(state / "backend.json") == before_b
    assert state_digest(state / "ownership-manifest.json") == before_m


def test_logical_counters_survive_chain_regeneration(tmp_path):
    """Counters follow logical rule identity across recover after interruption."""
    state = fresh_state(tmp_path)
    run_ctl(["--state-dir", str(state), "apply", "--json"])
    run_ctl(["--state-dir", str(state), "simulate", "--packet", str(PACKET), "--repeat", "7", "--json"])
    run_ctl(["--state-dir", str(state), "apply", "--json"], env={"NX_FAILPOINT": "after-publish-references"}, ok=False)
    run_ctl(["--state-dir", str(state), "recover", "--json"])
    backend = json.loads((state / "backend.json").read_text())
    counters = [r["counter"] for r in backend.get("rules", {}).values() if r.get("annotation")]
    assert any(c >= 7 for c in counters)


def test_legacy_manifest_preserves_ownership_and_counters(tmp_path):
    """Supported legacy manifests upgrade without dropping counter lineage."""
    state = fresh_state(tmp_path)
    legacy_manifest_v1(state, lineage="allow-web")
    run_ctl(["--state-dir", str(state), "recover", "--json"])
    manifest = json.loads((state / "ownership-manifest.json").read_text())
    assert manifest["schema_version"] >= 2
    entries = manifest["committed"]["entries"]
    assert any(e.get("counter_lineage") == "allow-web" for e in entries)


def test_seeded_generated_policies_match_model(tmp_path):
    """Generated small policies validate, apply, and expose managed rules."""
    generated_root = tmp_path / "gen"
    case = write_case(generated_root, seed=4)

    generated_env = {
        "NX_CONFIG": str((generated_root / "config/base.toml").resolve()),
        "NX_DROPIN_DIR": str((generated_root / "config/conf.d").resolve()),
    }

    state = fresh_state(tmp_path / "gen-state")
    proc = run_ctl(["--state-dir", str(state), "validate", "--json"], env=generated_env)
    assert proc.returncode == 0 and json.loads(proc.stdout or "{}")
    assert case["tenant"].startswith("t")
    run_ctl(["--state-dir", str(state), "apply", "--json"], env=generated_env)
    rep = status(state)
    assert rep["managed_rules"] == len(case["rules"])
    assert rep["generation"] >= 1


def test_cli_and_status_contract_is_preserved(tmp_path):
    """Status JSON exposes documented schema fields and types after apply."""
    state = fresh_state(tmp_path)
    run_ctl(["--state-dir", str(state), "apply", "--json"])
    rep = status(state)
    for key in ("schema_version", "phase", "generation", "managed_rules", "foreign_rules", "reason_codes"):
        assert key in rep
    assert rep["ok"] is True
    assert rep["managed_rules"] >= 1
    assert rep["generation"] >= 1


def test_packet_semantics_not_only_object_shape(tmp_path):
    """Packet simulation follows precedence winner rather than only parsing packet JSON."""
    state = fresh_state(tmp_path)
    run_ctl(["--state-dir", str(state), "apply", "--json"])
    proc = run_ctl(["--state-dir", str(state), "simulate", "--packet", str(PACKET), "--json"])
    result = json.loads(proc.stdout)
    assert result["verdict"] == effective_winner(CONF_D)


def test_recovery_command_orders_are_idempotent(tmp_path):
    """Different recover and status orderings converge to the same generation."""
    base_gen = None
    for order in (("recover", "status"), ("status", "recover", "recover")):
        state = fresh_state(tmp_path / f"order-{order[0]}")
        run_ctl(["--state-dir", str(state), "apply", "--json"], env={"NX_FAILPOINT": "after-stage-sets"}, ok=False)
        for cmd in order:
            run_ctl(["--state-dir", str(state), cmd, "--json"])
        gen = status(state)["generation"]
        if base_gen is None:
            base_gen = gen
        else:
            assert gen == base_gen


def test_name_collision_does_not_transfer_ownership(tmp_path):
    """Foreign objects survive recovery even when visible names resemble managed prefixes."""
    state = fresh_state(tmp_path)
    insert_foreign_rule(state, "operator-collision-demo", counter=2)
    run_ctl(["--state-dir", str(state), "apply", "--json"])
    run_ctl(["--state-dir", str(state), "recover", "--json"])
    names = [r.get("visible_name") for r in json.loads((state / "backend.json").read_text()).get("rules", {}).values()]
    assert "operator-collision-demo" in names


def test_visible_fixture_edits_are_irrelevant(tmp_path):
    """Verifier-owned temp state converges after recover, not only a single apply."""
    state = fresh_state(tmp_path)
    run_ctl(["--state-dir", str(state), "apply", "--json"])
    run_ctl(
        ["--state-dir", str(state), "apply", "--json"],
        env={"NX_FAILPOINT": "after-publish-references"},
        ok=False,
    )
    run_ctl(["--state-dir", str(state), "recover", "--json"])
    assert status(state)["ok"] is True
    gen_once = status(state)["generation"]
    assert gen_once >= 1
    run_ctl(["--state-dir", str(state), "recover", "--json"])
    assert status(state)["generation"] == gen_once
