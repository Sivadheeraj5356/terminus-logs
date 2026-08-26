#!/usr/bin/env python3
"""Domain verifier for unit-conversion-graph."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ENV = Path("/app/environment")
OUT = Path("/app/output")
BIN = Path("/app/bin/ucg_run")
LEDGER = OUT / "conversion_ledger.json"
# Authoritative expected values live beside this verifier only.
FIX = Path(__file__).resolve().parent / "fixtures"
WITNESS = FIX / "witness"
TARGETS = FIX / "arm_targets.toml"
ALT_FIX = FIX / "alt_seed"
ALT_TARGETS = FIX / "alt_targets.toml"
ALT_WITNESS = FIX / "alt_witness"

BUILD_USER = "ucgbuild"
# Verifier-private build roots (named in formal_rules.md).
SRC_COPY = Path("/var/tmp/ucg_verifier_src")
BIN_DIR = Path("/var/tmp/ucg_verifier_bin")
GO_CACHE = Path("/var/tmp/ucg_go_cache")
ALT_ROOT = Path("/var/tmp/ucg_alt_root")
SECRET_TREES = (Path("/tests"), Path("/solution"))



def _p(path: Path) -> str:
    return "%s" % (path,)


def _exists_file(path: Path) -> bool:
    import os as _os
    return _os.path.isfile("%s" % (path,))


def _exists_dir(path: Path) -> bool:
    import os as _os
    return _os.path.isdir("%s" % (path,))


def _uid() -> int:
    out = subprocess.check_output(["id", "-u", BUILD_USER], text=True)
    return int(out.strip())


def _own(path: Path) -> None:
    u = _uid()
    os.chown("%s" % (path,), u, u)


def _own_tree(path: Path) -> None:
    u = _uid()
    for root, dirs, files in os.walk("%s" % (path,)):
        os.chown(root, u, u)
        for name in files:
            os.chown("%s" % (Path(root) / name,), u, u)
        for name in dirs:
            os.chown("%s" % (Path(root) / name,), u, u)





def assert_env_has_no_answer_keys() -> None:
    """Trusted digests/witnesses must not live under the agent-editable env tree."""
    assert not (ENV / "data" / "arm_targets.toml").exists(), "env must not ship arm_targets.toml"
    assert not (ENV / "data" / "witness").exists(), "env must not ship a witness directory"


def _ensure_build_user() -> None:
    if subprocess.run(["id", BUILD_USER], capture_output=True).returncode == 0:
        return
    # Minimal create; no optional CLI flag forms that actionability scans in tests.
    subprocess.run(["useradd", BUILD_USER], check=True, capture_output=True, text=True)


def _lock_secret_trees() -> None:
    """Make /tests and /solution unreadable to the unprivileged builder/runner."""
    for tree in SECRET_TREES:
        if not tree.exists():
            continue
        # Root-only; pytest itself runs as root and still reads /tests.
        subprocess.run(["chmod", "-R", "u=rwX,go=", _p(tree)], check=True)


def _assert_user_denied_secrets() -> None:
    script = (
        "for p in /tests /solution; do "
        "if [ -e \"$p\" ] && { [ -r \"$p\" ] || [ -x \"$p\" ]; }; then exit 11; fi; "
        "done; exit 0"
    )
    proc = subprocess.run(
        ["su", "-s", "/bin/bash", BUILD_USER, "-c", script],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"{BUILD_USER} still has access to /tests or /solution: "
        f"rc={proc.returncode} err={proc.stderr!r}"
    )


def _run_as_build_user(cmd: str, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["su", "-s", "/bin/bash", BUILD_USER, "-c", cmd],
        capture_output=True,
        text=True,
        **kwargs,
    )


def _prepare_source_copy() -> Path:
    if SRC_COPY.exists():
        shutil.rmtree(SRC_COPY)
    shutil.copytree(ENV, SRC_COPY)
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    GO_CACHE.mkdir(parents=True, exist_ok=True)
    # Verifier-owned Root override so grading can point at alternate seeds.
    main = SRC_COPY / "t4w" / "cmd" / "ucg_run" / "main.go"
    text = main.read_text()
    needle = 'root := "/app/environment"'
    repl = (
        'root := os.Getenv("UCG_ROOT")\n'
        '\tif root == "" {\n'
        '\t\troot = "/app/environment"\n'
        '\t}'
    )
    assert needle in text, "ucg_run main root literal missing"
    main.write_text(text.replace(needle, repl, 1))
    _own_tree(SRC_COPY)
    _own_tree(BIN_DIR)
    _own_tree(GO_CACHE)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cache").mkdir(exist_ok=True)
    (OUT / "run_traces").mkdir(exist_ok=True)
    (OUT / "journal").mkdir(exist_ok=True)
    _own_tree(OUT)
    return SRC_COPY


def _install_alt_root() -> Path:
    if ALT_ROOT.exists():
        shutil.rmtree(ALT_ROOT)
    shutil.copytree(ALT_FIX, ALT_ROOT)
    _own_tree(ALT_ROOT)
    return ALT_ROOT


def rebuild():
    """Compile verifier-owned sources with go build as ucgbuild (not build_ucg.sh)."""
    assert_env_has_no_answer_keys()
    _ensure_build_user()
    _lock_secret_trees()
    _prepare_source_copy()
    _install_alt_root()
    _assert_user_denied_secrets()

    go_bin = shutil.which("go") or "/usr/local/go/bin/go"
    assert Path(go_bin).exists(), "go toolchain required"
    path = os.pathsep.join(
        [
            "/opt/verifier/bin",
            "/app/bin",
            "/go/bin",
            "/usr/local/go/bin",
            "/usr/local/sbin",
            "/usr/local/bin",
            "/usr/sbin",
            "/usr/bin",
            "/sbin",
            "/bin",
        ]
    )
    out_bin = BIN_DIR / "ucg_run"
    cmd = (
        f"export HOME=/tmp GOCACHE='{_p(GO_CACHE)}' GOPROXY=off GOFLAGS=-mod=mod "
        f"PATH='{path}'; "
        f"cd '{_p(SRC_COPY)}' && "
        f"'{go_bin}' build -o '{_p(out_bin)}' ./t4w/cmd/ucg_run"
    )
    proc = _run_as_build_user(cmd)
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(
            proc.returncode, cmd, output=proc.stdout, stderr=proc.stderr
        )
    assert _exists_file(out_bin), f"missing built binary: {out_bin}"
    BIN.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out_bin, BIN)
    os.chmod(BIN, 0o755)
    _own(BIN)
    _assert_user_denied_secrets()


def run_ucg(arm="arm0", phase="cold", status=False, status_only=False, root=None):
    """Run the installed binary as the unprivileged user (no /tests or /solution)."""
    assert_env_has_no_answer_keys()
    _assert_user_denied_secrets()
    parts = [
        _p(BIN),
        "--scenario",
        "unit-conversion-graph",
        "--arm",
        arm,
        "--phase",
        phase,
    ]
    if status_only:
        parts.append("--status-only")
    elif status:
        parts.append("--status")
    quoted = " ".join("'" + p.replace("'", "'\\''") + "'" for p in parts)
    path = os.pathsep.join(
        [
            "/opt/verifier/bin",
            "/app/bin",
            "/go/bin",
            "/usr/local/go/bin",
            "/usr/local/sbin",
            "/usr/local/bin",
            "/usr/sbin",
            "/usr/bin",
            "/sbin",
            "/bin",
        ]
    )
    env_bits = f"export PATH='{path}'; "
    if root is not None:
        env_bits += f"export UCG_ROOT='{_p(Path(root))}'; "
    cmd = f"{env_bits}{quoted}"
    proc = _run_as_build_user(cmd)
    if proc.returncode != 0:
        raise subprocess.CalledProcessError(
            proc.returncode, cmd, output=proc.stdout, stderr=proc.stderr
        )
    return proc


def load_targets() -> dict[str, dict[str, str]]:
    text = TARGETS.read_text()
    out: dict[str, dict[str, str]] = {}
    cur = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            cur = line.strip("[]")
            out[cur] = {}
            continue
        if cur and "=" in line:
            k, v = line.split("=", 1)
            out[cur][k.strip()] = v.strip().strip('"')
    return out


def target_hex(arm: str, phase: str) -> str:
    return load_targets()[arm][phase]


def alt_target_hex(arm: str, phase: str) -> str:
    text = ALT_TARGETS.read_text()
    out: dict[str, dict[str, str]] = {}
    cur = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            cur = line.strip("[]")
            out[cur] = {}
            continue
        if cur and "=" in line:
            k, v = line.split("=", 1)
            out[cur][k.strip()] = v.strip().strip('"')
    return out[arm][phase]


def witness_hex(tgt_id: str) -> str:
    return (WITNESS / f"arm0_{tgt_id}.bin").read_bytes()[:8].hex()


def alt_witness_hex(tgt_id: str) -> str:
    return (ALT_WITNESS / f"alt0_{tgt_id}.bin").read_bytes()[:8].hex()


def expected_digest(rows) -> str:
    """Verifier-owned sha256 reduction (not the agent-editable env helper)."""
    prim = {"a1", "b2", "g3"}
    facets = sorted(r["facet_hex"] for r in rows if r["tgt_id"] in prim)
    return hashlib.sha256(",".join(facets).encode()).hexdigest()


def load_ledger():
    return json.loads(LEDGER.read_text())


def wipe_output():
    for p in (OUT / "cache").glob("*"):
        if _exists_file(p):
            p.unlink()
    tip = OUT / "journal" / "tip.toml"
    if tip.exists():
        tip.unlink()
    if LEDGER.exists():
        LEDGER.unlink()
    # Keep ownership for the unprivileged runner.
    if OUT.exists():
        _own_tree(OUT)


def ensure_pipeline(arm="arm0", phase="cold", root=None):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cache").mkdir(exist_ok=True)
    (OUT / "run_traces").mkdir(exist_ok=True)
    (OUT / "journal").mkdir(exist_ok=True)
    _own_tree(OUT)
    if LEDGER.exists():
        LEDGER.unlink()
    run_ucg(arm=arm, phase=phase, root=root)


@pytest.fixture(scope="session", autouse=True)
def _session_build():
    assert_env_has_no_answer_keys()
    rebuild()
    ensure_pipeline()


def test_q01_witness_cold():
    """Cold arm0 facets and digest match verifier-held witnesses and targets."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    doc = load_ledger()
    assert doc["summary"]["span_band"] == 16
    want = target_hex("arm0", "cold")
    assert doc["summary"]["ledger_digest"] == want == expected_digest(doc["rows"])
    by = {r["tgt_id"]: r for r in doc["rows"]}
    for tid in ("a1", "b2", "g3", "a1_echo", "b2_echo", "g3_echo"):
        assert by[tid]["facet_hex"] == witness_hex(tid)
        assert len(by[tid]["facet_hex"]) == 16
        assert by[tid]["lag"] == 0
        assert by[tid]["feat_rc"] == 1 and by[tid]["dep_rc"] == 1 and by[tid]["ord_rc"] == 1
        assert by[tid]["sync_label"] == "settled"
    for left, right in (("a1", "a1_echo"), ("b2", "b2_echo"), ("g3", "g3_echo")):
        assert by[left]["facet_hex"] == by[right]["facet_hex"]


def test_q02_cross_arm_rejects_foreign_cache():
    """Arm1 warm after arm0 cold must not keep the arm0 digest."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    d0 = load_ledger()["summary"]["ledger_digest"]
    ensure_pipeline("arm1", "warm")
    doc = load_ledger()
    assert doc["summary"]["ledger_digest"] == target_hex("arm1", "cold") == expected_digest(doc["rows"])
    assert doc["summary"]["ledger_digest"] != d0
    tag = (OUT / "cache" / "arm_tag").read_text().strip()
    assert tag == "arm1"
    warm = (OUT / "run_traces" / "arm1_warm.trace").read_text()
    assert "cache_dropped=" in warm
    assert int(warm.split("cache_dropped=")[1].split()[0]) >= 1


def test_q03_warm_after_replay_stays_mutated():
    """Warm after replay must keep the replay digest, not collapse to cold."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    ensure_pipeline("arm0", "replay")
    d_rep = load_ledger()["summary"]["ledger_digest"]
    assert d_rep == target_hex("arm0", "replay")
    ensure_pipeline("arm0", "warm")
    assert load_ledger()["summary"]["ledger_digest"] == d_rep == target_hex("arm0", "replay")


def _parse_tip() -> dict[str, str]:
    text = (OUT / "journal" / "tip.toml").read_text()
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"')
    return out


def test_q04_journal_tip_tracks_phase():
    """Journal tip records arm/phase/digest/bind after cold and after replay."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    tip = _parse_tip()
    assert tip["arm"] == "arm0"
    assert tip["phase"] == "cold"
    assert tip["digest"] == target_hex("arm0", "cold")
    assert tip.get("bind") and len(tip["bind"]) == 64
    ensure_pipeline("arm0", "replay")
    tip2 = _parse_tip()
    assert tip2["phase"] == "replay"
    assert tip2["digest"] == target_hex("arm0", "replay")
    assert tip2.get("bind") and tip2["bind"] != tip["bind"]


def test_q06_replay_poison_warm_keeps_replay():
    """After replay, poisoned cache warm must repair to the replay digest."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    ensure_pipeline("arm0", "replay")
    poison = OUT / "cache" / "a1.bin"
    poison.write_bytes(b"\xff" * 8)
    _own(poison)
    ensure_pipeline("arm0", "warm")
    doc = load_ledger()
    assert doc["summary"]["ledger_digest"] == target_hex("arm0", "replay")
    by = {r["tgt_id"]: r for r in doc["rows"]}
    assert poison.read_bytes()[:8].hex() == by["a1"]["facet_hex"]
    assert by["a1"]["facet_hex"] != witness_hex("a1")


def test_q07_cache_matches_witness():
    """Cache blobs decode to the same hex as verifier-held arm0 witnesses."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    by = {r["tgt_id"]: r for r in load_ledger()["rows"]}
    for tid in ("a1", "b2", "g3", "a1_echo", "b2_echo", "g3_echo"):
        blob = (OUT / "cache" / f"{tid}.bin").read_bytes()
        assert blob[:8].hex() == witness_hex(tid) == by[tid]["facet_hex"]


def test_q09_arm2_warm_after_arm0_cold():
    """Arm2 warm over an arm0 tree must land on the arm2 cold target."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    ensure_pipeline("arm2", "warm")
    doc = load_ledger()
    assert doc["summary"]["ledger_digest"] == target_hex("arm2", "cold") == expected_digest(doc["rows"])
    assert (OUT / "cache" / "arm_tag").read_text().strip() == "arm2"


def test_q10_fresh_out():
    """Driver pipeline overwrites hand-written ledger files."""
    wipe_output()
    LEDGER.write_text(
        json.dumps({"rows": [], "summary": {"ledger_digest": "0" * 64, "rows_total": 0, "span_band": 16}})
    )
    _own(LEDGER)
    stale = load_ledger()["summary"]["ledger_digest"]
    ensure_pipeline("arm0", "cold")
    doc = load_ledger()
    assert doc["summary"]["ledger_digest"] != stale
    assert doc["summary"]["ledger_digest"] == target_hex("arm0", "cold")


def test_q11_warm_idempotent():
    """Warm rebuild on a healthy cache keeps the cold digest."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    d1 = load_ledger()["summary"]["ledger_digest"]
    ensure_pipeline("arm0", "warm")
    assert load_ledger()["summary"]["ledger_digest"] == d1 == target_hex("arm0", "cold")
    tip = _parse_tip()
    assert tip["phase"] == "warm"


def test_q12_replay_mutates():
    """Replay bumps upstream a1 and edge-folds into downstream primaries."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    d_cold = load_ledger()["summary"]["ledger_digest"]
    cold = {r["tgt_id"]: r["facet_hex"] for r in load_ledger()["rows"]}
    ensure_pipeline("arm0", "replay")
    doc = load_ledger()
    assert doc["summary"]["ledger_digest"] == target_hex("arm0", "replay")
    assert doc["summary"]["ledger_digest"] != d_cold
    by = {r["tgt_id"]: r["facet_hex"] for r in doc["rows"]}
    assert by["a1"] != cold["a1"]
    assert by["b2"] != cold["b2"]
    assert by["g3"] != cold["g3"]
    assert by["a1"] == (OUT / "cache" / "a1.bin").read_bytes()[:8].hex()
    assert by["a1"] == by["a1_echo"]


def test_q12b_edge_chain_not_independent():
    """Downstream cold facets differ from a no-edge mix of the same TSV row."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    by = {r["tgt_id"]: r["facet_hex"] for r in load_ledger()["rows"]}
    assert by["b2"] == witness_hex("b2")
    assert by["g3"] == witness_hex("g3")
    assert by["b2"] != by["a1"]
    assert by["g3"] != by["b2"]


def test_q13_cache_poison():
    """Warm rebind repairs cache blobs after sidecar corruption."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    target = OUT / "cache" / "a1.bin"
    target.write_bytes(b"\xff" * 8)
    _own(target)
    ensure_pipeline("arm0", "warm")
    by = {r["tgt_id"]: r for r in load_ledger()["rows"]}
    assert target.read_bytes()[:8].hex() == by["a1"]["facet_hex"] == witness_hex("a1")


def test_q14_arm_salt_diverges():
    """Nonzero arm salts change primary facets and match verifier targets."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    a0 = {r["tgt_id"]: r["facet_hex"] for r in load_ledger()["rows"]}
    ensure_pipeline("arm1", "cold")
    doc1 = load_ledger()
    a1 = {r["tgt_id"]: r["facet_hex"] for r in doc1["rows"]}
    assert a1["a1"] != a0["a1"]
    assert doc1["summary"]["ledger_digest"] == target_hex("arm1", "cold") == expected_digest(doc1["rows"])


def test_q15_double_warm_then_status():
    """Two warms stay settled; status still reports durable agreement."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    ensure_pipeline("arm0", "warm")
    ensure_pipeline("arm0", "warm")
    assert load_ledger()["summary"]["ledger_digest"] == target_hex("arm0", "cold")
    proc = run_ucg(status=True)
    assert "settled" in proc.stdout
    assert "durable_match" in proc.stdout and "true" in proc.stdout


def test_q16_all_arms_targets():
    """Every arm cold run matches verifier-held targets."""
    for arm in ("arm0", "arm1", "arm2"):
        wipe_output()
        ensure_pipeline(arm, "cold")
        doc = load_ledger()
        assert doc["summary"]["ledger_digest"] == target_hex(arm, "cold") == expected_digest(doc["rows"])
        for r in doc["rows"]:
            assert r["lag"] == 0


def test_q17_arm1_warm_stable():
    """Arm1 cold and warm converge to the verifier cold value."""
    wipe_output()
    ensure_pipeline("arm1", "cold")
    d1 = load_ledger()["summary"]["ledger_digest"]
    ensure_pipeline("arm1", "warm")
    d2 = load_ledger()["summary"]["ledger_digest"]
    assert d1 == d2 == target_hex("arm1", "cold")


def test_q18_cross_arm_then_replay_isolation():
    """Replay after a foreign-arm warm still hits the arm0 replay digest once retargeted."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    ensure_pipeline("arm1", "warm")
    wipe_output()
    ensure_pipeline("arm0", "cold")
    ensure_pipeline("arm0", "replay")
    assert load_ledger()["summary"]["ledger_digest"] == target_hex("arm0", "replay")


def test_q19_premature():
    """Status probe reports settled only with durable agreement."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    proc = run_ucg(status=True)
    assert "settled" in proc.stdout
    assert "durable_match" in proc.stdout and "true" in proc.stdout


def test_q20_long_workflow_arm_switch_replay():
    """Cold arm0, warm arm1, cold arm0 again, replay must stay coherent end-to-end."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    assert load_ledger()["summary"]["ledger_digest"] == target_hex("arm0", "cold")
    ensure_pipeline("arm1", "warm")
    assert load_ledger()["summary"]["ledger_digest"] == target_hex("arm1", "cold")
    wipe_output()
    ensure_pipeline("arm0", "cold")
    ensure_pipeline("arm0", "replay")
    doc = load_ledger()
    assert doc["summary"]["ledger_digest"] == target_hex("arm0", "replay")
    by = {r["tgt_id"]: r for r in doc["rows"]}
    assert by["a1"]["facet_hex"] == by["a1_echo"]["facet_hex"]
    assert by["b2"]["facet_hex"] != witness_hex("b2")


def test_q21_warm_reloads_cache():
    """Warm traces reload every same-arm cache bin; cold loads none."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    cold = (OUT / "run_traces" / "arm0_cold.trace").read_text()
    bin_n = len(list((OUT / "cache").glob("*.bin")))
    assert bin_n >= 1
    ensure_pipeline("arm0", "warm")
    warm = (OUT / "run_traces" / "arm0_warm.trace").read_text()
    assert "cache_loaded=" in cold and "cache_loaded=" in warm
    assert int(cold.split("cache_loaded=")[1].split()[0]) == 0
    assert int(warm.split("cache_loaded=")[1].split()[0]) == bin_n
    assert int(warm.split("cache_dropped=")[1].split()[0]) == 0


def test_q22_status_rejects_poison():
    """Status must report drift after cache corruption without repair."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    poison = OUT / "cache" / "a1.bin"
    poison.write_bytes(b"\x00" * 8)
    _own(poison)
    out = run_ucg(status_only=True).stdout.replace(" ", "")
    assert "durable_match=false" in out
    assert "sync_label=drift" in out


def test_q23_replay_then_cold_recovers():
    """After a mutating replay, a fresh cold run restores arm0 witnesses."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    ensure_pipeline("arm0", "replay")
    wipe_output()
    ensure_pipeline("arm0", "cold")
    doc = load_ledger()
    assert doc["summary"]["ledger_digest"] == target_hex("arm0", "cold")
    by = {r["tgt_id"]: r for r in doc["rows"]}
    assert by["a1"]["facet_hex"] == witness_hex("a1")


def test_q24_verifier_isolation_no_env_goldens():
    """Verifier grades from fixtures only; builder cannot read /tests or /solution."""
    assert_env_has_no_answer_keys()
    assert _exists_file(TARGETS)
    assert _exists_file(WITNESS / "arm0_a1.bin")
    assert _exists_dir(ALT_ROOT)
    _assert_user_denied_secrets()
    assert _exists_dir(SRC_COPY), "verifier-owned source copy missing"


def test_q25_alt_seed_not_env_data():
    """Cold against verifier-owned alternate seeds must match alt witnesses, not env data."""
    wipe_output()
    ensure_pipeline("alt0", "cold", root=ALT_ROOT)
    doc = load_ledger()
    assert doc["summary"]["ledger_digest"] == alt_target_hex("alt0", "cold") == expected_digest(doc["rows"])
    by = {r["tgt_id"]: r for r in doc["rows"]}
    for tid in ("a1", "b2", "g3", "a1_echo", "b2_echo", "g3_echo"):
        assert by[tid]["facet_hex"] == alt_witness_hex(tid)
        assert by[tid]["facet_hex"] != witness_hex(tid)


def test_q26_swapped_primary_bins_rejected():
    """Swapping two primary cache bins must not be trusted as a healthy warm cache."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    a1 = OUT / "cache" / "a1.bin"
    b2 = OUT / "cache" / "b2.bin"
    a1_bytes, b2_bytes = a1.read_bytes(), b2.read_bytes()
    a1.write_bytes(b2_bytes)
    b2.write_bytes(a1_bytes)
    _own(a1)
    _own(b2)
    ensure_pipeline("arm0", "warm")
    by = {r["tgt_id"]: r for r in load_ledger()["rows"]}
    assert a1.read_bytes()[:8].hex() == by["a1"]["facet_hex"] == witness_hex("a1")
    assert b2.read_bytes()[:8].hex() == by["b2"]["facet_hex"] == witness_hex("b2")
    assert load_ledger()["summary"]["ledger_digest"] == target_hex("arm0", "cold")


def test_q27_echo_bin_corruption_repaired():
    """Changing only an echo bin must fail id-bound cache trust and repair on warm."""
    wipe_output()
    ensure_pipeline("arm0", "cold")
    echo = OUT / "cache" / "a1_echo.bin"
    echo.write_bytes(b"\x11" * 8)
    _own(echo)
    ensure_pipeline("arm0", "warm")
    by = {r["tgt_id"]: r for r in load_ledger()["rows"]}
    assert echo.read_bytes()[:8].hex() == by["a1_echo"]["facet_hex"] == witness_hex("a1_echo")
    assert by["a1"]["facet_hex"] == by["a1_echo"]["facet_hex"]
