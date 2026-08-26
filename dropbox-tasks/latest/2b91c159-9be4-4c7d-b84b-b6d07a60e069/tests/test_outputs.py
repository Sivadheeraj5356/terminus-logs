"""Pytest gates for the neighbor-list-boundary recovery verifier."""

from __future__ import annotations

import os
import subprocess

VERIFIER_SRC = "/tests/verifier_main.rs"
VERIFIER_BIN = "/tmp/nlb_grade_harness"


def _compile_harness() -> None:
    compile_proc = subprocess.run(
        ["rustc", VERIFIER_SRC, "-O", "-o", VERIFIER_BIN],
        capture_output=True,
        text=True,
        check=False,
    )
    assert compile_proc.returncode == 0, compile_proc.stderr


def _run_gate(gate: str) -> None:
    env = {**os.environ, "NLB_GATE": gate}
    run_proc = subprocess.run(
        [VERIFIER_BIN],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert run_proc.returncode == 0, run_proc.stdout + run_proc.stderr


def test_nlb_core_matrix_contract() -> None:
    """Scrambled emit matrix and composite digest must match the grade model."""
    _compile_harness()
    _run_gate("scrambled_full_matrix,composite_digest_lock,exact_ledger_pair_gaps")


def test_nlb_checkpoint_ledger_contract() -> None:
    """Pause/resume trials, trace agreement, and ledger gaps must stay coupled."""
    _compile_harness()
    _run_gate("trace_emit_agreement,pause_vs_continuous_separation,rebuild_after_every_token")


def test_nlb_journal_replay_contract() -> None:
    """Journal freeze/thaw replay must byte-match direct emit on checkpoint trials."""
    _compile_harness()
    _run_gate("journal_thaw_replay_agreement,segment_generation_checkpoint_only")


def test_nlb_delayed_validation_contract() -> None:
    """Journal CRC, wrap epoch fold, and refresh stamps reject partial ledger-only fixes."""
    _compile_harness()
    _run_gate("journal_crc_partial_fix_trap,refresh_stamp_exact_on_pause_trials")


def test_nlb_runtime_invariants() -> None:
    """Determinism, addon isolation, path independence, and scalar bands must hold."""
    _compile_harness()
    _run_gate(
        "determinism_all_modes,addon_isolated_to_q5,alternate_output_paths,scalar_band_invariants,default_output_path"
    )
