import json
import os
import shutil
import subprocess

APP = "/app"
SIM_SRC = "/tests/sim"
SIM_DST = "/app/simdrv"
OUT = "/app/simout"
SEEDS = "/tests/seeds/hidden.txt"


def _build():
    if os.path.isdir(SIM_DST):
        shutil.rmtree(SIM_DST)
    shutil.copytree(SIM_SRC, SIM_DST)
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    srcs = []
    for root in (os.path.join(APP, "src"), SIM_DST):
        for name in os.listdir(root):
            if name.endswith(".java"):
                srcs.append(os.path.join(root, name))
    return subprocess.run(
        ["javac", "-d", OUT] + srcs,
        cwd=APP,
        capture_output=True,
        text=True,
    )


BUILD = _build()


def run_sim(mode, seed, nodes, impl="agent"):
    assert BUILD.returncode == 0, "sim build failed: " + BUILD.stderr[-3000:]
    proc = subprocess.run(
        ["java", "-cp", OUT, "sim.Main", mode, str(seed), str(nodes), impl],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, "sim run failed: " + proc.stderr[-3000:]
    lines = proc.stdout.strip().splitlines()
    assert lines, "sim produced no verdict"
    return json.loads(lines[-1])


def violation(mode, seed, nodes, impl="agent"):
    return run_sim(mode, seed, nodes, impl)["violation"]


def clean(mode, seed, nodes, impl="agent"):
    return violation(mode, seed, nodes, impl) is None


def opa(seed):
    return 100 + seed % 17


def opb(seed):
    return 200 + seed % 17


def load_hidden():
    rows = []
    with open(SEEDS) as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            rows.append((parts[0], int(parts[1]), int(parts[2])))
    return rows


HIDDEN = load_hidden()

# Crash-restart families (oracle clean; a returning replica must re-acquire state
# from a majority before it counts). Reorder is excluded from baseline "loses"
# assertions because message shuffling perturbs which peer answers first.
RESTART_DETERMINISTIC = [
    ("restart", 90401, 5),
    ("restart", 90402, 7),
    ("restart", 90403, 3),
    ("restart_small", 90407, 3),
    ("restart_wide", 90406, 7),
    ("restart_b2b", 90408, 5),
    ("restart_b2b", 90409, 7),
    ("restart_forge", 90410, 5),
    ("restart_forge", 90411, 7),
    ("restart_replay", 90413, 5),
    ("restart_replay", 90414, 7),
    ("recover_replay", 90415, 5),
    ("recover_replay", 90416, 7),
    ("recover_replay", 90417, 3),
    ("restart", 90418, 9),
    ("restart", 90419, 11),
    ("restart_wide", 90422, 9),
    ("restart_b2b", 90423, 9),
    ("restart_forge", 90424, 9),
    ("restart_replay", 90425, 9),
    ("recover_replay", 90426, 9),
    ("recover_replay", 90427, 5),
]

# Forge families: a forged view-change lies about how current its state is.
FORGE_FAMILY = [
    ("forge", 90201, 5),
    ("forge", 90202, 7),
    ("forge_reorder", 90203, 5),
    ("forge_wide", 90204, 7),
    ("forge_small", 90205, 3),
    ("restart_forge", 90410, 5),
    ("restart_forge", 90411, 7),
    ("forge", 90210, 9),
    ("forge", 90211, 5),
    ("forge_wide", 90212, 9),
    ("forge_reorder", 90213, 7),
    ("restart_forge", 90424, 9),
]

# Replay families: the transport duplicates one genuine sender's vote.
REPLAY_FAMILY = [
    ("replay", 90301, 5),
    ("replay", 90302, 7),
    ("replay_reorder", 90303, 5),
    ("replay_b2b", 90304, 5),
    ("replay_b2b", 90305, 7),
    ("restart_replay", 90413, 5),
    ("restart_replay", 90414, 7),
    ("replay", 90310, 9),
    ("replay", 90311, 7),
    ("replay_b2b", 90312, 9),
    ("replay_reorder", 90313, 7),
    ("restart_replay", 90425, 9),
]

# View-change families that a serve-your-own-log replica loses.
VIEWCHANGE_FAMILY = [
    ("failover", 90101, 5),
    ("failover", 90102, 7),
    ("failover", 90105, 3),
    ("failover_reorder", 90103, 5),
    ("failover_b2b", 90104, 5),
    ("forge", 90201, 5),
    ("replay", 90301, 5),
    ("failover", 90120, 9),
    ("failover", 90121, 11),
    ("failover_reorder", 90122, 7),
    ("failover_b2b", 90123, 9),
]

NONFAULT = [
    ("control", 90108, 5),
    ("clean", 90106, 5),
    ("minority", 90107, 5),
    ("control", 90130, 9),
    ("clean", 90132, 9),
    ("clean_reorder", 90133, 9),
    ("minority", 90134, 9),
]

# Replayed-acknowledgement families: a genuine vote captured from a replica's
# earlier life is resurfaced after that replica has come back empty.
STALE_ACK_FAMILY = [
    ("stale_ack", 5550, 3),
    ("stale_ack", 5551, 5),
    ("stale_ack", 5552, 7),
    ("stale_ack_wide", 5553, 7),
    ("stale_ack_wide", 5554, 5),
    ("stale_ack_reorder", 5555, 5),
    ("stale_ack_reorder", 5556, 7),
    ("stale_ack_reorder", 5557, 3),
    ("stale_ack", 5560, 9),
    ("stale_ack_wide", 5561, 9),
    ("stale_ack_reorder", 5562, 9),
    ("stale_ack", 5563, 5),
    ("stale_ack_reorder", 5564, 3),
]


# ---------------------------------------------------------------------------
# Oracle: the reference implementation must survive every shipped schedule.
# ---------------------------------------------------------------------------


def test_oracle_hidden_battery_all_clean():
    """Every hidden benign and adversarial schedule reports no violation for the agent."""
    for mode, seed, nodes in HIDDEN:
        assert clean(mode, seed, nodes), (mode, seed, nodes)


def test_oracle_control_commits_three_ops_in_order():
    """The fault-free control commits three distinct client ops in their submitted order."""
    assert run_sim("control", 1, 5)["committed"] == [41, 42, 43]


def test_oracle_failover_order_preserved_seed_2():
    """The recovered log keeps the committed ops in original order across a failover."""
    assert run_sim("failover", 2, 5)["committed"] == [41, opa(2), opb(2)]


def test_oracle_failover_preserves_excluded_op_seed_4():
    """An op committed to a quorum without the new primary survives the failover."""
    assert opa(4) in run_sim("failover", 4, 5)["committed"]


def test_oracle_failover_acked_subset_of_committed_seed_3():
    """Every acknowledged op remains in the committed log after a failover."""
    verdict = run_sim("failover", 3, 5)
    assert set(verdict["acked"]).issubset(set(verdict["committed"]))


def test_oracle_failover_wide_preserves_op_seed_34():
    """The excluded-quorum op survives a seven-replica failover."""
    assert opa(34) in run_sim("failover", 34, 7)["committed"]


def test_oracle_failover_small_survives_seed_41():
    """A committed op survives a three-replica failover."""
    assert clean("failover", 41, 3)


def test_oracle_failover_b2b_reaches_second_view_seed_23():
    """Back to back view changes advance the group past the first new view."""
    assert run_sim("failover_b2b", 23, 5)["maxView"] >= 2


def test_oracle_forge_preserves_op_seed_4():
    """A committed op survives despite a forged truncated view-change message."""
    assert opa(4) in run_sim("forge", 4, 5)["committed"]


def test_oracle_forge_commits_new_op_seed_6():
    """New operations still commit after a forged message is turned away."""
    assert opb(6) in run_sim("forge", 6, 5)["committed"]


def test_oracle_replay_preserves_op_seed_5():
    """A committed op survives replayed duplicate view-change messages."""
    assert opa(5) in run_sim("replay", 5, 5)["committed"]


def test_oracle_replay_b2b_preserves_op_seed_6():
    """The committed op survives replayed duplicates across back to back view changes."""
    assert opa(6) in run_sim("replay_b2b", 6, 5)["committed"]


def test_oracle_restart_preserves_stored_op():
    """An op stored by a restarted holder survives once recovery re-acquires it."""
    for mode, seed, nodes in [
        ("restart", 90401, 5),
        ("restart", 90402, 7),
        ("restart", 90403, 3),
        ("restart_wide", 90406, 7),
        ("restart_small", 90407, 3),
    ]:
        assert opa(seed) in run_sim(mode, seed, nodes)["committed"], (mode, seed, nodes)


def test_oracle_restart_makes_progress_after_heal():
    """A fresh op commits after a crash, recovery, and view change complete."""
    for mode, seed, nodes in [
        ("restart", 90401, 5),
        ("restart", 90402, 7),
        ("restart_b2b", 90408, 5),
    ]:
        verdict = run_sim(mode, seed, nodes)
        assert opb(seed) in verdict["acked"], (mode, seed, nodes)


def test_oracle_restart_forge_preserves_op():
    """A stored op survives a crash-restart with a forged view-change in the same window."""
    for mode, seed, nodes in [("restart_forge", 90410, 5), ("restart_forge", 90411, 7)]:
        assert opa(seed) in run_sim(mode, seed, nodes)["committed"], (mode, seed, nodes)


def test_oracle_restart_replay_preserves_op():
    """A stored op survives a crash-restart with replayed votes in the same window."""
    for mode, seed, nodes in [
        ("restart_replay", 90413, 5),
        ("restart_replay", 90414, 7),
    ]:
        assert opa(seed) in run_sim(mode, seed, nodes)["committed"], (mode, seed, nodes)


def test_oracle_recover_replay_preserves_op():
    """A stored op survives two crashes where stale recovery answers are replayed."""
    for mode, seed, nodes in [
        ("recover_replay", 90415, 5),
        ("recover_replay", 90416, 7),
        ("recover_replay", 90417, 3),
    ]:
        assert opa(seed) in run_sim(mode, seed, nodes)["committed"], (mode, seed, nodes)


def test_oracle_restart_acked_all_survive():
    """Across the crash-restart battery every acknowledged op stays committed for the agent."""
    for mode, seed, nodes in RESTART_DETERMINISTIC:
        verdict = run_sim(mode, seed, nodes)
        assert set(verdict["acked"]).issubset(set(verdict["committed"])), (
            mode,
            seed,
            nodes,
        )


def test_oracle_stale_ack_family_all_clean():
    """The agent survives the replayed-acknowledgement schedule at every width and reordering."""
    for mode, seed, nodes in STALE_ACK_FAMILY:
        assert clean(mode, seed, nodes), (mode, seed, nodes)


def test_oracle_stale_ack_op_absent_from_committed():
    """The op backed only by a resurfaced acknowledgement never enters the agent's committed log."""
    for mode, seed, nodes in [("stale_ack", 5551, 5), ("stale_ack_wide", 5553, 7)]:
        assert 150 + seed % 17 not in run_sim(mode, seed, nodes)["committed"], (
            mode,
            seed,
            nodes,
        )


def test_oracle_single_primary_everywhere():
    """No view ever sees two primaries for the agent across the whole battery."""
    for mode, seed, nodes in HIDDEN:
        assert run_sim(mode, seed, nodes)["violation"] != "two_primaries", (
            mode,
            seed,
            nodes,
        )


def test_oracle_determinism_repeatable():
    """The same seed yields an identical verdict across three independent runs."""
    for mode, seed, nodes in [
        ("failover", 4, 5),
        ("forge", 6, 5),
        ("replay", 5, 5),
        ("restart", 90401, 5),
        ("restart_b2b", 90408, 7),
        ("recover_replay", 90415, 5),
        ("restart_small", 90407, 3),
        ("restart_wide", 90406, 7),
    ]:
        first = run_sim(mode, seed, nodes)
        again = run_sim(mode, seed, nodes)
        third = run_sim(mode, seed, nodes)
        assert first == again == third, (mode, seed, nodes)


# ---------------------------------------------------------------------------
# norecover: recovers nothing, rejoins immediately as an ordinary replica.
# Fails ONLY the crash-restart families.
# ---------------------------------------------------------------------------


def test_norecover_loses_crash_restart_families():
    """A replica that skips recovery drops the stored op on every crash-restart schedule."""
    for mode, seed, nodes in RESTART_DETERMINISTIC:
        assert violation(mode, seed, nodes, "norecover") == "committed_op_lost", (
            mode,
            seed,
            nodes,
        )


def test_norecover_loses_restart_reorder():
    """The no-recovery replica also drops the op when the crash-restart run reorders."""
    for seed, nodes in [(90404, 5), (90405, 7)]:
        assert (
            violation("restart_reorder", seed, nodes, "norecover")
            == "committed_op_lost"
        )


def test_norecover_missing_stored_op():
    """The dropped op is absent from the no-recovery replica's committed log."""
    for mode, seed, nodes in [("restart", 90401, 5), ("recover_replay", 90415, 5)]:
        assert opa(seed) not in run_sim(mode, seed, nodes, "norecover")["committed"]


def test_norecover_passes_view_change_families():
    """The no-recovery replica is exposed only by restarts, not by ordinary view changes."""
    for mode, seed, nodes in VIEWCHANGE_FAMILY:
        assert clean(mode, seed, nodes, "norecover"), (mode, seed, nodes)


def test_norecover_passes_nonfault():
    """The no-recovery replica commits cleanly with no adversary present."""
    for mode, seed, nodes in NONFAULT:
        assert clean(mode, seed, nodes, "norecover"), (mode, seed, nodes)


# ---------------------------------------------------------------------------
# onepeer: recovers, but installs the first answer instead of a majority.
# The first responder is a deterministic non-holder, so it adopts a stale log.
# ---------------------------------------------------------------------------


def test_onepeer_loses_crash_restart_families():
    """Installing one peer's answer instead of a majority drops the stored op."""
    for mode, seed, nodes in RESTART_DETERMINISTIC:
        assert violation(mode, seed, nodes, "onepeer") == "committed_op_lost", (
            mode,
            seed,
            nodes,
        )


def test_onepeer_missing_stored_op():
    """The op the first responder never held is absent from the onepeer committed log."""
    for mode, seed, nodes in [("restart", 90401, 5), ("restart_small", 90407, 3)]:
        assert opa(seed) not in run_sim(mode, seed, nodes, "onepeer")["committed"]


def test_onepeer_passes_view_change_families():
    """The single-answer recovery replica handles ordinary view changes correctly."""
    for mode, seed, nodes in VIEWCHANGE_FAMILY:
        assert clean(mode, seed, nodes, "onepeer"), (mode, seed, nodes)


def test_onepeer_passes_nonfault():
    """The single-answer recovery replica commits cleanly with no adversary present."""
    for mode, seed, nodes in NONFAULT:
        assert clean(mode, seed, nodes, "onepeer"), (mode, seed, nodes)


# ---------------------------------------------------------------------------
# stale: recovers from a majority, but accepts an answer not bound to the
# challenge it raised this time. Fails ONLY the replayed-recovery family.
# ---------------------------------------------------------------------------


def test_stale_loses_only_recover_replay():
    """Accepting an unbound recovery answer drops the op when stale answers are replayed."""
    for mode, seed, nodes in [
        ("recover_replay", 90415, 5),
        ("recover_replay", 90416, 7),
        ("recover_replay", 90417, 3),
    ]:
        assert violation(mode, seed, nodes, "stale") == "committed_op_lost", (
            mode,
            seed,
            nodes,
        )


def test_stale_recover_replay_contrast_with_oracle():
    """On the replayed-recovery schedule the agent stays clean while the stale replica is flagged."""
    assert clean("recover_replay", 90415, 5)
    assert violation("recover_replay", 90415, 5, "stale") == "committed_op_lost"


def test_stale_passes_single_restart_families():
    """A single crash-restart without replayed answers does not expose the stale replica."""
    for mode, seed, nodes in [
        ("restart", 90401, 5),
        ("restart", 90402, 7),
        ("restart_small", 90407, 3),
        ("restart_wide", 90406, 7),
        ("restart_forge", 90410, 5),
        ("restart_replay", 90413, 5),
    ]:
        assert clean(mode, seed, nodes, "stale"), (mode, seed, nodes)


def test_stale_passes_view_change_families():
    """The stale replica handles ordinary view changes correctly."""
    for mode, seed, nodes in VIEWCHANGE_FAMILY:
        assert clean(mode, seed, nodes, "stale"), (mode, seed, nodes)


def test_stale_passes_nonfault():
    """The stale replica commits cleanly with no adversary present."""
    for mode, seed, nodes in NONFAULT:
        assert clean(mode, seed, nodes, "stale"), (mode, seed, nodes)


# ---------------------------------------------------------------------------
# noverify: skips authentication. Fails ONLY the forge families.
# ---------------------------------------------------------------------------


def test_noverify_loses_forge_families():
    """A replica that skips authentication adopts a forged log and drops the committed op."""
    for mode, seed, nodes in FORGE_FAMILY:
        assert violation(mode, seed, nodes, "noverify") == "committed_op_lost", (
            mode,
            seed,
            nodes,
        )


def test_noverify_missing_op_forge():
    """The dropped op is absent from the unauthenticated committed log."""
    for mode, seed, nodes in [("forge", 4, 5), ("forge_small", 2, 3)]:
        assert opa(seed) not in run_sim(mode, seed, nodes, "noverify")["committed"]


def test_noverify_passes_failover_and_replay():
    """The unauthenticated replica is exposed only by forgery, not by failover or replay."""
    for mode, seed, nodes in [
        ("failover", 4, 5),
        ("replay", 5, 5),
        ("replay_b2b", 6, 5),
    ]:
        assert clean(mode, seed, nodes, "noverify"), (mode, seed, nodes)


def test_noverify_passes_plain_restart():
    """The unauthenticated replica handles a crash-restart without forgery correctly."""
    for mode, seed, nodes in [
        ("restart", 90401, 5),
        ("restart_replay", 90413, 5),
        ("recover_replay", 90415, 5),
    ]:
        assert clean(mode, seed, nodes, "noverify"), (mode, seed, nodes)


def test_noverify_passes_nonfault():
    """The unauthenticated replica commits cleanly with no adversary present."""
    for mode, seed, nodes in NONFAULT:
        assert clean(mode, seed, nodes, "noverify"), (mode, seed, nodes)


# ---------------------------------------------------------------------------
# replay: counts duplicate senders. Fails ONLY the replay families.
# ---------------------------------------------------------------------------


def test_replaydup_loses_replay_families():
    """A replica that counts duplicate senders reaches a false majority and drops the op."""
    for mode, seed, nodes in REPLAY_FAMILY:
        assert violation(mode, seed, nodes, "replay") == "committed_op_lost", (
            mode,
            seed,
            nodes,
        )


def test_replaydup_missing_op():
    """The dropped op is absent from the duplicate-counting committed log."""
    assert opa(5) not in run_sim("replay", 5, 5, "replay")["committed"]


def test_replaydup_passes_forge_and_failover():
    """The duplicate-counting replica is exposed only by replay, not by forgery or failover."""
    for mode, seed, nodes in [
        ("forge", 4, 5),
        ("failover", 4, 5),
        ("failover_b2b", 90104, 5),
    ]:
        assert clean(mode, seed, nodes, "replay"), (mode, seed, nodes)


def test_replaydup_passes_plain_restart():
    """The duplicate-counting replica handles a crash-restart without replayed votes."""
    for mode, seed, nodes in [("restart", 90401, 5), ("restart_forge", 90410, 5)]:
        assert clean(mode, seed, nodes, "replay"), (mode, seed, nodes)


# ---------------------------------------------------------------------------
# naive: serves its own log the instant it sees a view-change quorum.
# Loses the excluded-quorum op across every view change.
# ---------------------------------------------------------------------------


def test_naive_loses_view_change_families():
    """The serve-immediately replica drops the excluded-quorum op across view changes."""
    for mode, seed, nodes in VIEWCHANGE_FAMILY:
        assert violation(mode, seed, nodes, "naive") == "committed_op_lost", (
            mode,
            seed,
            nodes,
        )


def test_naive_loses_restart_family():
    """The serve-immediately replica also drops the stored op across a crash-restart."""
    for mode, seed, nodes in [("restart", 90401, 5), ("recover_replay", 90415, 5)]:
        assert violation(mode, seed, nodes, "naive") == "committed_op_lost", (
            mode,
            seed,
            nodes,
        )


def test_naive_passes_nonfault():
    """The serve-immediately replica commits cleanly with no view change."""
    for mode, seed, nodes in NONFAULT:
        assert clean(mode, seed, nodes, "naive"), (mode, seed, nodes)


# ---------------------------------------------------------------------------
# dual: self-appoints as primary. Produces two primaries in one view.
# ---------------------------------------------------------------------------


def test_dual_two_primaries_view_change_families():
    """A self-appointing replica produces two primaries under every view change."""
    for mode, seed, nodes in VIEWCHANGE_FAMILY:
        assert violation(mode, seed, nodes, "dual") == "two_primaries", (
            mode,
            seed,
            nodes,
        )


def test_dual_passes_nonfault():
    """The self-appointing replica commits cleanly when no view change occurs."""
    for mode, seed, nodes in [("control", 90108, 5), ("minority", 90107, 5)]:
        assert clean(mode, seed, nodes, "dual"), (mode, seed, nodes)


# ---------------------------------------------------------------------------
# frozen: never changes view. Stalls progress once the primary is isolated.
# ---------------------------------------------------------------------------


def test_frozen_no_progress_view_change_families():
    """A replica that never changes view stalls progress after the primary is isolated."""
    for mode, seed, nodes in [
        ("failover", 90101, 5),
        ("forge", 90201, 5),
        ("replay", 90301, 5),
    ]:
        assert violation(mode, seed, nodes, "frozen") == "no_progress", (
            mode,
            seed,
            nodes,
        )


def test_frozen_passes_control():
    """The never-change-view replica commits cleanly under the fault-free control."""
    assert clean("control", 90108, 5, "frozen")


# ---------------------------------------------------------------------------
# mute: refuses client ops. Never commits anything.
# ---------------------------------------------------------------------------


def test_mute_no_progress_control():
    """A replica that refuses client ops never commits under the control."""
    assert violation("control", 1, 5, "mute") == "no_progress"


def test_mute_commits_nothing():
    """The refusing replica leaves the committed log empty under the control."""
    assert run_sim("control", 1, 5, "mute")["committed"] == []


# ---------------------------------------------------------------------------
# noincarn: counts an acknowledgement without regard to which life of a replica
# produced it. Fails ONLY the replayed-acknowledgement families.
# ---------------------------------------------------------------------------


def test_noincarn_loses_stale_ack_family():
    """Counting a resurfaced acknowledgement commits an op held by no live majority."""
    for mode, seed, nodes in STALE_ACK_FAMILY:
        assert violation(mode, seed, nodes, "noincarn") == "committed_op_lost", (
            mode,
            seed,
            nodes,
        )


def test_noincarn_passes_non_stale_ack_families():
    """The life-agnostic replica is exposed only by replayed acknowledgements, not other schedules."""
    for mode, seed, nodes in VIEWCHANGE_FAMILY + RESTART_DETERMINISTIC + NONFAULT:
        assert clean(mode, seed, nodes, "noincarn"), (mode, seed, nodes)


# ---------------------------------------------------------------------------
# Structural checks.
# ---------------------------------------------------------------------------


def test_simulator_build_succeeded():
    """The verifier simulator compiled against the agent implementation."""
    assert BUILD.returncode == 0, BUILD.stderr[-3000:]


def test_verdict_report_is_populated():
    """A failover run yields a populated verdict rather than an empty report."""
    verdict = run_sim("failover", 1, 5)
    assert verdict["ran"] is True
    assert isinstance(verdict["committed"], list)
    assert len(verdict["acked"]) >= 1
