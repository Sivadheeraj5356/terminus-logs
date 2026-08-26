import json
import os
import shutil
import subprocess
from pathlib import Path

OUT = Path("/app/output/kq_report.json")
STAGE = Path("/app/output/kq_stage.ndjson")
FRAMES = Path("/app/output/kq_frames.ndjson")
AUTH = Path("/app/output/kq_auth.bin")
S0 = Path("/app/environment/deck_p/s0")
HIDDEN = Path("/app/environment/deck_p/hidden")
DECK_JSON = S0 / "deck_s0.json"


def _require(cond: bool, msg: str = "") -> None:
    if not cond:
        raise AssertionError(msg)


def _kq_invoke(deck: Path, extra_env: dict | None = None, reload: bool = False) -> dict:
    for p in (OUT, STAGE, FRAMES, AUTH):
        if p.exists():
            p.unlink()
    env = os.environ.copy()
    for k in ("KQ_APPEND_CONTROL", "KQ_DEFINE_BLOB", "KQ_ARGV_WIRE", "KQ_WRAP_BIN", "KQ_DENYLIST"):
        env.pop(k, None)
    if extra_env:
        env.update(extra_env)
    cmd = ["/app/environment/tools/kq_run", "--deck", str(deck), "--out", str(OUT)]
    if reload:
        cmd.append("--reload")
    subprocess.run(cmd, check=True, env=env, cwd="/app")
    return json.loads(OUT.read_text())


def _view(rec: dict, scen: str, view: str) -> list[dict]:
    return [r for r in rec["rows"] if r["scenario"] == scen and r["view"] == view]


def test_kq_a01():
    """Offline rebuild: identical cache_digest and frame ingest present."""
    first = _kq_invoke(S0)
    second = _kq_invoke(S0)
    _require(FRAMES.exists() and STAGE.exists())
    _require(any('"kind":"epoch"' in ln.replace(" ", "") for ln in FRAMES.read_text().splitlines()))
    _require(first["cache_digest"] == second["cache_digest"])
    _require(len(first["cache_digest"]) == 64)
    deck = json.loads(DECK_JSON.read_text())
    for scen in ("base_a", "base_b", "base_c"):
        gen = deck["scenarios"][scen]["generation"]
        _require(all(r["generation"] == gen for r in first["rows"] if r["scenario"] == scen))


def test_kq_a02():
    """Lock-tier reload: env_resp.rsp wins; scope_hash is length+tier."""
    rsp = (S0 / "env_resp.rsp").read_text().strip()
    _require(rsp == "env_lane_prime")
    rec = _kq_invoke(S0, reload=True)
    scope = _view(rec, "reload_r1", "scope")
    _require(scope and scope[0]["hash_count"] == len(rsp) + 3)
    _require(scope[0]["hash_count"] != len("env_reload"))
    _require(scope[0]["hash_count"] != len(rsp))


def test_kq_a03(tmp_path):
    """Define-order pin variants: permuted keys and scaled ticks match public lock."""
    base = _kq_invoke(S0)
    base_ticks = {r["key"]: r["hash_count"] for r in _view(base, "base_a", "define_trace")}
    _require(base_ticks == {"alpha": 100, "beta": 200, "gamma": 150})
    fix = tmp_path / "perm"
    shutil.copytree(S0, fix)
    shutil.copy(HIDDEN / "blob_perm.bin", fix / "blob_perm.bin")
    perm = _kq_invoke(fix, extra_env={"KQ_DEFINE_BLOB": str(fix / "blob_perm.bin")})
    _require({r["key"]: r["hash_count"] for r in _view(perm, "base_a", "define_trace")} == base_ticks)
    scale = _kq_invoke(S0, extra_env={"KQ_DEFINE_BLOB": str(HIDDEN / "blob_scale.bin")})
    _require({r["key"]: r["hash_count"] for r in _view(scale, "base_a", "define_trace")} == base_ticks)


def test_kq_a04(tmp_path):
    """Pin-mismatch release gate: wrapper/argv blend and fork_f1 attestation."""
    fix = tmp_path / "mis"
    shutil.copytree(S0, fix)
    rec = _kq_invoke(
        fix,
        extra_env={
            "KQ_ARGV_WIRE": str(HIDDEN / "mismatch_argv.bin"),
            "KQ_WRAP_BIN": str(HIDDEN / "mismatch_wrap.bin"),
        },
    )
    _require("decoy_z" not in {r["key"] for r in _view(rec, "base_a", "argv_text")})
    w = [r for r in rec["rows"] if r["scenario"] == "base_a" and r["view"] == "witness"]
    _require(len(w) == 1 and w[0]["hash_count"] == 7)
    fork = _kq_invoke(S0)
    fw = [r for r in fork["rows"] if r["scenario"] == "fork_f1" and r["view"] == "witness"]
    _require(len(fw) == 1 and fw[0]["hash_count"] == 7)
    _require(_view(fork, "base_a", "wrapper_hash_bin")[0]["hash_count"] == 6)


def test_kq_a05():
    """Native compiler stub witness band; staging ledger_bind for bind closure."""
    rec = _kq_invoke(S0)
    _require(_view(rec, "native_n1", "witness")[0]["hash_count"] == 16)
    _require(any('"kind":"native"' in ln.replace(" ", "") for ln in FRAMES.read_text().splitlines()))
    _require(any(",ledger_bind,bind," in ln for ln in STAGE.read_text().splitlines()))


def test_kq_a06(tmp_path):
    """Dependency tick budget: over-budget fold and perm+scale coupled flags."""
    fix = tmp_path / "tick"
    shutil.copytree(S0, fix)
    over = _kq_invoke(fix, extra_env={"KQ_DEFINE_BLOB": str(HIDDEN / "blob_over_tick.bin")})
    ticks = [r["hash_count"] for r in _view(over, "base_a", "define_trace")]
    _require(len(ticks) == 3 and sum(ticks) == 510 and sorted(ticks) == [53, 213, 244])
    combo = _kq_invoke(fix, extra_env={"KQ_DEFINE_BLOB": str(HIDDEN / "blob_perm_scale.bin")})
    _require({r["key"] for r in _view(combo, "base_a", "define_trace")} == {"alpha", "beta", "gamma"})
    combo_ticks = sorted(r["hash_count"] for r in _view(combo, "base_a", "define_trace"))
    _require(combo_ticks == [148, 169, 191])
    _require(sum(combo_ticks) == 508)


def test_kq_a07():
    """Epoch-weighted ledger_bind closure on base_a equals 102."""
    a = _kq_invoke(S0)
    b = _kq_invoke(S0)
    _require(a["cache_digest"] == b["cache_digest"])
    _require(_view(a, "base_a", "ledger_bind")[0]["hash_count"] == 102)
    _require(_view(b, "base_a", "ledger_bind")[0]["hash_count"] == 102)
    _require((S0 / "epoch.txt").read_text().strip() == "3")


def test_kq_a08():
    """Metamorphic empty-control wrap shifts reproducibility digest."""
    base = _kq_invoke(S0)
    shifted = _kq_invoke(S0, extra_env={"KQ_APPEND_CONTROL": "1"})
    _require(base["cache_digest"] != shifted["cache_digest"])
    _require(FRAMES.exists())
    _require(_view(shifted, "base_a", "ledger_bind"))
    _require(any(ln.startswith("control_empty,wrapper_hash_bin,ctrl,") for ln in STAGE.read_text().splitlines()))


def test_kq_a09(tmp_path):
    """Denylist must not drop define-order gamma or admit decoy argv pins."""
    fix = tmp_path / "deny"
    shutil.copytree(S0, fix)
    rec = _kq_invoke(
        fix,
        extra_env={
            "KQ_DEFINE_BLOB": str(HIDDEN / "blob_perm.bin"),
            "KQ_DENYLIST": str(HIDDEN / "denylist_tight.json"),
        },
    )
    _require("gamma" in {r["key"] for r in _view(rec, "base_a", "define_trace")})
    _require("decoy_x" not in {r["key"] for r in _view(rec, "base_a", "argv_text")})
    _require("ph_b" not in {r["key"] for r in _view(rec, "base_a", "argv_text")})


def test_kq_a10():
    """Public lock pins: YAML scope, frames required, wrap sum attestation."""
    rec = _kq_invoke(S0)
    _require(FRAMES.exists() and len(rec["cache_digest"]) == 64)
    _require(_view(rec, "base_a", "scope")[0]["hash_count"] == len("env_gamma"))
    _require(len(_view(rec, "base_a", "argv_text")) == 2)
    _require("ph_b" not in {r["key"] for r in _view(rec, "base_a", "argv_text")})
    _require(_view(rec, "base_c", "wrapper_hash_bin")[0]["hash_count"] == 6)
    _require(_view(rec, "fork_f1", "ledger_bind"))


def test_kq_a11():
    """Auth lane artifact present with two-byte little-endian closure."""
    _kq_invoke(S0)
    _require(AUTH.exists() and AUTH.stat().st_size == 2)
    lane = int.from_bytes(AUTH.read_bytes(), "little")
    _require(lane == 81)


def test_kq_a12(tmp_path):
    """Argv status gate suppresses argv_text when status is not nominal."""
    fix = tmp_path / "hold"
    shutil.copytree(S0, fix)
    deck = json.loads((fix / "deck_s0.json").read_text())
    deck["scenarios"]["base_a"]["argv_status"] = "quarantine"
    (fix / "deck_s0.json").write_text(json.dumps(deck, indent=2) + "\n")
    rec = _kq_invoke(fix)
    _require(len(_view(rec, "base_a", "argv_text")) == 0)
    _require(_view(rec, "base_a", "define_trace"))


def test_kq_a13():
    """Phantom argv authority triggers band_reconcile witness on base_a."""
    rec = _kq_invoke(S0)
    w = [r for r in rec["rows"] if r["scenario"] == "base_a" and r["view"] == "witness"]
    _require(len(w) == 1 and w[0]["hash_count"] == 8)


def test_kq_a14(tmp_path):
    """Denylist width mismatch leaves blocked argv keys visible."""
    fix = tmp_path / "wide"
    shutil.copytree(S0, fix)
    deny = HIDDEN / "denylist_tight.json"
    text = deny.read_text().replace('"required_width": 41', '"required_width": 99')
    bad = fix / "deny_bad.json"
    bad.write_text(text)
    rec = _kq_invoke(fix, extra_env={"KQ_DENYLIST": str(bad)})
    _require("arg_a" in {r["key"] for r in _view(rec, "base_a", "argv_text")})


def test_kq_a15():
    """Reload path shifts cache_digest from YAML-only scope."""
    plain = _kq_invoke(S0)
    reloaded = _kq_invoke(S0, reload=True)
    _require(plain["cache_digest"] != reloaded["cache_digest"])


def test_kq_a16():
    """Fork scenario wrapper authority sums segment counts."""
    rec = _kq_invoke(S0)
    _require(_view(rec, "fork_f1", "wrapper_hash_bin")[0]["hash_count"] == 9)


def test_kq_a17():
    """Staging ledger has more rows than report when control wrap appended."""
    shifted = _kq_invoke(S0, extra_env={"KQ_APPEND_CONTROL": "1"})
    stage_n = len(STAGE.read_text().splitlines())
    _require(stage_n > len(shifted["rows"]))


def test_kq_a18():
    """Base_b preserves generation stamp from deck."""
    rec = _kq_invoke(S0)
    rows = [r for r in rec["rows"] if r["scenario"] == "base_b"]
    _require(len(rows) >= 3)
    _require(all(r["generation"] == 2 for r in rows))


def test_kq_a19():
    """Native witness appears only on native_n1."""
    rec = _kq_invoke(S0)
    native = [r for r in rec["rows"] if r["view"] == "witness" and r["scenario"] == "native_n1"]
    other = [r for r in rec["rows"] if r["view"] == "witness" and r["scenario"] != "native_n1" and r["key"] == "band_reconcile"]
    _require(len(native) == 1 and native[0]["hash_count"] == 16)
    _require(len(other) >= 1)


def test_kq_a20(tmp_path):
    """Pin-mismatch wires keep witness closure at seven."""
    fix = tmp_path / "pin"
    shutil.copytree(S0, fix)
    rec = _kq_invoke(
        fix,
        extra_env={
            "KQ_ARGV_WIRE": str(HIDDEN / "mismatch_argv.bin"),
            "KQ_WRAP_BIN": str(HIDDEN / "mismatch_wrap.bin"),
        },
    )
    w = [r for r in rec["rows"] if r["scenario"] == "base_a" and r["view"] == "witness"]
    _require(len(w) == 1 and w[0]["hash_count"] == 7)
