"""
Behavioral tests for slot-merge.
"""
import json
import os
import subprocess
import tempfile

BINARY = "/app/target/release/slot-merge"

USAGE_ERROR_CASES = [
    ("usage_no_arguments", []),
    ("usage_merge_without_directory", ["merge"]),
    ("usage_gaps_without_directory", ["gaps"]),
    ("usage_report_without_directory", ["report"]),
    ("usage_stats_without_directory", ["stats"]),
    ("usage_check_without_directory", ["check"]),
]


def run(args):
    return subprocess.run([BINARY] + args, capture_output=True, text=True)


def write_dir(files: dict) -> str:
    tmp = tempfile.mkdtemp()
    for name, lines in files.items():
        path = os.path.join(tmp, name)
        with open(path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(line.rstrip("\n") + "\n")
    return tmp


def cleanup(path):
    for root, _, files in os.walk(path):
        for f in files:
            os.unlink(os.path.join(root, f))
    os.rmdir(path)


def parse_merge(stdout: str):
    rows = []
    for line in stdout.splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _make_usage_error_test(case_id, argv):
    def test_fn():
        r = run(argv)
        assert r.returncode == 1, (
            f"{case_id}: expected exit 1, got {r.returncode}\nstderr: {r.stderr!r}"
        )
        assert "usage" in r.stderr.lower(), (
            f"{case_id}: expected 'usage' in stderr\nstderr: {r.stderr!r}"
        )

    test_fn.__name__ = f"test_{case_id}"
    test_fn.__doc__ = (
        "instruction.md: slot-merge "
        + (" ".join(argv) if argv else "(no arguments)")
        + " -> exit 1, stderr contains 'usage'"
    )
    return test_fn


for _case_id, _argv in USAGE_ERROR_CASES:
    globals()[f"test_{_case_id}"] = _make_usage_error_test(_case_id, _argv)


def test_merge_touching_intervals_coalesce():
    """Verify that intervals sharing an endpoint (end == start) merge into one row."""
    d = write_dir(
        {
            "early.slot": [
                '{"resource": "lab-1", "start_ms": 100, "end_ms": 200, "holder": "a", "slot_id": 1}',
            ],
            "late.slot": [
                '{"resource": "lab-1", "start_ms": 200, "end_ms": 400, "holder": "b", "slot_id": 2}',
            ],
        }
    )
    try:
        r = run(["merge", d])
        assert r.returncode == 0, r.stderr
        rows = parse_merge(r.stdout)
        assert len(rows) == 1
        assert rows[0]["start_ms"] == 100
        assert rows[0]["end_ms"] == 400
        assert rows[0]["holder"] == "b"
    finally:
        cleanup(d)


def test_merge_overlapping_intervals_within_file():
    """Verify overlapping intervals in the same file coalesce into one span."""
    d = write_dir(
        {
            "batch.slot": [
                '{"resource": "room-9", "start_ms": 1000, "end_ms": 2500, "holder": "x", "slot_id": 10}',
                '{"resource": "room-9", "start_ms": 2000, "end_ms": 3000, "holder": "y", "slot_id": 11}',
            ],
        }
    )
    try:
        r = run(["merge", d])
        assert r.returncode == 0
        rows = parse_merge(r.stdout)
        assert len(rows) == 1
        assert rows[0]["start_ms"] == 1000
        assert rows[0]["end_ms"] == 3000
    finally:
        cleanup(d)


def test_merge_overlapping_intervals_across_files():
    """Verify overlapping intervals across files merge per resource."""
    d = write_dir(
        {
            "aaa.slot": [
                '{"resource": "desk-3", "start_ms": 500, "end_ms": 1500, "holder": "morning", "slot_id": 1}',
            ],
            "bbb.slot": [
                '{"resource": "desk-3", "start_ms": 1200, "end_ms": 2200, "holder": "afternoon", "slot_id": 2}',
            ],
        }
    )
    try:
        r = run(["merge", d])
        assert r.returncode == 0
        rows = parse_merge(r.stdout)
        assert len(rows) == 1
        assert rows[0]["start_ms"] == 500
        assert rows[0]["end_ms"] == 2200
        assert rows[0]["holder"] == "afternoon"
    finally:
        cleanup(d)


def test_merge_keeps_disjoint_intervals_separate():
    """Verify non-overlapping intervals for the same resource stay separate."""
    d = write_dir(
        {
            "one.slot": [
                '{"resource": "hall-a", "start_ms": 100, "end_ms": 200, "holder": "a", "slot_id": 1}',
                '{"resource": "hall-a", "start_ms": 500, "end_ms": 700, "holder": "b", "slot_id": 2}',
            ],
        }
    )
    try:
        r = run(["merge", d])
        assert r.returncode == 0
        rows = parse_merge(r.stdout)
        assert len(rows) == 2
        assert rows[0]["start_ms"] == 100
        assert rows[1]["start_ms"] == 500
    finally:
        cleanup(d)


def test_merge_sorted_by_resource_then_start():
    """Verify merged output is sorted by resource then start_ms ascending."""
    d = write_dir(
        {
            "data.slot": [
                '{"resource": "room-b", "start_ms": 300, "end_ms": 400, "holder": "b", "slot_id": 3}',
                '{"resource": "room-a", "start_ms": 100, "end_ms": 200, "holder": "a", "slot_id": 1}',
                '{"resource": "room-a", "start_ms": 250, "end_ms": 350, "holder": "c", "slot_id": 2}',
            ],
        }
    )
    try:
        r = run(["merge", d])
        assert r.returncode == 0
        rows = parse_merge(r.stdout)
        keys = [(row["resource"], row["start_ms"]) for row in rows]
        assert keys == sorted(keys)
        assert keys[0][0] == "room-a"
        assert keys[-1][0] == "room-b"
    finally:
        cleanup(d)


def test_merge_holder_from_later_filename_on_touch():
    """Verify holder comes from the lexicographically later source file on touch."""
    d = write_dir(
        {
            "alpha.slot": [
                '{"resource": "pod-2", "start_ms": 10, "end_ms": 20, "holder": "first", "slot_id": 1}',
            ],
            "omega.slot": [
                '{"resource": "pod-2", "start_ms": 20, "end_ms": 30, "holder": "second", "slot_id": 2}',
            ],
        }
    )
    try:
        r = run(["merge", d])
        assert r.returncode == 0
        rows = parse_merge(r.stdout)
        assert len(rows) == 1
        assert rows[0]["holder"] == "second"
    finally:
        cleanup(d)


def test_merge_ignores_lower_epoch_rows():
    """Only max-epoch rows participate in merge."""
    d = write_dir(
        {
            "a.slot": [
                '{"resource": "r1", "start_ms": 0, "end_ms": 100, "holder": "old", "slot_id": 1, "epoch": 1}',
                '{"resource": "r1", "start_ms": 200, "end_ms": 300, "holder": "new", "slot_id": 2, "epoch": 2}',
            ],
        }
    )
    try:
        r = run(["merge", d])
        assert r.returncode == 0
        rows = parse_merge(r.stdout)
        assert len(rows) == 1
        assert rows[0]["start_ms"] == 200
        assert rows[0]["end_ms"] == 300
        assert rows[0]["holder"] == "new"
    finally:
        cleanup(d)


def test_merge_case_insensitive_resource():
    """Resources differing only by case merge together."""
    d = write_dir(
        {
            "a.slot": [
                '{"resource": "Lab-1", "start_ms": 10, "end_ms": 20, "holder": "a", "slot_id": 1}',
            ],
            "b.slot": [
                '{"resource": "lab-1", "start_ms": 20, "end_ms": 30, "holder": "b", "slot_id": 2}',
            ],
        }
    )
    try:
        r = run(["merge", d])
        assert r.returncode == 0
        rows = parse_merge(r.stdout)
        assert len(rows) == 1
        assert rows[0]["end_ms"] == 30
    finally:
        cleanup(d)


def test_gaps_between_merged_intervals():
    """Gaps are computed on merged max-epoch intervals."""
    d = write_dir(
        {
            "a.slot": [
                '{"resource": "r1", "start_ms": 0, "end_ms": 10, "holder": "a", "slot_id": 1}',
                '{"resource": "r1", "start_ms": 20, "end_ms": 30, "holder": "b", "slot_id": 2}',
            ],
        }
    )
    try:
        r = run(["gaps", d])
        assert r.returncode == 0
        assert r.stdout.strip() == "resource=r1 start=11 end=19"
    finally:
        cleanup(d)


def test_gaps_no_line_when_touching():
    """Touching merged rows produce no gap."""
    d = write_dir(
        {
            "a.slot": [
                '{"resource": "r1", "start_ms": 0, "end_ms": 10, "holder": "a", "slot_id": 1}',
                '{"resource": "r1", "start_ms": 11, "end_ms": 20, "holder": "b", "slot_id": 2}',
            ],
        }
    )
    try:
        r = run(["gaps", d])
        assert r.returncode == 0
        assert r.stdout.strip() == ""
    finally:
        cleanup(d)


def test_gaps_ignores_fenced_out_epochs():
    """Gaps use merged max-epoch intervals; lower-epoch rows are ignored."""
    d = write_dir(
        {
            "a.slot": [
                '{"resource": "r1", "start_ms": 0, "end_ms": 10, "holder": "old", "slot_id": 1, "epoch": 1}',
                '{"resource": "r1", "start_ms": 50, "end_ms": 60, "holder": "new", "slot_id": 2, "epoch": 2}',
            ],
        }
    )
    try:
        r = run(["gaps", d])
        assert r.returncode == 0
        assert r.stdout.strip() == ""
    finally:
        cleanup(d)


def test_report_span_respects_epoch_fence():
    """Report SPAN aggregates only max-epoch rows per resource."""
    d = write_dir(
        {
            "a.slot": [
                '{"resource": "alpha", "start_ms": 0, "end_ms": 1000, "holder": "old", "slot_id": 1, "epoch": 1}',
                '{"resource": "alpha", "start_ms": 200, "end_ms": 400, "holder": "new", "slot_id": 2, "epoch": 2}',
            ],
        }
    )
    try:
        r = run(["report", d])
        assert r.returncode == 0
        lines = r.stdout.splitlines()
        assert "alpha" in lines[2]
        assert lines[2].split()[-1] == "200"
    finally:
        cleanup(d)


def test_report_exact_layout():
    """Report table columns, widths, sort, and TOTAL row."""
    d = write_dir(
        {
            "a.slot": [
                '{"resource": "alpha", "start_ms": 0, "end_ms": 100, "holder": "x", "slot_id": 1}',
                '{"resource": "alpha", "start_ms": 50, "end_ms": 150, "holder": "y", "slot_id": 2}',
            ],
            "b.slot": [
                '{"resource": "beta", "start_ms": 0, "end_ms": 40, "holder": "z", "slot_id": 3}',
            ],
        }
    )
    try:
        r = run(["report", d])
        assert r.returncode == 0
        expected = "\n".join(
            [
                "RESOURCE  SLOTS  HOLDERS  SPAN",
                "--------  -----  -------  ----",
                "alpha         2        2   150",
                "beta          1        1    40",
                "--------  -----  -------  ----",
                "TOTAL         3        3   190",
            ]
        )
        assert r.stdout.rstrip("\n") == expected
    finally:
        cleanup(d)


def test_check_detects_duplicate_slot_id_across_files():
    """Verify check exits 2 when the same slot_id appears in multiple files."""
    d = write_dir(
        {
            "one.slot": ['{"resource": "r1", "start_ms": 1, "end_ms": 2, "holder": "a", "slot_id": 99}'],
            "two.slot": ['{"resource": "r2", "start_ms": 3, "end_ms": 4, "holder": "b", "slot_id": 99}'],
        }
    )
    try:
        r = run(["check", d])
        assert r.returncode == 2, (r.returncode, r.stdout, r.stderr)
        assert "duplicate slot id" in r.stderr.lower()
    finally:
        cleanup(d)


def test_check_epoch_regression_across_files():
    """Epoch regression spans files in global scan order."""
    d = write_dir(
        {
            "aaa.slot": [
                '{"resource": "r1", "start_ms": 1, "end_ms": 2, "holder": "a", "slot_id": 1, "epoch": 3}',
            ],
            "bbb.slot": [
                '{"resource": "r1", "start_ms": 3, "end_ms": 4, "holder": "b", "slot_id": 2, "epoch": 1}',
            ],
        }
    )
    try:
        r = run(["check", d])
        assert r.returncode == 2
        assert "epoch regression" in r.stderr.lower()
    finally:
        cleanup(d)


def test_check_ok_unique_slot_ids():
    """Verify check exits 0 and prints ok when all slot_ids are unique."""
    d = write_dir(
        {
            "a.slot": ['{"resource": "r1", "start_ms": 1, "end_ms": 2, "holder": "a", "slot_id": 1}'],
            "b.slot": ['{"resource": "r2", "start_ms": 3, "end_ms": 4, "holder": "b", "slot_id": 2}'],
        }
    )
    try:
        r = run(["check", d])
        assert r.returncode == 0
        assert r.stdout.strip() == "ok"
    finally:
        cleanup(d)


def test_stats_counts_files_and_records():
    """Verify stats reports file count and total non-empty record count."""
    d = write_dir(
        {
            "x.slot": [
                '{"resource": "r1", "start_ms": 1, "end_ms": 2, "holder": "a", "slot_id": 1}',
                '{"resource": "r2", "start_ms": 3, "end_ms": 4, "holder": "b", "slot_id": 2}',
            ],
            "y.slot": ['{"resource": "r3", "start_ms": 5, "end_ms": 6, "holder": "c", "slot_id": 3}'],
        }
    )
    try:
        r = run(["stats", d])
        assert r.returncode == 0
        obj = json.loads(r.stdout.strip())
        assert obj == {"files": 2, "records": 3}
    finally:
        cleanup(d)


def test_no_slots_exit_3():
    """Verify merge exits 3 when the directory contains no .slot files."""
    d = tempfile.mkdtemp()
    try:
        r = run(["merge", d])
        assert r.returncode == 3
        assert "no slots" in r.stderr.lower()
    finally:
        os.rmdir(d)


def test_invalid_json_exit_2():
    """Verify merge exits 2 with invalid json when a .slot line is malformed."""
    d = write_dir({"bad.slot": ["{"]})
    try:
        r = run(["merge", d])
        assert r.returncode == 2
        assert "invalid json" in r.stderr.lower()
    finally:
        cleanup(d)


def test_missing_directory_exit_1():
    """Verify merge exits 1 with error when the directory does not exist."""
    r = run(["merge", "/tmp/no-slot-merge-dir-99999"])
    assert r.returncode == 1
    assert "error" in r.stderr.lower()


def test_unknown_command_exit_1():
    """Verify an unrecognized subcommand exits 1 with unknown command."""
    d = write_dir({"a.slot": ['{"resource": "r", "start_ms": 1, "end_ms": 2, "holder": "x", "slot_id": 1}']})
    try:
        r = run(["nope", d])
        assert r.returncode == 1
        assert "unknown command" in r.stderr.lower()
    finally:
        cleanup(d)
