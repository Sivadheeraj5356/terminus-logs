import json
import hashlib
import os
import subprocess
import tempfile

REPORT_PATH = "/app/output/report.json"
DATA_PATH = "/app/data/rules.json"
BINARY = "/app/target/release/prometheus-rule-checker"


def get_report():
    with open(REPORT_PATH) as f:
        return json.load(f)


class TestBinaryCompiles:
    def test_binary_exists(self):
        assert os.path.exists(BINARY), f"Binary not found at {BINARY}"

    def test_binary_executable(self):
        assert os.access(BINARY, os.X_OK), f"Binary at {BINARY} is not executable"

    def test_binary_runs_successfully(self):
        result = subprocess.run([BINARY], capture_output=True, timeout=30)
        assert result.returncode == 0, f"Tool failed: {result.stderr.decode()}"


class TestReportStructure:
    def test_report_exists(self):
        assert os.path.exists(REPORT_PATH), "No report.json produced"

    def test_report_has_required_keys(self):
        report = get_report()
        required = {"total_rule_groups", "total_rules", "valid_rules", "invalid_rules", "groups", "errors"}
        missing = required - set(report.keys())
        assert not missing, f"Report missing fields: {missing}"

    def test_total_rule_groups(self):
        report = get_report()
        assert report["total_rule_groups"] == 4

    def test_total_rules(self):
        report = get_report()
        assert report["total_rules"] == 15

    def test_valid_rules(self):
        report = get_report()
        assert report["valid_rules"] == 12

    def test_invalid_rules(self):
        report = get_report()
        assert report["invalid_rules"] == 3

    def test_no_errors(self):
        report = get_report()
        assert report["errors"] == [], f"Unexpected errors: {report['errors']}"


class TestGroupReports:
    def test_all_groups_present(self):
        report = get_report()
        names = {g["name"] for g in report["groups"]}
        expected = {"node_rules", "app_rules", "infra_rules", "db_rules"}
        assert names == expected, f"Missing groups: {expected - names}"

    def test_node_rules_breakdown(self):
        report = get_report()
        g = next(g for g in report["groups"] if g["name"] == "node_rules")
        assert g["total_rules"] == 3
        assert g["valid_rules"] == 3
        assert g["invalid_rules"] == 0

    def test_app_rules_breakdown(self):
        report = get_report()
        g = next(g for g in report["groups"] if g["name"] == "app_rules")
        assert g["total_rules"] == 7
        assert g["valid_rules"] == 5
        assert g["invalid_rules"] == 2

    def test_infra_rules_breakdown(self):
        report = get_report()
        g = next(g for g in report["groups"] if g["name"] == "infra_rules")
        assert g["total_rules"] == 2
        assert g["valid_rules"] == 1
        assert g["invalid_rules"] == 1

    def test_db_rules_breakdown(self):
        report = get_report()
        g = next(g for g in report["groups"] if g["name"] == "db_rules")
        assert g["total_rules"] == 3
        assert g["valid_rules"] == 3
        assert g["invalid_rules"] == 0


class TestIndependentVerification:
    def test_data_file_integrity(self):
        with open(DATA_PATH, "rb") as f:
            content = f.read()
        h = hashlib.sha256(content).hexdigest()
        expected = "ff986bf0886ca469d161f1bf1233323d2e521d449c6d3090704b2b6a96a073ce"
        assert h == expected, f"Data file hash mismatch: {h}"

    def test_rerun_consistency(self):
        subprocess.run([BINARY], capture_output=True, timeout=30)
        data1 = get_report()
        subprocess.run([BINARY], capture_output=True, timeout=30)
        data2 = get_report()
        assert data1 == data2

    def test_independent_validity_check(self):
        report = get_report()
        groups = report["groups"]
        total_valid = sum(g["valid_rules"] for g in groups)
        total_invalid = sum(g["invalid_rules"] for g in groups)
        total_rules = sum(g["total_rules"] for g in groups)
        assert total_valid == report["valid_rules"]
        assert total_invalid == report["invalid_rules"]
        assert total_rules == report["total_rules"]
        assert total_valid + total_invalid == total_rules


class TestHiddenData:
    BINARY = BINARY

    @staticmethod
    def hidden_data():
        return {
            "groups": [
                {
                    "name": "hidden_group",
                    "rules": [
                        {"type": "recording", "record": "my_metric", "expr": "rate(foo[5m])"},
                        {"type": "alert", "alert": "9BadAlert", "expr": "bar > 0"},
                        {"type": "alert", "alert": "ValidAlert", "expr": "baz > 0{env=\"prod\"}", "for_duration": "5m"},
                    ]
                }
            ]
        }

    def test_hidden_data_correctness(self):
        data = self.hidden_data()
        with tempfile.TemporaryDirectory() as tmp:
            data_path = os.path.join(tmp, "test_data.json")
            out_path = os.path.join(tmp, "report.json")
            with open(data_path, "w") as f:
                json.dump(data, f)

            env = os.environ.copy()
            env["APP_DATA_PATH"] = data_path
            env["APP_OUTPUT_PATH"] = out_path
            env["APP_CONFIG_PATH"] = "/app/config/default.toml"

            result = subprocess.run([self.BINARY], capture_output=True, timeout=30, env=env)
            assert result.returncode == 0, f"Binary failed: {result.stderr.decode()}"

            with open(out_path) as f:
                report = json.load(f)

            assert report["total_rule_groups"] == 1
            assert report["total_rules"] == 3
            assert report["valid_rules"] == 2
            assert report["invalid_rules"] == 1
            assert report["errors"] == []

            g = report["groups"][0]
            assert g["name"] == "hidden_group"
            assert g["total_rules"] == 3
            assert g["valid_rules"] == 2
            assert g["invalid_rules"] == 1

    def test_hidden_data_rerun_consistency(self):
        data = self.hidden_data()
        with tempfile.TemporaryDirectory() as tmp:
            data_path = os.path.join(tmp, "test_data.json")
            out_path = os.path.join(tmp, "report.json")
            with open(data_path, "w") as f:
                json.dump(data, f)

            env = os.environ.copy()
            env["APP_DATA_PATH"] = data_path
            env["APP_OUTPUT_PATH"] = out_path
            env["APP_CONFIG_PATH"] = "/app/config/default.toml"

            subprocess.run([self.BINARY], capture_output=True, timeout=30, env=env)
            with open(out_path) as f:
                r1 = json.load(f)

            subprocess.run([self.BINARY], capture_output=True, timeout=30, env=env)
            with open(out_path) as f:
                r2 = json.load(f)

            assert r1 == r2
