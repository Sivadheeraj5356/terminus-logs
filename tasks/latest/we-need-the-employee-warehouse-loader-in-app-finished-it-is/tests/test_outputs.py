import csv
import json
import sqlite3
import subprocess
from pathlib import Path


APP_DIR = Path("/app")
HEADERS = [
    "batch_id",
    "source_system",
    "employee_id",
    "full_name",
    "department",
    "title",
    "manager_id",
    "location",
    "annual_salary",
    "status",
    "attrs_json",
    "valid_from",
    "recorded_at",
    "operation",
    "correction_id",
]


def write_feed(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def run_loader(db_path, input_path):
    result = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--",
            "ingest",
            "--db",
            str(db_path),
            "--input",
            str(input_path),
        ],
        cwd=APP_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def fetch_history(db_path, employee_id):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT employee_id, full_name, department, title, manager_id, location,
                   annual_salary, status, attrs_json, source_system, effective_start,
                   effective_end, is_current, row_hash, batch_id, correction_id, recorded_at
            FROM employee_history
            WHERE employee_id = ?
            ORDER BY effective_start
            """,
            (employee_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def base_row(**overrides):
    row = {
        "batch_id": "B-001",
        "source_system": "workday",
        "employee_id": "E100",
        "full_name": "Ada Ng",
        "department": "Engineering",
        "title": "Analyst I",
        "manager_id": "M010",
        "location": "NYC",
        "annual_salary": "90000",
        "status": "active",
        "attrs_json": json.dumps({"level": 1, "cost_center": "ENG1"}),
        "valid_from": "2024-01-01",
        "recorded_at": "2024-01-02T09:00:00Z",
        "operation": "UPSERT",
        "correction_id": "ORIG",
    }
    row.update(overrides)
    return row


def test_out_of_order_and_late_updates_rebuild_non_overlapping_windows(tmp_path):
    """Verify late effective dates are inserted into the right place without overlapping SCD windows."""
    db_path = tmp_path / "warehouse.sqlite"
    first = tmp_path / "later.csv"
    second = tmp_path / "late_correction.csv"
    write_feed(
        first,
        [base_row(batch_id="B-003", title="Analyst II", annual_salary="100000", valid_from="2024-04-01", recorded_at="2024-04-02T09:00:00Z")],
    )
    write_feed(
        second,
        [
            base_row(batch_id="B-001", valid_from="2024-01-01", recorded_at="2024-01-02T09:00:00Z"),
            base_row(batch_id="B-002", annual_salary="95000", valid_from="2024-01-15", recorded_at="2024-05-01T09:00:00Z", correction_id="C1"),
        ],
    )

    run_loader(db_path, first)
    run_loader(db_path, second)

    rows = fetch_history(db_path, "E100")
    assert [(r["effective_start"], r["effective_end"], r["annual_salary"], r["title"], r["is_current"]) for r in rows] == [
        ("2024-01-01", "2024-01-15", 90000, "Analyst I", 0),
        ("2024-01-15", "2024-04-01", 95000, "Analyst I", 0),
        ("2024-04-01", None, 100000, "Analyst II", 1),
    ]
    assert sum(row["is_current"] for row in rows) == 1


def test_same_day_correction_wins_and_replay_is_idempotent(tmp_path):
    """Verify corrections for the same effective date replace the older version and replay does not duplicate history."""
    db_path = tmp_path / "warehouse.sqlite"
    wrong = tmp_path / "wrong.csv"
    correction = tmp_path / "correction.csv"
    batch_tie = tmp_path / "batch_tie.csv"
    write_feed(
        wrong,
        [base_row(employee_id="E500", department="Operations", valid_from="2024-03-01", recorded_at="2024-03-03T10:00:00Z", correction_id="C1")],
    )
    write_feed(
        correction,
        [
            base_row(employee_id="E500", department="People", valid_from="2024-03-01", recorded_at="2024-03-05T10:00:00Z", correction_id="C2"),
            base_row(employee_id="E500", department="Finance", valid_from="2024-03-01", recorded_at="2024-03-05T10:00:00Z", correction_id="C3", attrs_json='{"level":3,"cost_center":"F100"}'),
        ],
    )
    write_feed(
        batch_tie,
        [
            base_row(employee_id="E501", batch_id="B-010", department="Finance", valid_from="2024-03-01", recorded_at="2024-03-05T10:00:00Z", correction_id="C1"),
            base_row(employee_id="E501", batch_id="B-009", department="Operations", valid_from="2024-03-01", recorded_at="2024-03-05T10:00:00Z", correction_id="C1"),
        ],
    )

    run_loader(db_path, wrong)
    run_loader(db_path, correction)
    run_loader(db_path, correction)
    run_loader(db_path, batch_tie)

    rows = fetch_history(db_path, "E500")
    assert len(rows) == 1
    assert rows[0]["department"] == "Finance"
    assert rows[0]["correction_id"] == "C3"
    assert json.loads(rows[0]["attrs_json"]) == {"cost_center": "F100", "level": 3}
    assert rows[0]["attrs_json"] == json.dumps({"cost_center": "F100", "level": 3}, separators=(",", ":"), sort_keys=True)
    batch_rows = fetch_history(db_path, "E501")
    assert len(batch_rows) == 1
    assert batch_rows[0]["department"] == "Finance"
    assert batch_rows[0]["batch_id"] == "B-010"


def test_no_change_rows_are_suppressed_and_delete_leaves_current_tombstone(tmp_path):
    """Verify repeated business state does not split history and a delete is retained as the current terminated state."""
    db_path = tmp_path / "warehouse.sqlite"
    feed = tmp_path / "changes.csv"
    write_feed(
        feed,
        [
            base_row(employee_id="E700", valid_from="2024-01-01", recorded_at="2024-01-01T08:00:00Z"),
            base_row(employee_id="E700", valid_from="2024-02-01", recorded_at="2024-02-01T08:00:00Z"),
            base_row(employee_id="E700", title="Senior Analyst", annual_salary="112000", valid_from="2024-03-15", recorded_at="2024-03-15T08:00:00Z"),
            base_row(employee_id="E700", title="Senior Analyst", annual_salary="112000", valid_from="2024-05-01", recorded_at="2024-05-01T08:00:00Z", operation="DELETE"),
        ],
    )

    run_loader(db_path, feed)

    rows = fetch_history(db_path, "E700")
    assert [(r["effective_start"], r["effective_end"], r["title"], r["status"], r["is_current"]) for r in rows] == [
        ("2024-01-01", "2024-03-15", "Analyst I", "active", 0),
        ("2024-03-15", "2024-05-01", "Senior Analyst", "active", 0),
        ("2024-05-01", None, "Senior Analyst", "terminated", 1),
    ]
    first_hashes = [(row["effective_start"], row["row_hash"]) for row in rows]
    assert all(row_hash for _, row_hash in first_hashes)
    assert len({row_hash for _, row_hash in first_hashes}) == len(first_hashes)

    run_loader(db_path, feed)

    replayed_hashes = [(row["effective_start"], row["row_hash"]) for row in fetch_history(db_path, "E700")]
    assert replayed_hashes == first_hashes


def test_bad_rows_are_rejected_without_blocking_valid_rows(tmp_path):
    """Verify invalid records are written to employee_rejects while valid records from the same file still load."""
    db_path = tmp_path / "warehouse.sqlite"
    feed = tmp_path / "mixed.csv"
    write_feed(
        feed,
        [
            base_row(employee_id="E800", valid_from="2024-01-01"),
            base_row(employee_id="E801", annual_salary="oops"),
            base_row(employee_id="E802", attrs_json="{bad json"),
            base_row(employee_id="", full_name="Missing Id"),
            base_row(employee_id="E803", operation="MERGE"),
            base_row(employee_id="E804", annual_salary="-1"),
            base_row(employee_id="E805", valid_from="not-a-date"),
            base_row(employee_id="E806", recorded_at="bad"),
        ],
    )

    run_loader(db_path, feed)

    assert len(fetch_history(db_path, "E800")) == 1
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rejects = conn.execute("SELECT source_file, line_number, employee_id, reason, raw_record, batch_id FROM employee_rejects").fetchall()
        audit = conn.execute("SELECT source_file, accepted_count, rejected_count FROM load_audit ORDER BY source_file").fetchall()
    assert len(rejects) == 7
    rejected_employee_ids = {row["employee_id"] or "" for row in rejects}
    assert rejected_employee_ids == {"E801", "E802", "", "E803", "E804", "E805", "E806"}
    assert {row["line_number"] for row in rejects} == {3, 4, 5, 6, 7, 8, 9}
    assert all(row["source_file"].endswith("mixed.csv") for row in rejects)
    assert all(row["reason"] and row["raw_record"] and row["batch_id"] == "B-001" for row in rejects)
    assert len(audit) == 1
    assert audit[0]["source_file"].endswith("mixed.csv")
    assert (audit[0]["accepted_count"], audit[0]["rejected_count"]) == (1, 7)


def test_directory_input_processes_nested_csv_files(tmp_path):
    """Verify a directory input includes csv files below the top level and keeps separate employees current."""
    db_path = tmp_path / "warehouse.sqlite"
    root = tmp_path / "inbound"
    write_feed(root / "a.csv", [base_row(employee_id="E900", full_name="Rae Lin", valid_from="2024-01-01")])
    write_feed(root / "nested" / "b.csv", [base_row(employee_id="E901", full_name="Mo Shah", valid_from="2024-02-01")])
    (root / "nested" / "ignore.txt").write_text("not a feed")

    run_loader(db_path, root)

    assert fetch_history(db_path, "E900")[0]["is_current"] == 1
    assert fetch_history(db_path, "E901")[0]["is_current"] == 1
    with sqlite3.connect(db_path) as conn:
        audit_rows = conn.execute("SELECT source_file, accepted_count, rejected_count FROM load_audit ORDER BY source_file").fetchall()
    assert audit_rows == [(str(root / "a.csv"), 1, 0), (str(root / "nested" / "b.csv"), 1, 0)]
