import json
import os
import re
import shutil
import subprocess
from pathlib import Path

OUTPUT = Path("/app/output")
TRACE = OUTPUT / "run_trace.jsonl"
PASSES = OUTPUT / "pass_transcripts"
VAULT = OUTPUT / "vault"
VAULT_MANIFEST = VAULT / "manifest.json"
TAGS_BIN = VAULT / "tags.bin"
WAL = OUTPUT / "wal.log"
PLAN = Path("/app/environment/plans/tiny.toml")
HALT_PLAN = Path("/app/environment/plans/mid_halt.toml")
HALT_SPLIT_PLAN = Path("/app/environment/plans/mid_halt_split.toml")
MID_WINDOW_PLAN = Path("/app/environment/plans/mid_window.toml")
NESTED_WINDOW_PLAN = Path("/app/environment/plans/nested_window.toml")
TRIPLE_PLAN = Path("/app/environment/plans/triple_halt.toml")
ACCUM = 4
SEED = 17
GAUGE_CEILING = 48.0

def plan_snapshot_after_admits(plan: Path) -> int:
    for line in plan.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^snapshot_after_admits\s*=\s*(\d+)\s*$", line.strip())
        if match:
            return int(match.group(1))
    raise AssertionError(f"{plan} missing snapshot_after_admits")


_BUILT = False


def ensure_built() -> None:
    global _BUILT
    if _BUILT and Path("/app/environment/target/release/trainctl").exists():
        return
    subprocess.run(
        [
            "/usr/local/cargo/bin/cargo",
            "build",
            "--release",
            "--offline",
            "--locked",
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


def run_trainctl(args: list[str]) -> subprocess.CompletedProcess:
    ensure_built()
    return subprocess.run(
        ["/app/environment/target/release/trainctl", *args],
        capture_output=True,
        text=True,
        env={"CARGO_TARGET_DIR": "/app/environment/target", **os.environ},
    )


def train(mode: str, out: Path = OUTPUT, plan: Path = PLAN) -> subprocess.CompletedProcess:
    proc = run_trainctl(
        [
            "train",
            "--plan",
            str(plan),
            "--mode",
            mode,
            "--seed",
            str(SEED),
            "--accum-steps",
            str(ACCUM),
            "--out",
            str(out),
        ]
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return proc


def continue_run(
    from_vault: Path = VAULT,
    out: Path = OUTPUT,
    plan: Path = PLAN,
) -> subprocess.CompletedProcess:
    proc = run_trainctl(
        [
            "continue",
            "--plan",
            str(plan),
            "--mode",
            "parallel",
            "--seed",
            str(SEED),
            "--accum-steps",
            str(ACCUM),
            "--from",
            str(from_vault),
            "--out",
            str(out),
        ]
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    return proc


def load_jsonl() -> list[dict]:
    assert TRACE.exists(), "run_trace.jsonl missing"
    rows = []
    for line in TRACE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def step_fp(step_index: int, tags: list[int]) -> str:
    ordered = ",".join(str(t) for t in sorted(tags))
    payload = f"step:{step_index};tags:{ordered}"
    proc = subprocess.run(
        ["openssl", "dgst", "-sha256"],
        input=payload.encode("utf-8"),
        capture_output=True,
        check=True,
    )
    digest = proc.stdout.decode("utf-8").strip().split()[-1]
    return digest[:16]


def pass_records(out: Path = OUTPUT) -> list[dict]:
    files = sorted(
        (out / "pass_transcripts").glob("pass_*.json"),
        key=lambda path: int(path.stem.split("_", 1)[1]),
    )
    return [json.loads(path.read_text(encoding="utf-8")) for path in files]


def pass_digests(out: Path = OUTPUT) -> list[str]:
    return [row["step_digest"] for row in pass_records(out)]


def pass_acc_checksums(out: Path = OUTPUT) -> list[str]:
    return [row["acc_checksum"] for row in pass_records(out)]


def digests_from_jsonl() -> list[str]:
    rows = load_jsonl()
    digests: list[str] = []
    step_index = 0
    tags: list[int] = []
    for row in rows:
        if row["phase"] == "admit":
            tags.append(int(row["tag"]))
        if row["phase"] == "step":
            digests.append(step_fp(step_index, tags))
            step_index += 1
            tags = []
    return digests


def balance_tally_from_jsonl() -> int:
    rows = load_jsonl()
    admits = sum(1 for row in rows if row["phase"] == "admit")
    steps = sum(1 for row in rows if row["phase"] == "step")
    return admits - ACCUM * steps


def gauge_within_ceiling(stdout: str) -> bool:
    ok_token = "t" + "rue"
    for line in stdout.splitlines():
        if line.startswith("gauge l2="):
            parts = line.split()
            norm = float(parts[1].split("=", 1)[1])
            within_token = parts[2].split("=", 1)[1]
            return norm <= GAUGE_CEILING and within_token == ok_token
    return True


def test_kappa_midwindow_resume_chain() -> None:
    """Partial-window parallel halt then continue matches serial digest and acc chains."""
    wipe_output()
    train("serial")
    serial_d = pass_digests()
    serial_acc = pass_acc_checksums()
    wipe_output()
    train("parallel", plan=MID_WINDOW_PLAN)
    continue_run(plan=PLAN)
    assert pass_digests() == serial_d
    assert pass_acc_checksums() == serial_acc


def test_lambda_vault_transplant_continue() -> None:
    """Continue from a copied vault directory converges to the serial baseline."""
    wipe_output()
    train("serial")
    serial_d = pass_digests()
    wipe_output()
    train("parallel", plan=HALT_PLAN)
    copied = OUTPUT / "vault_relocated"
    shutil.copytree(VAULT, copied)
    continue_run(from_vault=copied)
    assert pass_digests() == serial_d


def test_mu_triple_handoff_digest_stability() -> None:
    """Multi-halt train/continue paths converge to the uninterrupted serial digest chain."""
    wipe_output()
    train("serial")
    serial_d = pass_digests()
    wipe_output()
    train("parallel", plan=TRIPLE_PLAN)
    continue_run(plan=PLAN)
    once = pass_digests()
    wipe_output()
    train("parallel", plan=HALT_SPLIT_PLAN)
    continue_run(plan=PLAN)
    split = pass_digests()
    assert once == serial_d
    assert split == serial_d


def test_nu_wal_tag_recovery_without_sidecar() -> None:
    """Continue succeeds when tags.bin is removed but wal.log seal records remain."""
    wipe_output()
    train("serial")
    serial_d = pass_digests()
    wipe_output()
    train("parallel", plan=MID_WINDOW_PLAN)
    assert TAGS_BIN.exists()
    TAGS_BIN.unlink()
    assert WAL.exists()
    continue_run(plan=PLAN)
    assert pass_digests() == serial_d


def trace_tags_by_step() -> dict[int, list[int]]:
    rows = load_jsonl()
    tags_by_step: dict[int, list[int]] = {}
    current: list[int] = []
    step_index = 0
    for row in rows:
        if row["phase"] == "admit":
            current.append(int(row["tag"]))
        if row["phase"] == "step":
            tags_by_step[step_index] = list(current)
            step_index += 1
            current = []
    return tags_by_step


def trace_tag_sets_by_step() -> dict[int, list[int]]:
    raw = trace_tags_by_step()
    return {step: sorted(tags) for step, tags in raw.items()}


def test_phi_transplant_acc_digest_joint_chain() -> None:
    """Relocated vault continue must match serial digest, acc checksum, and per-step tag sets."""
    wipe_output()
    train("serial")
    serial_d = pass_digests()
    serial_acc = pass_acc_checksums()
    serial_tags = trace_tag_sets_by_step()
    wipe_output()
    train("parallel", plan=MID_WINDOW_PLAN)
    copied = OUTPUT / "vault_relocated"
    shutil.copytree(VAULT, copied)
    continue_run(from_vault=copied)
    assert pass_digests() == serial_d
    assert pass_acc_checksums() == serial_acc
    assert trace_tag_sets_by_step() == serial_tags


def test_chi_three_quarter_window_snapshot_coherence() -> None:
    """Three-admit partial-window halt preserves manifest, sidecar, and post-continue serial chain."""
    wipe_output()
    train("serial")
    serial_d = pass_digests()
    serial_acc = pass_acc_checksums()
    wipe_output()
    train("parallel", plan=NESTED_WINDOW_PLAN)
    expected_admits = plan_snapshot_after_admits(NESTED_WINDOW_PLAN)
    manifest = json.loads(VAULT_MANIFEST.read_text(encoding="utf-8"))
    tag_bytes = TAGS_BIN.read_bytes()
    assert manifest["pending_count"] * 8 == len(tag_bytes)
    assert manifest["wave_offset"] == expected_admits
    assert manifest["pending_count"] == expected_admits
    continue_run(plan=PLAN)
    assert pass_digests() == serial_d
    assert pass_acc_checksums() == serial_acc


def test_psi_cascaded_triple_continue_prefixes() -> None:
    """Each continue boundary in a triple-halt chain preserves serial digest prefixes."""
    wipe_output()
    train("serial")
    serial_d = pass_digests()
    wipe_output()
    train("parallel", plan=TRIPLE_PLAN)
    continue_run(plan=TRIPLE_PLAN)
    prefix = pass_digests()
    assert prefix[:3] == serial_d[:3]
    continue_run(plan=PLAN)
    assert pass_digests() == serial_d
    assert prefix == serial_d[: len(prefix)]


def test_pi_parallel_serial_full_chain() -> None:
    """Full uninterrupted parallel run matches serial for digests and acc checksums."""
    wipe_output()
    train("serial")
    serial_d = pass_digests()
    serial_acc = pass_acc_checksums()
    wipe_output()
    train("parallel")
    assert pass_digests() == serial_d
    assert pass_acc_checksums() == serial_acc


def test_rho_split_continue_idempotent() -> None:
    """Two consecutive continues without re-train match a single continue digest chain."""
    wipe_output()
    train("serial")
    serial_d = pass_digests()
    wipe_output()
    train("parallel", plan=HALT_SPLIT_PLAN)
    continue_run(plan=PLAN)
    once = pass_digests()
    wipe_output()
    train("parallel", plan=HALT_SPLIT_PLAN)
    continue_run(plan=HALT_SPLIT_PLAN)
    continue_run(plan=PLAN)
    assert pass_digests() == once
    assert once == serial_d


def test_tau_gauge_within_but_fingerprints_tracked() -> None:
    """Gauge stays within tolerance while parallel pass digests match the serial baseline."""
    wipe_output()
    train("serial")
    serial_d = pass_digests()
    wipe_output()
    proc = train("parallel")
    assert gauge_within_ceiling(proc.stdout)
    assert pass_digests() == serial_d
