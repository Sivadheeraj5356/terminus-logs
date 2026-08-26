import json
import os
import subprocess
from pathlib import Path

WORKSPACE = Path(os.environ.get("WORKSPACE", "/workspace"))
CMD = ["go", "run", str(WORKSPACE / "cmd/claimtower")]


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def read_tsv(path: Path):
    return [line.rstrip("\n").split("\t") for line in path.read_text(encoding="utf-8").splitlines()]


def assert_pretty_json(path: Path):
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert raw == json.dumps(data, indent=2) + "\n"
    return data


def make_claim(claim_id, product, county, score, code="SIG", signal_count=1):
    return {
        "claim_id": claim_id,
        "product": product,
        "county": county,
        "severity": 3,
        "reserve": 10000,
        "paid": 0,
        "age_days": 30,
        "total_score": score,
        "signals": [
            {
                "code": code if i == 0 else f"{code}{i}",
                "label": "label",
                "score": score // signal_count,
                "strength": 3,
                "observed_on": "2026-06-10",
            }
            for i in range(signal_count)
        ],
    }


def write_index(path: Path, claims):
    write_json(
        path,
        {
            "as_of": "2026-06-15",
            "claim_count": len(claims),
            "candidate_count": sum(len(c["signals"]) for c in claims),
            "claims": claims,
        },
    )


def write_plan(path: Path, teams, *, max_total_score=100000, limits=None, skills=None, windows=None,
               blocked=None, requires=None, precedence=None, same_team=None, different_team=None,
               bonuses=None):
    if limits is None:
        limits = {team: {"day1": 100000, "day2": 100000} for team in teams}
    if skills is None:
        skills = {team: ["*"] for team in teams}
    write_json(
        path,
        {
            "max_total_score": max_total_score,
            "team_day_score_limits": limits,
            "team_signal_skills": skills,
            "claim_windows": windows or {},
            "blocked_same_day": blocked or [],
            "requires": requires or [],
            "precedence": precedence or [],
            "same_team_groups": same_team or [],
            "different_team_pairs": different_team or [],
            "bundle_bonuses": bonuses or [],
        },
    )


def run_assign(index_path, capacity, plan, assignments_out, summary_out, issues_out, check=True):
    return subprocess.run(
        CMD
        + [
            "assign",
            "--index-in",
            str(index_path),
            "--capacity",
            str(capacity),
            "--plan",
            str(plan),
            "--assignments-out",
            str(assignments_out),
            "--summary-out",
            str(summary_out),
            "--issues-out",
            str(issues_out),
        ],
        cwd=WORKSPACE,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


class TestMilestone3:
    def test_assign_lanes_capacity_score_limits_hold_backlog_and_summary(self, tmp_path):
        """Assignment preserves lane order while optimizing eligible team/day placements and reporting count and score usage."""
        index_path = tmp_path / "input" / "index.json"
        claims = [
            make_claim("CLM-A", "auto", "north", 120, "HOT", 2),
            make_claim("CLM-B", "auto", "north", 90, "HOT"),
            make_claim("CLM-C", "property", "west", 70, "PROP"),
            make_claim("CLM-D", "auto", "north", 45, "HOT"),
            make_claim("CLM-E", "liability", "south", 60, "LIAB"),
            make_claim("CLM-F", "auto", "north", 65, "HOT"),
        ]
        write_index(index_path, claims)
        capacity = tmp_path / "capacity.tsv"
        capacity.write_text(
            "team\tproducts\tcounties\tday1\tday2\trisk_ceiling\tactive\n"
            "TeamA\tauto\tnorth\t1\t1\t200\ttrue\n"
            "InactiveMega\tauto\tnorth\t9\t9\t200\tfalse\n"
            "TeamB\tauto\t*\t1\t0\t95\tyes\n"
            "TeamC\tproperty\twest\t0\t1\t80\t1\n"
            "TeamD\tliability\tsouth\t1\t1\t50\ttrue\n",
            encoding="utf-8",
        )
        plan = tmp_path / "plan.json"
        teams = ["TeamA", "InactiveMega", "TeamB", "TeamC", "TeamD"]
        write_plan(
            plan,
            teams,
            limits={
                "TeamA": {"day1": 120, "day2": 70},
                "InactiveMega": {"day1": 999, "day2": 999},
                "TeamB": {"day1": 95, "day2": 0},
                "TeamC": {"day1": 0, "day2": 80},
                "TeamD": {"day1": 100, "day2": 100},
            },
        )
        assignments_out = tmp_path / "nested" / "out" / "assignments.tsv"
        summary_out = tmp_path / "nested" / "out" / "summary.json"
        issues_out = tmp_path / "nested" / "audit" / "assign_issues.tsv"
        run_assign(index_path, capacity, plan, assignments_out, summary_out, issues_out)

        assert read_tsv(assignments_out) == [
            ["claim_id", "lane", "status", "team", "day", "total_score", "product", "county", "signal_count"],
            ["CLM-A", "expedited", "assigned", "TeamA", "day1", "120", "auto", "north", "2"],
            ["CLM-B", "expedited", "assigned", "TeamB", "day1", "90", "auto", "north", "1"],
            ["CLM-C", "standard", "assigned", "TeamC", "day2", "70", "property", "west", "1"],
            ["CLM-F", "standard", "assigned", "TeamA", "day2", "65", "auto", "north", "1"],
            ["CLM-E", "standard", "hold_no_team", "", "", "60", "liability", "south", "1"],
            ["CLM-D", "monitor", "backlog_capacity", "", "", "45", "auto", "north", "1"],
        ]
        summary = assert_pretty_json(summary_out)
        assert set(summary) == {"assigned_count", "backlog_count", "hold_count", "plan_value", "bonus_value", "total_score_used", "lanes", "days", "teams"}
        assert all(set(day) == {"day", "assigned_count", "score_used"} for day in summary["days"])
        assert all(set(team) == {"team", "day1_used", "day2_used", "day1_score_used", "day2_score_used", "remaining_day1", "remaining_day2", "remaining_day1_score", "remaining_day2_score", "assigned_claims"} for team in summary["teams"])
        assert summary["assigned_count"] == 4
        assert summary["backlog_count"] == 1
        assert summary["hold_count"] == 1
        assert summary["plan_value"] == 345
        assert summary["bonus_value"] == 0
        assert summary["total_score_used"] == 345
        assert summary["lanes"] == {"expedited": 2, "standard": 3, "monitor": 1}
        assert summary["days"] == [
            {"day": "day1", "assigned_count": 2, "score_used": 210},
            {"day": "day2", "assigned_count": 2, "score_used": 135},
        ]
        teams_out = {t["team"]: t for t in summary["teams"]}
        assert teams_out["TeamA"] == {
            "team": "TeamA",
            "day1_used": 1,
            "day2_used": 1,
            "day1_score_used": 120,
            "day2_score_used": 65,
            "remaining_day1": 0,
            "remaining_day2": 0,
            "remaining_day1_score": 0,
            "remaining_day2_score": 5,
            "assigned_claims": ["CLM-A", "CLM-F"],
        }
        assert teams_out["InactiveMega"]["assigned_claims"] == []
        assert teams_out["InactiveMega"]["remaining_day1"] == 9
        assert read_tsv(issues_out) == [
            ["source_file", "source_line", "kind", "entity", "detail"],
            [str(capacity.resolve()), "0", "no_team", "CLM-E", "liability/south"],
        ]

    def test_capacity_recovery_determinism_parent_dirs_and_required_flags(self, tmp_path):
        """Bad capacity rows remain recoverable, a bad header still allows positional rows, and repeated runs are byte-identical."""
        index_path = tmp_path / "index.json"
        write_index(index_path, [make_claim("CLM-X", "auto", "east", 55, "A"), make_claim("CLM-Y", "auto", "east", 52, "B")])
        capacity = tmp_path / "bad_capacity.tsv"
        capacity.write_text(
            "team\tproducts\tcounties\tday1\tday2\trisk_ceiling\tactive\n"
            "BadDay\tauto\teast\tx\t0\t99\ttrue\n"
            "BadActive\tauto\teast\t1\t0\t99\tmaybe\n"
            "EastDesk\tauto\teast\t1\t0\t99\ttrue\n",
            encoding="utf-8",
        )
        plan = tmp_path / "plan.json"
        write_plan(plan, ["EastDesk"], limits={"EastDesk": {"day1": 60, "day2": 0}})
        outputs = []
        for name in ["run1", "run2"]:
            a, s, i = tmp_path / name / "a.tsv", tmp_path / name / "s.json", tmp_path / name / "i.tsv"
            run_assign(index_path, capacity, plan, a, s, i)
            outputs.append((a, s, i))
        assert outputs[0][0].read_bytes() == outputs[1][0].read_bytes()
        assert outputs[0][1].read_bytes() == outputs[1][1].read_bytes()
        assert outputs[0][2].read_bytes() == outputs[1][2].read_bytes()
        assert [r[2:5] for r in read_tsv(outputs[0][2])[1:]] == [
            ["invalid_capacity", "BadDay", "row"],
            ["invalid_capacity", "BadActive", "row"],
        ]
        assert [r[:5] for r in read_tsv(outputs[0][0])[1:]] == [
            ["CLM-X", "standard", "assigned", "EastDesk", "day1"],
            ["CLM-Y", "standard", "backlog_capacity", "", ""],
        ]

        bad_header = tmp_path / "bad_header.tsv"
        bad_header.write_text(
            "team\tproducts\tcounties\tday_one\tday2\trisk_ceiling\tactive\n"
            "HeaderDesk\tauto\teast\t1\t0\t99\tyes\n",
            encoding="utf-8",
        )
        header_plan = tmp_path / "header_plan.json"
        write_plan(header_plan, ["HeaderDesk"], limits={"HeaderDesk": {"day1": 60, "day2": 0}})
        ha, hs, hi = tmp_path / "header" / "a.tsv", tmp_path / "header" / "s.json", tmp_path / "header" / "i.tsv"
        run_assign(index_path, bad_header, header_plan, ha, hs, hi)
        assert read_tsv(hi) == [
            ["source_file", "source_line", "kind", "entity", "detail"],
            [str(bad_header.resolve()), "1", "invalid_capacity", "", "header"],
        ]
        assert read_tsv(ha)[1][:5] == ["CLM-X", "standard", "assigned", "HeaderDesk", "day1"]

        missing = subprocess.run(
            CMD + ["assign", "--index-in", str(index_path), "--capacity", str(capacity)],
            cwd=WORKSPACE,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert missing.returncode != 0

    def test_inactive_team_is_summarized_but_never_assigned(self, tmp_path):
        """Inactive valid teams retain unused capacity in the summary but are excluded from static eligibility."""
        index_path = tmp_path / "index.json"
        write_index(index_path, [make_claim("CLM-I", "auto", "east", 88, "HOT")])
        capacity = tmp_path / "capacity.tsv"
        capacity.write_text(
            "team\tproducts\tcounties\tday1\tday2\trisk_ceiling\tactive\n"
            "InactiveBest\tauto\teast\t9\t9\t200\tfalse\n"
            "ActiveDesk\tauto\teast\t1\t0\t200\ttrue\n",
            encoding="utf-8",
        )
        plan = tmp_path / "plan.json"
        write_plan(
            plan,
            ["InactiveBest", "ActiveDesk"],
            limits={"InactiveBest": {"day1": 900, "day2": 900}, "ActiveDesk": {"day1": 100, "day2": 0}},
        )
        a, s, i = tmp_path / "out" / "a.tsv", tmp_path / "out" / "s.json", tmp_path / "out" / "i.tsv"
        run_assign(index_path, capacity, plan, a, s, i)
        assert read_tsv(a)[1] == ["CLM-I", "expedited", "assigned", "ActiveDesk", "day1", "88", "auto", "east", "1"]
        teams = {t["team"]: t for t in assert_pretty_json(s)["teams"]}
        assert teams["InactiveBest"]["day1_used"] == 0
        assert teams["InactiveBest"]["remaining_day1"] == 9
        assert teams["InactiveBest"]["remaining_day1_score"] == 900
        assert teams["InactiveBest"]["assigned_claims"] == []
        assert read_tsv(i) == [["source_file", "source_line", "kind", "entity", "detail"]]

    def test_joint_optimizer_beats_greedy_with_skills_windows_bundles_and_dependencies(self, tmp_path):
        """The selected plan is globally optimal rather than a greedy score ranking under skills, windows, bundles, and dependencies."""
        index_path = tmp_path / "index.json"
        claims = [
            make_claim("A", "auto", "north", 110, "HOT"),
            make_claim("B", "auto", "north", 105, "HOT"),
            make_claim("C", "property", "west", 80, "FRAUD"),
            make_claim("D", "property", "west", 75, "FRAUD"),
            make_claim("E", "auto", "north", 65, "RESERVE"),
            make_claim("F", "auto", "north", 60, "RESERVE"),
            make_claim("G", "auto", "north", 55, "HOT"),
        ]
        write_index(index_path, claims)
        capacity = tmp_path / "capacity.tsv"
        capacity.write_text(
            "team\tproducts\tcounties\tday1\tday2\trisk_ceiling\tactive\n"
            "Alpha\t*\t*\t2\t2\t200\ttrue\n"
            "Beta\t*\t*\t2\t2\t200\ttrue\n",
            encoding="utf-8",
        )
        plan = tmp_path / "plan.json"
        write_plan(
            plan,
            ["Alpha", "Beta"],
            max_total_score=310,
            limits={"Alpha": {"day1": 190, "day2": 170}, "Beta": {"day1": 170, "day2": 130}},
            skills={"Alpha": ["HOT", "FRAUD"], "Beta": ["HOT", "RESERVE"]},
            windows={"A": ["day1"], "C": ["day1"], "D": ["day2"], "E": ["day1"], "F": ["day2"]},
            blocked=[["B", "C"]],
            requires=[["A", "E"]],
            precedence=[{"before": "E", "after": "F", "min_day_gap": 1}],
            same_team=[["C", "D"]],
            different_team=[["A", "B"]],
            bonuses=[
                {"claims": ["C", "D"], "bonus": 90, "same_day": False},
                {"claims": ["E", "F"], "bonus": 70, "same_day": False},
                {"claims": ["A", "E"], "bonus": 20, "same_day": True},
            ],
        )
        a, s, i = tmp_path / "out" / "a.tsv", tmp_path / "out" / "s.json", tmp_path / "out" / "i.tsv"
        run_assign(index_path, capacity, plan, a, s, i)
        assigned = {row[0]: (row[3], row[4]) for row in read_tsv(a)[1:] if row[2] == "assigned"}
        assert assigned == {
            "C": ("Alpha", "day1"),
            "D": ("Alpha", "day2"),
            "E": ("Beta", "day1"),
            "F": ("Beta", "day2"),
        }
        summary = assert_pretty_json(s)
        assert summary["plan_value"] == 440
        assert summary["bonus_value"] == 160
        assert summary["total_score_used"] == 280
        assert summary["assigned_count"] == 4
        assert summary["days"] == [
            {"day": "day1", "assigned_count": 2, "score_used": 145},
            {"day": "day2", "assigned_count": 2, "score_used": 135},
        ]
        assert read_tsv(i) == [["source_file", "source_line", "kind", "entity", "detail"]]

    def test_requires_changes_the_selected_portfolio(self, tmp_path):
        """A high-scoring dependent is excluded when its required prerequisite would break the global score budget."""
        index_path = tmp_path / "index.json"
        write_index(
            index_path,
            [
                make_claim("A", "auto", "north", 100, "HOT"),
                make_claim("P", "auto", "north", 20, "HOT"),
                make_claim("X", "auto", "north", 95, "HOT"),
            ],
        )
        capacity = tmp_path / "capacity.tsv"
        capacity.write_text(
            "team\tproducts\tcounties\tday1\tday2\trisk_ceiling\tactive\n"
            "Alpha\t*\t*\t2\t2\t200\ttrue\n",
            encoding="utf-8",
        )
        plan = tmp_path / "plan.json"
        write_plan(plan, ["Alpha"], max_total_score=110, requires=[["A", "P"]])
        a, s, i = tmp_path / "out" / "a.tsv", tmp_path / "out" / "s.json", tmp_path / "out" / "i.tsv"
        run_assign(index_path, capacity, plan, a, s, i)
        assigned = [row[0] for row in read_tsv(a)[1:] if row[2] == "assigned"]
        assert assigned == ["X"]
        summary = assert_pretty_json(s)
        assert summary["plan_value"] == 95
        assert summary["total_score_used"] == 95
        assert read_tsv(i) == [["source_file", "source_line", "kind", "entity", "detail"]]

    def test_blocked_precedence_and_same_day_bonus_change_days(self, tmp_path):
        """Precedence and same-day blocking force day placements, and a same-day bonus is withheld when its claims are separated."""
        index_path = tmp_path / "index.json"
        write_index(
            index_path,
            [
                make_claim("P", "auto", "north", 50, "HOT"),
                make_claim("Q", "auto", "north", 45, "HOT"),
                make_claim("R", "auto", "north", 40, "HOT"),
            ],
        )
        capacity = tmp_path / "capacity.tsv"
        capacity.write_text(
            "team\tproducts\tcounties\tday1\tday2\trisk_ceiling\tactive\n"
            "Alpha\t*\t*\t3\t3\t200\ttrue\n",
            encoding="utf-8",
        )
        plan = tmp_path / "plan.json"
        write_plan(
            plan,
            ["Alpha"],
            max_total_score=200,
            blocked=[["P", "R"]],
            precedence=[{"before": "P", "after": "Q", "min_day_gap": 1}],
            bonuses=[{"claims": ["P", "Q"], "bonus": 100, "same_day": True}],
        )
        a, s, i = tmp_path / "out" / "a.tsv", tmp_path / "out" / "s.json", tmp_path / "out" / "i.tsv"
        run_assign(index_path, capacity, plan, a, s, i)
        assigned = {row[0]: row[4] for row in read_tsv(a)[1:] if row[2] == "assigned"}
        assert assigned == {"P": "day1", "Q": "day2", "R": "day2"}
        summary = assert_pretty_json(s)
        assert summary["total_score_used"] == 135
        assert summary["bonus_value"] == 0
        assert summary["plan_value"] == 135
        assert read_tsv(i) == [["source_file", "source_line", "kind", "entity", "detail"]]

    def test_team_continuity_separation_and_schedule_key_tie_break(self, tmp_path):
        """Different-team and same-team relationships combine with the lexicographic schedule key to select exact teams."""
        index_path = tmp_path / "index.json"
        write_index(
            index_path,
            [
                make_claim("A", "auto", "north", 90, "HOT"),
                make_claim("B", "auto", "north", 85, "HOT"),
                make_claim("C", "auto", "north", 40, "RESERVE"),
                make_claim("D", "auto", "north", 35, "RESERVE"),
            ],
        )
        capacity = tmp_path / "capacity.tsv"
        capacity.write_text(
            "team\tproducts\tcounties\tday1\tday2\trisk_ceiling\tactive\n"
            "Alpha\t*\t*\t1\t1\t200\ttrue\n"
            "Beta\t*\t*\t3\t1\t200\ttrue\n",
            encoding="utf-8",
        )
        plan = tmp_path / "plan.json"
        write_plan(
            plan,
            ["Alpha", "Beta"],
            max_total_score=250,
            limits={"Alpha": {"day1": 100, "day2": 100}, "Beta": {"day1": 200, "day2": 100}},
            windows={"A": ["day1"], "B": ["day1"], "C": ["day1"], "D": ["day2"]},
            same_team=[["C", "D"]],
            different_team=[["A", "B"]],
        )
        a, s, i = tmp_path / "out" / "a.tsv", tmp_path / "out" / "s.json", tmp_path / "out" / "i.tsv"
        run_assign(index_path, capacity, plan, a, s, i)
        assigned = {row[0]: (row[3], row[4]) for row in read_tsv(a)[1:] if row[2] == "assigned"}
        assert assigned == {
            "A": ("Alpha", "day1"),
            "B": ("Beta", "day1"),
            "C": ("Beta", "day1"),
            "D": ("Beta", "day2"),
        }
        summary = assert_pretty_json(s)
        assert summary["plan_value"] == 250
        assert summary["assigned_count"] == 4
        assert read_tsv(i) == [["source_file", "source_line", "kind", "entity", "detail"]]

    def test_objective_prefers_lower_raw_score_after_value_and_count_tie(self, tmp_path):
        """When plan value and assigned count tie, the optimizer chooses the portfolio with lower raw score before schedule-key ordering."""
        index_path = tmp_path / "index.json"
        write_index(
            index_path,
            [
                make_claim("B", "auto", "north", 60, "HOT"),
                make_claim("C", "auto", "north", 40, "HOT"),
                make_claim("D", "auto", "north", 50, "HOT"),
                make_claim("E", "auto", "north", 40, "HOT"),
            ],
        )
        capacity = tmp_path / "capacity.tsv"
        capacity.write_text(
            "team\tproducts\tcounties\tday1\tday2\trisk_ceiling\tactive\n"
            "Alpha\t*\t*\t2\t0\t200\ttrue\n",
            encoding="utf-8",
        )
        plan = tmp_path / "plan.json"
        write_plan(
            plan,
            ["Alpha"],
            max_total_score=100,
            limits={"Alpha": {"day1": 100, "day2": 0}},
            bonuses=[
                {"claims": ["B", "C"], "bonus": 0, "same_day": True},
                {"claims": ["D", "E"], "bonus": 10, "same_day": True},
            ],
        )
        a, s, i = tmp_path / "out" / "a.tsv", tmp_path / "out" / "s.json", tmp_path / "out" / "i.tsv"
        run_assign(index_path, capacity, plan, a, s, i)
        assigned = [row[0] for row in read_tsv(a)[1:] if row[2] == "assigned"]
        assert assigned == ["D", "E"]
        summary = assert_pretty_json(s)
        assert summary["plan_value"] == 100
        assert summary["bonus_value"] == 10
        assert summary["total_score_used"] == 90
        assert read_tsv(i) == [["source_file", "source_line", "kind", "entity", "detail"]]

    def test_primary_signal_skills_can_create_hold_no_team(self, tmp_path):
        """Team signal eligibility uses the first indexed signal as the primary signal and reports no_team when none match it."""
        index_path = tmp_path / "index.json"
        claim = make_claim("SKILL", "auto", "north", 70, "FRAUD", 2)
        claim["signals"][1]["code"] = "HOT"
        write_index(index_path, [claim])
        capacity = tmp_path / "capacity.tsv"
        capacity.write_text(
            "team\tproducts\tcounties\tday1\tday2\trisk_ceiling\tactive\n"
            "HotOnly\tauto\tnorth\t1\t1\t100\ttrue\n",
            encoding="utf-8",
        )
        plan = tmp_path / "plan.json"
        write_plan(plan, ["HotOnly"], skills={"HotOnly": ["HOT"]})
        a, s, i = tmp_path / "out" / "a.tsv", tmp_path / "out" / "s.json", tmp_path / "out" / "i.tsv"
        run_assign(index_path, capacity, plan, a, s, i)
        assert read_tsv(a)[1][2] == "hold_no_team"
        assert assert_pretty_json(s)["hold_count"] == 1
        assert read_tsv(i)[1] == [str(capacity.resolve()), "0", "no_team", "SKILL", "auto/north"]

    def test_invalid_strict_plan_fails_without_creating_or_replacing_outputs(self, tmp_path):
        """Strict plan schema, references, team entries, limits, and group shapes fail before any output changes."""
        index_path = tmp_path / "index.json"
        write_index(index_path, [make_claim("A", "auto", "north", 60, "HOT")])
        capacity = tmp_path / "capacity.tsv"
        capacity.write_text(
            "team\tproducts\tcounties\tday1\tday2\trisk_ceiling\tactive\n"
            "Alpha\tauto\tnorth\t1\t1\t100\ttrue\n",
            encoding="utf-8",
        )
        base = {
            "max_total_score": 100,
            "team_day_score_limits": {"Alpha": {"day1": 100, "day2": 100}},
            "team_signal_skills": {"Alpha": ["HOT"]},
            "claim_windows": {},
            "blocked_same_day": [],
            "requires": [],
            "precedence": [],
            "same_team_groups": [],
            "different_team_pairs": [],
            "bundle_bonuses": [],
        }
        cases = []
        missing = dict(base)
        missing.pop("bundle_bonuses")
        cases.append(missing)
        unknown_field = dict(base)
        unknown_field["unexpected"] = True
        cases.append(unknown_field)
        unknown_claim = json.loads(json.dumps(base))
        unknown_claim["blocked_same_day"] = [["A", "UNKNOWN"]]
        cases.append(unknown_claim)
        unknown_team = json.loads(json.dumps(base))
        unknown_team["team_signal_skills"]["Ghost"] = ["HOT"]
        cases.append(unknown_team)
        negative_limit = json.loads(json.dumps(base))
        negative_limit["team_day_score_limits"]["Alpha"]["day1"] = -1
        cases.append(negative_limit)
        duplicate_group = json.loads(json.dumps(base))
        duplicate_group["same_team_groups"] = [["A", "A"]]
        cases.append(duplicate_group)

        for idx, payload in enumerate(cases):
            bad_plan = tmp_path / f"bad_plan_{idx}.json"
            write_json(bad_plan, payload)
            a = tmp_path / f"out_{idx}" / "a.tsv"
            s = tmp_path / f"out_{idx}" / "s.json"
            i = tmp_path / f"out_{idx}" / "i.tsv"
            for path in (a, s, i):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("sentinel\n", encoding="utf-8")
            result = run_assign(index_path, capacity, bad_plan, a, s, i, check=False)
            assert result.returncode != 0
            assert a.read_text(encoding="utf-8") == "sentinel\n"
            assert s.read_text(encoding="utf-8") == "sentinel\n"
            assert i.read_text(encoding="utf-8") == "sentinel\n"
