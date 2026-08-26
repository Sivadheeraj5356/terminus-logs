import gzip
import json
import os
import subprocess
from pathlib import Path

WORKSPACE = Path(os.environ.get("WORKSPACE", "/workspace"))
CMD = ["go", "run", str(WORKSPACE / "cmd/claimtower")]


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            if isinstance(row, str):
                f.write(row + "\n")
            else:
                f.write(json.dumps(row, separators=(",", ":")) + "\n")


def write_gzip_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")


def read_tsv(path: Path):
    return [line.rstrip("\n").split("\t") for line in path.read_text(encoding="utf-8").splitlines()]


def assert_pretty_json(path: Path):
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert raw == json.dumps(data, indent=2) + "\n"
    return data


def base_claim_report(tmp_path: Path):
    claims_path = tmp_path / "claims" / "claims.json"
    write_json(claims_path, {
        "as_of": "2026-06-15",
        "claim_count": 3,
        "claims": [
            {"claim_id": "CLM-A", "product": "auto", "loss_date": "2026-05-01", "status": "open", "reserve": 90000, "paid": 10000, "severity": 5, "handler": "Uma", "county": "north", "revision": 1, "age_days": 45, "source_file": "/tmp/a", "source_line": 1},
            {"claim_id": "CLM-B", "product": "auto", "loss_date": "2026-06-10", "status": "open", "reserve": 10000, "paid": 0, "severity": 2, "handler": "Ken", "county": "north", "revision": 1, "age_days": 5, "source_file": "/tmp/b", "source_line": 1},
            {"claim_id": "CLM-C", "product": "property", "loss_date": "2026-05-20", "status": "open", "reserve": 20000, "paid": 5000, "severity": 4, "handler": "Li", "county": "west", "revision": 1, "age_days": 26, "source_file": "/tmp/c", "source_line": 1},
        ],
        "totals": {"open_claims": 3, "reserve": 120000, "paid": 15000},
    })
    return claims_path


class TestMilestone2:
    def test_score_rules_duplicates_retractions_aliases_and_index_order(self, tmp_path):
        """Signal scoring applies rules, aliases, selected revisions, retractions, score math, and deterministic index ordering."""
        claims_path = base_claim_report(tmp_path)
        rules = tmp_path / "rules.tsv"
        rules.write_text("code\tbase_points\tage_days\tmultiplier\tlabel\nFRAUD\t30\t10\t5\tFraud watch\nRESERVE\t20\t30\t8\tReserve lift\n", encoding="utf-8")
        signals_root = tmp_path / "signals"
        write_jsonl(signals_root / "plain" / "a.signal.jsonl", [
            {"claim_id": "CLM-A", "signal_code": "FRAUD", "revision": 1, "observed_on": "2026-06-10", "strength": 3},
            {"id": "CLM-A", "code": "RESERVE", "rev": 2, "observed_on": "2026-06-12", "strength": 4},
            {"claim_id": "CLM-B", "signal_code": "FRAUD", "revision": 1, "observed_on": "2026-06-14", "strength": 5},
            {"claim_id": "CLM-C", "signal_code": "FRAUD", "revision": 1, "observed_on": "2026-06-01", "strength": 2},
            {"claim_id": "CLM-C", "signal_code": "FRAUD", "revision": 2, "observed_on": "2026-06-02", "strength": 2, "action": "retract"},
        ])
        write_gzip_jsonl(signals_root / "gz" / "b.signal.jsonl.gz", [
            {"claim_id": "CLM-A", "signal_code": "FRAUD", "revision": 0, "observed_on": "2026-06-09", "strength": 1},
        ])
        signals_out = tmp_path / "out" / "candidate_signals.tsv"
        index_out = tmp_path / "out" / "claim_signal_index.json"
        issues_out = tmp_path / "out" / "signal_issues.tsv"
        subprocess.run(CMD + ["score", "--claims-in", str(claims_path), "--signals-root", str(signals_root), "--rules", str(rules), "--signals-out", str(signals_out), "--index-out", str(index_out), "--issues-out", str(issues_out)], cwd=WORKSPACE, check=True, text=True)

        rows = read_tsv(signals_out)
        assert rows[0] == ["claim_id", "signal_code", "label", "score", "strength", "observed_on", "claim_severity", "age_days", "source_file", "source_line"]
        assert [r[:4] for r in rows[1:]] == [
            ["CLM-A", "FRAUD", "Fraud watch", "64"],
            ["CLM-A", "RESERVE", "Reserve lift", "59"],
            ["CLM-B", "FRAUD", "Fraud watch", "47"],
        ]
        plain_source = str((signals_root / "plain" / "a.signal.jsonl").resolve())
        assert rows[1:] == [
            ["CLM-A", "FRAUD", "Fraud watch", "64", "3", "2026-06-10", "5", "45", plain_source, "1"],
            ["CLM-A", "RESERVE", "Reserve lift", "59", "4", "2026-06-12", "5", "45", plain_source, "2"],
            ["CLM-B", "FRAUD", "Fraud watch", "47", "5", "2026-06-14", "2", "5", plain_source, "3"],
        ]
        index = assert_pretty_json(index_out)
        assert set(index) == {"as_of", "claim_count", "candidate_count", "claims"}
        assert index["as_of"] == "2026-06-15"
        assert index["claim_count"] == 3
        assert index["candidate_count"] == 3
        expected_claim_keys = {"claim_id", "product", "county", "severity", "reserve", "paid", "age_days", "total_score", "signals"}
        assert [set(c) for c in index["claims"]] == [expected_claim_keys, expected_claim_keys]
        assert [(c["claim_id"], c["product"], c["county"], c["severity"], c["reserve"], c["paid"], c["age_days"], c["total_score"]) for c in index["claims"]] == [
            ("CLM-A", "auto", "north", 5, 90000, 10000, 45, 123),
            ("CLM-B", "auto", "north", 2, 10000, 0, 5, 47),
        ]
        expected_signal_keys = {"code", "label", "score", "strength", "observed_on"}
        assert [set(s) for s in index["claims"][0]["signals"]] == [expected_signal_keys, expected_signal_keys]
        assert index["claims"][0]["signals"] == [
            {"code": "FRAUD", "label": "Fraud watch", "score": 64, "strength": 3, "observed_on": "2026-06-10"},
            {"code": "RESERVE", "label": "Reserve lift", "score": 59, "strength": 4, "observed_on": "2026-06-12"},
        ]
        assert index["claims"][1]["signals"] == [
            {"code": "FRAUD", "label": "Fraud watch", "score": 47, "strength": 5, "observed_on": "2026-06-14"},
        ]
        assert read_tsv(issues_out) == [["source_file", "source_line", "kind", "entity", "detail"]]
        assert index_out.read_bytes().endswith(b"\n") and signals_out.read_bytes().endswith(b"\n")

    def test_score_invalid_signals_missing_claims_missing_rules_and_required_flags(self, tmp_path):
        """Malformed signal inputs recover into issue rows with the documented kinds while good candidates still score."""
        claims_path = base_claim_report(tmp_path)
        rules = tmp_path / "rules.tsv"
        rules.write_text("code\tbase_points\tage_days\tmultiplier\tlabel\nFRAUD\t30\t10\t5\tFraud watch\n", encoding="utf-8")
        signals_root = tmp_path / "signals"
        bad_file = signals_root / "bad.signal.jsonl"
        write_jsonl(bad_file, [
            "{bad json",
            ["not", "object"],
            {"claim_id": "CLM-A", "signal_code": "FRAUD", "revision": 1, "observed_on": "2026-06-13", "strength": 3},
            {"claim_id": "CLM-MISSING", "signal_code": "FRAUD", "revision": 1, "observed_on": "2026-06-13", "strength": 3},
            {"claim_id": "CLM-A", "signal_code": "UNKNOWN", "revision": 1, "observed_on": "2026-06-13", "strength": 3},
            {"claim_id": "CLM-A", "signal_code": "FRAUD", "revision": 2, "observed_on": "2026-07-01", "strength": 3},
            {"claim_id": "CLM-B", "signal_code": "FRAUD", "revision": 1, "observed_on": "2026-06-13", "strength": 9},
            {"claim_id": "CLM-B", "revision": 2, "observed_on": "2026-06-13", "strength": 3},
            {"claim_id": "CLM-B", "signal_code": "FRAUD", "observed_on": "2026-06-13", "strength": 3},
            {"claim_id": "CLM-B", "signal_code": "FRAUD", "revision": "new", "observed_on": "2026-06-13", "strength": 3},
            {"claim_id": "CLM-B", "signal_code": "FRAUD", "revision": 3, "observed_on": 20260613, "strength": 3},
            {"claim_id": "CLM-B", "signal_code": "FRAUD", "revision": 4, "observed_on": "2026-06-13", "strength": "high"},
        ])
        signals_out = tmp_path / "deep" / "candidate_signals.tsv"
        index_out = tmp_path / "deep" / "claim_signal_index.json"
        issues_out = tmp_path / "deep" / "signal_issues.tsv"
        subprocess.run(CMD + ["score", "--claims-in", str(claims_path), "--signals-root", str(signals_root), "--rules", str(rules), "--signals-out", str(signals_out), "--index-out", str(index_out), "--issues-out", str(issues_out)], cwd=WORKSPACE, check=True, text=True)
        assert [r[0:2] for r in read_tsv(signals_out)[1:]] == [["CLM-A", "FRAUD"]]
        issue_rows = read_tsv(issues_out)
        assert issue_rows[0] == ["source_file", "source_line", "kind", "entity", "detail"]
        kinds = [row[2] for row in issue_rows[1:]]
        assert "invalid_signal" in kinds and "missing_claim" in kinds and "missing_rule" in kinds
        assert {row[4] for row in issue_rows[1:]} >= {"bad_json", "not_object", "observed_on_after_as_of", "strength", "signal_code", "revision", "observed_on", "FRAUD", "UNKNOWN"}
        issue_by_line = {int(row[1]): row[4] for row in issue_rows[1:] if row[2] == "invalid_signal"}
        assert issue_by_line[8] == "signal_code"
        assert issue_by_line[9] == "revision"
        assert issue_by_line[10] == "revision"
        assert issue_by_line[11] == "observed_on"
        assert issue_by_line[12] == "strength"
        assert all(row[0] == str(bad_file.resolve()) for row in issue_rows[1:])
        assert [int(row[1]) for row in issue_rows[1:]] == sorted(int(row[1]) for row in issue_rows[1:])

        missing = subprocess.run(CMD + ["score", "--claims-in", str(claims_path)], cwd=WORKSPACE, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert missing.returncode != 0


    def test_score_candidate_tsv_and_index_json_schema_all_fields(self, tmp_path):
        """Candidate TSV and nested index JSON expose every documented signal and claim field with exact names and values."""
        claims_path = base_claim_report(tmp_path)
        rules = tmp_path / "rules.tsv"
        rules.write_text(
            "code\tbase_points\tage_days\tmultiplier\tlabel\n"
            "LARGE\t20\t30\t7\tLarge loss\n"
            "LIT\t25\t0\t4\tLitigation watch\n",
            encoding="utf-8",
        )
        signals_root = tmp_path / "signals_schema"
        signal_file = signals_root / "schema.signal.jsonl"
        write_jsonl(signal_file, [
            {"claim_id": "CLM-A", "signal_code": "LARGE", "revision": 1, "observed_on": "2026-06-11", "strength": 5},
            {"claim_id": "CLM-A", "signal_code": "LIT", "revision": 1, "observed_on": "2026-06-12", "strength": 1},
        ])
        signals_out = tmp_path / "schema" / "candidate_signals.tsv"
        index_out = tmp_path / "schema" / "claim_signal_index.json"
        issues_out = tmp_path / "schema" / "signal_issues.tsv"
        subprocess.run(
            CMD + [
                "score",
                "--claims-in", str(claims_path),
                "--signals-root", str(signals_root),
                "--rules", str(rules),
                "--signals-out", str(signals_out),
                "--index-out", str(index_out),
                "--issues-out", str(issues_out),
            ],
            cwd=WORKSPACE,
            check=True,
            text=True,
        )

        expected_source = str(signal_file.resolve())
        rows = read_tsv(signals_out)
        assert rows == [
            ["claim_id", "signal_code", "label", "score", "strength", "observed_on", "claim_severity", "age_days", "source_file", "source_line"],
            ["CLM-A", "LARGE", "Large loss", "60", "5", "2026-06-11", "5", "45", expected_source, "1"],
            ["CLM-A", "LIT", "Litigation watch", "54", "1", "2026-06-12", "5", "45", expected_source, "2"],
        ]

        index = assert_pretty_json(index_out)
        assert index == {
            "as_of": "2026-06-15",
            "claim_count": 3,
            "candidate_count": 2,
            "claims": [
                {
                    "claim_id": "CLM-A",
                    "product": "auto",
                    "county": "north",
                    "severity": 5,
                    "reserve": 90000,
                    "paid": 10000,
                    "age_days": 45,
                    "total_score": 114,
                    "signals": [
                        {"code": "LARGE", "label": "Large loss", "score": 60, "strength": 5, "observed_on": "2026-06-11"},
                        {"code": "LIT", "label": "Litigation watch", "score": 54, "strength": 1, "observed_on": "2026-06-12"},
                    ],
                }
            ],
        }
        assert read_tsv(issues_out) == [["source_file", "source_line", "kind", "entity", "detail"]]

    def test_score_same_revision_signal_tiebreak_and_malformed_rules_recovery(self, tmp_path):
        """Signal scoring selects same-revision ties by source path and line, and malformed rules rows recover as issue rows."""
        claims_path = base_claim_report(tmp_path)
        rules = tmp_path / "rules.tsv"
        rules.write_text(
            "code\tbase_points\tage_days\tmultiplier\tlabel\n"
            "TIE\t10\t0\t1\tTie rule\n"
            "BROKEN\tbad\t0\t1\tBroken numeric\n"
            "\t5\t0\t1\tBlank code\n"
            "SHORT\t1\t2\n",
            encoding="utf-8",
        )
        signals_root = tmp_path / "signals_tie"
        later_file = signals_root / "z_later.signal.jsonl"
        earlier_file = signals_root / "a_earlier.signal.jsonl"
        write_jsonl(later_file, [
            {"claim_id": "CLM-A", "signal_code": "TIE", "revision": 7, "observed_on": "2026-06-14", "strength": 1},
        ])
        write_jsonl(earlier_file, [
            {"claim_id": "CLM-A", "signal_code": "TIE", "revision": 7, "observed_on": "2026-06-13", "strength": 5},
            {"claim_id": "CLM-B", "signal_code": "BROKEN", "revision": 1, "observed_on": "2026-06-13", "strength": 3},
        ])

        signals_out = tmp_path / "tie" / "candidate_signals.tsv"
        index_out = tmp_path / "tie" / "claim_signal_index.json"
        issues_out = tmp_path / "tie" / "signal_issues.tsv"
        subprocess.run(
            CMD + [
                "score",
                "--claims-in", str(claims_path),
                "--signals-root", str(signals_root),
                "--rules", str(rules),
                "--signals-out", str(signals_out),
                "--index-out", str(index_out),
                "--issues-out", str(issues_out),
            ],
            cwd=WORKSPACE,
            check=True,
            text=True,
        )

        rows = read_tsv(signals_out)
        assert rows == [
            ["claim_id", "signal_code", "label", "score", "strength", "observed_on", "claim_severity", "age_days", "source_file", "source_line"],
            ["CLM-A", "TIE", "Tie rule", "44", "5", "2026-06-13", "5", "45", str(earlier_file.resolve()), "1"],
        ]
        index = assert_pretty_json(index_out)
        assert index["candidate_count"] == 1
        assert index["claims"][0]["signals"] == [
            {"code": "TIE", "label": "Tie rule", "score": 44, "strength": 5, "observed_on": "2026-06-13"}
        ]

        issue_rows = read_tsv(issues_out)
        assert issue_rows[0] == ["source_file", "source_line", "kind", "entity", "detail"]
        assert [row for row in issue_rows[1:] if row[0] == str(rules.resolve())] == [
            [str(rules.resolve()), "3", "invalid_signal", "BROKEN", "rules_row"],
            [str(rules.resolve()), "4", "invalid_signal", "", "rules_row"],
            [str(rules.resolve()), "5", "invalid_signal", "SHORT", "rules_row"],
        ]
        assert [row for row in issue_rows[1:] if row[2] == "missing_rule"] == [
            [str(earlier_file.resolve()), "2", "missing_rule", "CLM-B", "BROKEN"]
        ]

    def test_score_bad_rules_header_is_recoverable_and_emits_header_issue(self, tmp_path):
        """A malformed rules TSV header emits the documented rules_header issue while valid-looking signal rows remain recoverable."""
        claims_path = base_claim_report(tmp_path)
        rules = tmp_path / "bad_rules.tsv"
        rules.write_text(
            "code\tbase_points\tage_days\tlabel\n"
            "FRAUD\t30\t10\tFraud watch\n",
            encoding="utf-8",
        )
        signals_root = tmp_path / "signals_header"
        signal_file = signals_root / "header.signal.jsonl"
        write_jsonl(signal_file, [
            {"claim_id": "CLM-A", "signal_code": "FRAUD", "revision": 1, "observed_on": "2026-06-13", "strength": 3},
        ])
        signals_out = tmp_path / "bad_header" / "candidate_signals.tsv"
        index_out = tmp_path / "bad_header" / "claim_signal_index.json"
        issues_out = tmp_path / "bad_header" / "signal_issues.tsv"
        subprocess.run(
            CMD + [
                "score",
                "--claims-in", str(claims_path),
                "--signals-root", str(signals_root),
                "--rules", str(rules),
                "--signals-out", str(signals_out),
                "--index-out", str(index_out),
                "--issues-out", str(issues_out),
            ],
            cwd=WORKSPACE,
            check=True,
            text=True,
        )

        assert read_tsv(signals_out) == [["claim_id", "signal_code", "label", "score", "strength", "observed_on", "claim_severity", "age_days", "source_file", "source_line"]]
        assert_pretty_json(index_out) == {"as_of": "2026-06-15", "claim_count": 3, "candidate_count": 0, "claims": []}
        assert read_tsv(issues_out) == [
            ["source_file", "source_line", "kind", "entity", "detail"],
            [str(rules.resolve()), "1", "invalid_signal", "", "rules_header"],
            [str(rules.resolve()), "2", "invalid_signal", "FRAUD", "rules_row"],
            [str(signal_file.resolve()), "1", "missing_rule", "CLM-A", "FRAUD"],
        ]

