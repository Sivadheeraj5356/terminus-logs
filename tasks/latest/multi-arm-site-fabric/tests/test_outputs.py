import configparser
import hashlib
import json
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, "/usr/lib/sitefab")
from law_digest import law_digest_lines  # noqa: E402

SHARE = Path("/app/environment")
TOPOLOGY = SHARE / "topology"
SCENARIOS = SHARE / "scenarios"
OUT = Path("/app/output/sitefab_report.json")
JOURNAL = Path("/var/lib/sitefab/journal.json")
ETC = Path("/etc/sitefab")
ENGINE = Path("/usr/lib/sitefab/engine.py")
SEAL = Path("/usr/lib/sitefab/SEAL")

ALL_SCRIPTS = sorted(SCENARIOS.glob("*.script"))
PARTIAL_CONTINUE = {
    "n15_carry_resume.script",
    "n21_dep_release.script",
    "n23_chain_mid.script",
    "n23_chain_end.script",
    "n25_latch_clear.script",
}
SWEEP_EXCLUDE = PARTIAL_CONTINUE | {
    "n21_dep_hold.script",
    "n23_chain_seed.script",
    "n25_latch_seed.script",
    "n07_bind_suffix.script",
}


def _assert_runtime_seal() -> None:
    want = SEAL.read_text(encoding="utf-8").strip()
    got = hashlib.sha256(ENGINE.read_bytes()).hexdigest()
    assert got == want, "sealed sitefab runtime was modified"


def _purge_journal() -> None:
    if JOURNAL.exists():
        JOURNAL.unlink()


def _seed_journal(payload: dict) -> None:
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    JOURNAL.write_text(json.dumps(payload), encoding="utf-8")


def _run(
    script_name: str,
    *,
    continue_run: bool = False,
    purge: bool = False,
) -> dict:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    cmd = ["/app/bin/sitefab", f"--script={SCENARIOS / script_name}"]
    if continue_run:
        cmd.append("--continue")
    if purge:
        cmd.append("--purge")
    subprocess.run(cmd, check=True)
    return json.loads(OUT.read_text(encoding="utf-8"))


def _load_profile(name: str) -> dict:
    return json.loads((TOPOLOGY / f"{name}.json").read_text(encoding="utf-8"))


def _parse_script_profile(script_name: str) -> str:
    for line in (SCENARIOS / script_name).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("profile "):
            return line.split()[1]
    return "alpha"


def _script_has_bar(script_name: str) -> bool:
    return any(
        line.strip().startswith("step bar")
        for line in (SCENARIOS / script_name).read_text(encoding="utf-8").splitlines()
    )


def _merged_policy() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.read(ETC / "sitefab.conf")
    drop = ETC / "policy.d"
    if drop.is_dir():
        for path in sorted(drop.glob("*.conf")):
            part = configparser.ConfigParser()
            part.read(path)
            for section in part.sections():
                if not cfg.has_section(section):
                    cfg.add_section(section)
                for key, val in part.items(section):
                    cfg.set(section, key, val)
    return cfg


def _parse_unit(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    section = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        data[f"{section}.{key.strip()}"] = val.strip()
    return data


def _load_template(name: str) -> dict[str, str]:
    if not name:
        return {}
    return _parse_unit(ETC / "templates" / f"{name}.mount")


def _arm_unit(arm: str, profile: str) -> dict[str, str]:
    scoped = ETC / "units" / profile / f"{arm}.mount"
    shared = ETC / "units" / f"{arm}.mount"
    base = scoped if scoped.exists() else shared
    merged: dict[str, str] = {}
    if base.exists():
        inherit = _parse_unit(base).get("Unit.X-Sitefab-Inherit", "").strip()
        if inherit:
            merged.update(_load_template(inherit))
        merged.update(_parse_unit(base))
        drop = base.parent / f"{arm}.mount.d"
        if drop.is_dir():
            for path in sorted(drop.glob("*.conf")):
                merged.update(_parse_unit(path))
    return merged


def _has_nf(opts: str) -> bool:
    parts = [p.strip() for p in opts.split(",") if p.strip()]
    return "_nf" in parts or "nofail" in parts


def _expected_order_key(arm_name: str, fallback: dict, profile: str) -> int:
    unit = _arm_unit(arm_name, profile)
    opts = unit.get("Mount.Options", fallback["opts"])
    remote_raw = unit.get(
        "Mount.X-Sitefab-Remote",
        "yes" if fallback.get("remote") else "no",
    )
    remote = str(remote_raw).lower() in {"1", "yes", "true", "on"}
    hint = int(unit.get("Mount.X-Sitefab-OrderHint", fallback["order_hint"]))
    order_key = hint
    if remote:
        order_key = hint if _has_nf(opts) else hint + 10000
    link_after = unit.get("Unit.X-Sitefab-LinkAfter", "").strip()
    if link_after:
        peer = _arm_unit(link_after, profile)
        peer_hint = int(
            peer.get(
                "Mount.X-Sitefab-OrderHint",
                next(
                    (
                        a["order_hint"]
                        for a in _load_profile(profile)["arms"]
                        if a["name"] == link_after
                    ),
                    hint,
                ),
            )
        )
        if hint <= peer_hint:
            order_key += 5000
    prop = unit.get("Mount.X-Sitefab-Propagate", "").strip()
    if prop and prop not in {"shared", "slave", "private", "rshared", "rslave"}:
        order_key += 2500
    cfg = _merged_policy()
    if cfg.get("Compile", "SealPaths", fallback="") == "yes":
        want_what = fallback.get("what") or f"/srv/backing/{profile}/{arm_name}"
        want_where = fallback.get("where") or f"/srv/arms/{profile}/{arm_name}"
        if unit.get("Mount.What") != want_what or unit.get("Mount.Where") != want_where:
            order_key += 10000
    return order_key


def _reconcile_opts(gen_opts: str, hand_opts: str) -> str:
    bs = ",bs="
    gen_has = bs in gen_opts
    hand_has = bs in hand_opts
    if gen_has and not hand_has:
        suffix = gen_opts.split(bs, 1)[1]
        return f"{hand_opts}{bs}{suffix}"
    if hand_has and not gen_has:
        return hand_opts
    if gen_has and hand_has and gen_opts != hand_opts:
        suffix = gen_opts.split(bs, 1)[1]
        base = hand_opts.split(bs, 1)[0]
        return f"{base}{bs}{suffix}"
    return hand_opts or gen_opts


def _pending_arms(profile_name: str) -> dict[str, str]:
    pending: dict[str, str] = {}
    for base in (
        ETC / "units" / profile_name / "data.mount.d",
        ETC / "units" / "data.mount.d",
    ):
        gen_drop = base / "10-generator.conf"
        hand_drop = base / "20-hand.conf"
        if gen_drop.exists() and hand_drop.exists():
            gen = _parse_unit(gen_drop).get("Mount.Options", "")
            hand = _parse_unit(hand_drop).get("Mount.Options", "")
            rec = _reconcile_opts(gen, hand)
            pending["unit"] = rec
            pending["data"] = rec
            return pending
    return pending


def _expected_store_arms(profile_name: str, script_name: str) -> dict[str, str]:
    if _script_has_bar(script_name):
        return _pending_arms(profile_name)
    return {}


def _refresh_count(script_name: str) -> int:
    return sum(
        1
        for line in (SCENARIOS / script_name).read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("step prp")
    )


def _law_digest(report: dict, script_name: str) -> str:
    profile = _parse_script_profile(script_name)
    store_arms = _expected_store_arms(profile, script_name)
    lines: list[str] = []
    for entry in report["entries"]:
        arm = entry["arm"]
        reconciled = store_arms.get(arm, entry["opts"])
        lines.append(f"entry:{arm}:{entry['order_key']}:{reconciled}")
    for cref in sorted(report["consumer_refs"], key=lambda x: x["arm"]):
        lines.append(f"cref:{cref['arm']}:{cref['epoch']}")
    lines.append(f"refresh:{_refresh_count(script_name)}")
    lines.append(f"barrier:{report['barrier_rev']}")
    lines.append(f"run:{report['run_id']}")
    lines.append(f"seq:{report['journal_seq']}")
    lines.append(f"steps:{len(report['steps'])}")
    lines.sort()
    return law_digest_lines(lines)


def _assert_digest_law(report: dict, script_name: str) -> None:
    expected = _law_digest(report, script_name)
    assert report["durable_digest"] == expected, (
        f"digest mismatch for {script_name}: got {report['durable_digest']}, want {expected}"
    )


def _assert_refs_sorted(report: dict) -> None:
    arms = [c["arm"] for c in report["consumer_refs"]]
    assert arms == sorted(arms), "consumer_refs must be sorted by arm name"


def _require_fabric() -> None:
    assert (ETC / "sitefab.conf").is_file(), "missing /etc/sitefab/sitefab.conf"
    cfg = _merged_policy()
    assert cfg.get("Digest", "Source", fallback="") == "durable-store"
    assert cfg.get("Reconcile", "Mode", fallback="") == "gen-hand-bs"
    assert cfg.get("Reconcile", "RequireDropIns", fallback="") == "yes"
    assert cfg.get("Visibility", "DependentHold", fallback="") == "until-propagate"
    assert cfg.get("Visibility", "DependToken", fallback="") == "x-hold"
    assert cfg.get("Visibility", "MaintLatch", fallback="") == "yes"
    assert cfg.get("Compile", "PreferUnit", fallback="") == "strict"
    assert cfg.get("Compile", "SealPaths", fallback="") == "yes"
    carry = {p.strip() for p in cfg.get("Journal", "Carry", fallback="").split(",") if p.strip()}
    assert {"epochs", "last_ro", "stale_ref", "pending_arms", "latch"} <= carry
    assert cfg.get("Journal", "Path", fallback="") == "/var/lib/sitefab/journal.json"
    primary = configparser.ConfigParser()
    primary.read(ETC / "sitefab.conf")
    assert primary.get("Digest", "Source", fallback="") != "durable-store"
    assert primary.get("Journal", "Carry", fallback="") == ""
    drop_files = list((ETC / "policy.d").glob("*.conf")) if (ETC / "policy.d").is_dir() else []
    assert drop_files, "missing /etc/sitefab/policy.d snippets"
    required = {
        "alpha": ("data", "share", "cache"),
        "beta": ("data", "work", "spill"),
        "gamma": ("root", "stage", "publish"),
        "remote": ("data", "scratch", "archive", "mirror"),
    }
    for profile, arms in required.items():
        for arm in arms:
            path = ETC / "units" / profile / f"{arm}.mount"
            assert path.is_file(), f"missing unit {path}"
    for name in ("10-generator.conf", "20-hand.conf"):
        assert (ETC / "units" / "beta" / "data.mount.d" / name).is_file()
    share = _arm_unit("share", "alpha")
    assert "data" in share.get("Unit.X-Sitefab-Depends", "")
    assert "x-hold" in share.get("Mount.Options", "")
    scratch = _arm_unit("scratch", "remote")
    archive = _arm_unit("archive", "remote")
    mirror = _arm_unit("mirror", "remote")
    data_r = _arm_unit("data", "remote")
    assert _has_nf(scratch.get("Mount.Options", ""))
    assert _has_nf(archive.get("Mount.Options", ""))
    assert not _has_nf(mirror.get("Mount.Options", ""))
    assert not _has_nf(data_r.get("Mount.Options", ""))


def setup_module(_module):  # noqa: ARG001
    _assert_runtime_seal()
    _require_fabric()
    _purge_journal()


def test_h01_coherent_digest_sweep():
    """Durable digests stay coherent across independent scenario tickets."""
    for script in ALL_SCRIPTS:
        if script.name in SWEEP_EXCLUDE:
            continue
        report = _run(script.name)
        _assert_refs_sorted(report)
        _assert_digest_law(report, script.name)


def test_h02_dep_hold_until_prp():
    """Dependent share stays omitted until a propagate refresh releases it."""
    share_unit = _arm_unit("share", "alpha")
    deps = share_unit.get("Unit.X-Sitefab-Depends", "")
    assert deps.strip() != ""
    assert "x-hold" in share_unit.get("Mount.Options", "")
    _purge_journal()
    mid = _run("n21_dep_hold.script")
    mid_epochs = {c["arm"]: c["epoch"] for c in mid["consumer_refs"]}
    assert "share" not in mid_epochs
    assert "data" in mid_epochs
    report = _run("n21_dep_release.script", continue_run=True)
    end_epochs = {c["arm"]: c["epoch"] for c in report["consumer_refs"]}
    assert "share" in end_epochs
    assert end_epochs["share"] > 0
    _assert_refs_sorted(report)
    _assert_digest_law(report, "n21_dep_release.script")


def test_h03_carry_journal_replay_alignment():
    """Journal carry preserves epochs across a continued run."""
    _purge_journal()
    seed = _run("n15_carry_seed.script")
    seed_epochs = {c["arm"]: c["epoch"] for c in seed["consumer_refs"]}
    report = _run("n15_carry_resume.script", continue_run=True)
    end_epochs = {c["arm"]: c["epoch"] for c in report["consumer_refs"]}
    for arm, epoch in seed_epochs.items():
        assert end_epochs.get(arm, 0) > epoch
    assert report["journal_seq"] > seed["journal_seq"]


def test_h04_purge_reset_recovery_cycle():
    """Purge clears prior state before a fresh ro/rw ladder."""
    first = _run("n02_rw_toggle.script")
    report = _run("n16_purge_reset.script")
    first_epochs = {c["arm"]: c["epoch"] for c in first["consumer_refs"]}
    end_epochs = {c["arm"]: c["epoch"] for c in report["consumer_refs"]}
    assert end_epochs
    assert all(arm in end_epochs for arm in first_epochs)
    _assert_digest_law(report, "n16_purge_reset.script")


def test_h05_triple_continue_journal_chain():
    """Three-run continue chain advances journal_seq and epochs."""
    _purge_journal()
    seed = _run("n23_chain_seed.script")
    mid = _run("n23_chain_mid.script", continue_run=True)
    report = _run("n23_chain_end.script", continue_run=True)
    seed_epochs = {c["arm"]: c["epoch"] for c in seed["consumer_refs"]}
    end_epochs = {c["arm"]: c["epoch"] for c in report["consumer_refs"]}
    for arm, epoch in seed_epochs.items():
        assert end_epochs.get(arm, 0) > epoch
    assert report["journal_seq"] > mid["journal_seq"] > seed["journal_seq"]
    _assert_digest_law(report, "n23_chain_end.script")


def test_h06_stale_barrier_revision():
    """Barrier bumps revision and clears a seeded violation."""
    prior_rev = 3
    _seed_journal(
        {
            "seq": 1,
            "epochs": {},
            "refresh_count": 0,
            "barrier_rev": prior_rev,
            "violation": True,
            "last_ro": {},
            "stale_ref": {},
            "pending_arms": {},
            "latch": {},
        }
    )
    report = _run("n20_stale_barrier.script")
    assert report["barrier_rev"] == prior_rev + 1
    assert not report["violation"]


def test_h07_settlement_bar_commits_reconcile():
    """Barrier settlement commits beta bind-suffix reconcile into the durable store."""
    report = _run("n22_settle_bar.script")
    _assert_digest_law(report, "n22_settle_bar.script")
    store = _expected_store_arms("beta", "n22_settle_bar.script")
    assert store.get("data", "").endswith("bs=work") or "bs=work" in store.get("data", "")


def test_h08_health_durable_crosscheck():
    """Reported durable_digest matches the durable law for the health ticket."""
    report = _run("n09_health_durable.script")
    expected = _law_digest(report, "n09_health_durable.script")
    assert report["durable_digest"] == expected


def test_h09_refreshes_count_prp():
    """Refresh ticks are consecutive and match prp steps."""
    report = _run("n12_propagation.script")
    ticks = [r["tick"] for r in report["refreshes"]]
    assert ticks == list(range(1, len(ticks) + 1))
    assert len(ticks) == _refresh_count("n12_propagation.script")
    _assert_digest_law(report, "n12_propagation.script")


def test_h10_remote_nf_ordering():
    """Remote compile order respects nofail markers and deferral."""
    report = _run("n04_remote_order.script")
    profile = _load_profile("remote")
    expected = sorted(
        (_expected_order_key(a["name"], a, "remote"), a["name"]) for a in profile["arms"]
    )
    actual = [(e["order_key"], e["arm"]) for e in report["entries"]]
    assert actual == expected
    assert actual[0][1] in {"scratch", "archive"}
    assert actual[-1][1] in {"data", "mirror"}


def test_h11_rw_toggle_epoch_and_digest():
    """Alpha ro/rw toggle advances epochs under durable digest law."""
    report = _run("n02_rw_toggle.script")
    epochs = {c["arm"]: c["epoch"] for c in report["consumer_refs"]}
    assert epochs
    assert max(epochs.values()) > 0
    _assert_refs_sorted(report)
    _assert_digest_law(report, "n02_rw_toggle.script")


def test_h12_deferred_refresh_store_alignment():
    """Deferred refresh counts align with prp steps."""
    report = _run("n18_deferred_refresh.script")
    assert len(report["refreshes"]) == _refresh_count("n18_deferred_refresh.script")
    _assert_digest_law(report, "n18_deferred_refresh.script")


def test_h13_ladder_mutation_moves_digest():
    """Distinct remote ladders produce distinct durable digests."""
    remote_a = _run("n04_remote_order.script")
    remote_b = _run("n11_nofail_mask.script")
    _assert_digest_law(remote_a, "n04_remote_order.script")
    _assert_digest_law(remote_b, "n11_nofail_mask.script")
    assert remote_a["durable_digest"] != remote_b["durable_digest"]


def test_h14_settlement_changes_digest():
    """Settled barrier digest differs from unsettled bind-suffix digest."""
    unsettled = _run("n07_bind_suffix.script")
    settled = _run("n22_settle_bar.script")
    unsettled_law = _law_digest(unsettled, "n07_bind_suffix.script")
    settled_law = _law_digest(settled, "n22_settle_bar.script")
    assert unsettled_law != settled_law
    _assert_digest_law(settled, "n22_settle_bar.script")


def test_h15_idempotent_digest_new_run_id():
    """Repeated runs keep digest law but mint a new run_id UUID."""
    first = _run("n02_rw_toggle.script")
    second = _run("n02_rw_toggle.script")
    _assert_digest_law(first, "n02_rw_toggle.script")
    _assert_digest_law(second, "n02_rw_toggle.script")
    assert first["run_id"] != second["run_id"]
    uuid.UUID(first["run_id"])
    uuid.UUID(second["run_id"])


def test_h16_gamma_profile_ladder():
    """Gamma profile ladder exposes root/stage refs and bumps the barrier."""
    report = _run("n24_gamma_ladder.script")
    arms = {c["arm"] for c in report["consumer_refs"]}
    assert "root" in arms
    assert "stage" in arms
    assert report["barrier_rev"] >= 1
    _assert_digest_law(report, "n24_gamma_ladder.script")


def test_h17_maintenance_latch_carry_and_clear():
    """Bind-move latch carries across continue and clears on barrier."""
    _purge_journal()
    seed = _run("n25_latch_seed.script")
    assert set(seed["maintenance_latch"]) >= {"data", "work"}
    cleared = _run("n25_latch_clear.script", continue_run=True)
    assert cleared["maintenance_latch"] == []
    assert cleared["barrier_rev"] >= 1
    _assert_digest_law(cleared, "n25_latch_clear.script")


def test_h18_policy_layer_and_path_seal():
    """Policy.d layering, templates, and sealed What/Where remain in force."""
    cfg = _merged_policy()
    assert cfg.get("Digest", "Source") == "durable-store"
    assert (ETC / "templates" / "local-arm.mount").is_file()
    assert (ETC / "templates" / "remote-nf.mount").is_file()
    data = _arm_unit("data", "alpha")
    assert data.get("Mount.What") == "/srv/backing/alpha/data"
    assert data.get("Mount.Where") == "/srv/arms/alpha/data"
    assert data.get("Unit.X-Sitefab-Inherit") == "local-arm" or data.get(
        "Mount.X-Sitefab-Remote"
    ) == "no"
    report = _run("n02_rw_toggle.script")
    _assert_digest_law(report, "n02_rw_toggle.script")
