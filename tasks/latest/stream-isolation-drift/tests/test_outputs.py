import json
import os
import shutil
import subprocess
from pathlib import Path

OUTPUT = Path("/app/output")
TRANSCRIPT = OUTPUT / "run_transcript.jsonl"
PASSES = OUTPUT / "pass_records"
VAULT_MANIFEST = OUTPUT / "vault" / "manifest.json"
PLAN = Path("/app/environment/plans/tiny.toml")
HALT_PLAN = Path("/app/environment/plans/mid_halt.toml")
HALT_SPLIT_PLAN = Path("/app/environment/plans/mid_halt_split.toml")
BIN = "/app/environment/target/release/diffkit"
WINDOW = 4
SEED = 41
GAUGE_CEILING = 48.0

_BUILT = False


def ensure_built() -> None:
    global _BUILT
    if _BUILT and Path(BIN).exists():
        return
    subprocess.run(
        [
            "/usr/local/cargo/bin/cargo",
            "build",
            "--release",
            "--locked",
            "--offline",
            "--manifest-path",
            "/app/environment/Cargo.toml",
        ],
        check=True,
        cwd="/app",
        env={"CARGO_TARGET_DIR": "/app/environment/target", **os.environ},
    )
    _BUILT = True


def wipe_output() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True, exist_ok=True)


def run_diffkit(args: list[str]) -> subprocess.CompletedProcess:
    ensure_built()
    base = [BIN, *args]
    return subprocess.run(
        base,
        capture_output=True,
        text=True,
        env={"CARGO_TARGET_DIR": "/app/environment/target", **os.environ},
    )


def diffkit_run(sched: str, out: Path = OUTPUT, plan: Path = PLAN) -> None:
    proc = run_diffkit(
        [
            "run",
            "--plan",
            str(plan),
            "--mode",
            sched,
            "--seed",
            str(SEED),
            "--out",
            str(out),
        ]
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout


def diffkit_continue(
    from_vault: Path = OUTPUT / "vault",
    out: Path = OUTPUT,
    plan: Path = HALT_PLAN,
) -> None:
    proc = run_diffkit(
        [
            "continue",
            "--plan",
            str(plan),
            "--mode",
            "parallel",
            "--seed",
            str(SEED),
            "--from",
            str(from_vault),
            "--out",
            str(out),
        ]
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout


def load_jsonl() -> list[dict]:
    assert TRANSCRIPT.exists(), "run_transcript.jsonl missing"
    rows = []
    for line in TRANSCRIPT.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def pass_fp(pass_index: int, slots: list[int], _sched: str) -> str:
    ordered = ",".join(str(s) for s in sorted(slots))
    payload = f"pass:{pass_index};slots:{ordered}"
    proc = subprocess.run(
        ["openssl", "dgst", "-sha256"],
        input=payload.encode("utf-8"),
        capture_output=True,
        check=True,
    )
    digest = proc.stdout.decode("utf-8").strip().split()[-1]
    return digest[:16]


def pass_chain(out: Path = OUTPUT) -> list[str]:
    files = sorted(
        (out / "pass_records").glob("pass_*.json"),
        key=lambda path: int(path.stem.split("_", 1)[1]),
    )
    return [
        json.loads(path.read_text(encoding="utf-8"))["stream_fingerprint"]
        for path in files
    ]


def fingerprints_from_jsonl(sched: str) -> list[str]:
    rows = load_jsonl()
    digests: list[str] = []
    pass_index = 0
    slots: list[int] = []
    for row in rows:
        if row["phase"] == "spawn":
            slots.append(int(row["slot"]))
        if row["phase"] == "step":
            digests.append(pass_fp(pass_index, slots, sched))
            pass_index += 1
            slots = []
    return digests


def slot_balance_from_jsonl() -> int:
    rows = load_jsonl()
    spawns = sum(1 for row in rows if row["phase"] == "spawn")
    steps = sum(1 for row in rows if row["phase"] == "step")
    return spawns - WINDOW * steps


def gauge_within_ceiling(stdout: str) -> bool:
    ok_token = "t" + "rue"
    for line in stdout.splitlines():
        if line.startswith("gauge l2="):
            parts = line.split()
            norm = float(parts[1].partition("=")[2])
            within_token = parts[2].partition("=")[2]
            return norm <= GAUGE_CEILING and within_token == ok_token
    return True


def test_scene_alpha_baseline_chain() -> None:
    """Serial uninterrupted run: pass fingerprints match JSONL-derived formula."""
    wipe_output()
    diffkit_run("serial")
    assert pass_chain() == fingerprints_from_jsonl("serial")


def test_scene_beta_overlap_parity() -> None:
    """Parallel uninterrupted run matches serial fingerprint chain for seed 41."""
    wipe_output()
    diffkit_run("serial")
    serial_chain = pass_chain()
    wipe_output()
    diffkit_run("parallel")
    assert pass_chain() == serial_chain


def test_scene_gamma_handoff_chain() -> None:
    """Parallel run with mid checkpoint and continue matches serial baseline."""
    wipe_output()
    diffkit_run("serial")
    serial_chain = pass_chain()
    wipe_output()
    diffkit_run("parallel", plan=HALT_PLAN)
    diffkit_continue()
    assert pass_chain() == serial_chain


def test_scene_delta_surface_trap() -> None:
    """Gauge stdout within tolerance while pass fingerprints track JSONL formula."""
    wipe_output()
    proc = run_diffkit(
        [
            "run",
            "--plan",
            str(PLAN),
            "--mode",
            "parallel",
            "--seed",
            str(SEED),
            "--out",
            str(OUTPUT),
        ]
    )
    assert proc.returncode == 0, proc.stderr
    assert gauge_within_ceiling(proc.stdout)
    assert pass_chain() == fingerprints_from_jsonl("parallel")


def test_scene_epsilon_slot_boundary() -> None:
    """Checkpoint manifest open_count matches pass open_slots at boundary."""
    wipe_output()
    diffkit_run("parallel", plan=HALT_PLAN)
    manifest = json.loads(VAULT_MANIFEST.read_text(encoding="utf-8"))
    first_pass = json.loads(
        sorted(PASSES.glob("pass_*.json"), key=lambda p: int(p.stem.split("_", 1)[1]))[
            0
        ].read_text()
    )
    assert manifest["open_count"] == len(first_pass["open_slots"])


def test_scene_zeta_cancel_retry() -> None:
    """Partial run then continue recovers slot_balance and fingerprint chain."""
    wipe_output()
    diffkit_run("serial")
    serial_chain = pass_chain()
    serial_balance = slot_balance_from_jsonl()
    wipe_output()
    diffkit_run("parallel", plan=HALT_PLAN)
    diffkit_continue()
    assert pass_chain() == serial_chain
    assert slot_balance_from_jsonl() == serial_balance


def test_scene_eta_twice_boot() -> None:
    """Two consecutive continues converge to the same final fingerprint as one continue."""
    wipe_output()
    diffkit_run("parallel", plan=HALT_SPLIT_PLAN)
    diffkit_continue(plan=HALT_PLAN)
    once_chain = pass_chain()
    wipe_output()
    diffkit_run("parallel", plan=HALT_SPLIT_PLAN)
    diffkit_continue(plan=HALT_SPLIT_PLAN)
    diffkit_continue(plan=HALT_SPLIT_PLAN)
    assert pass_chain() == once_chain


def test_scene_theta_count_closure() -> None:
    """JSONL-derived slot_balance matches closed form for serial and parallel modes."""
    wipe_output()
    diffkit_run("serial")
    serial_balance = slot_balance_from_jsonl()
    wipe_output()
    diffkit_run("parallel")
    parallel_balance = slot_balance_from_jsonl()
    assert serial_balance == parallel_balance == 0
