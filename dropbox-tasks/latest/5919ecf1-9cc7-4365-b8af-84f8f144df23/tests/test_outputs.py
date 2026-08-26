import csv
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

APP = Path(os.environ.get("APP_DIR", "/app"))
BIN = APP / "securities_lending_fee"
SRC = APP / "securities_lending_fee.go"
PUBLIC = APP / "input"
CFG = {"num":87,"slug":"87-go-securities-lending-fee-ledger","title":"securities lending fee ledger","domain":"securities lending fee ledger","binary":"securities_lending_fee","src":"securities_lending_fee.go","out":"securities_lending_fee_report.json","manifest":"lending_batches.csv","entity":"borrowers.csv","events":"fee_accruals.jsonl","entity_name":"borrower_id","segment_name":"lending_desk","id_field":"fee_id","batch_field":"lending_batch_id","entity_field":"borrower_id","time_field":"accrued_at","seq_field":"loan_sequence","kind_field":"fee_type","amount_field":"fee_cents","ref_field":"rebates_fee_id","positive":"accrual","reverse":"rebate"}


def parse_time(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def write_case(path, seed=0):
    path.mkdir(parents=True, exist_ok=True)
    manifest_text = "batch_id,cutoff_at\n"
    manifest_text += f"B{seed}A,2026-02-03T00:00:00Z\n"
    manifest_text += f"B{seed}B,2026-02-06T00:00:00Z\n"
    entity_text = f"{CFG['entity_name']},{CFG['segment_name']},active_limit\n"
    entity_text += f"E{seed}1,north,{170 + seed}\n"
    entity_text += f"E{seed}2,south,40\n"
    entity_text += f"E{seed}3,west,90\n"
    (path / CFG["manifest"]).write_text(manifest_text)
    (path / CFG["entity"]).write_text(entity_text)

    def row(record_id, batch, entity_id, when, seq, kind, amount, ref=""):
        return {
            CFG["id_field"]: record_id,
            CFG["batch_field"]: batch,
            CFG["entity_field"]: entity_id,
            CFG["time_field"]: when,
            CFG["seq_field"]: seq,
            CFG["kind_field"]: kind,
            CFG["amount_field"]: amount,
            CFG["ref_field"]: ref,
        }

    rows = [
        row(f"A{seed}", f"B{seed}A", f"E{seed}1", "2026-02-01T10:00:00Z", 2, CFG["positive"], 100 + seed),
        row(f"B{seed}", f"B{seed}A", f"E{seed}1", "2026-02-01T09:00:00Z", 1, CFG["positive"], 50),
        row(f"C{seed}", f"B{seed}B", f"E{seed}1", "2026-02-04T00:00:00Z", 1, CFG["reverse"], 999, f"B{seed}"),
        row(f"D{seed}", f"B{seed}B", f"E{seed}2", "not-time", 1, CFG["positive"], 10),
        row(f"A{seed}", f"B{seed}B", f"E{seed}2", "2026-02-04T01:00:00Z", 1, CFG["positive"], 10),
        row(f"E{seed}", "missing", f"E{seed}2", "2026-02-04T01:00:00Z", 2, CFG["positive"], 10),
        row(f"F{seed}", f"B{seed}A", f"E{seed}2", "2026-02-04T01:00:00Z", 3, CFG["positive"], 10),
        row(f"G{seed}", f"B{seed}B", "missing", "2026-02-04T01:00:00Z", 4, CFG["positive"], 10),
        row(f"H{seed}", f"B{seed}B", f"E{seed}2", "2026-02-04T01:00:00Z", 5, "badkind", 10),
        row(f"I{seed}", f"B{seed}B", f"E{seed}2", "2026-02-04T01:00:00Z", 6, CFG["positive"], -1),
        row(f"J{seed}", f"B{seed}B", f"E{seed}2", "2026-02-04T01:00:00Z", 7, CFG["reverse"], 0, "none"),
        row(f"K{seed}", f"B{seed}B", f"E{seed}3", "2026-02-05T00:00:00Z", 1, CFG["positive"], 75),
        row(f"L{seed}", f"B{seed}B", f"E{seed}3", "2026-02-05T00:01:00Z", 2, CFG["positive"], 20),
    ]
    text = "\n".join(json.dumps(item, separators=(",", ":")) for item in rows) + "\n"
    (path / CFG["events"]).write_text(text)


def load_oracle(path):
    batches = {}
    with open(path / CFG["manifest"], newline="") as handle:
        for row in csv.DictReader(handle):
            batches[row["batch_id"].strip()] = parse_time(row["cutoff_at"].strip())

    entities = {}
    with open(path / CFG["entity"], newline="") as handle:
        for row in csv.DictReader(handle):
            entities[row[CFG["entity_name"]].strip()] = {
                "segment": row[CFG["segment_name"]].strip(),
                "cap": float(row["active_limit"]),
            }

    events = []
    with open(path / CFG["events"]) as handle:
        for index, line in enumerate(handle):
            item = json.loads(line)
            item["_index"] = index
            item["_id"] = str(item.get(CFG["id_field"], "")).strip()
            item["_batch"] = str(item.get(CFG["batch_field"], "")).strip()
            item["_entity"] = str(item.get(CFG["entity_field"], "")).strip()
            item["_kind"] = str(item.get(CFG["kind_field"], "")).strip()
            item["_ref"] = str(item.get(CFG["ref_field"], "")).strip()
            item["_seq"] = int(item.get(CFG["seq_field"], 0))
            item["_amount"] = float(item.get(CFG["amount_field"], 0))
            item["_time"] = parse_time(item.get(CFG["time_field"], ""))
            events.append(item)

    events.sort(key=lambda item: (
        item["_time"] is not None,
        item["_index"] if item["_time"] is None else item["_time"],
        item["_seq"],
        item["_id"],
    ))
    seen = set()
    accepted = {}
    accepted_order = []
    rejected = []
    ent_net = {}
    ent_current = {}
    ent_rev = {}
    batch_net = {}
    batch_acc = {}
    batch_rej = {}
    trace = []

    for item in events:
        reason = None
        if item["_time"] is None:
            reason = "invalid timestamp"
        elif item["_id"] in seen:
            reason = "duplicate id"
        elif item["_batch"] not in batches:
            reason = "unknown batch"
        elif item["_time"] > batches[item["_batch"]]:
            reason = "after watermark"
        elif item["_entity"] not in entities:
            reason = "unknown entity"
        elif item["_kind"] not in {CFG["positive"], CFG["reverse"]}:
            reason = "invalid kind"
        elif item["_kind"] == CFG["positive"] and item["_amount"] < 0:
            reason = "negative amount"
        elif item["_kind"] == CFG["positive"] and ent_net.get(item["_entity"], 0) + item["_amount"] > entities[item["_entity"]]["cap"]:
            reason = "entity cap exceeded"

        prior = None
        if reason is None and item["_kind"] == CFG["reverse"]:
            prior = accepted.get(item["_ref"])
            if prior is None or prior["reversed"] or prior["entity"] != item["_entity"]:
                reason = "state conflict"

        seen.add(item["_id"])
        if reason:
            rejected.append({"record_id": item["_id"], "reason": reason})
            if item["_batch"] in batches:
                batch_rej[item["_batch"]] = batch_rej.get(item["_batch"], 0) + 1
            continue

        accepted_order.append(item["_id"])
        batch_acc[item["_batch"]] = batch_acc.get(item["_batch"], 0) + 1
        if item["_kind"] == CFG["positive"]:
            accepted[item["_id"]] = {
                "batch": item["_batch"],
                "entity": item["_entity"],
                "amount": item["_amount"],
                "reversed": False,
            }
            ent_net[item["_entity"]] = ent_net.get(item["_entity"], 0) + item["_amount"]
            ent_current[item["_entity"]] = ent_current.get(item["_entity"], 0) + 1
            batch_net[item["_batch"]] = batch_net.get(item["_batch"], 0) + item["_amount"]
        else:
            prior["reversed"] = True
            ent_net[item["_entity"]] = ent_net.get(item["_entity"], 0) - prior["amount"]
            ent_current[item["_entity"]] = ent_current.get(item["_entity"], 0) - 1
            ent_rev[item["_entity"]] = ent_rev.get(item["_entity"], 0) + 1
            batch_net[item["_batch"]] = batch_net.get(item["_batch"], 0) - prior["amount"]
        trace.append({
            "record_id": item["_id"],
            "batch_id": item["_batch"],
            "entity_id": item["_entity"],
            "current_records": ent_current.get(item["_entity"], 0),
            "active_amount": ent_net.get(item["_entity"], 0),
            "reversal_count": ent_rev.get(item["_entity"], 0),
        })

    curated = [
        {
            "record_id": record_id,
            "entity_id": rec["entity"],
            "segment": entities[rec["entity"]]["segment"],
            "batch_id": rec["batch"],
            "amount": rec["amount"],
        }
        for record_id, rec in accepted.items()
        if not rec["reversed"]
    ]
    curated.sort(key=lambda row: row["record_id"])
    rejected.sort(key=lambda row: row["record_id"])
    return {
        "curated_records": curated,
        "entity_summary": [
            {
                "entity_id": entity_id,
                "segment": entities[entity_id]["segment"],
                "current_records": ent_current.get(entity_id, 0),
                "reversal_count": ent_rev.get(entity_id, 0),
                "active_limit": entities[entity_id]["cap"],
                "net_amount": ent_net.get(entity_id, 0),
            }
            for entity_id in sorted(entities)
        ],
        "batch_audit": [
            {
                "batch_id": batch_id,
                "accepted_events": batch_acc.get(batch_id, 0),
                "rejected_events": batch_rej.get(batch_id, 0),
                "net_amount": batch_net.get(batch_id, 0),
            }
            for batch_id in sorted(batches)
        ],
        "entity_trace": trace,
        "rejected_records": rejected,
        "accepted_records": accepted_order,
    }


def run_subject(input_dir, output_dir):
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir()
    result = subprocess.run(
        [str(BIN)],
        cwd=APP,
        env={**os.environ, "INPUT_DIR": str(input_dir), "OUTPUT_DIR": str(output_dir)},
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    with open(output_dir / CFG["out"]) as handle:
        return json.load(handle)


def test_artifacts_exist():
    """Verify that the required Go source and executable were produced."""
    assert SRC.exists()
    assert BIN.exists()


def test_public_input_matches_oracle(tmp_path):
    """Compare the shipped public input against the independent Python oracle."""
    expected = load_oracle(PUBLIC)
    actual = run_subject(PUBLIC, tmp_path / "out")
    assert actual == expected


def test_generated_cases_match_oracle(tmp_path):
    """Exercise generated compatible cases with timestamp, duplicate, watermark, and reversal variations."""
    for seed in range(6):
        case_dir = tmp_path / f"case-{seed}"
        write_case(case_dir, seed)
        expected = load_oracle(case_dir)
        actual = run_subject(case_dir, tmp_path / f"out-{seed}")
        assert actual == expected


def test_reversal_entity_and_watermark_stress(tmp_path):
    """Combine reversal conflict, reopened capacity, cap rejection, duplicate invalid ids, and watermark rejection."""
    case_dir = tmp_path / "stress"
    write_case(case_dir, 44)
    rows = []
    with open(case_dir / CFG["events"]) as handle:
        for line in handle:
            rows.append(json.loads(line))
    rows.append({
        CFG["id_field"]: "ZZ1",
        CFG["batch_field"]: "B44B",
        CFG["entity_field"]: "E442",
        CFG["time_field"]: "2026-02-04T00:00:00Z",
        CFG["seq_field"]: 0,
        CFG["kind_field"]: CFG["reverse"],
        CFG["amount_field"]: 0,
        CFG["ref_field"]: "A44",
    })
    rows.append({
        CFG["id_field"]: "ZZ2",
        CFG["batch_field"]: "B44B",
        CFG["entity_field"]: "E442",
        CFG["time_field"]: "2026-02-06T00:00:01Z",
        CFG["seq_field"]: 1,
        CFG["kind_field"]: CFG["positive"],
        CFG["amount_field"]: 1,
        CFG["ref_field"]: "",
    })
    rows.append({
        CFG["id_field"]: "ZZ3",
        CFG["batch_field"]: "B44B",
        CFG["entity_field"]: "E441",
        CFG["time_field"]: "2026-02-04T00:00:30Z",
        CFG["seq_field"]: 1,
        CFG["kind_field"]: CFG["positive"],
        CFG["amount_field"]: 60,
        CFG["ref_field"]: "",
    })
    rows.append({
        CFG["id_field"]: "ZZ4",
        CFG["batch_field"]: "B44B",
        CFG["entity_field"]: "E441",
        CFG["time_field"]: "2026-02-04T00:00:31Z",
        CFG["seq_field"]: 2,
        CFG["kind_field"]: CFG["positive"],
        CFG["amount_field"]: 11,
        CFG["ref_field"]: "",
    })
    rows.append({
        CFG["id_field"]: "ZZ5",
        CFG["batch_field"]: "B44B",
        CFG["entity_field"]: "E441",
        CFG["time_field"]: "bad-time",
        CFG["seq_field"]: 3,
        CFG["kind_field"]: CFG["positive"],
        CFG["amount_field"]: 1,
        CFG["ref_field"]: "",
    })
    rows.append({
        CFG["id_field"]: "ZZ5",
        CFG["batch_field"]: "B44B",
        CFG["entity_field"]: "E441",
        CFG["time_field"]: "2026-02-04T00:00:32Z",
        CFG["seq_field"]: 4,
        CFG["kind_field"]: CFG["positive"],
        CFG["amount_field"]: 1,
        CFG["ref_field"]: "",
    })
    text = "\n".join(json.dumps(item, separators=(",", ":")) for item in rows) + "\n"
    (case_dir / CFG["events"]).write_text(text)
    expected = load_oracle(case_dir)
    actual = run_subject(case_dir, tmp_path / "out-stress")
    assert actual == expected
    reasons = {row["record_id"]: row["reason"] for row in actual["rejected_records"]}
    assert reasons["ZZ1"] == "state conflict"
    assert reasons["ZZ2"] == "after watermark"
    assert reasons["ZZ4"] == "entity cap exceeded"
    assert reasons["ZZ5"] == "duplicate id"
    assert "ZZ3" in actual["accepted_records"]
    trace_by_id = {row["record_id"]: row for row in actual["entity_trace"]}
    assert trace_by_id["ZZ3"] == {
        "record_id": "ZZ3",
        "batch_id": "B44B",
        "entity_id": "E441",
        "current_records": 2,
        "active_amount": 204,
        "reversal_count": 1,
    }
