"""Verifier harness for observ_trace.json observation rows."""

import json
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
ENV = APP / "environment"
OUT_PATH = "/app/output/observ_trace.json"
OUT = Path(OUT_PATH)
WORK = Path("/app/work/policy")
BLOCK = ENV / "fixtures" / "rule_seed.dat"
WITNESS = WORK / "replay.witness"
ROUND = "/app/environment/tools/j4_round"
EMIT = "/app/environment/tools/p7_emit"
EPOCH_CHAIN = WORK / "epoch.chain"

SCENARIOS = [
    "pin_base",
    "map_row",
    "scope_a",
    "scope_b",
    "probe_h",
    "probe_w",
    "cross_row",
]

HANDOFF_ORD = {"arr1": 1, "arr2": 2, "arr3": 3}


def _build() -> None:
    subprocess.run(["make", "-C", "/app/environment", "all"], check=True, timeout=180)


def _sha256_hex(data: str, n: int = 16) -> str:
    proc = subprocess.run(
        ["sha256sum"],
        input=data.encode("utf-8"),
        capture_output=True,
        check=True,
        timeout=10,
    )
    full = proc.stdout.decode("utf-8").split()[0]
    return full[:n]


def _env_val(profile: str, key: str) -> str:
    text = (ENV / "fixtures" / f"{profile}.env").read_text()
    prefix = f"{key}="
    for line in text.splitlines():
        if line.startswith(prefix):
            return line.split("=", 1)[1]
    raise AssertionError(f"missing {key} in {profile}.env")


def _gen_id(seed_file: str) -> int:
    text = (ENV / "fixtures" / seed_file).read_text()
    for line in text.splitlines():
        if line.startswith("GEN_ID="):
            return int(line.split("=", 1)[1])
    raise AssertionError(f"GEN_ID missing in {seed_file}")


def _read_tick() -> int:
    return int(WORK.joinpath("window.tick").read_text().strip())


def _cookie_gen(epoch_id: int, if_index: int, slots: int, tick: int = 0, carry: int = 0) -> int:
    blob = BLOCK.read_bytes()
    acc = 0
    for i in range(min(slots, len(blob))):
        acc = (acc + (blob[i] ^ epoch_id)) % 256
    lane = if_index + carry + (tick % 16 if tick > 0 else 0)
    return (acc + lane * epoch_id) % 256


def _carry_from_prior(prior_site: str) -> int:
    text = WORK.joinpath("m1.state").read_text()
    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] == prior_site:
            return (int(parts[1]) + int(parts[2])) % 256
    raise AssertionError(f"missing prior publish for {prior_site}")


def _handoff_token_from_chain(site: str) -> str:
    _, _, _, handoff_ord = _read_epoch_chain(site)
    for token, ord_val in HANDOFF_ORD.items():
        if ord_val == handoff_ord:
            return token
    raise AssertionError(f"unknown handoff ordinal for {site}")


def _read_u4_epoch(site: str) -> int:
    return _read_u4_scope(site)


def _p7_material(row: dict) -> str:
    return (
        f"{row['link_count']}|{row['cookie_gen_a']}|{row['cookie_gen_b']}|"
        f"{row['scope_code']}|{row['rule_idx']}"
    )


def _expected_p7_chain(rows: list[dict]) -> list[str]:
    prev = ""
    out: list[str] = []
    for row in rows:
        mat = _p7_material(row)
        payload = mat if not prev else prev + mat
        digest = _sha256_hex(payload, 16)
        out.append(digest)
        prev = digest
    return out


def _scope_b_expected(store_scope_code: str) -> str:
    if store_scope_code == "S3":
        return "S3"
    return "S2"


def _host_admit_numeric(scope_num: int, link: int, cap: int) -> str:
    if scope_num == 3 and link == cap:
        return "P0"
    return "P8"


def _work_admit(handoff: str, scope_num: int) -> str:
    if handoff == "arr3" and scope_num == 3:
        return "P1"
    return "P9"


def _read_u4_scope(site: str) -> int:
    for line in WORK.joinpath("u4.state").read_text().splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] == site:
            return int(parts[2])
    raise AssertionError(f"missing u4 scope for {site}")


def _read_u4_link(site: str) -> int:
    for line in WORK.joinpath("u4.state").read_text().splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] == site:
            return int(parts[1])
    raise AssertionError(f"missing u4 link for {site}")


def _read_handoff(site: str) -> str:
    for line in WORK.joinpath("p5.state").read_text().splitlines():
        parts = line.split("\t")
        if len(parts) == 2 and parts[0] == site:
            return parts[1]
    raise AssertionError(f"missing handoff for {site}")


def _expected_handoff(site: str, pin_scope: int) -> str:
    inherit = int(_env_val(site, "INHERIT_ARR"))
    if inherit == 0:
        return "arr1"
    if site == "site_p7" and pin_scope >= 3:
        return "arr3"
    if inherit:
        return "arr2"
    return "arr1"


def _read_m1_publish(site: str) -> tuple[int, int]:
    for line in WORK.joinpath("m1.state").read_text().splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] == site:
            return int(parts[1]), int(parts[2])
    raise AssertionError(f"missing m1 publish for {site}")


def _read_epoch_chain(site: str) -> tuple[int, int, int, int]:
    for line in EPOCH_CHAIN.read_text().splitlines():
        parts = line.split()
        if len(parts) == 5 and parts[0] == site:
            return int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
    raise AssertionError(f"missing epoch.chain row for {site}")


def _tick_from_chain(site: str) -> int:
    scope, pub_a, pub_b, handoff = _read_epoch_chain(site)
    tick = (scope + pub_a + pub_b + handoff) % 16
    return tick if tick > 0 else 1


def _witness_byte_for_site(site: str) -> int:
    scope, pub_a, pub_b, handoff = _read_epoch_chain(site)
    return (scope ^ pub_a ^ pub_b ^ handoff) % 256


def _read_witness(site: str) -> int:
    if not WITNESS.is_file():
        raise AssertionError("replay.witness missing")
    for line in WITNESS.read_text().splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == site:
            return int(parts[1], 16)
    raise AssertionError(f"missing witness row for {site}")


def _epoch_chain_rows() -> list[tuple[str, int, int, int, int]]:
    rows: list[tuple[str, int, int, int, int]] = []
    if not EPOCH_CHAIN.is_file():
        return rows
    for line in EPOCH_CHAIN.read_text().splitlines():
        parts = line.split()
        if len(parts) == 5:
            rows.append((parts[0], int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])))
    return rows


def _bind_seq_expected() -> str:
    acc = 0
    for _site, scope, pub_a, pub_b, handoff in _epoch_chain_rows():
        acc ^= scope ^ pub_a ^ pub_b ^ handoff
    return f"{acc % 256:02x}"


def _replay_cksum(rows: list[dict]) -> str:
    acc = 0
    for row in rows:
        acc ^= int(row["window_seq"])
    return f"{acc % 256:02x}"


def _assert_summary_contract(doc: dict) -> None:
    ordered = _ordered_rows(doc)
    summary = doc["summary"]
    assert summary["trace_stamp"] == "policy-v1"
    assert summary["row_count"] == 14
    assert summary["bind_seq"] == _bind_seq_expected()
    assert summary["replay_cksum"] == _replay_cksum(ordered)


def _run_chain(*, rebuild: bool = True) -> dict:
    if rebuild:
        _build()
    if OUT.exists():
        OUT.unlink()
    subprocess.run([ROUND, "--round"], check=True, timeout=90)
    subprocess.run([EMIT, "--out", OUT_PATH], check=True, timeout=20)
    assert OUT.exists(), "round chain must recreate observ_trace.json"
    return json.loads(OUT.read_text())


def _row(doc: dict, site: str, scenario: str) -> dict:
    matches = [r for r in doc["rows"] if r["site_id"] == site and r["scenario"] == scenario]
    assert len(matches) == 1, f"missing row {site}/{scenario}"
    return matches[0]


def _ordered_rows(doc: dict) -> list[dict]:
    ordered: list[dict] = []
    for site in ("site_j4", "site_p7"):
        for scenario in SCENARIOS:
            ordered.append(_row(doc, site, scenario))
    return ordered


@pytest.fixture(scope="session")
def built_env() -> None:
    _build()


@pytest.fixture(scope="module")
def trace_doc(built_env: None) -> dict:
    return _run_chain(rebuild=False)


def test_z0_witness_store_triangulation(trace_doc: dict, built_env: None) -> None:
    """Chain rebind scope must track u4 epoch not link inventory; bind_seq and regen traps hold."""
    for site in ("site_j4", "site_p7"):
        chain_scope, _, _, _ = _read_epoch_chain(site)
        u4_scope = _read_u4_scope(site)
        u4_link = _read_u4_link(site)
        assert chain_scope == u4_scope
        if u4_link != u4_scope:
            assert chain_scope != u4_link
    _assert_summary_contract(trace_doc)
    saved = EPOCH_CHAIN.read_text()
    poisoned = saved.replace("site_j4\t3\t", "site_j4\t2\t", 1)
    EPOCH_CHAIN.write_text(poisoned)
    assert _bind_seq_expected() != trace_doc["summary"]["bind_seq"]
    EPOCH_CHAIN.write_text(saved)
    first_bytes = OUT.read_bytes()
    subprocess.run([EMIT, "--out", OUT_PATH], check=True, timeout=20)
    assert OUT.read_bytes() == first_bytes
    ledger_path = WORK / "ledger.tsv"
    assert ledger_path.is_file()
    ledger_path.unlink()
    bad_emit = subprocess.run([EMIT, "--out", OUT_PATH], capture_output=True, timeout=20)
    assert bad_emit.returncode != 0
    regen_doc = _run_chain(rebuild=False)
    assert regen_doc == trace_doc
    assert _read_tick() == _tick_from_chain("site_j4")


def test_z1_chain_ledger_coupling(trace_doc: dict) -> None:
    """epoch.chain must seed rebind scope, publish both generations, and stay aligned with u4."""
    for site in ("site_j4", "site_p7"):
        scope_u4 = _read_u4_scope(site)
        link_u4 = _read_u4_link(site)
        pub_a, pub_b = _read_m1_publish(site)
        handoff = _read_handoff(site)
        chain_scope, chain_a, chain_b, chain_h = _read_epoch_chain(site)
        assert chain_scope == scope_u4
        if link_u4 != scope_u4:
            assert chain_scope != link_u4
        assert chain_a == pub_a and chain_b == pub_b
        if pub_a != pub_b:
            assert chain_a != chain_b
        assert chain_h == HANDOFF_ORD[handoff]
    assert _read_tick() == _tick_from_chain("site_j4")
    row = _row(trace_doc, "site_p7", "map_row")
    ns_gen_a = _gen_id("ns_gen_a.txt")
    ns_gen_b = _gen_id("ns_gen_b.txt")
    slots = int(_env_val("site_p7", "RULE_SLOTS"))
    if_index = int(_env_val("site_p7", "IF_INDEX"))
    tick = _read_tick()
    carry = _carry_from_prior("site_j4")
    want_a = _cookie_gen(ns_gen_a, if_index, slots, tick, carry)
    want_b = _cookie_gen(ns_gen_b, if_index, slots, tick, carry)
    assert want_a != want_b
    assert row["cookie_gen_a"] == want_a
    assert row["cookie_gen_b"] == want_b
    wrong_lane_b = _cookie_gen(ns_gen_b, if_index + want_a, slots, tick, carry)
    assert row["cookie_gen_b"] != wrong_lane_b, "generation B must share lane with A not A output offset"
    j4_scope, j4_a, j4_b, j4_h = _read_epoch_chain("site_j4")
    p7_scope, p7_a, p7_b, p7_h = _read_epoch_chain("site_p7")
    assert j4_h == HANDOFF_ORD["arr1"]
    assert p7_h == HANDOFF_ORD["arr3"]
    assert p7_scope == 3
    assert j4_scope == 3
    assert (j4_a + j4_b) % 256 == _carry_from_prior("site_j4")


def test_z2_boundary_digest_poison(trace_doc: dict) -> None:
    """Short-profile cookie drift poisons long-profile digests across the site boundary."""
    tick = _read_tick()
    assert tick == _tick_from_chain("site_j4")
    ordered = _ordered_rows(trace_doc)
    expected = _expected_p7_chain(ordered)
    for row, want in zip(ordered, expected, strict=True):
        assert row["p7_digest_hex"] == want
    site_j4_last = _row(trace_doc, "site_j4", "cross_row")["p7_digest_hex"]
    site_p7_first = _row(trace_doc, "site_p7", "pin_base")["p7_digest_hex"]
    mat = _p7_material(_row(trace_doc, "site_p7", "pin_base"))
    assert site_p7_first == _sha256_hex(site_j4_last + mat, 16)
    assert site_p7_first != _sha256_hex(mat, 16)
    j4_map = _row(trace_doc, "site_j4", "map_row")
    off = j4_map["rule_idx"] if j4_map["rule_idx"] else 1
    alt_row = dict(j4_map)
    alt_row["cookie_gen_a"] = (j4_map["cookie_gen_a"] + off) % 256
    alt_row["cookie_gen_b"] = (j4_map["cookie_gen_b"] + off) % 256
    alt_mat = _p7_material(alt_row)
    poison_first = _sha256_hex(site_j4_last + alt_mat, 16)
    assert poison_first != site_p7_first
    p7_map = _row(trace_doc, "site_p7", "map_row")
    slots = int(_env_val("site_p7", "RULE_SLOTS"))
    if_index = int(_env_val("site_p7", "IF_INDEX"))
    carry = _carry_from_prior("site_j4")
    with_tick = _cookie_gen(_gen_id("ns_gen_a.txt"), if_index, slots, tick, carry)
    without_carry = _cookie_gen(_gen_id("ns_gen_a.txt"), if_index, slots, tick, 0)
    assert with_tick != without_carry
    assert p7_map["cookie_gen_a"] == with_tick
    for row in ordered:
        assert "window_seq" not in _p7_material(row)


def test_z3_scope_sync_recovery(trace_doc: dict) -> None:
    """Stale chain scope and desynced p5.state must not survive round or tail probe replay."""
    chain_scope, _, _, _ = _read_epoch_chain("site_j4")
    assert chain_scope == _read_u4_scope("site_j4")
    text = EPOCH_CHAIN.read_text()
    stale = text.replace("site_j4\t3\t", "site_j4\t1\t", 1)
    EPOCH_CHAIN.write_text(stale)
    subprocess.run([ROUND, "--round"], check=True, timeout=90)
    subprocess.run([EMIT, "--out", OUT_PATH], check=True, timeout=20)
    refreshed = json.loads(OUT.read_text())
    rebuilt_scope, _, _, _ = _read_epoch_chain("site_j4")
    assert rebuilt_scope == 3
    assert _row(refreshed, "site_j4", "scope_b")["scope_code"] == "S3"
    assert _row(refreshed, "site_p7", "probe_w")["admit_code"] == "P1"
    p5_path = WORK / "p5.state"
    p5_lines = p5_path.read_text().splitlines()
    p5_path.write_text(
        "\n".join(
            "site_p7\tarr2" if line.startswith("site_p7") else line for line in p5_lines
        )
        + "\n",
    )
    assert _read_handoff("site_p7") == "arr2"
    assert _handoff_token_from_chain("site_p7") == "arr3"
    if OUT.exists():
        OUT.unlink()
    subprocess.run([ROUND, "--round", "--tail"], check=True, timeout=90)
    subprocess.run([EMIT, "--out", OUT_PATH], check=True, timeout=20)
    tail_doc = json.loads(OUT.read_text())
    assert _row(tail_doc, "site_p7", "probe_w")["admit_code"] == "P1"
    _assert_summary_contract(tail_doc)
    assert tail_doc == trace_doc


def test_z4_scope_chain_row_binding(trace_doc: dict) -> None:
    """Scope rows follow chain rebind_scope; carry residue folds through the long profile lane."""
    carry = _carry_from_prior("site_j4")
    assert carry > 0
    pub_a, pub_b = _read_m1_publish("site_j4")
    assert carry == (pub_a + pub_b) % 256
    p7_map = _row(trace_doc, "site_p7", "map_row")
    slots = int(_env_val("site_p7", "RULE_SLOTS"))
    if_index = int(_env_val("site_p7", "IF_INDEX"))
    tick = _read_tick()
    bare = _cookie_gen(_gen_id("ns_gen_a.txt"), if_index, slots, tick, 0)
    folded = _cookie_gen(_gen_id("ns_gen_a.txt"), if_index, slots, tick, carry)
    assert bare != folded
    assert p7_map["cookie_gen_a"] == folded
    assert p7_map["cookie_gen_a"] != bare
    for site in ("site_j4", "site_p7"):
        a = _row(trace_doc, site, "scope_a")
        b = _row(trace_doc, site, "scope_b")
        store = _row(trace_doc, site, "pin_base")
        cross = _row(trace_doc, site, "cross_row")
        chain_scope, _, _, _ = _read_epoch_chain(site)
        u4_scope = _read_u4_scope(site)
        assert chain_scope == u4_scope
        assert a["scope_code"] == "S1"
        if chain_scope >= 3:
            assert b["scope_code"] == "S3"
        else:
            assert b["scope_code"] == "S2"
        assert cross["scope_code"] == f"S{chain_scope}"
        assert store["scope_code"] == f"S{chain_scope}"
        assert store["scope_code"] != "S1"
    ordered = _ordered_rows(trace_doc)
    assert [r["window_seq"] for r in ordered] == list(range(14))
    assert ordered[6]["site_id"] == "site_j4"
    assert ordered[7]["site_id"] == "site_p7"
    assert ordered[7]["window_seq"] == 7


def test_z5_cold_scratch_rebuild(trace_doc: dict) -> None:
    """Full round rebuilds scratch from fixtures; partial stores cannot satisfy cross-run invariants."""
    for site in ("site_j4", "site_p7"):
        store = _row(trace_doc, site, "pin_base")
        cross = _row(trace_doc, site, "cross_row")
        slot_cap = int(_env_val(site, "LINK_CAP"))
        assert store["link_count"] == slot_cap
        assert cross["link_count"] == slot_cap
        tick = _read_tick() if site == "site_p7" else 0
        carry = _carry_from_prior("site_j4") if site == "site_p7" else 0
        assert cross["cookie_gen_a"] == _cookie_gen(
            _gen_id("ns_gen_a.txt"),
            int(_env_val(site, "IF_INDEX")),
            int(_env_val(site, "RULE_SLOTS")),
            tick,
            carry,
        )
        assert cross["cookie_gen_b"] == _cookie_gen(
            _gen_id("ns_gen_b.txt"),
            int(_env_val(site, "IF_INDEX")),
            int(_env_val(site, "RULE_SLOTS")),
            tick,
            carry,
        )
        chain_scope, _, _, _ = _read_epoch_chain(site)
        assert cross["scope_code"] == f"S{chain_scope}"
    _assert_summary_contract(trace_doc)
    chain_backup = EPOCH_CHAIN.read_text()
    for name in ("u4.state", "m1.state", "p5.state", "ledger.tsv"):
        path = WORK / name
        if path.is_file():
            path.unlink()
    EPOCH_CHAIN.write_text(chain_backup)
    if OUT.exists():
        OUT.unlink()
    partial = subprocess.run([EMIT, "--out", OUT_PATH], capture_output=True, timeout=20)
    assert partial.returncode != 0
    second_doc = _run_chain(rebuild=False)
    assert second_doc == trace_doc
    subprocess.run([ROUND, "--round"], check=True, timeout=90)


def test_z6_tail_authority_precedence(trace_doc: dict, built_env: None) -> None:
    """Tail replay refreshes tick from chain, rebuilds ledger, and probes honor chain over stale p5.state."""
    _build()
    if OUT.exists():
        OUT.unlink()
    subprocess.run([ROUND, "--round"], check=True, timeout=90)
    subprocess.run([EMIT, "--out", OUT_PATH], check=True, timeout=20)
    fresh = json.loads(OUT.read_text())
    assert fresh == trace_doc
    p5_path = WORK / "p5.state"
    p5_lines = p5_path.read_text().splitlines()
    p5_path.write_text(
        "\n".join(
            "site_p7\tarr2" if line.startswith("site_p7") else line for line in p5_lines
        )
        + "\n",
    )
    ledger_path = WORK / "ledger.tsv"
    assert ledger_path.is_file()
    ledger_path.unlink()
    for site in ("site_j4", "site_p7"):
        for kind in ("host", "work"):
            probe = WORK / f"probe_{site}_{kind}.txt"
            if probe.is_file():
                probe.unlink()
    subprocess.run([ROUND, "--round", "--tail"], check=True, timeout=90)
    assert _read_tick() == _tick_from_chain("site_j4")
    scope, pub_a, pub_b, handoff = _read_epoch_chain("site_j4")
    partial_tick = (scope + handoff) % 16
    partial_tick = partial_tick if partial_tick > 0 else 1
    assert _read_tick() != partial_tick or (pub_a + pub_b) % 16 == 0
    subprocess.run([EMIT, "--out", OUT_PATH], check=True, timeout=20)
    tail_doc = json.loads(OUT.read_text())
    assert _row(tail_doc, "site_p7", "probe_w")["admit_code"] == "P1"
    assert tail_doc == trace_doc


def test_z7_publish_gated_tick(trace_doc: dict) -> None:
    """window.tick requires all four epoch.chain fields including both publish columns for site_j4."""
    scope, pub_a, pub_b, handoff = _read_epoch_chain("site_j4")
    want = (scope + pub_a + pub_b + handoff) % 16
    want = want if want > 0 else 1
    broken = (scope + handoff) % 16
    broken = broken if broken > 0 else 1
    assert _read_tick() == want
    assert _read_tick() == _tick_from_chain("site_j4")
    if broken != want:
        assert _read_tick() != broken
    text = EPOCH_CHAIN.read_text()
    lines = [ln for ln in text.splitlines() if ln.startswith("site_j4")]
    assert len(lines) == 1, "expected one site_j4 chain row"
    parts = lines[0].split()
    assert len(parts) == 5
    partial_row = f"site_j4\t{parts[1]}\t{parts[2]}\t0\t{parts[4]}"
    full_row = lines[0]
    partial_want = (scope + pub_a + handoff) % 16
    partial_want = partial_want if partial_want > 0 else 1
    poisoned_chain = text.replace(full_row, partial_row, 1)
    assert poisoned_chain != text, "chain row must drop publish_b for ablation"
    EPOCH_CHAIN.write_text(poisoned_chain)
    z_scope, z_pub_a, z_pub_b, z_handoff = _read_epoch_chain("site_j4")
    assert z_pub_b == 0
    partial_want = (z_scope + z_pub_a + z_handoff) % 16
    partial_want = partial_want if partial_want > 0 else 1
    assert partial_want != want or pub_b % 16 == 0
    tick_path = WORK / "window.tick"
    tick_path.write_text("0\n")
    tick_apply = str(ENV / "d0" / "tick_apply")
    subprocess.run([tick_apply, "--site", "site_j4"], check=True, timeout=20)
    stale_tick = int(tick_path.read_text().strip())
    EPOCH_CHAIN.write_text(text)
    if pub_b % 16 != 0:
        assert stale_tick == partial_want
        assert stale_tick != want
    subprocess.run([tick_apply, "--site", "site_j4"], check=True, timeout=20)
    assert _read_tick() == want


def test_z8_replay_witness_emit_gate(trace_doc: dict, built_env: None) -> None:
    """replay.witness must triangulate epoch.chain; stale witness blocks emit; tail rebuilds witness."""
    assert WITNESS.is_file(), "round chain must write replay.witness"
    for site in ("site_j4", "site_p7"):
        assert _read_witness(site) == _witness_byte_for_site(site)
    saved = WITNESS.read_text()
    j4_byte = _witness_byte_for_site("site_j4")
    wrong_byte = (j4_byte ^ 0x55) % 256
    assert wrong_byte != j4_byte
    poisoned = saved.replace(f"site_j4\t{j4_byte:02x}", f"site_j4\t{wrong_byte:02x}", 1)
    WITNESS.write_text(poisoned)
    assert _read_witness("site_j4") == wrong_byte
    bad_emit = subprocess.run([EMIT, "--out", OUT_PATH], capture_output=True, timeout=20)
    assert bad_emit.returncode != 0
    WITNESS.write_text(saved)
    if OUT.exists():
        OUT.unlink()
    subprocess.run([ROUND, "--round", "--tail"], check=True, timeout=90)
    for site in ("site_j4", "site_p7"):
        assert _read_witness(site) == _witness_byte_for_site(site)
    subprocess.run([EMIT, "--out", OUT_PATH], check=True, timeout=20)
    tail_doc = json.loads(OUT.read_text())
    assert tail_doc == trace_doc


def test_z9_residue_lane_lifecycle(trace_doc: dict) -> None:
    """Long profile lane residue sums both publish columns; short profile clears lane before carry export."""
    pub_a, pub_b = _read_m1_publish("site_j4")
    residue = (pub_a + pub_b) % 256
    nibble = pub_b & 15
    assert pub_a != 0
    assert _carry_from_prior("site_j4") == residue
    assert residue != nibble or (pub_a + nibble) % 256 == residue
    p7_map = _row(trace_doc, "site_p7", "map_row")
    tick = _read_tick()
    if_index = int(_env_val("site_p7", "IF_INDEX"))
    slots = int(_env_val("site_p7", "RULE_SLOTS"))
    assert p7_map["cookie_gen_a"] == _cookie_gen(
        _gen_id("ns_gen_a.txt"), if_index, slots, tick, residue
    )
    if residue != nibble:
        assert p7_map["cookie_gen_a"] != _cookie_gen(
            _gen_id("ns_gen_a.txt"), if_index, slots, tick, nibble
        )
    j4_map = _row(trace_doc, "site_j4", "map_row")
    p7_a, p7_b = _read_m1_publish("site_p7")
    assert j4_map["cookie_gen_a"] != p7_map["cookie_gen_a"] or j4_map["cookie_gen_b"] != p7_map["cookie_gen_b"]
    assert p7_a != pub_a or p7_b != pub_b
