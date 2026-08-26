"""Verifier for gacha-pull-commit-audit-go — contract-driven reference recompute."""

from __future__ import annotations

import hashlib
import hmac
import json
import struct
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

import pytest

APP = Path("/app")
BINARY = APP / "bin" / "gachaudit"
DATA = APP / "data" / "sessions.json"
CONFIG = APP / "config" / "gacha.json"
OVERRIDE = APP / "config" / "live_overrides.toml"
FALLBACK = APP / "config" / "desk_fallback.json"
REPORT = APP / "output" / "report.json"
LEDGER = APP / "output" / "pity_ledger.json"
FIXTURES = Path("/tests/fixtures")

DATA_SHA256 = "2a50fa357e6e4083a069d2f734615e4427709ad39756a12d96d2abf300067345"
HMAC_KEY = "banner-s9-commit-key"
PITY_THRESHOLD = 10
PITY_GAP = 86400
DOMAINS = {"draw": "draw", "item": "item", "receipt": "receipt", "digest": "digest"}
TIER_ORDER = ["common", "uncommon", "rare", "epic"]
RARITY_TABLE = {"common": 0.70, "uncommon": 0.20, "rare": 0.08, "epic": 0.02}
POOL = {
    "common": ["dust_shard", "ember_dust", "spark_dust"],
    "uncommon": ["lumen_shard", "prism_shard"],
    "rare": ["aurora_blade", "nebula_cloak"],
    "epic": ["stellar_crown"],
}


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _domain_key(domain: str, hmac_key: str = HMAC_KEY, domains: dict | None = None) -> bytes:
    labels = domains or DOMAINS
    label = labels.get(domain, domain)
    return hashlib.sha256(f"{hmac_key}|{label}".encode()).digest()


def _draw_roll(server_seed: str, session_id: str, pull_index: int) -> float:
    digest = hmac.new(
        _domain_key("draw"), f"{server_seed}|{session_id}|{pull_index}".encode(), hashlib.sha256
    ).digest()
    return struct.unpack(">Q", digest[:8])[0] / float(2**64 - 1)


def _tier_from_roll(roll: float) -> str:
    cum = 0.0
    for tier in TIER_ORDER:
        cum += RARITY_TABLE[tier]
        if roll < cum:
            return tier
    return TIER_ORDER[-1]


def _select_item(server_seed: str, session_id: str, pull_index: int, tier: str) -> str:
    items = sorted(POOL[tier])
    digest = hmac.new(
        _domain_key("item"), f"{server_seed}|{session_id}|{pull_index}|item".encode(), hashlib.sha256
    ).digest()
    return items[struct.unpack(">Q", digest[:8])[0] % len(items)]


def _receipt(session_id: str, pull_index: int, item_id: str, rarity: str) -> str:
    return hmac.new(
        _domain_key("receipt"),
        f"{session_id}|{pull_index}|{item_id}|{rarity}".encode(),
        hashlib.sha256,
    ).hexdigest()


def _session_digest(session_id: str, receipts: list[str]) -> str:
    payload = session_id + "".join("|" + r for r in receipts)
    return hmac.new(_domain_key("digest"), payload.encode(), hashlib.sha256).hexdigest()


def _tier_rank(tier: str) -> int:
    return TIER_ORDER.index(tier)


def _expected_pull(server_seed: str, session_id: str, pull_index: int, pity: int) -> tuple[str, str]:
    tier = _tier_from_roll(_draw_roll(server_seed, session_id, pull_index))
    if pity >= PITY_THRESHOLD - 1 and _tier_rank(tier) < _tier_rank("rare"):
        tier = "rare"
    return _select_item(server_seed, session_id, pull_index, tier), tier


def _dedupe_pulls(pulls: list[dict]) -> list[dict]:
    seen: set[int] = set()
    kept: list[dict] = []
    for p in pulls:
        if p["pull_index"] in seen:
            continue
        seen.add(p["pull_index"])
        kept.append(p)
    return sorted(kept, key=lambda p: p["pull_index"])


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def reference_report(
    sessions: list[dict], ledger: dict[str, int] | None = None
) -> tuple[dict, dict[str, int]]:
    pity_state: dict[str, int] = dict(ledger or {})
    last_open: dict[str, str] = {}
    best: dict[str, dict] = {}
    for s in sessions:
        sid = s["session_id"]
        rev = int(s.get("revision", 1))
        if sid not in best:
            best[sid] = s
            continue
        prev = best[sid]
        prev_rev = int(prev.get("revision", 1))
        if rev > prev_rev or (rev == prev_rev and s["opened_at"] < prev["opened_at"]):
            best[sid] = s
    kept_sessions = sorted(best.values(), key=lambda s: s["opened_at"])

    rows = []
    for s in kept_sessions:
        lk = f"{s['player_id']}|{s['banner_id']}"
        pity_start = pity_state.get(lk, 0)
        prev = last_open.get(lk)
        if prev:
            gap = (_parse_ts(s["opened_at"]) - _parse_ts(prev)).total_seconds()
            if gap > PITY_GAP:
                pity_start = 0
        pity = pity_start
        anomalies: list[dict] = []
        seed_ok = s["server_seed_hash"] == _sha256_hex(s["server_seed"])
        if not seed_ok:
            anomalies.append({"kind": "seed_hash_mismatch", "pull_index": -1, "item_id": ""})
        pulls = _dedupe_pulls(s["pulls"])
        seen_receipt: dict[str, int] = {}
        for p in pulls:
            pi = p["pull_index"]
            exp_item, exp_tier = _expected_pull(s["server_seed"], s["session_id"], pi, pity)
            if pity >= PITY_THRESHOLD - 1 and _tier_rank(p["rarity"]) < _tier_rank("rare"):
                anomalies.append({"kind": "pity_violation", "pull_index": pi, "item_id": p["item_id"]})
            if p["item_id"] != exp_item or p["rarity"] != exp_tier:
                anomalies.append({"kind": "draw_mismatch", "pull_index": pi, "item_id": p["item_id"]})
            if p["receipt"] != _receipt(s["session_id"], pi, p["item_id"], p["rarity"]):
                anomalies.append({"kind": "receipt_invalid", "pull_index": pi, "item_id": p["item_id"]})
            if p["receipt"] in seen_receipt:
                anomalies.append({"kind": "receipt_reuse", "pull_index": pi, "item_id": p["item_id"]})
            else:
                seen_receipt[p["receipt"]] = pi
            if _tier_rank(p["rarity"]) >= _tier_rank("rare"):
                pity = 0
            else:
                pity += 1
        if seed_ok:
            pity_state[lk] = pity
            pity_end = pity
        else:
            pity_end = pity_start
            pity_state[lk] = pity_start
        last_open[lk] = s["opened_at"]
        receipts = [p["receipt"] for p in pulls]
        kinds = sorted({a["kind"] for a in anomalies})
        status = "clean" if seed_ok and not anomalies else "tainted"
        rows.append(
            {
                "session_id": s["session_id"],
                "player_id": s["player_id"],
                "banner_id": s["banner_id"],
                "status": status,
                "pulls_kept": len(pulls),
                "pity_at_start": pity_start,
                "pity_at_end": pity_end,
                "seed_ok": seed_ok,
                "session_digest": _session_digest(s["session_id"], receipts),
                "anomalies": anomalies,
                "anomaly_kinds": kinds,
            }
        )
    rows.sort(key=lambda r: r["session_id"])
    clean = [r for r in rows if r["status"] == "clean"]
    total = len(rows)
    report = {
        "summary": {
            "sessions_total": total,
            "sessions_clean": len(clean),
            "sessions_tainted": total - len(clean),
            "pulls_total": sum(r["pulls_kept"] for r in rows),
            "anomaly_count": sum(len(r["anomalies"]) for r in rows),
            "integrity_score": round(100.0 * len(clean) / total, 2) if total else 0.0,
        },
        "sessions": rows,
        "clean_session_ids": sorted(r["session_id"] for r in clean),
    }
    return report, pity_state


def _run(input_path: Path, output_path: Path, ledger_path: Path, *, clear_ledger: bool = False) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if clear_ledger and ledger_path.exists():
        ledger_path.unlink()
    subprocess.run(
        [
            str(BINARY),
            "--input",
            str(input_path),
            "--config",
            str(CONFIG),
            "--override",
            str(OVERRIDE),
            "--ledger",
            str(ledger_path),
            "--output",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="module")
def report() -> dict:
    """Load report produced by test.sh."""
    assert REPORT.is_file()
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def expected() -> dict:
    """Independent reference for bundled sessions."""
    bundle = json.loads(DATA.read_text(encoding="utf-8"))
    rep, _ = reference_report(bundle["sessions"], {})
    return rep


def test_binary_compiles() -> None:
    """Desk binary must exist after rebuild."""
    assert BINARY.is_file()


def test_data_integrity() -> None:
    """Bundled export must stay unmodified."""
    assert _sha256_file(DATA) == DATA_SHA256


def test_config_integrity() -> None:
    """Base config audit knobs must remain at contract values."""
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert cfg["pity_threshold"] == 10
    assert cfg["hmac_key"] == HMAC_KEY
    assert cfg["pity_gap_sec"] == 86400
    assert cfg["mac_domains"] == DOMAINS
    assert OVERRIDE.is_file()


def test_report_matches_reference(report: dict, expected: dict) -> None:
    """Full report must match independent recomputation."""
    assert report == expected


def test_sessions_sorted_by_session_id(report: dict) -> None:
    """Session rows sorted by session_id."""
    ids = [r["session_id"] for r in report["sessions"]]
    assert ids == sorted(ids)


def test_session_digest_uses_domain_mac(report: dict, expected: dict) -> None:
    """session_digest must use digest-domain MAC key."""
    for exp in expected["sessions"]:
        got = next(r for r in report["sessions"] if r["session_id"] == exp["session_id"])
        assert got["session_digest"] == exp["session_digest"]


def test_revision_dedupe_prefers_highest_then_earliest(report: dict) -> None:
    """sess-005 must keep revision 2 earliest snapshot (clean)."""
    row = next(r for r in report["sessions"] if r["session_id"] == "sess-005")
    assert row["status"] == "clean"
    assert row["pulls_kept"] == 1


def test_seed_fail_freezes_pity_in_report(report: dict) -> None:
    """sess-004 seed failure must leave pity_at_end equal pity_at_start."""
    row = next(r for r in report["sessions"] if r["session_id"] == "sess-004")
    assert row["seed_ok"] is False
    assert row["pity_at_end"] == row["pity_at_start"]
    assert "seed_hash_mismatch" in row["anomaly_kinds"]


def test_pity_gap_decay_in_main_bundle(report: dict) -> None:
    """sess-011 more than pity_gap_sec after sess-010 must start pity at 0."""
    row = next(r for r in report["sessions"] if r["session_id"] == "sess-011")
    assert row["pity_at_start"] == 0


def test_receipt_reuse_and_collision(report: dict) -> None:
    """Collision session clean; reuse session tainted with receipt_reuse."""
    c = next(r for r in report["sessions"] if r["session_id"] == "sess-007")
    assert c["status"] == "clean" and c["pulls_kept"] == 1
    u = next(r for r in report["sessions"] if r["session_id"] == "sess-008")
    assert "receipt_reuse" in u["anomaly_kinds"]


def test_cross_banner_isolated(report: dict) -> None:
    """nightlotus must not inherit stellarbloom pity for same player."""
    row = next(r for r in report["sessions"] if r["session_id"] == "sess-009")
    assert row["pity_at_start"] == 0


def test_ledger_written_with_banner_keys() -> None:
    """Ledger entries must keep player|banner keys."""
    data = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert any("|" in k for k in data["entries"])


def test_live_override_ignored(report: dict, expected: dict) -> None:
    """Overlay must not change base hmac/pity/gap/domains effects."""
    assert "desk-live-hmac-wrong" in OVERRIDE.read_text(encoding="utf-8")
    assert report["summary"] == expected["summary"]


def test_rerun_consistency() -> None:
    """Cleared-ledger reruns must be identical."""
    out1, out2 = APP / "output" / "ra.json", APP / "output" / "rb.json"
    led1, led2 = APP / "output" / "la.json", APP / "output" / "lb.json"
    _run(DATA, out1, led1, clear_ledger=True)
    _run(DATA, out2, led2, clear_ledger=True)
    assert out1.read_text(encoding="utf-8") == out2.read_text(encoding="utf-8")


def test_hidden_pity_violation_with_ledger() -> None:
    """Preloaded pity 9 must force pity_violation on a common pull."""
    out = APP / "output" / "pity_v.json"
    led = APP / "output" / "pity_v_led.json"
    led.write_text((FIXTURES / "pity_ledger_start.json").read_text(encoding="utf-8"), encoding="utf-8")
    _run(FIXTURES / "pity_violation.json", out, led, clear_ledger=False)
    row = json.loads(out.read_text(encoding="utf-8"))["sessions"][0]
    assert "pity_violation" in row["anomaly_kinds"]
    assert row["pity_at_start"] == 9


def test_ledger_persists_across_runs() -> None:
    """Second run must load composite pity keys from the first run."""
    led = APP / "output" / f"persist_{uuid.uuid4().hex}.json"
    _run(FIXTURES / "ledger_pass_a.json", APP / "output" / "pa.json", led, clear_ledger=True)
    mid = json.loads(led.read_text(encoding="utf-8"))
    assert mid["entries"].get("p_lex|stellarbloom") == 3
    _run(FIXTURES / "ledger_pass_b.json", APP / "output" / "pb.json", led, clear_ledger=False)
    row = json.loads((APP / "output" / "pb.json").read_text(encoding="utf-8"))["sessions"][0]
    assert row["pity_at_start"] == 3


def test_ledger_banner_isolation_after_persist() -> None:
    """Nightlotus starts at 0 after stellarbloom ledger entries exist."""
    led = APP / "output" / f"iso_{uuid.uuid4().hex}.json"
    _run(FIXTURES / "ledger_pass_a.json", APP / "output" / "ia.json", led, clear_ledger=True)
    _run(FIXTURES / "ledger_pass_c.json", APP / "output" / "ic.json", led, clear_ledger=False)
    row = json.loads((APP / "output" / "ic.json").read_text(encoding="utf-8"))["sessions"][0]
    assert row["pity_at_start"] == 0


def test_hidden_pity_gap_decay_fixture() -> None:
    """Hidden pair separated by >pity_gap_sec must reset pity_at_start on the later session."""
    out = APP / "output" / "decay.json"
    led = APP / "output" / f"decay_{uuid.uuid4().hex}.json"
    fixture = FIXTURES / "pity_decay_pair.json"
    bundle = json.loads(fixture.read_text(encoding="utf-8"))
    exp, _ = reference_report(bundle["sessions"], {})
    _run(fixture, out, led, clear_ledger=True)
    got = json.loads(out.read_text(encoding="utf-8"))
    later = next(r for r in got["sessions"] if r["session_id"] == "sess-dec-b")
    assert later["pity_at_start"] == 0
    assert got["summary"] == exp["summary"]


def test_hidden_revision_pick_fixture() -> None:
    """Highest revision then earliest opened_at must win among duplicates."""
    out = APP / "output" / "rev.json"
    led = APP / "output" / f"rev_{uuid.uuid4().hex}.json"
    fixture = FIXTURES / "revision_pick.json"
    bundle = json.loads(fixture.read_text(encoding="utf-8"))
    exp, _ = reference_report(bundle["sessions"], {})
    _run(fixture, out, led, clear_ledger=True)
    got = json.loads(out.read_text(encoding="utf-8"))
    assert got == exp
    assert got["sessions"][0]["status"] == "clean"


def test_seed_fail_does_not_advance_ledger() -> None:
    """Seed-invalid session must leave preloaded ledger pity unchanged."""
    out = APP / "output" / "roll.json"
    led = APP / "output" / f"roll_{uuid.uuid4().hex}.json"
    led.write_text((FIXTURES / "seed_rollback_ledger.json").read_text(encoding="utf-8"), encoding="utf-8")
    _run(FIXTURES / "seed_rollback.json", out, led, clear_ledger=False)
    after = json.loads(led.read_text(encoding="utf-8"))
    assert after["entries"].get("p_roll|stellarbloom") == 5
    row = json.loads(out.read_text(encoding="utf-8"))["sessions"][0]
    assert row["pity_at_start"] == 5
    assert row["pity_at_end"] == 5


def test_mutated_unique_payload() -> None:
    """Unique mutated fixture must match reference recomputation."""
    out = APP / "output" / "mut.json"
    led = APP / "output" / f"mut_{uuid.uuid4().hex}.json"
    fixture = FIXTURES / "mutated_receipt.json"
    bundle = json.loads(fixture.read_text(encoding="utf-8"))
    exp, _ = reference_report(bundle["sessions"], {})
    _run(fixture, out, led, clear_ledger=True)
    assert json.loads(out.read_text(encoding="utf-8")) == exp


def test_override_file_must_remain() -> None:
    """live_overrides.toml must remain present."""
    assert OVERRIDE.is_file()


def test_missing_override_still_uses_base_hmac(tmp_path: Path) -> None:
    """Missing override must not activate desk_fallback."""
    bundle = json.loads(DATA.read_text(encoding="utf-8"))
    sessions = [s for s in bundle["sessions"] if s["session_id"] == "sess-001"]
    inp = tmp_path / "one.json"
    inp.write_text(json.dumps({"sessions": sessions}), encoding="utf-8")
    exp, _ = reference_report(sessions, {})
    out = APP / "output" / "no_ov.json"
    led = APP / "output" / f"no_ov_{uuid.uuid4().hex}.json"
    missing = tmp_path / "missing.toml"
    subprocess.run(
        [
            str(BINARY),
            "--input",
            str(inp),
            "--config",
            str(CONFIG),
            "--override",
            str(missing),
            "--ledger",
            str(led),
            "--output",
            str(out),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(out.read_text(encoding="utf-8"))["summary"] == exp["summary"]


def test_desk_fallback_file_unchanged() -> None:
    """desk_fallback.json may exist but is not audit authority."""
    data = json.loads(FALLBACK.read_text(encoding="utf-8"))
    assert data["hmac_key"] == "desk-fallback-weekend-key"
