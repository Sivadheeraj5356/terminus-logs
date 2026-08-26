"""Hard outcome tests for jextract FFM classifier packaging ledger.

Verifier locks protected mounts first, materializes a private sandbox with
symlink/special-file rejection, installs verifier-owned scenarios and Drive,
compiles packaging stages there, and runs a verifier-owned launcher as an
unprivileged user. Expected rows come from sealed fixture packs plus the
published selection contract.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
LEDGER = APP / "output" / "ffm_ledger.json"
CLAIM = APP / "output" / "reactor_claim.json"
SANDBOX = Path("/var") / "lib" / "verifier" / "run"
AGENT_USER = "tbagent"
_TESTS_ROOT = Path("/") / "tests"
_SOLUTION_ROOT = Path("/") / "solution"
_DENY_TESTS = _TESTS_ROOT / "test_outputs.py"
_DENY_SOLUTION = _SOLUTION_ROOT / "solve.sh"
_FIX = Path(__file__).resolve().parent / "fixtures"
_FIX_SCENARIOS = _FIX / "scenarios"
_FIX_PROBE = _FIX / "probe"
_FIX_LAUNCHER = _FIX / "bin" / "reactor"

# Agent-controlled packaging stages and support trees only (no probe/data/bin).
COPY_ROOTS = (
    "loom",
    "hearth",
    "anvil",
    "pulse",
    "brace",
    "span",
    "modules",
    "reactor",
    "ops",
)
PUBLIC_PACKS = frozenset({"helix", "prism", "quartz"})


def _sha256_hex(text: str) -> str:
    proc = subprocess.run(
        ["sha256sum"],
        input=text.encode("utf-8"),
        capture_output=True,
        check=True,
    )
    return proc.stdout.decode("utf-8").split()[0]


def _row_token(
    case_id: str,
    mode: str,
    pick: str,
    lane: str,
    stamp: str,
    soname: str,
    gate: str,
    ok: bool,
) -> str:
    ok_s = "true" if ok else "false"
    return _sha256_hex(
        f"{case_id}|{mode}|{pick}|{lane}|{stamp}|{soname}|{gate}|{ok_s}"
    )


def _state_hash(cp_token: str, mp_token: str) -> str:
    return _sha256_hex(f"{{classpath={cp_token}, module-path={mp_token}}}")


def _fixture_case_ids() -> tuple[str, ...]:
    names = sorted(p.stem for p in _FIX_SCENARIOS.glob("*.json"))
    assert names, "verifier fixtures missing scenario packs"
    return tuple(names)


CASE_NAMES = _fixture_case_ids()


def _load_case(case_id: str) -> dict:
    path = _FIX_SCENARIOS / f"{case_id}.json"
    assert path.is_file(), f"missing sealed scenario {case_id}"
    return json.loads(path.read_text(encoding="utf-8"))


def _derive_case(case: dict) -> tuple:
    """Derive expected ledger fields from a sealed pack and the contract."""
    case_id = case["case_id"]
    tool = int(case["toolchain_arch"])
    real = case.get(f"id_real_{tool}", "") or ""
    if real:
        pick = real
        stamp = case[f"stamp_{tool}"]
        soname = case[f"soname_{tool}"]
        gate = "refuse"
    else:
        pick = case["id_stub"]
        stamp = case["stamp_0"]
        soname = case["soname_0"]
        gate = "allow"

    has_cp = int(case["has_cp_classifier"])
    has_mp = int(case["has_mp_classifier"])
    has_cp_stub = int(case["has_cp_stub"])

    if has_cp == 1:
        cp_lane, cp_ok = "real", True
    elif has_cp_stub == 1:
        cp_lane, cp_ok = "stub", False
    else:
        cp_lane, cp_ok = "none", False

    if has_mp == 1:
        mp_lane, mp_ok = "real", True
    elif has_cp == 1 or has_cp_stub == 1:
        mp_lane, mp_ok = "leak", False
    else:
        mp_lane, mp_ok = "none", False

    cp_tok = _row_token(case_id, "classpath", pick, cp_lane, stamp, soname, gate, cp_ok)
    mp_tok = _row_token(case_id, "module-path", pick, mp_lane, stamp, soname, gate, mp_ok)
    return (
        pick,
        stamp,
        soname,
        gate,
        cp_lane,
        cp_ok,
        mp_lane,
        mp_ok,
        cp_tok,
        mp_tok,
        _state_hash(cp_tok, mp_tok),
    )


def _expect_case(case_id: str) -> tuple:
    return _derive_case(_load_case(case_id))


def _entry(case: dict, mode: str) -> dict:
    for row in case["entries"]:
        if row["path_mode"] == mode:
            return row
    raise AssertionError(f"missing path_mode {mode}")


def _run_as_agent(cmd: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    full = ["runuser", "-u", AGENT_USER, "--", *cmd]
    return subprocess.run(
        full,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _lock_protected(paths: list[Path]) -> dict[Path, int]:
    prior: dict[Path, int] = {}
    for path in paths:
        if not path.exists():
            continue
        mode = path.stat().st_mode
        prior[path] = stat.S_IMODE(mode)
        path.chmod(0o700)
    return prior


def _restore_protected(prior: dict[Path, int]) -> None:
    for path, mode in prior.items():
        if path.exists():
            path.chmod(mode)


def _reject_special(path: Path) -> None:
    if path.is_symlink():
        raise AssertionError(f"refusing symlink before copy: {path}")
    try:
        st = path.lstat()
    except OSError as exc:
        raise AssertionError(f"unreadable path before copy: {path}") from exc
    mode = st.st_mode
    if stat.S_ISLNK(mode):
        raise AssertionError(f"refusing symlink before copy: {path}")
    if path.is_dir():
        if not stat.S_ISDIR(mode):
            raise AssertionError(f"refusing non-directory: {path}")
        return
    if not stat.S_ISREG(mode):
        raise AssertionError(f"refusing special file before copy: {path}")


def _safe_copy_tree(src: Path, dst: Path) -> None:
    _reject_special(src)
    dst.mkdir(parents=True, exist_ok=True)
    for root, dirs, files in os.walk(src, followlinks=False):
        root_path = Path(root)
        _reject_special(root_path)
        rel = root_path.relative_to(src)
        target_root = dst / rel
        target_root.mkdir(parents=True, exist_ok=True)
        for name in dirs:
            child = root_path / name
            _reject_special(child)
            (target_root / name).mkdir(parents=True, exist_ok=True)
        for name in files:
            child = root_path / name
            _reject_special(child)
            shutil.copy2(child, target_root / name)


def _install_verifier_owned(sandbox: Path) -> None:
    scen_dst = sandbox / "data" / "scenarios"
    if scen_dst.exists():
        shutil.rmtree(scen_dst)
    scen_dst.mkdir(parents=True, exist_ok=True)
    for pack in sorted(_FIX_SCENARIOS.glob("*.json")):
        _reject_special(pack)
        shutil.copy2(pack, scen_dst / pack.name)

    probe_dst = sandbox / "probe"
    if probe_dst.exists():
        shutil.rmtree(probe_dst)
    _safe_copy_tree(_FIX_PROBE, probe_dst)

    bin_dir = sandbox / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    _reject_special(_FIX_LAUNCHER)
    shutil.copy2(_FIX_LAUNCHER, bin_dir / "reactor")
    (bin_dir / "reactor").chmod(0o755)


def _materialize_sandbox() -> Path:
    if SANDBOX.exists():
        shutil.rmtree(SANDBOX)
    SANDBOX.mkdir(parents=True, exist_ok=True)
    for name in COPY_ROOTS:
        src = APP / name
        assert src.exists(), f"missing agent tree {src}"
        dst = SANDBOX / name
        if src.is_dir():
            _safe_copy_tree(src, dst)
        else:
            _reject_special(src)
            shutil.copy2(src, dst)
    _install_verifier_owned(SANDBOX)
    for script in (SANDBOX / "ops").glob("*.sh"):
        script.chmod(0o755)
    (SANDBOX / "classes").mkdir(parents=True, exist_ok=True)
    (SANDBOX / "output").mkdir(parents=True, exist_ok=True)
    (SANDBOX / "work").mkdir(parents=True, exist_ok=True)
    shutil.chown(SANDBOX, user=AGENT_USER, group=AGENT_USER)
    for root, dirs, files in os.walk(SANDBOX):
        shutil.chown(root, user=AGENT_USER, group=AGENT_USER)
        for name in dirs + files:
            shutil.chown(os.path.join(root, name), user=AGENT_USER, group=AGENT_USER)
    return SANDBOX


def _agent_env(sandbox: Path) -> dict[str, str]:
    home = sandbox / ("." + "home")
    tmp = sandbox / ("." + "tmp")
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "TMPDIR": str(tmp),
        "LANG": "C.UTF-8",
        "REACTOR_CLASSES": str(sandbox / "classes"),
    }
    home.mkdir(parents=True, exist_ok=True)
    tmp.mkdir(parents=True, exist_ok=True)
    shutil.chown(home, user=AGENT_USER, group=AGENT_USER)
    shutil.chown(tmp, user=AGENT_USER, group=AGENT_USER)
    return env


def _regenerate_outputs() -> None:
    if LEDGER.exists():
        LEDGER.unlink()
    if CLAIM.exists():
        CLAIM.unlink()
    out_dir = APP / "output"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Protect private mounts before any agent-tree copy work.
    protected = _lock_protected([_TESTS_ROOT, _SOLUTION_ROOT])
    try:
        sandbox = _materialize_sandbox()
        env = _agent_env(sandbox)

        deny = _run_as_agent(
            ["test", "!", "-r", str(_DENY_TESTS)],
            cwd=sandbox,
            env=env,
        )
        assert deny.returncode == 0, "agent user can still read tests mount"
        deny_sol = _run_as_agent(
            ["test", "!", "-r", str(_DENY_SOLUTION)],
            cwd=sandbox,
            env=env,
        )
        assert deny_sol.returncode == 0, "agent user can still read solution mount"

        sources = sorted(
            [
                *sandbox.joinpath("loom").rglob("*.java"),
                *sandbox.joinpath("hearth").rglob("*.java"),
                *sandbox.joinpath("anvil").rglob("*.java"),
                *sandbox.joinpath("pulse").rglob("*.java"),
                *sandbox.joinpath("brace").rglob("*.java"),
                *sandbox.joinpath("span").rglob("*.java"),
                *sandbox.joinpath("probe").rglob("*.java"),
            ]
        )
        assert sources, "sandbox has no Java sources"
        for src in sources:
            assert str(src).startswith(str(sandbox)), src
            assert not src.is_symlink(), src

        compile_cmd = [
            "javac",
            "-d",
            str(sandbox / "classes"),
            *[str(p) for p in sources],
        ]
        comp = _run_as_agent(compile_cmd, cwd=sandbox, env=env)
        assert comp.returncode == 0, (
            "sandbox javac failed:\n" + (comp.stdout or "") + (comp.stderr or "")
        )

        boot = _run_as_agent(
            [str(sandbox / "bin" / "reactor")],
            cwd=sandbox,
            env=env,
        )
        assert boot.returncode == 0, (
            "sandbox reactor failed:\n" + (boot.stdout or "") + (boot.stderr or "")
        )

        sand_ledger = sandbox / "output" / "ffm_ledger.json"
        sand_claim = sandbox / "output" / "reactor_claim.json"
        assert sand_ledger.is_file(), "missing sandbox ledger"
        assert sand_claim.is_file(), "missing sandbox claim"
        shutil.copy2(sand_ledger, LEDGER)
        shutil.copy2(sand_claim, CLAIM)
    finally:
        _restore_protected(protected)

    assert LEDGER.exists(), "missing /app/output/ffm_ledger.json after regenerate"
    assert CLAIM.exists(), "missing /app/output/reactor_claim.json after regenerate"


@pytest.fixture(scope="module")
def ledger():
    _regenerate_outputs()
    return json.loads(LEDGER.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def claim(ledger):
    return json.loads(CLAIM.read_text(encoding="utf-8"))


def test_helix_cells_match(ledger):
    """Helix host-matched classifier_pick must bind on both path modes."""
    pick, stamp, soname, gate, cp_lane, cp_ok, mp_lane, mp_ok, cp_tok, mp_tok, st = (
        _expect_case("helix")
    )
    case = ledger["cases"]["helix"]
    cp = _entry(case, "classpath")
    mp = _entry(case, "module-path")
    assert cp["classifier_pick"] == pick
    assert mp["classifier_pick"] == pick
    assert cp["path_lane"] == cp_lane
    assert mp["path_lane"] == mp_lane
    assert cp["bind_ok"] is cp_ok
    assert mp["bind_ok"] is mp_ok
    assert cp["stamp_bind"] == stamp
    assert cp["soname_mark"] == soname
    assert cp["stub_gate"] == gate
    assert cp["row_token"] == cp_tok
    assert mp["row_token"] == mp_tok
    assert case["state_hash"] == st


def test_prism_slot_hold(ledger):
    """Prism must select secondary toolchain classifier, not host."""
    pick, stamp, soname, gate, _, _, _, _, cp_tok, mp_tok, st = _expect_case("prism")
    case = ledger["cases"]["prism"]
    cp = _entry(case, "classpath")
    mp = _entry(case, "module-path")
    assert pick == "linux-aarch64"
    assert cp["classifier_pick"] == pick
    assert mp["classifier_pick"] == pick
    assert cp["classifier_pick"] != "linux-x86_64"
    assert cp["stamp_bind"] == stamp
    assert cp["soname_mark"] == soname
    assert cp["stub_gate"] == gate
    assert cp["row_token"] == cp_tok
    assert mp["row_token"] == mp_tok
    assert case["state_hash"] == st


def test_quartz_edge_keep(ledger):
    """Quartz classifier_pick stays on toolchain real id across modes."""
    pick, stamp, soname, gate, _, _, _, _, _, _, _ = _expect_case("quartz")
    case = ledger["cases"]["quartz"]
    for mode in ("classpath", "module-path"):
        row = _entry(case, mode)
        assert row["classifier_pick"] == pick
        assert row["classifier_pick"] != "linux-x86_64"
        assert row["classifier_pick"] != "stub"
        assert row["stamp_bind"] == stamp
        assert row["soname_mark"] == soname
        assert row["stub_gate"] == gate


def test_mp_omits_cp_bait(ledger):
    """Module-path without classifier jar must emit leak lane and bind_ok false."""
    _, _, _, _, cp_lane, cp_ok, mp_lane, mp_ok, _, mp_tok, _ = _expect_case("quartz")
    mp = _entry(ledger["cases"]["quartz"], "module-path")
    assert mp_lane == "leak"
    assert mp["path_lane"] == mp_lane
    assert mp["bind_ok"] is mp_ok
    assert mp["path_lane"] != "real"
    assert mp["row_token"] == mp_tok
    cp = _entry(ledger["cases"]["quartz"], "classpath")
    assert cp["path_lane"] == cp_lane
    assert cp["bind_ok"] is cp_ok


def test_pair_grid_agree(ledger):
    """Every sealed pack keeps dual path modes coherent with derived digests."""
    assert set(ledger["cases"]) == set(CASE_NAMES)
    assert any(name not in PUBLIC_PACKS for name in CASE_NAMES)
    local_assemble = True
    for name in CASE_NAMES:
        pick, stamp, soname, gate, cp_lane, cp_ok, mp_lane, mp_ok, cp_tok, mp_tok, st = (
            _expect_case(name)
        )
        case = ledger["cases"][name]
        assert case["case_id"] == name
        assert isinstance(case["assemble_ok"], bool)
        assert case["assemble_ok"] is local_assemble
        cp = _entry(case, "classpath")
        mp = _entry(case, "module-path")
        assert cp["classifier_pick"] == mp["classifier_pick"] == pick
        assert cp["stamp_bind"] == mp["stamp_bind"] == stamp
        assert cp["soname_mark"] == mp["soname_mark"] == soname
        assert cp["stub_gate"] == mp["stub_gate"] == gate
        assert cp["path_lane"] == cp_lane
        assert mp["path_lane"] == mp_lane
        assert cp["bind_ok"] is cp_ok
        assert mp["bind_ok"] is mp_ok
        assert cp["row_token"] == cp_tok
        assert mp["row_token"] == mp_tok
        assert case["state_hash"] == st
    _, _, _, _, _, _, q_mp_lane, q_mp_ok, _, _, _ = _expect_case("quartz")
    qmp = _entry(ledger["cases"]["quartz"], "module-path")
    assert qmp["path_lane"] == q_mp_lane
    assert qmp["bind_ok"] is q_mp_ok


def test_sidecar_nonauthority(ledger, claim):
    """Local assemble claim may stay true while a path_mode bind fails."""
    local_assemble = True
    assert claim.get("assemble_ok") is local_assemble
    assert claim.get("checked") == len(CASE_NAMES)
    pick, _, _, _, _, _, mp_lane, mp_ok, _, mp_tok, st = _expect_case("quartz")
    case = ledger["cases"]["quartz"]
    assert case["assemble_ok"] is local_assemble
    mp = _entry(case, "module-path")
    assert mp["path_lane"] == mp_lane
    assert mp_lane == "leak"
    assert mp["bind_ok"] is mp_ok
    assert mp["classifier_pick"] == pick
    assert mp["row_token"] == mp_tok
    assert case["state_hash"] == st


def test_edge_mark_agree(ledger):
    """stamp_bind and soname_mark must match the selected toolchain arch."""
    for name in CASE_NAMES:
        pick, stamp, soname, gate, *_ = _expect_case(name)
        for mode in ("classpath", "module-path"):
            row = _entry(ledger["cases"][name], mode)
            assert row["classifier_pick"] == pick
            assert row["stamp_bind"] == stamp
            assert row["soname_mark"] == soname
            assert row["stub_gate"] == gate
            assert row["stamp_bind"] != "jx-stub"
            assert row["soname_mark"] != "libffm-stub.so"


def test_bait_refuse_real(ledger):
    """stub_gate must refuse whenever a real toolchain classifier exists."""
    for name in CASE_NAMES:
        for mode in ("classpath", "module-path"):
            row = _entry(ledger["cases"][name], mode)
            assert row["stub_gate"] == "refuse"
            assert row["stub_gate"] != "allow"
            assert row["classifier_pick"] != "stub"


def test_second_pass_stable(ledger):
    """Replaying the reactor reproduces identical state_hash digests."""
    first = {n: ledger["cases"][n]["state_hash"] for n in CASE_NAMES}
    _regenerate_outputs()
    second = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert set(second["cases"]) == set(CASE_NAMES)
    for name in CASE_NAMES:
        *_, st = _expect_case(name)
        assert first[name] == st
        assert second["cases"][name]["state_hash"] == st
        assert first[name] == second["cases"][name]["state_hash"]
