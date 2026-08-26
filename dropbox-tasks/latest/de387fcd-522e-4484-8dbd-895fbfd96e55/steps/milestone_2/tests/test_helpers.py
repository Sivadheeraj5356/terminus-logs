"""Shared helpers for coinsurance recovery verifier tests."""

import hashlib
import json
import subprocess
from decimal import ROUND_HALF_DOWN, ROUND_HALF_UP, Decimal
from pathlib import Path

APP_DIR = Path("/app")
CONFIG_PATH = APP_DIR / "config" / "coinsurance-rules.properties"
OVERRIDE_CONFIG_PATH = APP_DIR / "config" / "coinsurance-rules.override.properties"
OUTPUT_PATH = APP_DIR / "output" / "coinsurance-report.json"
POLICIES_PATH = APP_DIR / "data" / "coinsurance-policies.json"

EXPECTED_POLICIES_SHA256 = ("50252001c7f519d27d4528b8510bfff8ee487d1e8027d7e229b708d92ede400b")
EXPECTED_CONFIG_SHA256 = ("345bf3d98e3b1560da379f6bbfb0522cfd42036c77e8f65986176fa33d02475a")

EXPECTED_POLICIES: list[dict] = [
    {"id": "COI-001", "insurer": "Atlantic Mutual", "grossIncurred": 8500.0, "deductibleAmount": 0.0, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "premium"},
    {"id": "COI-002", "insurer": "Pacific Re Ltd", "grossIncurred": 3200.0, "deductibleAmount": 0.0, "coinsuranceRate": 1.0, "status": "pending", "policyTier": "plus"},
    {"id": "COI-003", "insurer": "Midwest Treaty Co", "grossIncurred": 12000.0, "deductibleAmount": 1500.0, "coinsuranceRate": 1.0, "status": "APPROVED", "policyTier": "plus"},
    {"id": "COI-004", "insurer": "Zero Loss Batch", "grossIncurred": 0.0, "deductibleAmount": 0.0, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "basic"},
    {"id": "COI-005", "insurer": "Bayline Underwriters", "grossIncurred": 2100.0, "deductibleAmount": 0.0, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "basic"},
    {"id": "COI-006", "insurer": "Summit Re Group", "grossIncurred": 1200.0, "deductibleAmount": 0.0, "coinsuranceRate": 1.0, "status": "Approved", "policyTier": "basic"},
    {"id": "COI-007", "insurer": "Delta Cession Pool", "grossIncurred": 4500.0, "deductibleAmount": 500.0, "coinsuranceRate": 0.85, "status": "approved", "policyTier": "plus"},
    {"id": "COI-008", "insurer": "Crown Treaty", "grossIncurred": 1400.0, "deductibleAmount": 0.0, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "premium"},
    {"id": "COI-009", "insurer": "Fleet Cat Layer", "grossIncurred": 10000.0, "deductibleAmount": 2500.0, "coinsuranceRate": 0.75, "status": "approved", "policyTier": "premium"},
    {"id": "COI-010", "insurer": "Starter Recovery", "grossIncurred": 1500.0, "deductibleAmount": 0.0, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "basic"},
    {"id": "COI-011", "insurer": "Elite Cat Bond", "grossIncurred": 5000.0, "deductibleAmount": 0.0, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "PREMIUM"},
    {"id": "COI-012", "insurer": "Regional Quota Share", "grossIncurred": 7365.0, "deductibleAmount": 865.0, "coinsuranceRate": 0.8, "status": "approved", "policyTier": "premium"},
    {"id": "COI-013", "insurer": "Partner XoL", "grossIncurred": 6500.0, "deductibleAmount": 0.0, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "plus"},
    {"id": "COI-014", "insurer": "Volume Basic Layer", "grossIncurred": 10500.0, "deductibleAmount": 600.0, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "basic"},
    {"id": "COI-015", "insurer": "Enterprise Cat", "grossIncurred": 52150.0, "deductibleAmount": 2150.0, "coinsuranceRate": 0.9, "status": "approved", "policyTier": "premium"},
    {"id": "COI-016", "insurer": "Channel Surplus", "grossIncurred": 25500.0, "deductibleAmount": 0.0, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "plus"},
    {"id": "COI-017", "insurer": "Pilot Facultative", "grossIncurred": 22450.0, "deductibleAmount": 2450.0, "coinsuranceRate": 0.88, "status": "approved", "policyTier": "basic"},
    {"id": "COI-018", "insurer": "Flagship Event", "grossIncurred": 36850.0, "deductibleAmount": 1850.0, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "premium"},
    {"id": "COI-019", "insurer": "Mid-Tier Layer", "grossIncurred": 5200.0, "deductibleAmount": 0.0, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "plus"},
    {"id": "COI-020", "insurer": "High Basic Stack", "grossIncurred": 8800.0, "deductibleAmount": 800.0, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "basic"},
    {"id": "COI-021", "insurer": "Coastal Wind Pool", "grossIncurred": 9800.0, "deductibleAmount": 200.0, "coinsuranceRate": 0.92, "status": "approved", "policyTier": "plus"},
    {"id": "COI-022", "insurer": "Inland Flood XoL", "grossIncurred": 11200.0, "deductibleAmount": 1200.0, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "basic"},
    {"id": "COI-023", "insurer": "Retrocession Alpha", "grossIncurred": 15800.0, "deductibleAmount": 0.0, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "premium"},
    {"id": "COI-024", "insurer": "Retrocession Beta", "grossIncurred": 4200.0, "deductibleAmount": 200.0, "coinsuranceRate": 0.95, "status": "approved", "policyTier": "plus"},
    {"id": "COI-025", "insurer": "Minimum Edge Case", "grossIncurred": 1500.0, "deductibleAmount": 0.0, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "premium"},
    {"id": "COI-026", "insurer": "Staging Reject", "grossIncurred": 800.0, "deductibleAmount": 0.0, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "basic"},
    {"id": "COI-027", "insurer": "Cat Boundary Plus", "grossIncurred": 10000.0, "deductibleAmount": 0.0, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "plus"},
    {"id": "COI-028", "insurer": "Premium HALF_DOWN Note", "grossIncurred": 10001.19, "deductibleAmount": 0.0, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "premium"},
    {"id": "COI-029", "insurer": "Plus HALF_DOWN Basis", "grossIncurred": 10001.27, "deductibleAmount": 0.0, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "plus"},
    {"id": "COI-030", "insurer": "Subminimum Decimal", "grossIncurred": 1499.99, "deductibleAmount": 0.0, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "basic"},
    {"id": "COI-031", "insurer": "Premium Cat Edge Note", "grossIncurred": 10021.19, "deductibleAmount": 21.19, "coinsuranceRate": 0.78, "status": "approved", "policyTier": "premium"},
    {"id": "COI-032", "insurer": "Premium Basis Fraction", "grossIncurred": 10001.32, "deductibleAmount": 1.32, "coinsuranceRate": 1.0, "status": "approved", "policyTier": "premium"},
]


def assert_production_inputs_unchanged() -> None:
    d = hashlib.sha256(POLICIES_PATH.read_bytes()).hexdigest()
    c = hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()
    assert d == EXPECTED_POLICIES_SHA256, f"{POLICIES_PATH} was modified"
    assert c == EXPECTED_CONFIG_SHA256, f"{CONFIG_PATH} was modified"


def run_maven(args: list[str]) -> subprocess.CompletedProcess:
    if args and args[0] == "exec:java":
        install = subprocess.run(["mvn", "-q", "-B", "-o", "install", "-DskipTests"],
            cwd=APP_DIR, capture_output=True, text=True, check=False)
        if install.returncode != 0:
            return install
        args = ["-pl", "coinsurance-batch", "exec:java"]
    return subprocess.run(["mvn", "-q", "-B", "-o", *args], cwd=APP_DIR, capture_output=True, text=True, check=False)


def load_report() -> dict:
    with OUTPUT_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def load_policies() -> list[dict]:
    with POLICIES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def load_config() -> dict[str, str]:
    config = {}
    for line in CONFIG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        k, v = line.split("=", 1)
        config[k.strip()] = v.strip()
    return config


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def coinsurance_base(row: dict) -> Decimal:
    gross = Decimal(str(row["grossIncurred"]))
    deductible = Decimal(str(row["deductibleAmount"]))
    rate = Decimal(str(row["coinsuranceRate"]))
    net = gross * rate - deductible
    if net < 0:
        return Decimal("0.00")
    return round_money(net)


def is_quota_line(base: Decimal, threshold: Decimal) -> bool:
    return base >= threshold


def is_large_loss_line(base: Decimal, threshold: Decimal) -> bool:
    return base >= threshold


def round_quota_credit(value: Decimal, tier: str, quota_line: bool) -> Decimal:
    if quota_line and tier == "premium":
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_DOWN)
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def round_tier_adjustment(value: Decimal, tier: str, quota_line: bool, large_loss_line: bool) -> Decimal:
    if tier == "plus" and quota_line:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_DOWN)
    if tier == "premium" and large_loss_line:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_DOWN)
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def round_premium_holdback(value: Decimal, quota_line: bool) -> Decimal:
    if quota_line:
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_DOWN)
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def eligible_policy_ids() -> set[str]:
    config = load_config()
    minimum = Decimal(config["minimum.policy.amount"])
    eligible = set()
    for row in load_policies():
        if row["status"].lower() != "approved":
            continue
        if row["grossIncurred"] <= 0:
            continue
        if Decimal(str(row["grossIncurred"])) < minimum:
            continue
        eligible.add(row["id"])
    return eligible


def policy_source_by_id() -> dict[str, dict]:
    return {r["id"]: r for r in EXPECTED_POLICIES}


def expected_indemnity_share(source: dict, config: dict[str, str]) -> Decimal:
    return round_money(coinsurance_base(source) * Decimal(config["indemnity.share.rate"]))


def expected_m2_tier_adjustment(report_row: dict, source: dict, config: dict[str, str]) -> Decimal:
    indemnity_share = money(report_row["indemnityShare"])
    quota_credit = money(report_row["quotaCreditAmount"])
    adjustment_rate = money(report_row["adjustmentRate"])
    base = coinsurance_base(source)
    quota_threshold = Decimal(config["coinsurance.threshold.quota"])
    tier = source["policyTier"].lower()
    basis = indemnity_share
    if tier in ("premium", "plus") and base >= quota_threshold:
        basis = indemnity_share - quota_credit
    return round_money(basis * adjustment_rate)


def compute_expected(row: dict, config: dict[str, str]) -> dict | None:
    if row["status"].lower() != "approved" or row["grossIncurred"] <= 0:
        return None
    gross = round_money(Decimal(str(row["grossIncurred"])))
    if gross < Decimal(config["minimum.policy.amount"]):
        return None
    base = coinsurance_base(row)
    tier = row["policyTier"].lower()
    quota_threshold = Decimal(config["coinsurance.threshold.quota"])
    large_loss_threshold = Decimal(config["coinsurance.threshold.large.loss"])
    quota_line = is_quota_line(base, quota_threshold)
    large_loss_line = is_large_loss_line(base, large_loss_threshold)
    indemnity_share = round_money(base * Decimal(config["indemnity.share.rate"]))
    processing_fee = round_money(base * Decimal(config["processing.fee.rate"]))
    adjustment_rate = Decimal(config[f"adjustment.tier.{tier}"])
    quota_credit = Decimal("0.00")
    if quota_line:
        rate = Decimal(config["coinsurance.rate.quota.premium"] if large_loss_line else config["quota.credit.rate"])
        quota_credit = round_quota_credit(indemnity_share * rate, tier, quota_line)
    adj_basis = indemnity_share - quota_credit if tier in ("premium", "plus") and quota_line else indemnity_share
    tier_adj = round_tier_adjustment(adj_basis * adjustment_rate, tier, quota_line, large_loss_line)
    if tier == "basic" and gross == Decimal(config["minimum.policy.amount"]):
        holdback = Decimal("0.00")
    else:
        hrate = Decimal(config["coinsurance.rate.holdback.premium"] if large_loss_line else config["premium.holdback.rate"])
        taxable = indemnity_share - tier_adj - quota_credit + processing_fee
        holdback = round_premium_holdback(taxable * hrate, quota_line)
    net = round_money(indemnity_share - tier_adj - quota_credit + processing_fee - holdback)
    return {"id": row["id"], "indemnityShare": indemnity_share, "processingFeeAmount": processing_fee,
            "adjustmentRate": round_money(adjustment_rate), "tierAdjustmentAmount": tier_adj,
            "quotaCreditAmount": quota_credit, "premiumHoldbackAmount": holdback, "netRecovery": net}


def expected_report() -> dict:
    config = load_config()
    rows = [c for r in load_policies() if (c := compute_expected(r, config))]
    rows.sort(key=lambda x: (-x["netRecovery"], x["id"]))
    return {"policies": rows, "summary": {
        "policyCount": len(rows),
        "totalIndemnityShare": sum(r["indemnityShare"] for r in rows),
        "totalProcessingFee": sum(r["processingFeeAmount"] for r in rows),
        "totalTierAdjustment": sum(r["tierAdjustmentAmount"] for r in rows),
        "totalQuotaCredit": sum(r["quotaCreditAmount"] for r in rows),
        "totalPremiumHoldback": sum(r["premiumHoldbackAmount"] for r in rows),
        "totalRecovery": sum(r["netRecovery"] for r in rows),
    }}


def assert_report_matches_expected(report: dict, expected: dict) -> None:
    sources = {r["id"]: r for r in EXPECTED_POLICIES}
    assert report["summary"]["policyCount"] == expected["summary"]["policyCount"]
    assert len(report["policies"]) == expected["summary"]["policyCount"]
    for actual, exp in zip(report["policies"], expected["policies"]):
        assert actual["id"] == exp["id"]
        source = sources[actual["id"]]
        assert actual["insurer"] == source["insurer"]
        assert money(actual["grossIncurred"]) == money(source["grossIncurred"])
        assert money(actual["deductibleAmount"]) == money(source["deductibleAmount"])
        assert money(actual["coinsuranceRate"]) == money(source["coinsuranceRate"])
        assert actual["policyTier"] == source["policyTier"]
        assert money(actual["indemnityShare"]) == exp["indemnityShare"]
        assert money(actual["processingFeeAmount"]) == exp["processingFeeAmount"]
        assert money(actual["adjustmentRate"]) == exp["adjustmentRate"]
        assert money(actual["tierAdjustmentAmount"]) == exp["tierAdjustmentAmount"]
        assert money(actual["quotaCreditAmount"]) == exp["quotaCreditAmount"]
        assert money(actual["premiumHoldbackAmount"]) == exp["premiumHoldbackAmount"]
        assert money(actual["netRecovery"]) == exp["netRecovery"]
    summary = report["summary"]
    for field in ["totalIndemnityShare", "totalProcessingFee", "totalTierAdjustment",
                  "totalQuotaCredit", "totalPremiumHoldback", "totalRecovery"]:
        assert money(summary[field]) == money(expected["summary"][field])


def delete_report() -> None:
    if OUTPUT_PATH.exists():
        OUTPUT_PATH.unlink()


_report_from_exec_java = False


def regenerate_report(*, force: bool = False) -> None:
    global _report_from_exec_java
    if _report_from_exec_java and not force and OUTPUT_PATH.is_file():
        return
    delete_report()
    result = run_maven(["exec:java"])
    assert result.returncode == 0, result.stdout + result.stderr
    assert OUTPUT_PATH.is_file(), f"Missing report at {OUTPUT_PATH}"
    _report_from_exec_java = True
