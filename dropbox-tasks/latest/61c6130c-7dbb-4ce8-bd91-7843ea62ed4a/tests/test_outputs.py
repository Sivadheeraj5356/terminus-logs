import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
ENV_ROOT = APP_ROOT / "environment"
DATA_ROOT = ENV_ROOT / "r01"
VISIBLE_OUT = APP_ROOT / "output" / "moderation_ledger.json"

TOXIC_TERMS = {
    "toxic",
    "toxico",
    "toxica",
    "basura",
    "insult",
    "ganda",
    "dhamki",
    "threat",
    "samm",
    "amenaza",
    "sasa",
}
SUPPORT_TERMS = {"kind", "calm", "neutral", "support", "please", "stay", "review", "training"}
DIGIT_MAP = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t"})


@pytest.fixture(scope="session")
def built_tool(tmp_path_factory):
    build_dir = tmp_path_factory.mktemp("build")
    subprocess.run(["test", "-d", "/app/environment"], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    subprocess.run(["cmake", "-S", str(ENV_ROOT), "-B", str(build_dir)], check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    subprocess.run(["cmake", "--build", str(build_dir)], check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return build_dir / "r01_score"


def run_report(exe, data_root=DATA_ROOT, out_path=None, seed=314159):
    out_path = Path(out_path or VISIBLE_OUT)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(exe), "--data-root", str(data_root), "--seed", str(seed), "--out", str(out_path)], check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return json.loads(out_path.read_text()), out_path


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def normalize_text(text):
    lowered = text.lower().translate(DIGIT_MAP)
    return "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in lowered)


def trace_digest(rows):
    value = 17
    joined = "\n".join(rows)
    for byte in joined.encode():
        value = (value * 131 + byte) % 1000000007
    return f"{value:08x}"


def expected_report(data_root=DATA_ROOT, seed=314159):
    data_root = Path(data_root)
    rows = load_jsonl(data_root / "inputs" / "i1.jsonl") + load_jsonl(data_root / "inputs" / "i2.jsonl")
    comp_data = json.loads((data_root / "inputs" / "p1.json").read_text())
    node_data = json.loads((data_root / "inputs" / "p2.json").read_text())

    sig_by_canon = {item["package"]: item["hash"] for item in comp_data["components"]}
    comp_by_canon = {item["package"]: item["name"] for item in comp_data["components"]}
    alias_to_canon = {item["package"]: item["canonical"] for item in node_data["nodes"]}
    aliases_by_canon = {}
    for item in node_data["nodes"]:
        aliases_by_canon.setdefault(item["canonical"], []).append(item["package"])

    split_counts = {"train": 0, "eval": 0, "challenge": 0}
    records = []
    for row in rows:
        split_counts[row["split"]] += 1
        if row["split"] == "train":
            continue
        tokens = normalize_text(row["text"]).split()
        hot = sum(1 for token in tokens if token in TOXIC_TERMS)
        cool = sum(1 for token in tokens if token in SUPPORT_TERMS)
        margin = 3 * hot - 2 * cool
        label = "block" if margin >= 3 else ("review" if margin > 0 else "allow")
        canon = alias_to_canon[row["package"]]
        records.append(
            {
                "case_id": row["case_id"],
                "prompt_id": row["prompt_id"],
                "split": row["split"],
                "lang": row["lang"],
                "canonical_package": canon,
                "component": comp_by_canon[canon],
                "component_hash": sig_by_canon[canon],
                "margin": margin,
                "label": label,
            }
        )
    records.sort(key=lambda item: item["case_id"])

    grouped = {}
    for record in records:
        grouped.setdefault((record["prompt_id"], record["canonical_package"]), []).append(record)
    groups = []
    for (prompt_id, canon), items in grouped.items():
        mean_margin_milli = int(sum(item["margin"] for item in items) * 1000 / len(items) + 0.5)
        groups.append(
            {
                "prompt_id": prompt_id,
                "canonical_package": canon,
                "component": comp_by_canon[canon],
                "component_hash": sig_by_canon[canon],
                "variant_count": len(items),
                "mean_margin_milli": mean_margin_milli,
                "deficit_count": sum(1 for item in items if item["label"] != "block"),
                "languages": sorted({item["lang"] for item in items}),
                "case_ids": sorted(item["case_id"] for item in items),
            }
        )
    groups.sort(key=lambda item: (item["prompt_id"], item["canonical_package"]))

    nodes = []
    for canon in sorted(aliases_by_canon):
        nodes.append(
            {
                "canonical_package": canon,
                "component": comp_by_canon[canon],
                "component_hash": sig_by_canon[canon],
                "aliases": sorted(aliases_by_canon[canon]),
            }
        )

    trace_rows = sorted(
        "|".join(
            [
                item["case_id"],
                item["prompt_id"],
                item["split"],
                item["lang"],
                item["canonical_package"],
                str(item["margin"]),
                item["label"],
            ]
        )
        for item in records
    )

    return {
        "schema_version": "moderation-audit-v1",
        "seed": seed,
        "split_counts": split_counts,
        "metric_names": ["margin", "mean_margin_milli", "variant_count", "deficit_count"],
        "records": records,
        "groups": groups,
        "provenance_nodes": nodes,
        "estimator": {
            "obligation": 42,
            "comparison_count": len(groups),
            "deficit_count": sum(item["deficit_count"] for item in groups),
            "worst_group_margin": min(item["mean_margin_milli"] for item in groups),
        },
        "trace": {"canonical_rows": trace_rows, "trace_digest": trace_digest(trace_rows)},
    }


def by_case(report):
    return {item["case_id"]: item for item in report["records"]}


def digit_case_ids(data_root=DATA_ROOT):
    rows = load_jsonl(Path(data_root) / "inputs" / "i1.jsonl") + load_jsonl(Path(data_root) / "inputs" / "i2.jsonl")
    return sorted(row["case_id"] for row in rows if row["split"] != "train" and any(ch.isdigit() for ch in row["text"]))


def clone_data_root(target):
    shutil.copytree(DATA_ROOT, target)


def challenge_case_ids(expected):
    return sorted(item["case_id"] for item in expected["records"] if item["split"] == "challenge")


def test_qdrift_sum(built_tool):
    """Checks the public report surface, split accounting, deterministic seed, and digit-folded scored rows."""
    report, out_path = run_report(built_tool, out_path=VISIBLE_OUT)
    expected = expected_report()
    assert out_path == VISIBLE_OUT
    assert out_path.exists()
    assert set(report) == {
        "schema_version",
        "seed",
        "split_counts",
        "metric_names",
        "records",
        "groups",
        "provenance_nodes",
        "estimator",
        "trace",
    }
    assert report["schema_version"] == expected["schema_version"]
    assert report["seed"] == 314159
    assert report["split_counts"] == expected["split_counts"]
    assert report["metric_names"] == expected["metric_names"]
    assert [item["case_id"] for item in report["records"]] == sorted(item["case_id"] for item in report["records"])
    assert all(item["split"] != "train" for item in report["records"])
    rows = by_case(report)
    expected_rows = by_case(expected)
    for case_id in digit_case_ids():
        assert rows[case_id]["margin"] == expected_rows[case_id]["margin"]


def test_ridge_fold(built_tool, tmp_path):
    """Compares every scored row's margin and label against an independent implementation of the visible text rules."""
    report, _ = run_report(built_tool, out_path=tmp_path / "report.json")
    expected = expected_report()
    got = [(item["case_id"], item["margin"], item["label"]) for item in report["records"]]
    want = [(item["case_id"], item["margin"], item["label"]) for item in expected["records"]]
    assert got == want


def test_vanta_mark(built_tool, tmp_path):
    """Verifies group metrics and estimator values derived from the generated scored records."""
    report, _ = run_report(built_tool, out_path=tmp_path / "report.json")
    expected = expected_report()
    assert report["groups"] == expected["groups"]
    assert report["estimator"] == expected["estimator"]


def test_lumen_pair(built_tool, tmp_path):
    """Checks that dependency aliases collapse onto canonical evidence nodes with the expected component hashes."""
    report, _ = run_report(built_tool, out_path=tmp_path / "report.json")
    expected = expected_report()
    assert report["provenance_nodes"] == expected["provenance_nodes"]
    aliases = {prov["canonical_package"]: prov["aliases"] for prov in report["provenance_nodes"]}
    expected_aliases = {prov["canonical_package"]: prov["aliases"] for prov in expected["provenance_nodes"]}
    assert aliases == expected_aliases
    for record in report["records"]:
        prov = next(item for item in report["provenance_nodes"] if item["canonical_package"] == record["canonical_package"])
        assert record["component_hash"] == prov["component_hash"]


def test_sable_ring(built_tool, tmp_path):
    """Reconstructs the trace accumulator and confirms equivalent input ordering leaves groups and trace stable."""
    report, _ = run_report(built_tool, out_path=tmp_path / "report.json")
    expected = expected_report()
    assert report["trace"] == expected["trace"]
    assert report["trace"]["canonical_rows"] == sorted(report["trace"]["canonical_rows"])
    assert report["trace"]["trace_digest"] == trace_digest(report["trace"]["canonical_rows"])

    alt_root = tmp_path / "r01"
    clone_data_root(alt_root)
    for name in ("i1.jsonl", "i2.jsonl"):
        path = alt_root / "inputs" / name
        lines = [line for line in path.read_text().splitlines() if line.strip()]
        path.write_text("\n".join(reversed(lines)) + "\n")
    other, _ = run_report(built_tool, data_root=alt_root, out_path=tmp_path / "moderation_ledger.json")
    assert other["trace"] == report["trace"]
    assert other["groups"] == report["groups"]


def test_crest_join(built_tool, tmp_path):
    """Covers the challenge split records so public-row hardcoding and threshold-only fixes miss required behavior."""
    report, _ = run_report(built_tool, out_path=tmp_path / "report.json")
    expected = expected_report()
    got = by_case(report)
    want = by_case(expected)
    for case_id in challenge_case_ids(expected):
        assert got[case_id]["split"] == "challenge"
        assert got[case_id]["canonical_package"] == want[case_id]["canonical_package"]
        assert got[case_id]["margin"] == want[case_id]["margin"]
        assert got[case_id]["label"] == want[case_id]["label"]


def test_nova_cast(built_tool):
    """Rejects stale output by overwriting the visible artifact and requiring byte-stable reruns."""
    run_report(built_tool, out_path=VISIBLE_OUT)
    VISIBLE_OUT.write_text(json.dumps({}) + "\n")
    first, _ = run_report(built_tool, out_path=VISIBLE_OUT)
    first_bytes = VISIBLE_OUT.read_bytes()
    assert first["schema_version"] == expected_report()["schema_version"]
    second, _ = run_report(built_tool, out_path=VISIBLE_OUT)
    assert second == first
    assert VISIBLE_OUT.read_bytes() == first_bytes
