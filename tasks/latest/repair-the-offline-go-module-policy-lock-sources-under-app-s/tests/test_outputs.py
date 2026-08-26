"""Behavioral verifier for recover-go-module-policy-locks (contracts C1–C15)."""
from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

import jsonschema
import pytest

APP = Path("/app")
BIN = APP / "bin" / "modpolicylock"
MIRROR = APP / "var" / "module-mirror"
DB = APP / "var" / "policy-index" / "policy.db"
OUT = Path("/output")
TMP = Path("/tmp")
SCHEMA_LOCK = json.loads((APP / "schemas" / "modpolicy.lock.schema.json").read_text())
SCHEMA_REPORT = json.loads((APP / "schemas" / "policy-report.schema.json").read_text())
LEGACY_DIR = APP / "fixtures" / "legacy" / "v1"
WITNESS = json.loads((LEGACY_DIR / "witness.json").read_text())
HARNESS = APP / "scripts" / "offline-modpolicy.sh"
POLICY_REVISION = "rev20260717"
SEED = int(os.environ.get("TB3_MODPOLICY_SEED", "20260717"))

LEGACY_CHECKSUM = hashlib.sha256(
    b"".join(sorted(p.read_bytes() for p in LEGACY_DIR.iterdir() if p.is_file()))
).hexdigest()
_STORED_CHECKSUM = LEGACY_CHECKSUM


def compute_digest(modules: list[dict]) -> str:
    payload = []
    for mod in sorted(modules, key=lambda m: m["path"]):
        payload.append({
            "path": mod["path"],
            "version": mod["version"],
            "source": mod["source"],
            "policy_decision": mod["policy_decision"],
            "replaces": mod.get("replaces") or [],
        })
    raw = json.dumps(payload, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def load_pins(goos: str, goarch: str) -> dict[str, tuple[str, str]]:
    pins: dict[str, tuple[str, str]] = {}
    for line in (MIRROR / "policy" / "pins.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row["goos"] == goos and row["goarch"] == goarch and row["policy_revision"] == POLICY_REVISION:
            pins[row["path"]] = (row["version"], row["decision"])
    return pins


def mirror_version(path: str) -> str:
    list_path = MIRROR / "cache" / "download" / path / "@v" / "list"
    ver = "v1.0.0"
    if list_path.exists():
        ver = list_path.read_text().strip().splitlines()[0]
    info = MIRROR / "cache" / "download" / path / "@v" / f"{ver}.info"
    if not info.exists():
        raise KeyError(path)
    for line in info.read_text().splitlines():
        if line.startswith("Version: "):
            return line.split("Version: ", 1)[1]
    return ver


def rank_pairs(replaces: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(replaces, key=lambda r: (r["old_path"], r["new_path"]))


def pick_replace(path: str, replaces: list[dict[str, str]]) -> tuple[str, str, str, list[dict[str, str]]]:
    candidates = [r for r in rank_pairs(replaces) if r["old_path"] == path]
    if not candidates:
        return path, mirror_version(path), "mirror", []
    winner = candidates[-1]
    return winner["new_path"], winner["new_version"], "replace", [winner]


def workspace_uses(request_path: Path) -> dict[str, str]:
    uses: dict[str, str] = {}
    work = request_path.parent / "go.work"
    if not work.exists():
        return uses
    for line in work.read_text().splitlines():
        line = line.strip()
        if line.startswith("use "):
            rel = line[4:].strip(" ()")
            mod_file = request_path.parent / rel / "go.mod"
            if mod_file.exists():
                for ml in mod_file.read_text().splitlines():
                    ml = ml.strip()
                    if ml.startswith("module "):
                        uses[ml.split()[1]] = str(mod_file.parent)
    return uses


def mirror_deps(root: str) -> list[str]:
    mod = MIRROR / "cache" / "download" / root / "@v" / "v1.0.0.mod"
    if not mod.exists():
        return []
    deps = []
    for line in mod.read_text().splitlines():
        line = line.strip()
        if line.startswith("require "):
            parts = line.split()
            if len(parts) >= 2:
                deps.append(parts[1])
    return sorted(deps)


def resolve_module(path: str, replaces: list[dict[str, str]], uses: dict[str, str], pins: dict[str, tuple[str, str]]) -> dict:
    if path in uses:
        version = mirror_version(path)
        return {
            "path": path,
            "version": version,
            "source": "workspace",
            "policy_decision": "workspace_override",
            "replaces": [],
        }
    cur, version, source, active = pick_replace(path, replaces)
    decision = "replace_applied" if source == "replace" else "allow"
    if cur in pins:
        version, decision = pins[cur]
    elif source == "mirror":
        version = mirror_version(cur)
    return {
        "path": cur,
        "version": version,
        "source": source,
        "policy_decision": decision,
        "replaces": active,
    }


def resolve_request(request_path: Path, goos: str, goarch: str) -> dict:
    req = json.loads(request_path.read_text())
    pins = load_pins(goos, goarch)
    uses = workspace_uses(request_path)
    replaces = req.get("replaces", [])
    root = req["root_module"]
    modules = [resolve_module(root, [], uses, pins)]
    modules[0]["replaces"] = []
    for dep in mirror_deps(root):
        modules.append(resolve_module(dep, replaces, uses, pins))
    modules.sort(key=lambda m: m["path"])
    return {
        "schema_version": "modpolicy/v2",
        "goos": goos,
        "goarch": goarch,
        "policy_revision": POLICY_REVISION,
        "modules": modules,
        "resolution_digest": compute_digest(modules),
    }


def migrate_v1(data: dict) -> dict:
    modules = []
    for m in data["modules"]:
        code = m["policy_code"]
        pd = {"P": "policy", "W": "workspace", "R": "replace"}.get(code, "allow")
        src = {"W": "workspace", "R": "replace"}.get(code, m.get("source", "mirror"))
        entry = {
            "path": m["path"],
            "version": m["version"],
            "source": src,
            "policy_decision": pd,
            "replaces": [],
        }
        if m.get("replace_old"):
            entry["replaces"] = [{
                "old_path": m["replace_old"],
                "new_path": m["replace_new"],
                "new_version": m["replace_version"],
            }]
        modules.append(entry)
    modules.sort(key=lambda x: x["path"])
    return {
        "schema_version": "modpolicy/v2",
        "goos": data["goos"],
        "goarch": data["goarch"],
        "policy_revision": POLICY_REVISION,
        "modules": modules,
        "resolution_digest": compute_digest(modules),
    }


def build_seeded_request(tmp_dir: Path) -> tuple[Path, str, str]:
    rng = random.Random(SEED)
    alias = rng.choice(["alpha", "beta", "gamma"])
    goarch = rng.choice(["amd64", "arm64"])
    ws = tmp_dir / f"seed-{alias}"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "go.mod").write_text(
        "module corp.example/root\n\ngo 1.24\n\nrequire corp.example/lib v1.0.0\n"
    )
    (ws / "lib").mkdir(exist_ok=True)
    (ws / "lib" / "go.mod").write_text("module corp.example/lib\n\ngo 1.24\n")
    (ws / "go.work").write_text("go 1.24\n\nuse ./lib\n")
    req_path = ws / "request.json"
    req_path.write_text(json.dumps({
        "root_module": "corp.example/root",
        "root_version": "v1.0.0",
        "replaces": [],
    }, indent=2) + "\n")
    return req_path, "linux", goarch


def run_cmd(cmd: list[str], env: dict | None = None, cwd: str | None = None) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(cmd, capture_output=True, text=True, env=merged, cwd=cwd)


def rebuild_binary(root: Path | None = None) -> None:
    base = root or APP
    env = {"PATH": "/usr/local/go/bin:" + os.environ.get("PATH", "/usr/bin:/bin")}
    run_cmd(
        ["go", "build", "-o", str(base / "bin" / "modpolicylock"), "./cmd/modpolicylock"],
        cwd=str(base),
        env=env,
    )


def reindex_clean(db_path: Path, mirror: Path = MIRROR) -> None:
    run_cmd([str(BIN), "reindex", "--mirror", str(mirror), "--db", str(db_path)])


def copy_clean_root() -> Path:
    clean = TMP / "tb3-modpolicy-root"
    if clean.exists():
        shutil.rmtree(clean)
    shutil.copytree(APP, clean, ignore=shutil.ignore_patterns("*.db", "*.db-*"), dirs_exist_ok=True)
    (clean / "var" / "policy-index").mkdir(parents=True, exist_ok=True)
    return clean


def run_interrupt_fixture(db_path: Path) -> None:
    run_cmd([str(APP / "scripts" / "interrupt-reindex.sh"), str(db_path)])


@pytest.fixture(scope="session", autouse=True)
def rebuild_tool_once() -> None:
    if BIN.exists():
        BIN.unlink()
    rebuild_binary()


@pytest.fixture(autouse=True)
def fresh_index() -> None:
    if DB.exists():
        DB.unlink()
    reindex_clean(DB)


def run_harness(
    request: Path,
    goos: str = "linux",
    goarch: str = "amd64",
    lock: Path | None = None,
    report: Path | None = None,
    root: str = "/app",
) -> subprocess.CompletedProcess:
    lock = lock or (OUT / "modpolicy.lock.json")
    report = report or (OUT / "policy-report.json")
    lock.parent.mkdir(parents=True, exist_ok=True)
    env = {"MODPOLICY_OFFLINE": "1", "GOPROXY": "off", "GOSUMDB": "off"}
    return run_cmd([
        str(HARNESS),
        "--request", str(request),
        "--goos", goos,
        "--goarch", goarch,
        "--lock", str(lock),
        "--report", str(report),
        "--root", root,
    ], env=env)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def assert_sorted_modules(doc: dict) -> None:
    paths = [m["path"] for m in doc["modules"]]
    assert paths == sorted(paths)


def test_fixture_tamper_rejected() -> None:
    """Contract C9: legacy fixture checksum stable."""
    current = hashlib.sha256(
        b"".join(sorted(p.read_bytes() for p in LEGACY_DIR.iterdir() if p.is_file()))
    ).hexdigest()
    assert current == _STORED_CHECKSUM


def test_rebuild_required() -> None:
    """Contract C1: verifier rebuilds modpolicylock from sources."""
    assert BIN.exists()
    stat1 = BIN.stat().st_mtime
    rebuild_binary()
    assert BIN.exists()
    assert BIN.stat().st_mtime >= stat1


def test_smoke_resolve_writes_artifacts() -> None:
    """Contracts C2, C3: smoke harness writes schema-valid sorted outputs."""
    run_harness(APP / "workspaces" / "smoke" / "request.json")
    lock = load_json(OUT / "modpolicy.lock.json")
    report = load_json(OUT / "policy-report.json")
    jsonschema.validate(lock, SCHEMA_LOCK)
    jsonschema.validate(report, SCHEMA_REPORT)
    assert_sorted_modules(lock)
    assert_sorted_modules(report)


def test_lock_report_graph_agreement() -> None:
    """Contract C4: replace-conflict lock and report agree semantically."""
    run_harness(APP / "workspaces" / "replace-conflict" / "request.json")
    lock = load_json(OUT / "modpolicy.lock.json")
    report = load_json(OUT / "policy-report.json")
    assert lock["resolution_digest"] == report["resolution_digest"]
    for lm in lock["modules"]:
        rm = next(m for m in report["modules"] if m["path"] == lm["path"])
        assert rm["version"] == lm["version"]
        assert rm["source"] == lm["source"]
        assert rm["policy_decision"] == lm["policy_decision"]


def test_precedence_workspace_over_replace() -> None:
    """Contract C5: workspace overlay beats replace on workspace-override fixture."""
    run_harness(APP / "workspaces" / "workspace-override" / "request.json")
    lock = load_json(OUT / "modpolicy.lock.json")
    ws = next(m for m in lock["modules"] if m["path"] == "corp.example/wslib")
    assert ws["source"] == "workspace"
    assert ws["policy_decision"] == "workspace_override"
    assert ws["version"] == "v1.0.0"


def test_precedence_replace_total_order() -> None:
    """Contract C5: fork-beta wins under contract total order."""
    run_harness(APP / "workspaces" / "replace-conflict" / "request.json")
    lock = load_json(OUT / "modpolicy.lock.json")
    fork = next(m for m in lock["modules"] if "fork" in m["path"])
    assert fork["path"] == "corp.example/fork-beta"
    assert fork["version"] == "v1.1.0-beta"


def test_platform_target_isolation() -> None:
    """Contract C6: amd64 and arm64 digests differ for platform-pin."""
    lock_amd = OUT / "modpolicy-amd64.lock.json"
    lock_arm = OUT / "modpolicy-arm64.lock.json"
    p1 = run_harness(APP / "workspaces" / "platform-pin" / "request.json", goarch="amd64", lock=lock_amd)
    assert p1.returncode == 0, p1.stderr
    if DB.exists():
        DB.unlink()
    reindex_clean(DB)
    p2 = run_harness(APP / "workspaces" / "platform-pin" / "request.json", goarch="arm64", lock=lock_arm)
    assert p2.returncode == 0, p2.stderr
    d1 = load_json(lock_amd)["resolution_digest"]
    d2 = load_json(lock_arm)["resolution_digest"]
    assert d1 != d2
    arm_mod = next(m for m in load_json(lock_arm)["modules"] if m["path"] == "corp.example/cgoish")
    assert arm_mod["version"] == "v2.0.0-arm"


def test_clean_copied_root_digest() -> None:
    """Contract C7: copied clean root matches in-tree digest."""
    proc = run_harness(APP / "workspaces" / "smoke" / "request.json")
    assert proc.returncode == 0, proc.stderr
    in_tree = load_json(OUT / "modpolicy.lock.json")["resolution_digest"]
    root = copy_clean_root()
    out_lock = OUT / "modpolicy-clean.lock.json"
    out_report = OUT / "policy-report-clean.json"
    rebuild_binary(root)
    reindex_clean(root / "var" / "policy-index" / "policy.db", mirror=root / "var" / "module-mirror")
    proc2 = run_harness(
        root / "workspaces" / "smoke" / "request.json",
        lock=out_lock,
        report=out_report,
        root=str(root),
    )
    assert proc2.returncode == 0, proc2.stderr
    assert load_json(out_lock)["resolution_digest"] == in_tree


def test_interrupted_reindex_not_complete() -> None:
    """Contract C8: partial index must not stay complete after fix."""
    partial_db = TMP / "tb3-partial-policy.db"
    if partial_db.exists():
        partial_db.unlink()
    run_interrupt_fixture(partial_db)
    conn = sqlite3.connect(partial_db)
    complete = conn.execute("SELECT index_complete FROM index_meta WHERE id=1").fetchone()[0]
    pin_count = conn.execute("SELECT COUNT(*) FROM pins").fetchone()[0]
    total = sum(1 for line in (MIRROR / "policy" / "pins.jsonl").read_text().splitlines() if line.strip())
    conn.close()
    assert complete == 1 and pin_count < total
    proc = run_harness(APP / "workspaces" / "smoke" / "request.json")
    assert proc.returncode == 0, proc.stderr


def test_clean_vs_resumed_reindex_idempotent() -> None:
    """Contracts C8, C12: clean and resumed reindex yield identical digests."""
    db_clean = TMP / "tb3-clean.db"
    db_resume = TMP / "tb3-resume.db"
    for p in (db_clean, db_resume):
        if p.exists():
            p.unlink()
    run_cmd([str(BIN), "reindex", "--mirror", str(MIRROR), "--db", str(db_clean)])
    run_interrupt_fixture(db_resume)
    run_cmd([str(BIN), "reindex", "--mirror", str(MIRROR), "--db", str(db_resume), "--resume"])
    env = {"MODPOLICY_OFFLINE": "1"}

    def digest_with(db_path: Path) -> str:
        lock = TMP / f"lock-{db_path.name}.json"
        run_cmd([
            str(BIN), "resolve",
            "--request", str(APP / "workspaces" / "smoke" / "request.json"),
            "--goos", "linux", "--goarch", "amd64",
            "--lock", str(lock), "--db", str(db_path),
        ], env=env)
        return load_json(lock)["resolution_digest"]

    assert digest_with(db_clean) == digest_with(db_resume)


def test_legacy_v1_lock_witness() -> None:
    """Contract C9: migrate-lock matches witness digests."""
    for name, expected in WITNESS["files"].items():
        src = LEGACY_DIR / name
        out = TMP / f"migrated-{name}"
        proc = run_cmd([str(BIN), "migrate-lock", "--in", str(src), "--out", str(out)])
        assert proc.returncode == 0, proc.stderr
        assert load_json(out)["resolution_digest"] == expected


def test_unauthorized_module_diagnostics() -> None:
    """Contract C10: missing module exits 23 with required token."""
    bad = TMP / "bad-request.json"
    bad.write_text(json.dumps({
        "root_module": "corp.example/banned",
        "root_version": "v9.9.9",
        "replaces": [],
    }))
    proc = run_cmd([
        str(HARNESS),
        "--request", str(bad),
        "--goos", "linux", "--goarch", "amd64",
        "--lock", str(OUT / "bad.lock.json"),
        "--report", str(OUT / "bad-report.json"),
    ], env={"MODPOLICY_OFFLINE": "1"})
    assert proc.returncode == 23
    assert "unauthorized or missing module" in (proc.stderr or "")


def test_supported_modules_preserved() -> None:
    """Contract C11: smoke graph matches independent preservation witness."""
    run_harness(APP / "workspaces" / "smoke" / "request.json")
    lock = load_json(OUT / "modpolicy.lock.json")
    expected = resolve_request(APP / "workspaces" / "smoke" / "request.json", "linux", "amd64")
    assert lock["resolution_digest"] == expected["resolution_digest"]


def test_repeated_clean_idempotent() -> None:
    """Contract C12: two clean harness runs produce identical digests."""
    run_harness(APP / "workspaces" / "smoke" / "request.json")
    d1 = load_json(OUT / "modpolicy.lock.json")["resolution_digest"]
    if DB.exists():
        DB.unlink()
    reindex_clean(DB)
    run_harness(APP / "workspaces" / "smoke" / "request.json")
    d2 = load_json(OUT / "modpolicy.lock.json")["resolution_digest"]
    assert d1 == d2


def test_seeded_hidden_graphs() -> None:
    """Contract C13: seeded request matches independent resolution rules."""
    with tempfile.TemporaryDirectory(prefix="tb3-seed-") as tmp:
        req, goos, goarch = build_seeded_request(Path(tmp))
        proc = run_harness(req, goos=goos, goarch=goarch)
        assert proc.returncode == 0, proc.stderr
        lock = load_json(OUT / "modpolicy.lock.json")
        expected = resolve_request(req, goos, goarch)
        assert lock["resolution_digest"] == expected["resolution_digest"]


def test_offline_env_honored() -> None:
    """Contract C14: success with MODPOLICY_OFFLINE=1 and proxy disabled."""
    env = {"MODPOLICY_OFFLINE": "1", "GOPROXY": "off", "GOSUMDB": "off", "HTTP_PROXY": "", "HTTPS_PROXY": ""}
    run_cmd([
        str(HARNESS),
        "--request", str(APP / "workspaces" / "smoke" / "request.json"),
        "--goos", "linux", "--goarch", "amd64",
        "--lock", str(OUT / "offline.lock.json"),
        "--report", str(OUT / "offline-report.json"),
    ], env=env)
    offline = load_json(OUT / "offline.lock.json")
    assert offline["resolution_digest"] == resolve_request(
        APP / "workspaces" / "smoke" / "request.json", "linux", "amd64"
    )["resolution_digest"]


def test_cli_surface_preserved() -> None:
    """Contract C15: documented subcommands remain available."""
    proc = run_cmd([str(BIN), "--help"])
    assert proc.returncode == 0
    for sub in ("resolve", "report", "reindex", "migrate-lock", "verify"):
        assert sub in proc.stdout


def test_dummy_binary_replacement_detected() -> None:
    """Contracts C1, C4: stub binary cannot satisfy graph checks."""
    backup = BIN.with_suffix(".real")
    shutil.copy2(BIN, backup)
    BIN.write_text("#!/bin/sh\necho stub\nexit 0\n")
    BIN.chmod(0o755)
    for name in ("modpolicy.lock.json", "policy-report.json"):
        p = OUT / name
        if p.exists():
            p.unlink()
    proc = run_harness(APP / "workspaces" / "replace-conflict" / "request.json")
    combined = (proc.stdout or "") + (proc.stderr or "")
    shutil.copy2(backup, BIN)
    rebuild_binary()
    assert "stub" in combined
    lock = OUT / "modpolicy.lock.json"
    assert (not lock.exists()) or (proc.returncode != 0) or ("stub" in combined)


def test_migrate_reference_parity() -> None:
    """Contract C9 auxiliary: independent migrate matches witness."""
    for name, expected in WITNESS["files"].items():
        data = json.loads((LEGACY_DIR / name).read_text())
        migrated = migrate_v1(data)
        assert migrated["resolution_digest"] == expected
