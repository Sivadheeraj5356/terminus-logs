"""End-to-end tests for the SVOD residual pool ledger processor."""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from reference_oracle import DEFAULT_SECRET, GENESIS, compute_audit, compute_outputs

APP = Path("/app")
TESTS = Path(__file__).resolve().parent
OUTPUT = APP / "output"
DAILY = OUTPUT / "residual_daily.csv"
WEEKLY = OUTPUT / "residual_weekly.csv"
ESCROW = OUTPUT / "escrow_ledger.jsonl"
USAGE_DIR = APP / "data" / "usage"
INGEST_ORDER = APP / "config" / "usage_ingest_order.json"
WORKS = APP / "data" / "works.csv"
GO_RUN = ["go", "run", "./cmd/residual"]

HASH_LOCKED = [
    APP / "data" / "works.csv",
    APP / "data" / "aliases.csv",
    APP / "data" / "participants.csv",
    APP / "config" / "territory_calendar.json",
    APP / "config" / "rate_tiers.toml",
    APP / "config" / "recoupment_caps.json",
    APP / "config" / "usage_ingest_order.json",
    USAGE_DIR / "a.jsonl",
    USAGE_DIR / "b.jsonl",
    USAGE_DIR / "c.jsonl",
    USAGE_DIR / "d.jsonl",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_go(env: dict | None = None) -> subprocess.CompletedProcess:
    if OUTPUT.exists():
        for child in OUTPUT.iterdir():
            child.unlink()
    else:
        OUTPUT.mkdir(parents=True)
    return subprocess.run(
        GO_RUN,
        cwd=APP,
        capture_output=True,
        text=True,
        env=env or os.environ.copy(),
    )


@pytest.fixture(scope="session")
def run_program():
    before = {p: _sha256(p) for p in HASH_LOCKED if p.exists()}
    result = _run_go()
    assert result.returncode == 0, result.stderr
    after = {p: _sha256(p) for p in HASH_LOCKED if p.exists()}
    return {"before": before, "after": after, "stderr": result.stderr}


def _daily_rows() -> list[dict[str, str]]:
    return list(csv.DictReader(DAILY.read_text(encoding="utf-8").splitlines()))


def _weekly_rows() -> list[dict[str, str]]:
    return list(csv.DictReader(WEEKLY.read_text(encoding="utf-8").splitlines()))


def _escrow_lines() -> list[dict]:
    lines = []
    for line in ESCROW.read_text(encoding="utf-8").splitlines():
        if line.strip():
            lines.append(json.loads(line))
    return lines


def _escrow_body() -> list[dict]:
    return [entry for entry in _escrow_lines() if entry.get("type") != "footer"]


def _expected():
    return compute_outputs(APP)


class TestBuild:
    def test_outputs_exist(self, run_program):
        assert DAILY.is_file()
        assert WEEKLY.is_file()
        assert ESCROW.is_file()

    def test_inputs_unchanged(self, run_program):
        assert run_program["before"] == run_program["after"]

    def test_malformed_rows_audited_to_stderr(self, run_program):
        assert run_program["stderr"] == compute_audit(APP)


class TestDailyContract:
    def test_daily_matches_oracle(self, run_program):
        expected, _, _ = _expected()
        assert DAILY.read_text(encoding="utf-8") == expected

    def test_daily_header(self, run_program):
        header = DAILY.read_text(encoding="utf-8").splitlines()[0]
        assert header == "workId,territory,dayLocal,medium,playCount,grossMicroCents,recoupedMicroCents,netMicroCents"

    def test_daily_recouped_zero(self, run_program):
        for row in _daily_rows():
            assert row["recoupedMicroCents"] == "0"
            assert row["netMicroCents"] == row["grossMicroCents"]

    def test_daily_sorted(self, run_program):
        keys = [(r["workId"], r["territory"], r["dayLocal"], r["medium"]) for r in _daily_rows()]
        assert keys == sorted(keys)

    def test_wk1_us_svod_dedup_winner(self, run_program):
        row = next(r for r in _daily_rows() if r["workId"] == "WK1" and r["medium"] == "SVOD" and r["dayLocal"] == "2024-03-10")
        assert int(row["playCount"]) == 1099
        assert int(row["grossMicroCents"]) == 537000

    def test_inactive_work_excluded(self, run_program):
        assert all(r["workId"] != "WK3" for r in _daily_rows())

    def test_alias_resolution(self, run_program):
        assert any(r["workId"] == "WK1" and r["dayLocal"] == "2024-03-12" for r in _daily_rows())


class TestWeeklyContract:
    def test_weekly_matches_oracle(self, run_program):
        _, expected, _ = _expected()
        assert WEEKLY.read_text(encoding="utf-8") == expected

    def test_weekly_rollup_matches_daily_sums(self, run_program):
        daily = _daily_rows()
        weekly = _weekly_rows()
        from reference_oracle import _load_territory, _week_start

        territory = _load_territory(APP / "config" / "territory_calendar.json")
        buckets: dict[tuple, int] = {}
        for row in daily:
            week = _week_start(row["dayLocal"], territory[row["territory"]]["iana"])
            key = (row["workId"], row["territory"], week)
            buckets[key] = buckets.get(key, 0) + int(row["grossMicroCents"])
        for row in weekly:
            key = (row["workId"], row["territory"], row["weekStartLocal"])
            assert int(row["grossMicroCents"]) == buckets[key]

    def test_wk2_uk_weekly_combined_mediums(self, run_program):
        row = next(r for r in _weekly_rows() if r["workId"] == "WK2" and r["territory"] == "UK" and r["weekStartLocal"] == "2024-03-11")
        assert int(row["grossMicroCents"]) == 93500
        assert int(row["playCount"]) == 510

    def test_weekly_sorted(self, run_program):
        keys = [(r["workId"], r["territory"], r["weekStartLocal"]) for r in _weekly_rows()]
        assert keys == sorted(keys)


class TestEscrow:
    def test_escrow_matches_oracle(self, run_program):
        _, _, expected = _expected()
        assert ESCROW.read_text(encoding="utf-8") == expected

    def test_escrow_footer_hmac(self, run_program):
        lines = _escrow_lines()
        footer = lines[-1]
        assert footer["type"] == "footer"
        msg = f"{footer['periodMonth']}|{footer['poolTotalMicroCents']}|{footer['lineCount']}|{footer['prevHash']}"
        expected = hmac.new(DEFAULT_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
        assert footer["entryHash"] == expected
        assert footer["prevHash"] == GENESIS

    def test_escrow_json_compact_key_order(self, run_program):
        raw_lines = [line for line in ESCROW.read_text(encoding="utf-8").splitlines() if line]
        body_re = re.compile(
            r'^\{"workId":"[^"]+","territory":"[^"]+","periodMonth":"\d{4}-\d{2}",'
            r'"participantId":"[^"]+","amountMicroCents":\d+,"catalogIndex":\d+\}$'
        )
        footer_re = re.compile(
            r'^\{"type":"footer","periodMonth":"\d{4}-\d{2}","poolTotalMicroCents":\d+,'
            r'"lineCount":\d+,"prevHash":"[0-9a-f]{64}","entryHash":"[0-9a-f]{64}"\}$'
        )
        assert all(body_re.match(line) for line in raw_lines[:-1])
        assert footer_re.match(raw_lines[-1])

    def test_escrow_pool_total_matches_body(self, run_program):
        lines = _escrow_lines()
        body = _escrow_body()
        footer = lines[-1]
        assert footer["poolTotalMicroCents"] == sum(int(entry["amountMicroCents"]) for entry in body)
        assert footer["lineCount"] == len(body)

    def test_recoupment_reduces_latest_uk(self, run_program):
        body = _escrow_body()
        latest_uk = [entry for entry in body if entry["workId"] == "WK2" and entry["territory"] == "UK"]
        total = sum(int(entry["amountMicroCents"]) for entry in latest_uk)
        assert total == 5200

    def test_zero_amount_participant_omitted(self, run_program):
        body = _escrow_body()
        assert all(entry["participantId"] != "P5" for entry in body)

    def test_escrow_body_sorted(self, run_program):
        body = _escrow_body()
        keys = [(entry["workId"], entry["territory"], entry["participantId"]) for entry in body]
        assert keys == sorted(keys)


class TestDedupMutation:
    def test_manifest_swap_changes_dedup_winner(self, run_program):
        backup = INGEST_ORDER.read_bytes()
        swapped = json.loads(backup.decode())
        swapped["files"] = list(reversed(swapped["files"]))
        INGEST_ORDER.write_text(json.dumps(swapped, indent=2) + "\n", encoding="utf-8")
        try:
            expected, _, _ = compute_outputs(APP)
            result = _run_go()
            assert result.returncode == 0, result.stderr
            assert DAILY.read_text(encoding="utf-8") == expected
            row = next(r for r in csv.DictReader(io.StringIO(DAILY.read_text())) if r["workId"] == "WK1" and r["dayLocal"] == "2024-03-10" and r["medium"] == "SVOD")
            assert int(row["playCount"]) == 1099
        finally:
            INGEST_ORDER.write_bytes(backup)
            _run_go()


class TestPrivateFixture:
    def test_private_shard_remainder_split(self):
        backup_usage = {p.name: p.read_bytes() for p in USAGE_DIR.glob("*.jsonl")}
        backup_order = INGEST_ORDER.read_bytes()
        try:
            for p in USAGE_DIR.glob("*.jsonl"):
                p.unlink()
            private = TESTS / "fixtures" / "private" / "mini.jsonl"
            shutil.copy(private, USAGE_DIR / "mini.jsonl")
            INGEST_ORDER.write_text(json.dumps({"files": ["data/usage/mini.jsonl"]}) + "\n", encoding="utf-8")
            expected, _, _ = compute_outputs(APP)
            result = _run_go()
            assert result.returncode == 0, result.stderr
            assert DAILY.read_text(encoding="utf-8") == expected
            body = _escrow_body()
            assert len(body) == 3
            assert sum(int(entry["amountMicroCents"]) for entry in body) == 47500
        finally:
            for p in USAGE_DIR.glob("mini.jsonl"):
                p.unlink()
            for name, data in backup_usage.items():
                (USAGE_DIR / name).write_bytes(data)
            INGEST_ORDER.write_bytes(backup_order)
            _run_go()

    def test_private_malformed_audit_and_dedup(self):
        backup_usage = {p.name: p.read_bytes() for p in USAGE_DIR.glob("*.jsonl")}
        backup_order = INGEST_ORDER.read_bytes()
        try:
            for p in USAGE_DIR.glob("*.jsonl"):
                p.unlink()
            private = TESTS / "fixtures" / "private" / "adversarial.jsonl"
            shutil.copy(private, USAGE_DIR / "adversarial.jsonl")
            INGEST_ORDER.write_text(json.dumps({"files": ["data/usage/adversarial.jsonl"]}) + "\n", encoding="utf-8")
            expected, _, expected_escrow = compute_outputs(APP)
            result = _run_go()
            assert result.returncode == 0, result.stderr
            assert result.stderr == compute_audit(APP)
            assert DAILY.read_text(encoding="utf-8") == expected
            assert ESCROW.read_text(encoding="utf-8") == expected_escrow
            row = _daily_rows()[0]
            assert row["playCount"] == "101"
        finally:
            for p in USAGE_DIR.glob("adversarial.jsonl"):
                p.unlink()
            for name, data in backup_usage.items():
                (USAGE_DIR / name).write_bytes(data)
            INGEST_ORDER.write_bytes(backup_order)
            _run_go()


class TestFalseGreenTrap:
    def test_shape_only_check_does_not_verify_totals(self, run_program):
        daily = DAILY.read_text(encoding="utf-8")
        assert "workId" in daily.splitlines()[0]
        tampered = daily.replace("537000", "537001", 1)
        assert "537001" in tampered
        assert tampered != daily

    def test_go_shape_validator_passes_tampered_totals(self, run_program):
        tampered_daily = OUTPUT / "tampered_daily.csv"
        tampered_daily.write_text(DAILY.read_text(encoding="utf-8").replace("537000", "537001", 1), encoding="utf-8")
        test_file = APP / "internal" / "validate" / "pool_validator_test.go"
        test_file.write_text(
            '''package validate

import "testing"

func TestTamperedTotalsStillShapeValid(t *testing.T) {
	if err := ValidateShape("/app/output/tampered_daily.csv", "/app/output/residual_weekly.csv", "/app/output/escrow_ledger.jsonl"); err != nil {
		t.Fatal(err)
	}
}
''',
            encoding="utf-8",
        )
        try:
            result = subprocess.run(["go", "test", "./internal/validate"], cwd=APP, capture_output=True, text=True)
            assert result.returncode == 0, result.stderr + result.stdout
        finally:
            test_file.unlink(missing_ok=True)
            tampered_daily.unlink(missing_ok=True)

    def test_rerun_restores_after_tamper(self):
        _run_go()
        good = DAILY.read_text(encoding="utf-8")
        DAILY.write_text(good.replace("537000", "537001"), encoding="utf-8")
        _run_go()
        assert DAILY.read_text(encoding="utf-8") == good


class TestRateAndTerritory:
    def test_jp_rerun_bracket(self, run_program):
        row = next(r for r in _daily_rows() if r["territory"] == "JP")
        assert int(row["grossMicroCents"]) == 106875

    def test_uk_theatrical_rate(self, run_program):
        row = next(r for r in _daily_rows() if r["territory"] == "UK" and r["medium"] == "THEATRICAL" and r["dayLocal"] == "2024-03-11")
        assert int(row["grossMicroCents"]) == 27500

    def test_us_dst_spring_forward_day_local(self, run_program):
        row = next(r for r in _daily_rows() if r["workId"] == "WK1" and r["dayLocal"] == "2024-03-10" and r["medium"] == "SVOD")
        assert int(row["playCount"]) == 1099

    def test_uk_dst_fall_back_day_local(self, run_program):
        row = next(r for r in _daily_rows() if r["workId"] == "WK2" and r["territory"] == "UK" and r["dayLocal"] == "2024-10-27")
        assert row["medium"] == "AVOD"
        assert int(row["playCount"]) == 100


class TestCrossArtifact:
    def test_triple_output_immutability_rerun(self, run_program):
        before = {p: _sha256(p) for p in HASH_LOCKED}
        _run_go()
        after = {p: _sha256(p) for p in HASH_LOCKED}
        assert before == after

    def test_escrow_period_month_latest(self, run_program):
        footer = _escrow_lines()[-1]
        assert footer["periodMonth"] == "2024-10"

    def test_prior_month_daily_excluded_from_latest_escrow(self, run_program):
        assert any(r["workId"] == "WK2" and r["dayLocal"] == "2024-02-29" for r in _daily_rows())
        assert all(entry["periodMonth"] == "2024-10" for entry in _escrow_body())


    def test_wk1_us_avod_daily(self, run_program):
        row = next(r for r in _daily_rows() if r["workId"] == "WK1" and r["medium"] == "AVOD")
        assert int(row["grossMicroCents"]) == 30000

    def test_wk2_uk_recoupment_net_in_escrow(self, run_program):
        body = _escrow_body()
        uk = sum(int(entry["amountMicroCents"]) for entry in body if entry["territory"] == "UK")
        assert uk == 5200


class TestCounts:
    def test_daily_row_count(self, run_program):
        assert len(_daily_rows()) == 7

    def test_weekly_row_count(self, run_program):
        assert len(_weekly_rows()) == 6

    def test_escrow_body_line_count(self, run_program):
        assert len(_escrow_body()) == 2


class TestEscrowSecret:
    def test_custom_audit_secret(self):
        env = os.environ.copy()
        env["ESCROW_AUDIT_SECRET"] = "test-secret-123"
        expected, _, expected_escrow = compute_outputs(APP, secret="test-secret-123")
        result = _run_go(env=env)
        assert result.returncode == 0, result.stderr
        assert ESCROW.read_text(encoding="utf-8") == expected_escrow
        footer = _escrow_lines()[-1]
        msg = f"{footer['periodMonth']}|{footer['poolTotalMicroCents']}|{footer['lineCount']}|{footer['prevHash']}"
        digest = hmac.new(b"test-secret-123", msg.encode(), hashlib.sha256).hexdigest()
        assert footer["entryHash"] == digest
        _run_go()
