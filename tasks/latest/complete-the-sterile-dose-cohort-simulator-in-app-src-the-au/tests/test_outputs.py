import csv
import json
import random
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from reference_model import expected_report

APP_SRC = Path("/app/src")
BIN = Path("/app/bin/amberglass")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEADERS = {
    "lots.csv": [
        "lot_id",
        "material_id",
        "family",
        "potency_mg_per_g",
        "uncertainty_mg_per_g",
        "grams",
        "prime_grams",
        "expires_day",
        "open_stability_days",
        "status",
        "cost_cents_per_g",
    ],
    "assays.csv": [
        "lot_id",
        "assay_group",
        "assay_day",
        "valid_through_day",
        "decay_mg_per_g_per_day",
        "uncertainty_growth_mg_per_g_per_day",
    ],
    "packaging.csv": ["lot_id", "vial_grams", "max_open_cycles", "open_decay_mg_per_g_per_day", "open_uncertainty_growth_mg_per_g_per_day"],
    "formulas.csv": [
        "product_id",
        "required_material_id",
        "grams_per_unit",
        "min_robust_potency_mg_per_unit",
        "uncertainty_budget",
        "max_lots",
        "mix_loss_mg_per_extra_lot",
        "substitute_family",
        "substitution_penalty_cents_per_g",
    ],
    "orders.csv": ["order_id", "product_id", "units", "requested_day", "priority", "max_cost_cents"],
    "events.csv": ["lot_id", "kind", "day", "grams"],
}


def build_binary():
    chroot = shutil.which("chroot")
    assert chroot is not None
    goroot = Path("/usr/local/go")
    assert (goroot / "bin/go").exists()
    with tempfile.TemporaryDirectory(prefix="amberglass-build-", dir="/var/tmp") as temporary:
        jail = Path(temporary)
        shutil.copytree(goroot, jail / "go", symlinks=True)
        shutil.copytree(APP_SRC, jail / "src", symlinks=True)
        for name in ("cache", "dev", "home", "out", "tmp"):
            (jail / name).mkdir()
        (jail / "dev/null").touch()
        (jail / "dev/null").chmod(0o666)
        proc = subprocess.run(
            [
                chroot,
                str(jail),
                "/go/bin/go",
                "-C",
                "/src",
                "build",
                "-mod=readonly",
                "-trimpath",
                "-o",
                "/out/amberglass",
                ".",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={
                "CGO_ENABLED": "0",
                "GOCACHE": "/cache",
                "GOPROXY": "off",
                "GOSUMDB": "off",
                "GOROOT": "/go",
                "GOTELEMETRY": "off",
                "GOTOOLCHAIN": "local",
                "GOTMPDIR": "/tmp",
                "HOME": "/home",
                "PATH": "/go/bin",
            },
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        built = jail / "out/amberglass"
        assert built.exists()
        BIN.parent.mkdir(parents=True, exist_ok=True)
        BIN.unlink(missing_ok=True)
        shutil.copy2(built, BIN)
    BIN.chmod(0o555)
    assert BIN.read_bytes()[:4] == b"\x7fELF"
    metadata = subprocess.run(
        [str(goroot / "bin/go"), "version", "-m", str(BIN)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    assert "go1." in metadata.stdout
    assert "build\t-buildmode=exe" in metadata.stdout


@pytest.fixture(scope="session", autouse=True)
def verifier_owned_binary():
    build_binary()


def unique_lot_ids(lots):
    seen = set()
    result = []
    for row in lots:
        if row[0] not in seen:
            seen.add(row[0])
            result.append(row[0])
    return result


def default_assays(lots):
    return [[lot_id, lot_id, "0", "1000000", "0", "0"] for lot_id in unique_lot_ids(lots)]


def default_packaging(lots):
    return [[lot_id, "1", "1", "0", "0"] for lot_id in unique_lot_ids(lots)]


def write_case(
    root,
    lots,
    formulas,
    orders,
    events,
    assays=None,
    packaging=None,
    line_ending="\n",
    blank_after=None,
):
    root.mkdir(parents=True, exist_ok=True)
    payloads = {
        "lots.csv": lots,
        "assays.csv": default_assays(lots) if assays is None else assays,
        "packaging.csv": default_packaging(lots) if packaging is None else packaging,
        "formulas.csv": formulas,
        "orders.csv": orders,
        "events.csv": events,
    }
    blank_after = blank_after or {}
    for name, rows in payloads.items():
        with (root / name).open("w", newline="") as handle:
            writer = csv.writer(handle, lineterminator=line_ending)
            writer.writerow(HEADERS[name])
            for index, row in enumerate(rows):
                writer.writerow(row)
                if index in blank_after.get(name, set()):
                    handle.write(" \t" + line_ending)


def run_binary_isolated(root=None, out=None, arguments=None, stale_output=None):
    chroot = shutil.which("chroot")
    assert chroot is not None
    with tempfile.TemporaryDirectory(prefix="amberglass-jail-", dir="/tmp") as temporary:
        jail = Path(temporary)
        jail.chmod(0o755)
        shutil.copy2(BIN, jail / "amberglass")
        (jail / "amberglass").chmod(0o555)
        if root is not None:
            shutil.copytree(root, jail / "input")
        output_dir = jail / "output"
        output_dir.mkdir()
        output_dir.chmod(0o777)
        jailed_output = output_dir / "report.json"
        if stale_output is not None:
            jailed_output.write_bytes(stale_output)
            jailed_output.chmod(0o666)
        command_arguments = ["/input", "/output/report.json"] if arguments is None else arguments
        proc = subprocess.run(
            [chroot, "--userspec=65534:65534", str(jail), "/amberglass", *command_arguments],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={"PATH": ""},
        )
        if out is not None:
            if jailed_output.exists():
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(jailed_output.read_bytes())
            else:
                out.unlink(missing_ok=True)
        return proc


def run_case(root, out):
    proc = run_binary_isolated(root=root, out=out)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout == ""
    assert proc.stderr == ""
    raw = out.read_bytes()
    assert raw.endswith(b"\n")
    return json.loads(raw), raw


def assert_exact_report(actual, expected):
    assert actual == expected
    assert list(actual) == ["schema", "input_digest", "orders", "rejections", "materials", "cohort_audit", "summary"]
    assert actual["schema"] == "amberglass.v6"
    assert HEX64.fullmatch(actual["input_digest"])
    for item in actual["orders"]:
        assert list(item) == [
            "order_id",
            "product_id",
            "status",
            "grams",
            "nominal_potency_mg",
            "open_decay_loss_mg",
            "uncertainty_deduction_mg",
            "open_uncertainty_growth_mg",
            "mix_loss_mg",
            "robust_potency_mg",
            "robust_margin_mg",
            "cost_cents",
            "substitute_grams",
            "lots",
        ]
        assert item["status"] == "FILLED"
        for key in (
            "grams",
            "nominal_potency_mg",
            "open_decay_loss_mg",
            "uncertainty_deduction_mg",
            "open_uncertainty_growth_mg",
            "mix_loss_mg",
            "robust_potency_mg",
            "robust_margin_mg",
            "cost_cents",
            "substitute_grams",
        ):
            assert type(item[key]) is int
        assert type(item["lots"]) is list
        for use in item["lots"]:
            assert list(use) == ["lot_id", "material_id", "grams"]
            assert type(use["lot_id"]) is str
            assert type(use["material_id"]) is str
            assert type(use["grams"]) is int
    for item in actual["rejections"]:
        assert list(item) == ["order_id", "reason"]
        assert type(item["order_id"]) is str
        assert item["reason"] in {"UNKNOWN_PRODUCT", "NO_MATERIAL", "OVER_BUDGET", "DEFERRED_CAPACITY"}
    for item in actual["materials"]:
        assert list(item) == [
            "lot_id",
            "remaining_grams",
            "prime_cycles",
            "primed_grams",
            "vial_waste_grams",
            "opened_vial_count",
            "opened",
            "first_use_day",
            "last_use_day",
            "status",
        ]
        for key in (
            "remaining_grams",
            "prime_cycles",
            "primed_grams",
            "vial_waste_grams",
            "opened_vial_count",
        ):
            assert type(item[key]) is int
        assert type(item["opened"]) is bool
        if item["opened"]:
            assert type(item["first_use_day"]) is int
            assert type(item["last_use_day"]) is int
        else:
            assert item["first_use_day"] is None
            assert item["last_use_day"] is None
    assert [item["priority"] for item in actual["cohort_audit"]] == ["urgent", "normal", "standby"]
    for item in actual["cohort_audit"]:
        assert list(item) == [
            "priority",
            "eligible_order_count",
            "filled_order_count",
            "filled_units",
            "opened_lot_count",
            "prime_cycle_count",
            "vial_waste_grams",
            "opened_vial_count",
            "nominal_potency_mg",
            "open_decay_loss_mg",
            "uncertainty_deduction_mg",
            "open_uncertainty_growth_mg",
            "mix_loss_mg",
            "robust_potency_mg",
            "robust_margin_mg",
            "total_cost_cents",
            "substitute_grams",
            "expiry_risk",
            "allocation_key",
        ]
        for key, value in item.items():
            if key not in {"priority", "allocation_key"}:
                assert type(value) is int
    assert list(actual["summary"]) == [
        "filled_count",
        "rejected_count",
        "total_cost_cents",
        "total_dispensed_grams",
        "total_prime_cycles",
        "total_prime_grams",
        "total_vial_waste_grams",
        "total_opened_vials",
        "opened_lot_count",
        "total_open_decay_loss_mg",
        "total_open_uncertainty_growth_mg",
        "robust_margin_mg",
        "digest",
    ]
    for key, value in actual["summary"].items():
        if key != "digest":
            assert type(value) is int
    assert HEX64.fullmatch(actual["summary"]["digest"])


def static_case():
    lots = [
        ["L1", "M1", "alpha", "11", "1", "9", "1", "30", "5", "active", "2"],
        ["L1", "M2", "alpha", "10", "0", "30", "0", "40", "10", "active", "1"],
        ["L2", "M2", "alpha", "13", "2", "5", "0", "20", "10", "hold", "1"],
        ["L3", "M1", "alpha", "10", "0", "4", "0", "7", "2", "hold", "3"],
        ["L4", "M1", "alpha", "12", "1", "6", "1", "25", "10", "hold", "2"],
    ]
    formulas = [
        ["P1", "M1", "4", "40", "0", "1", "0", "alpha", "2"],
        ["P1", "M1", "4", "40", "1", "2", "1", "alpha", "2"],
        ["P2", "Z", "3", "30", "1", "1", "0", "-", "0"],
    ]
    orders = [
        ["O1", "P1", "1", "5", "normal", "30"],
        ["O1", "P1", "1", "5", "urgent", "30"],
        ["O2", "P1", "1", "5", "urgent", "2"],
        ["O3", "PX", "1", "5", "urgent", "30"],
        ["O4", "P2", "1", "5", "normal", "30"],
        ["O5", "P1", "1", "5", "urgent", "30"],
        ["O6", "P1", "1", "8", "standby", "30"],
    ]
    events = [["L1", "loss", "0", "2"], ["UNKNOWN", "restock", "0", "3"], ["L4", "release", "0", "0"], ["L4", "loss", "0", "1"]]
    return lots, formulas, orders, events


def make_dynamic_case(seed):
    rng = random.Random(seed)
    prefix = f"D{rng.randrange(10**8, 10**9)}"
    material = f"M{rng.randrange(1000, 9999)}"
    family = f"F{rng.randrange(1000, 9999)}"
    lots = [
        [f"{prefix}A", material, family, str(15 + rng.randrange(3)), "1", "14", "1", "50", "2", "active", "2"],
        [f"{prefix}B", f"X{material}", family, "16", "2", "10", "0", "45", "8", "active", "1"],
        [f"{prefix}C", material, family, "13", "0", "8", "0", "40", "8", "active", "3"],
    ]
    product = f"{prefix}P"
    exact = f"{prefix}E"
    formulas = [
        [product, material, "4", "44", "1", "2", "1", family, "1"],
        [exact, material, "4", "42", "1", "1", "0", "-", "0"],
    ]
    orders = [
        [f"{prefix}U", product, "1", "5", "urgent", "40"],
        [f"{prefix}N", exact, "1", "8", "normal", "40"],
        [f"{prefix}S", product, "1", "9", "standby", "40"],
    ]
    assays = [
        [f"{prefix}A", f"{prefix}G", "1", "30", "1", "1"],
        [f"{prefix}B", f"{prefix}G", "0", "30", "0", "0"],
        [f"{prefix}C", f"{prefix}H", "0", "30", "0", "1"],
    ]
    packaging = [
        [f"{prefix}A", "5", "3", "1", "0"],
        [f"{prefix}B", "2", "2", "0", "1"],
        [f"{prefix}C", "4", "2", "0", "0"],
    ]
    events = [[f"{prefix}A", "loss", "4", str(rng.randrange(0, 2))], [f"{prefix}C", "restock", "7", str(rng.randrange(0, 2))]]
    return prefix, lots, formulas, orders, events, assays, packaging


def test_static_contract_exact_schema_dedup_events_and_rejections(tmp_path):
    """Verify the complete v6 schema, deduplication, events, rejection priority, vial fields, and canonical digest."""
    lots, formulas, orders, events = static_case()
    root = tmp_path / "static"
    out = tmp_path / "static.json"
    write_case(root, lots, formulas, orders, events)
    actual, _ = run_case(root, out)
    assert_exact_report(actual, expected_report(root, lots, formulas, orders, events))
    reasons = {item["reason"] for item in actual["rejections"]}
    assert {"UNKNOWN_PRODUCT", "NO_MATERIAL", "OVER_BUDGET", "DEFERRED_CAPACITY"} <= reasons
    assert any(item["uncertainty_deduction_mg"] > 0 for item in actual["orders"])
    assert any(item["prime_cycles"] > 0 for item in actual["materials"])


def test_dynamic_variant_defeats_hardcoded_solution(tmp_path):
    """Generate two unseen assay and packaging instances and require fresh identifiers, exact results, and distinct digests."""
    lots, formulas, orders, events = static_case()
    baseline_root = tmp_path / "baseline"
    write_case(baseline_root, lots, formulas, orders, events)
    baseline, _ = run_case(baseline_root, tmp_path / "baseline.json")
    seen_input = {baseline["input_digest"]}
    seen_summary = {baseline["summary"]["digest"]}
    for seed in (81473, 99217):
        prefix, lots, formulas, orders, events, assays, packaging = make_dynamic_case(seed)
        root = tmp_path / prefix
        out = tmp_path / f"{prefix}.json"
        write_case(root, lots, formulas, orders, events, assays=assays, packaging=packaging)
        actual, _ = run_case(root, out)
        assert_exact_report(actual, expected_report(root, lots, formulas, orders, events))
        emitted = {item["order_id"] for item in actual["orders"]} | {item["order_id"] for item in actual["rejections"]}
        assert emitted == {row[0] for row in orders}
        assert all(identifier.startswith(prefix) for identifier in emitted)
        assert actual["input_digest"] not in seen_input
        assert actual["summary"]["digest"] not in seen_summary
        assert actual["summary"]["total_opened_vials"] > 0
        seen_input.add(actual["input_digest"])
        seen_summary.add(actual["summary"]["digest"])


def test_time_indexed_hold_release_changes_order_feasibility_and_material_status(tmp_path):
    """Replay same-day release before eligibility and later hold into filled orders, rejection reasons, final status, and digest."""
    lots = [["T", "M", "f", "10", "0", "4", "0", "20", "5", "hold", "1"]]
    formulas = [["P", "M", "4", "40", "0", "1", "0", "-", "0"]]
    orders = [["EARLY", "P", "1", "1", "urgent", "10"], ["LATE", "P", "1", "3", "normal", "10"]]
    events = [["T", "release", "3", "0"], ["T", "hold", "5", "0"]]
    assays = [["T", "G", "0", "20", "0", "0"]]
    packaging = [["T", "4", "1", "0", "0"]]
    root = tmp_path / "temporal-release"
    write_case(root, lots, formulas, orders, events, assays=assays, packaging=packaging)
    actual, _ = run_case(root, tmp_path / "temporal-release.json")
    assert_exact_report(actual, expected_report(root, lots, formulas, orders, events))
    assert [item["order_id"] for item in actual["orders"]] == ["LATE"]
    assert {item["order_id"]: item["reason"] for item in actual["rejections"]} == {"EARLY": "NO_MATERIAL"}
    assert actual["materials"][0]["status"] == "hold"
    assert actual["materials"][0]["remaining_grams"] == 0
    no_hold_root = tmp_path / "temporal-release-nohold"
    write_case(no_hold_root, lots, formulas, orders, events[:1], assays=assays, packaging=packaging)
    no_hold, _ = run_case(no_hold_root, tmp_path / "temporal-release-nohold.json")
    assert_exact_report(no_hold, expected_report(no_hold_root, lots, formulas, orders, events[:1]))
    assert no_hold["materials"][0]["status"] == "active"
    assert actual["summary"]["digest"] != no_hold["summary"]["digest"]


def test_future_loss_does_not_remove_earlier_opening_but_replays_final_inventory(tmp_path):
    """Ensure future loss events do not erase an earlier feasible opening while final material inventory and digest still include them."""
    lots = [["F", "M", "f", "11", "0", "4", "0", "30", "5", "active", "1"]]
    formulas = [["P", "M", "4", "44", "0", "1", "0", "-", "0"]]
    orders = [["O", "P", "1", "1", "urgent", "10"]]
    assays = [["F", "G", "0", "20", "0", "0"]]
    packaging = [["F", "4", "1", "0", "0"]]
    eventful = [["F", "loss", "3", "4"]]
    root = tmp_path / "future-loss"
    write_case(root, lots, formulas, orders, eventful, assays=assays, packaging=packaging)
    actual, _ = run_case(root, tmp_path / "future-loss.json")
    assert_exact_report(actual, expected_report(root, lots, formulas, orders, eventful))
    assert [item["order_id"] for item in actual["orders"]] == ["O"]
    assert actual["materials"][0]["remaining_grams"] == 0
    loss_now_root = tmp_path / "loss-now"
    write_case(loss_now_root, lots, formulas, orders, [["F", "loss", "0", "4"]], assays=assays, packaging=packaging)
    loss_now, _ = run_case(loss_now_root, tmp_path / "loss-now.json")
    assert_exact_report(loss_now, expected_report(loss_now_root, lots, formulas, orders, [["F", "loss", "0", "4"]]))
    assert loss_now["orders"] == []
    assert loss_now["rejections"] == [{"order_id": "O", "reason": "NO_MATERIAL"}]
    assert actual["input_digest"] != loss_now["input_digest"]
    assert actual["summary"]["digest"] != loss_now["summary"]["digest"]


def test_open_vial_decay_recomputes_cohort_feasibility_and_forces_substitute(tmp_path):
    """Require episode-start-dependent potency decay to invalidate a shared-lot cohort plan and force a substitute allocation."""
    lots = [
        ["A", "M", "core", "10", "0", "8", "0", "30", "5", "active", "1"],
        ["B", "X", "flex", "10", "0", "4", "0", "30", "5", "active", "4"],
    ]
    formulas = [
        ["ONLY", "M", "4", "36", "0", "1", "0", "-", "0"],
        ["FLEX", "M", "4", "36", "0", "1", "0", "flex", "0"],
    ]
    orders = [["U", "ONLY", "1", "1", "urgent", "20"], ["N", "FLEX", "1", "3", "normal", "20"]]
    assays = [["A", "GA", "0", "20", "0", "0"], ["B", "GB", "0", "20", "0", "0"]]
    packaging = [["A", "4", "1", "2", "0"], ["B", "4", "1", "0", "0"]]
    root = tmp_path / "open-decay"
    write_case(root, lots, formulas, orders, [], assays=assays, packaging=packaging)
    actual, _ = run_case(root, tmp_path / "open-decay.json")
    assert_exact_report(actual, expected_report(root, lots, formulas, orders, []))
    uses = {item["order_id"]: item["lots"][0]["lot_id"] for item in actual["orders"]}
    assert uses == {"U": "A", "N": "B"}
    no_decay_root = tmp_path / "open-decay-zero"
    no_decay_packaging = [["A", "4", "1", "0", "0"], ["B", "4", "1", "0", "0"]]
    write_case(no_decay_root, lots, formulas, orders, [], assays=assays, packaging=no_decay_packaging)
    no_decay, _ = run_case(no_decay_root, tmp_path / "open-decay-zero.json")
    assert_exact_report(no_decay, expected_report(no_decay_root, lots, formulas, orders, []))
    assert {item["order_id"]: item["lots"][0]["lot_id"] for item in no_decay["orders"]} == {"U": "A", "N": "A"}
    assert actual["input_digest"] != no_decay["input_digest"]
    assert actual["summary"]["digest"] != no_decay["summary"]["digest"]


def test_open_age_decay_and_uncertainty_growth_bind_episode_partition_to_report(tmp_path):
    """Recompute potency and correlated uncertainty from episode open age and bind the changed metrics, cycles, and digest."""
    formulas = [["P", "M", "4", "16", "1", "1", "0", "-", "0"]]
    orders = [["O1", "P", "1", "1", "urgent", "20"], ["O2", "P", "1", "3", "normal", "20"]]
    assays = [["A", "G", "0", "20", "0", "0"]]
    packaging = [["A", "4", "2", "1", "2"]]
    long_lots = [["A", "M", "f", "10", "0", "8", "0", "30", "3", "active", "1"]]
    long_root = tmp_path / "open-age-shared"
    write_case(long_root, long_lots, formulas, orders, [], assays=assays, packaging=packaging)
    shared, _ = run_case(long_root, tmp_path / "open-age-shared.json")
    assert_exact_report(shared, expected_report(long_root, long_lots, formulas, orders, []))
    second = next(item for item in shared["orders"] if item["order_id"] == "O2")
    assert second["nominal_potency_mg"] == 32
    assert second["open_decay_loss_mg"] == 8
    assert second["uncertainty_deduction_mg"] == 16
    assert second["open_uncertainty_growth_mg"] == 16
    assert second["robust_potency_mg"] == 16
    assert shared["summary"]["total_open_decay_loss_mg"] == 8
    assert shared["summary"]["total_open_uncertainty_growth_mg"] == 16
    short_lots = [["A", "M", "f", "10", "0", "8", "0", "30", "1", "active", "1"]]
    short_root = tmp_path / "open-age-split"
    write_case(short_root, short_lots, formulas, orders, [], assays=assays, packaging=packaging)
    split, _ = run_case(short_root, tmp_path / "open-age-split.json")
    assert_exact_report(split, expected_report(short_root, short_lots, formulas, orders, []))
    split_second = next(item for item in split["orders"] if item["order_id"] == "O2")
    assert split_second["open_decay_loss_mg"] == 0
    assert split_second["open_uncertainty_growth_mg"] == 0
    assert shared["summary"]["total_prime_cycles"] == 1
    assert split["summary"]["total_prime_cycles"] == 2
    assert shared["summary"]["digest"] != split["summary"]["digest"]


def test_assay_decay_and_correlated_uncertainty_change_selection_and_digest(tmp_path):
    """Couple assay age, potency decay, uncertainty growth, and same-group aggregation so lot-wise shortcuts select incorrectly."""
    lots = [
        ["A", "M", "f", "18", "1", "4", "0", "30", "10", "active", "1"],
        ["B", "M", "f", "14", "2", "4", "0", "30", "10", "active", "1"],
        ["C", "M", "f", "14", "2", "4", "0", "30", "10", "active", "2"],
    ]
    formulas = [["P", "M", "8", "88", "1", "2", "0", "-", "0"]]
    orders = [["O", "P", "1", "5", "urgent", "20"]]
    assays = [
        ["A", "GA", "0", "20", "2", "1"],
        ["B", "GB", "0", "20", "0", "0"],
        ["C", "GB", "0", "20", "0", "0"],
    ]
    packaging = [["A", "1", "1", "0", "0"], ["B", "1", "1", "0", "0"], ["C", "1", "1", "0", "0"]]
    root = tmp_path / "assay"
    write_case(root, lots, formulas, orders, [], assays=assays, packaging=packaging)
    actual, _ = run_case(root, tmp_path / "assay.json")
    assert_exact_report(actual, expected_report(root, lots, formulas, orders, []))
    assert actual["orders"][0]["lots"] == [
        {"lot_id": "B", "material_id": "M", "grams": 4},
        {"lot_id": "C", "material_id": "M", "grams": 4},
    ]
    assert actual["orders"][0]["nominal_potency_mg"] == 112
    assert actual["orders"][0]["uncertainty_deduction_mg"] == 16
    changed_root = tmp_path / "assay-changed"
    changed = [row.copy() for row in assays]
    changed[2][1] = "GC"
    write_case(changed_root, lots, formulas, orders, [], assays=changed, packaging=packaging)
    changed_report, _ = run_case(changed_root, tmp_path / "assay-changed.json")
    assert changed_report["input_digest"] != actual["input_digest"]
    assert changed_report["summary"]["digest"] != actual["summary"]["digest"]
    assert changed_report["orders"][0]["uncertainty_deduction_mg"] == 8


def test_reprime_cycles_and_vial_rounding_share_same_day_inventory(tmp_path):
    """Require same-day draws to share one episode while a later draw starts a second rounded-vial priming cycle."""
    lots = [["A", "M", "f", "20", "0", "10", "1", "30", "2", "active", "1"]]
    formulas = [
        ["SMALL", "M", "2", "35", "0", "1", "0", "-", "0"],
        ["LARGE", "M", "4", "70", "0", "1", "0", "-", "0"],
    ]
    orders = [
        ["U1", "SMALL", "1", "1", "urgent", "20"],
        ["U2", "SMALL", "1", "1", "urgent", "20"],
        ["N1", "LARGE", "1", "4", "normal", "20"],
    ]
    assays = [["A", "G", "0", "20", "0", "0"]]
    packaging = [["A", "5", "2", "0", "0"]]
    root = tmp_path / "episodes"
    write_case(root, lots, formulas, orders, [], assays=assays, packaging=packaging)
    actual, _ = run_case(root, tmp_path / "episodes.json")
    assert_exact_report(actual, expected_report(root, lots, formulas, orders, []))
    assert [item["order_id"] for item in actual["orders"]] == ["U1", "U2", "N1"]
    material = actual["materials"][0]
    assert material == {
        "lot_id": "A",
        "remaining_grams": 0,
        "prime_cycles": 2,
        "primed_grams": 2,
        "vial_waste_grams": 0,
        "opened_vial_count": 2,
        "opened": True,
        "first_use_day": 1,
        "last_use_day": 4,
        "status": "active",
    }


def test_max_open_cycles_forces_cross_priority_substitute_and_digest(tmp_path):
    """Use the episode limit to force an urgent flexible order onto a substitute so a later normal exact order remains fillable."""
    lots = [
        ["A", "M", "core", "20", "0", "8", "0", "30", "1", "active", "1"],
        ["B", "X", "flex", "20", "0", "4", "0", "30", "10", "active", "3"],
    ]
    formulas = [
        ["FLEX", "M", "4", "70", "0", "1", "0", "flex", "0"],
        ["ONLY", "M", "4", "70", "0", "1", "0", "-", "0"],
    ]
    orders = [["U", "FLEX", "1", "1", "urgent", "20"], ["N", "ONLY", "1", "4", "normal", "20"]]
    assays = [["A", "GA", "0", "20", "0", "0"], ["B", "GB", "0", "20", "0", "0"]]
    packaging = [["A", "4", "1", "0", "0"], ["B", "4", "1", "0", "0"]]
    root = tmp_path / "cycle-limit"
    write_case(root, lots, formulas, orders, [], assays=assays, packaging=packaging)
    actual, _ = run_case(root, tmp_path / "cycle-limit.json")
    assert_exact_report(actual, expected_report(root, lots, formulas, orders, []))
    uses = {item["order_id"]: item["lots"][0]["lot_id"] for item in actual["orders"]}
    assert uses == {"U": "B", "N": "A"}
    assert actual["summary"]["total_prime_cycles"] == 2
    assert actual["cohort_audit"][1]["filled_order_count"] == 1


def test_metadata_last_row_validity_boundaries_and_missing_metadata_fail_closed(tmp_path):
    """Verify last-row metadata wins, assay interval endpoints are inclusive, and missing surviving-lot metadata removes stale output."""
    lots = [["A", "M", "f", "10", "0", "8", "0", "20", "5", "active", "1"]]
    formulas = [["P", "M", "4", "40", "0", "1", "0", "-", "0"]]
    orders = [["O1", "P", "1", "2", "urgent", "10"], ["O2", "P", "1", "8", "normal", "10"]]
    assays = [["A", "OLD", "3", "3", "9", "9"], ["A", "NEW", "2", "8", "0", "0"], ["UNKNOWN", "X", "0", "1", "0", "0"]]
    packaging = [["A", "9", "1", "9", "9"], ["A", "4", "2", "0", "0"], ["UNKNOWN", "1", "1", "0", "0"]]
    root = tmp_path / "metadata"
    write_case(root, lots, formulas, orders, [], assays=assays, packaging=packaging)
    actual, _ = run_case(root, tmp_path / "metadata.json")
    assert_exact_report(actual, expected_report(root, lots, formulas, orders, []))
    assert [item["order_id"] for item in actual["orders"]] == ["O1", "O2"]
    broken = tmp_path / "missing-meta"
    write_case(broken, lots, formulas, orders, [], assays=[], packaging=packaging)
    stale = tmp_path / "missing-meta.json"
    stale.write_text("stale")
    proc = run_binary_isolated(root=broken, out=stale, stale_output=b"stale")
    assert proc.returncode != 0
    assert not stale.exists()


def test_priming_and_open_stability_require_joint_global_search(tmp_path):
    """Require non-greedy global choices when one-cycle capacity and stability reserve an exact lot for another order."""
    scenarios = [
        ("prime", "8", "1", "10", "5", "5"),
        ("stability", "9", "1", "0", "5", "6"),
    ]
    for name, grams, prime, stability, flex_day, only_day in scenarios:
        lots = [
            ["A", "M", "core", "10", "0", grams, prime, "30", stability, "active", "1"],
            ["B", "X", "flex", "10", "0", "4", "0", "30", "20", "active", "2"],
        ]
        formulas = [
            ["FLEX", "M", "4", "40", "0", "1", "0", "flex", "0"],
            ["ONLY", "M", "4", "40", "0", "1", "0", "-", "0"],
        ]
        orders = [["A_FLEX", "FLEX", "1", flex_day, "urgent", "20"], ["Z_ONLY", "ONLY", "1", only_day, "urgent", "20"]]
        packaging = [["A", "1", "1", "0", "0"], ["B", "1", "1", "0", "0"]]
        root = tmp_path / name
        out = tmp_path / f"{name}.json"
        write_case(root, lots, formulas, orders, [], packaging=packaging)
        actual, _ = run_case(root, out)
        assert_exact_report(actual, expected_report(root, lots, formulas, orders, []))
        uses = {item["order_id"]: item["lots"][0]["lot_id"] for item in actual["orders"]}
        assert uses == {"A_FLEX": "B", "Z_ONLY": "A"}


def test_cross_priority_global_plan_beats_sequential_greedy(tmp_path):
    """Preserve normal-order coverage after an urgent tie by assigning the urgent order a costlier substitute."""
    lots = [
        ["S", "M", "core", "10", "0", "4", "0", "30", "20", "active", "1"],
        ["X", "Q", "flex", "10", "0", "4", "0", "30", "20", "active", "3"],
    ]
    formulas = [["FLEX", "M", "4", "40", "0", "1", "0", "flex", "0"], ["ONLY", "M", "4", "40", "0", "1", "0", "-", "0"]]
    orders = [["U_FLEX", "FLEX", "1", "5", "urgent", "20"], ["N_ONLY", "ONLY", "1", "5", "normal", "20"]]
    root = tmp_path / "cross-priority"
    write_case(root, lots, formulas, orders, [])
    actual, _ = run_case(root, tmp_path / "cross-priority.json")
    assert_exact_report(actual, expected_report(root, lots, formulas, orders, []))
    uses = {item["order_id"]: item["lots"][0]["lot_id"] for item in actual["orders"]}
    assert uses == {"U_FLEX": "X", "N_ONLY": "S"}


def test_global_objective_prefers_filled_units_after_order_count(tmp_path):
    """Choose the higher-unit urgent order when capacity permits only one order and filled counts tie."""
    lots = [["L", "M", "f", "10", "0", "8", "0", "20", "10", "active", "1"]]
    formulas = [["P", "M", "4", "40", "0", "1", "0", "-", "0"]]
    orders = [
        ["A_SMALL", "P", "1", "5", "urgent", "100"],
        ["Z_LARGE", "P", "2", "5", "urgent", "100"],
    ]
    packaging = [["L", "1", "1", "0", "0"]]
    root = tmp_path / "filled-units"
    write_case(root, lots, formulas, orders, [], packaging=packaging)
    actual, _ = run_case(root, tmp_path / "filled-units.json")
    assert_exact_report(actual, expected_report(root, lots, formulas, orders, []))
    assert [item["order_id"] for item in actual["orders"]] == ["Z_LARGE"]
    assert actual["rejections"] == [{"order_id": "A_SMALL", "reason": "DEFERRED_CAPACITY"}]
    urgent = actual["cohort_audit"][0]
    assert urgent["filled_order_count"] == 1
    assert urgent["filled_units"] == 2


def test_global_objective_prefers_fewer_opened_lots_before_cost(tmp_path):
    """Verify opened-lot count precedes a cheaper split allocation after all priority coverage ties."""
    lots = [
        ["A", "M", "f", "10", "0", "2", "0", "20", "10", "active", "1"],
        ["B", "M", "f", "10", "0", "2", "0", "20", "10", "active", "1"],
        ["E", "M", "f", "10", "0", "4", "0", "20", "10", "active", "5"],
    ]
    formulas = [["P", "M", "4", "40", "0", "2", "0", "-", "0"]]
    orders = [["O", "P", "1", "5", "urgent", "30"]]
    root = tmp_path / "opened"
    write_case(root, lots, formulas, orders, [])
    actual, _ = run_case(root, tmp_path / "opened.json")
    assert_exact_report(actual, expected_report(root, lots, formulas, orders, []))
    assert actual["orders"][0]["lots"] == [{"lot_id": "E", "material_id": "M", "grams": 4}]
    assert actual["summary"]["opened_lot_count"] == 1


def test_vial_waste_precedes_dispensed_cost_after_cycle_ties(tmp_path):
    """Verify the cohort objective selects zero vial waste before a cheaper dispensed allocation when opened lots and cycles tie."""
    lots = [
        ["A", "M", "f", "10", "0", "5", "0", "20", "10", "active", "1"],
        ["B", "M", "f", "10", "0", "4", "0", "20", "10", "active", "3"],
    ]
    formulas = [["P", "M", "4", "40", "0", "1", "0", "-", "0"]]
    orders = [["O", "P", "1", "5", "urgent", "20"]]
    packaging = [["A", "5", "1", "0", "0"], ["B", "4", "1", "0", "0"]]
    root = tmp_path / "waste"
    write_case(root, lots, formulas, orders, [], packaging=packaging)
    actual, _ = run_case(root, tmp_path / "waste.json")
    assert_exact_report(actual, expected_report(root, lots, formulas, orders, []))
    assert actual["orders"][0]["lots"] == [{"lot_id": "B", "material_id": "M", "grams": 4}]
    assert actual["summary"]["total_vial_waste_grams"] == 0
    assert actual["summary"]["total_cost_cents"] == 12


def test_large_quantity_max_lots_and_mix_loss_are_generalized(tmp_path):
    """Use a large draw where max-lot pruning and non-additive mixing loss are required for a timely exact result."""
    lots = [[f"L{index:02d}", "M", "f", "10", "0", "50", "0", "40", "20", "active", str(index + 1)] for index in range(12)]
    formulas = [["P", "M", "90", "880", "0", "2", "20", "-", "0"]]
    orders = [["O", "P", "1", "5", "urgent", "10000"]]
    packaging = [[row[0], "10", "1", "0", "0"] for row in lots]
    root = tmp_path / "large"
    write_case(root, lots, formulas, orders, [], packaging=packaging)
    actual, _ = run_case(root, tmp_path / "large.json")
    assert_exact_report(actual, expected_report(root, lots, formulas, orders, []))
    assert actual["orders"][0]["lots"] == [
        {"lot_id": "L00", "material_id": "M", "grams": 50},
        {"lot_id": "L01", "material_id": "M", "grams": 40},
    ]
    assert actual["orders"][0]["mix_loss_mg"] == 20


def test_exact_workload_boundaries_remain_valid_and_deterministic(tmp_path):
    """Accept the documented row, lot, formula, order, required-gram, and max-lot limits without off-by-one rejection."""
    lots = [
        [f"A{index}", "M", "f", "10", "0", "32", "0", "40", "20", "active", "1"]
        for index in range(3)
    ] + [
        [f"H{index}", "M", "f", "10", "0", "32", "0", "40", "20", "hold", "1"]
        for index in range(9)
    ]
    formulas = [["P", "M", "96", "940", "0", "3", "10", "-", "0"]] + [
        [f"UNUSED{index:02d}", "M", "1", "0", "0", "1", "0", "-", "0"]
        for index in range(15)
    ]
    orders = [["O0", "P", "1", "5", "urgent", "1000"]] + [
        [f"O{index}", f"MISSING{index}", "1", "5", "standby", "0"]
        for index in range(1, 8)
    ]
    events = [[f"UNKNOWN{index:03d}", "loss", "0", "0"] for index in range(128)]
    root = tmp_path / "exact-limits"
    write_case(root, lots, formulas, orders, events)
    actual, first_raw = run_case(root, tmp_path / "exact-limits.json")
    assert_exact_report(actual, expected_report(root, lots, formulas, orders, events))
    assert actual["orders"][0]["grams"] == 96
    assert len(actual["orders"][0]["lots"]) == 3
    assert actual["orders"][0]["mix_loss_mg"] == 20
    repeated, second_raw = run_case(root, tmp_path / "exact-limits-repeat.json")
    assert repeated == actual
    assert second_raw == first_raw


def test_raw_digest_supports_crlf_and_whitespace_records(tmp_path):
    """Bind digests to exact six-file LF or CRLF bytes while keeping whitespace-only records semantically inert."""
    lots = [["R1", "M", "f", "10", "1", "5", "1", "20", "5", "active", "2"]]
    formulas = [["P", "M", "4", "35", "1", "1", "0", "-", "0"]]
    orders = [["O", "P", "1", "5", "urgent", "20"]]
    events = [["R1", "loss", "0", "0"]]
    assays = [["R1", "G", "0", "20", "0", "0"]]
    packaging = [["R1", "5", "1", "0", "0"]]
    first_root = tmp_path / "lf"
    second_root = tmp_path / "crlf"
    write_case(first_root, lots, formulas, orders, events, assays=assays, packaging=packaging, line_ending="\n")
    write_case(
        second_root,
        lots,
        formulas,
        orders,
        events,
        assays=assays,
        packaging=packaging,
        line_ending="\r\n",
        blank_after={name: {0} for name in HEADERS},
    )
    first, _ = run_case(first_root, tmp_path / "lf.json")
    second, _ = run_case(second_root, tmp_path / "crlf.json")
    assert_exact_report(first, expected_report(first_root, lots, formulas, orders, events))
    assert_exact_report(second, expected_report(second_root, lots, formulas, orders, events))
    assert first["input_digest"] != second["input_digest"]
    assert first["summary"]["digest"] != second["summary"]["digest"]
    first["input_digest"] = second["input_digest"] = ""
    first["summary"]["digest"] = second["summary"]["digest"] = ""
    assert first == second


def test_invalid_inputs_remove_stale_output_and_return_nonzero(tmp_path):
    """Reject malformed data, unsafe identifiers, bounded-workload violations, and absent files while removing stale output."""
    valid_lots = [["X", "M", "f", "10", "0", "4", "0", "20", "5", "active", "1"]]
    valid_formulas = [["P", "M", "4", "40", "0", "1", "0", "-", "0"]]
    valid_orders = [["O", "P", "1", "5", "urgent", "10"]]
    valid_assays = [["X", "G", "0", "20", "0", "0"]]
    valid_packaging = [["X", "1", "1", "0", "0"]]

    def fail_case(name, lots, formulas, orders, events, assays=None, packaging=None, mutate=None):
        root = tmp_path / name
        out = tmp_path / f"{name}.json"
        write_case(
            root,
            lots,
            formulas,
            orders,
            events,
            assays=valid_assays if assays is None else assays,
            packaging=valid_packaging if packaging is None else packaging,
        )
        if mutate:
            mutate(root)
        out.write_text("stale")
        proc = run_binary_isolated(root=root, out=out, stale_output=b"stale")
        assert proc.returncode != 0
        assert not out.exists()

    fail_case("event", valid_lots, valid_formulas, valid_orders, [["X", "warp", "0", "0"]])
    fail_case("integer", [["X", "M", "f", "+1", "0", "4", "0", "20", "5", "active", "1"]], valid_formulas, valid_orders, [])
    fail_case("overflow", [["X", "M", "f", str(2**63), "0", "4", "0", "20", "5", "active", "1"]], valid_formulas, valid_orders, [])
    fail_case("status", [["X", "M", "f", "10", "0", "4", "0", "20", "5", "expired", "1"]], valid_formulas, valid_orders, [])
    fail_case("priority", valid_lots, valid_formulas, [["O", "P", "1", "5", "low", "10"]], [])
    fail_case("zero-vial", valid_lots, valid_formulas, valid_orders, [], packaging=[["X", "0", "1", "0", "0"]])
    fail_case("zero-cycles", valid_lots, valid_formulas, valid_orders, [], packaging=[["X", "1", "0", "0", "0"]])
    fail_case("bad-open-rate", valid_lots, valid_formulas, valid_orders, [], packaging=[["X", "1", "1", "+1", "0"]])
    fail_case("bad-interval", valid_lots, valid_formulas, valid_orders, [], assays=[["X", "G", "9", "8", "0", "0"]])
    fail_case("missing-assay", valid_lots, valid_formulas, valid_orders, [], assays=[])
    fail_case("header", valid_lots, valid_formulas, valid_orders, [], mutate=lambda root: (root / "orders.csv").write_text("bad,header\n"))
    fail_case("width", valid_lots, valid_formulas, valid_orders, [], mutate=lambda root: (root / "events.csv").write_text("lot_id,kind,day,grams\nX,loss,0\n"))
    fail_case("missing", valid_lots, valid_formulas, valid_orders, [], mutate=lambda root: (root / "packaging.csv").unlink())
    fail_case(
        "identifier-delimiter",
        [["bad:id", "M", "f", "10", "0", "4", "0", "20", "5", "active", "1"]],
        valid_formulas,
        valid_orders,
        [],
        assays=[["bad:id", "G", "0", "20", "0", "0"]],
        packaging=[["bad:id", "1", "1", "0", "0"]],
    )
    fail_case(
        "identifier-length",
        [["X" * 65, "M", "f", "10", "0", "4", "0", "20", "5", "active", "1"]],
        valid_formulas,
        valid_orders,
        [],
        assays=[["X" * 65, "G", "0", "20", "0", "0"]],
        packaging=[["X" * 65, "1", "1", "0", "0"]],
    )
    fail_case("row-limit", valid_lots, valid_formulas, valid_orders, [[f"U{index}", "loss", "0"] for index in range(129)])
    many_lots = [[f"L{index:02d}", "M", "f", "10", "0", "4", "0", "20", "5", "active", "1"] for index in range(13)]
    fail_case(
        "lot-limit",
        many_lots,
        valid_formulas,
        valid_orders,
        [],
        assays=default_assays(many_lots),
        packaging=default_packaging(many_lots),
    )
    many_formulas = [[f"P{index:02d}", "M", "4", "40", "0", "1", "0", "-", "0"] for index in range(17)]
    fail_case("formula-limit", valid_lots, many_formulas, [["O", "P00", "1", "5", "urgent", "10"]], [])
    many_orders = [[f"O{index:02d}", "P", "1", "5", "urgent", "10"] for index in range(9)]
    fail_case("order-limit", valid_lots, valid_formulas, many_orders, [])
    fail_case("required-grams-limit", valid_lots, [["P", "M", "97", "40", "0", "1", "0", "-", "0"]], valid_orders, [])
    fail_case("max-lots-limit", valid_lots, [["P", "M", "4", "40", "0", "4", "0", "-", "0"]], valid_orders, [])
    plan_lots = [[f"A{index:02d}", "M", "f", "1", "0", "96", "0", "20", "5", "active", "1"] for index in range(12)]
    fail_case(
        "local-plan-limit",
        plan_lots,
        [["P", "M", "96", "0", "0", "2", "0", "-", "0"]],
        valid_orders,
        [],
        assays=default_assays(plan_lots),
        packaging=default_packaging(plan_lots),
    )
    cohort_lots = [[f"C{index}", "M", "f", "1", "0", "8", "0", "20", "5", "active", "1"] for index in range(6)]
    cohort_orders = [[f"Q{index}", "P", "1", "5", "urgent", "10"] for index in range(8)]
    fail_case(
        "cohort-plan-limit",
        cohort_lots,
        [["P", "M", "1", "0", "0", "1", "0", "-", "0"]],
        cohort_orders,
        [],
        assays=default_assays(cohort_lots),
        packaging=default_packaging(cohort_lots),
    )
    extra_out = tmp_path / "extra.json"
    extra_out.write_text("stale")
    proc = run_binary_isolated(
        out=extra_out,
        arguments=["/input", "/output/report.json", "extra"],
        stale_output=b"stale",
    )
    assert proc.returncode != 0
    assert not extra_out.exists()
    assert run_binary_isolated(arguments=[]).returncode != 0
    assert run_binary_isolated(root=tmp_path / "event", arguments=["/input"]).returncode != 0


def test_single_build_repeat_and_minimal_root_are_byte_identical_go_outputs(tmp_path):
    """Reuse one verifier-built Go executable and require byte-identical reports from separate interpreter-free isolated roots."""
    _, lots, formulas, orders, events, assays, packaging = make_dynamic_case(77123)
    root = tmp_path / "repeat"
    write_case(root, lots, formulas, orders, events, assays=assays, packaging=packaging)
    first, first_raw = run_case(root, tmp_path / "first.json")
    second, second_raw = run_case(root, tmp_path / "second.json")
    assert first_raw == second_raw
    assert first == second == expected_report(root, lots, formulas, orders, events)
