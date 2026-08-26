import json
import re
import subprocess
from collections import OrderedDict
from pathlib import Path

APP = Path("/app")
OUT = APP / "output" / "rule_lineage.json"
STATE = APP / "state"
FIXTURES = APP / "environment" / "fixtures"
LAYOUT = APP / "environment" / "runtime" / "layout.json"
LEDGER = APP / "environment" / "store" / "ledger.json"
CMD = ["/app/bin/arctl"]

TIER_RANK = {"operator": 0, "runtime": 1, "vendor": 2}


def _reset():
    STATE.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for path in STATE.glob("*"):
        path.unlink()
    if OUT.exists():
        OUT.unlink()
    subprocess.run(
        ["go", "build", "-o", "/app/bin/arctl", "/app/environment/cmd/arctl"],
        cwd="/app/environment",
        check=True,
        capture_output=True,
        text=True,
    )


def _sha256_hex(payload: str) -> str:
    result = subprocess.run(
        ("sha256sum",),
        input=payload,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.split()[0]


def _state_path(profile):
    return STATE / f"{profile}.json"


def _reload(profile, times=1):
    for _ in range(times):
        subprocess.run([*CMD, "reload", "--profile", profile], check=True, capture_output=True, text=True)


def _inspect(profile):
    subprocess.run([*CMD, "inspect", "--profile", profile], check=True, capture_output=True, text=True)
    return json.loads(OUT.read_text())


def _load_fixture_rows(profile):
    root = FIXTURES / f"{profile}_inputs"
    rows = []
    for tier_dir in sorted(root.iterdir(), key=lambda p: TIER_RANK[p.name], reverse=True):
        if not tier_dir.is_dir():
            continue
        tier = tier_dir.name
        for path in sorted(tier_dir.glob("*")):
            if path.is_dir():
                continue
            for idx, line in enumerate(path.read_text().splitlines(), start=1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.endswith("!"):
                    rows.append(
                        {
                            "tier": tier,
                            "class": line[:-1].strip(),
                            "body": "",
                            "op": "delete",
                            "file": path.name,
                            "index": idx,
                        }
                    )
                    continue
                if "+=" in line:
                    key, value = line.split("+=", 1)
                    op = "append"
                elif "-=" in line:
                    key, value = line.split("-=", 1)
                    op = "remove"
                else:
                    key, value = line.split("=", 1)
                    op = "set"
                rows.append(
                    {
                        "tier": tier,
                        "class": key.strip(),
                        "body": value.strip(),
                        "op": op,
                        "file": path.name,
                        "index": idx,
                    }
                )
    return rows


def _split_body(raw):
    if ":" not in raw:
        return raw, ""
    action, field = raw.split(":", 1)
    return action.strip(), field.strip()


def _winning_rules(profile, generation):
    by_class = OrderedDict()
    for row in _load_fixture_rows(profile):
        key = row["class"]
        if row["op"] == "delete":
            by_class.pop(key, None)
            continue
        current = by_class.get(key, {"class": key, "action": "", "field": "", "tier": row["tier"]})
        if row["op"] == "set" or key not in by_class:
            action, field = _split_body(row["body"])
            current["action"] = action
            current["field"] = field
            current["tier"] = row["tier"]
        elif row["op"] == "append":
            parts = [part for part in current["field"].split(",") if part]
            parts.append(row["body"])
            current["field"] = ",".join(parts)
            current["tier"] = row["tier"]
        elif row["op"] == "remove":
            parts = [part for part in current["field"].split(",") if part and part != row["body"]]
            current["field"] = ",".join(parts)
            current["tier"] = row["tier"]
        by_class[key] = current
    rules = []
    for key in sorted(by_class):
        row = by_class[key]
        rules.append(
            {
                "class": row["class"],
                "action": row["action"],
                "field": row["field"],
                "generation": generation,
                "observed_authority": row["tier"],
            }
        )
    return rules


def _scope_digest(rules):
    layout = json.loads(LAYOUT.read_text())
    pair = layout.get("digest_pair", ":")
    joiner = layout.get("digest_joiner", ";")
    parts = sorted(
        f"{row['class']}={row['action']}:{row['field']}{pair}{row['observed_authority']}{pair}{row['observed_authority']}"
        for row in rules
    )
    return _sha256_hex(joiner.join(parts))


def _tree_digest(profile):
    layout = json.loads(LAYOUT.read_text())
    pair = layout.get("digest_pair", ":")
    joiner = layout.get("digest_joiner", ";")
    parts = sorted(
        f"{row['tier']}{pair}{row['file']}{pair}{row['class']}{pair}{row['op']}{pair}{row['body']}"
        for row in _load_fixture_rows(profile)
    )
    return _sha256_hex(joiner.join(parts))


def _rule_map(rules):
    return {row["class"]: row for row in rules}


def _assert_no_booleans(value):
    if type(value) is dict:
        for key, child in value.items():
            lowered = key.lower()
            if lowered.endswith(("_ok", "_valid", "_green", "_passes")):
                raise AssertionError(key)
            _assert_no_booleans(child)
    elif type(value) is list:
        for child in value:
            _assert_no_booleans(child)


def test_t01_fresh_workflow_regenerates_lineage():
    """A normal reload and inspect regenerates rule rows with provenance notes from source state."""
    _reset()
    _reload("relay", 1)
    report = _inspect("relay")
    assert report["profile"] == "relay"
    assert isinstance(report["rules"], list) and report["rules"]
    assert isinstance(report["notes"], list) and report["notes"]
    assert isinstance(report["reloads"], list) and report["reloads"]
    _assert_no_booleans(report)
    got = _rule_map(report["rules"])
    expected = _rule_map(_winning_rules("relay", 1))
    assert "stale_row" not in got
    for key in ("net", "file", "classlist"):
        assert got[key]["action"] == expected[key]["action"]
        assert got[key]["field"] == expected[key]["field"]
        assert got[key]["observed_authority"] == expected[key]["observed_authority"]
    surfaces = {row["surface"] for row in report["notes"]}
    assert "input_tree" in surfaces
    assert "durable_state" in surfaces
    assert "emission" in surfaces


def test_t02_readiness_can_hide_stale_lineage():
    """Inspect remains the graded surface even when the input-tree digest already matches stored state."""
    _reset()
    profile = "relay"
    _reload(profile, 1)
    state_path = _state_path(profile)
    state = json.loads(state_path.read_text())
    state["rules"] = [
        {
            "class": "net",
            "action": "never",
            "field": "stale",
            "generation": 1,
            "observed_authority": "vendor",
        }
    ]
    state_path.write_text(json.dumps(state))
    _reload(profile, 1)
    report = _inspect(profile)
    got = _rule_map(report["rules"])
    expected = _rule_map(_winning_rules(profile, 2))
    assert got["net"]["action"] == expected["net"]["action"]
    assert got["net"]["field"] == expected["net"]["field"]
    assert got["net"]["observed_authority"] == expected["net"]["observed_authority"]
    assert got["net"]["generation"] == expected["net"]["generation"]
    for key in ("file", "auth", "classlist"):
        assert got[key]["action"] == expected[key]["action"]
        assert got[key]["field"] == expected[key]["field"]
        assert got[key]["observed_authority"] == expected[key]["observed_authority"]
        assert got[key]["generation"] == expected[key]["generation"]
    commit = [row for row in report["reloads"] if row["phase"] == "commit"][-1]
    assert commit["scope_digest"] == _scope_digest(report["rules"])
    surfaces = {row["surface"] for row in report["notes"]}
    assert {"input_tree", "durable_state", "emission"}.issubset(surfaces)


def test_t03_cross_tier_row_agreement():
    """Cross-tier rule rows match live fixture winners after conflicting tier histories."""
    _reset()
    _reload("relay", 2)
    report = _inspect("relay")
    got = _rule_map(report["rules"])
    expected = _rule_map(_winning_rules("relay", 2))
    assert got["net"]["action"] == expected["net"]["action"]
    assert got["net"]["field"] == expected["net"]["field"]
    assert got["net"]["observed_authority"] == "operator"
    assert got["file"]["observed_authority"] == expected["file"]["observed_authority"]
    assert got["classlist"]["action"] == expected["classlist"]["action"]
    assert got["classlist"]["field"] == expected["classlist"]["field"]
    assert got["classlist"]["observed_authority"] == expected["classlist"]["observed_authority"]
    assert "stale_row" not in got
    for row in report["rules"]:
        assert row["generation"] == 2


def test_t04_scope_digest_stable_across_reloads():
    """Repeated inspect for relay keeps commit scope_digest stable across reload cycles."""
    _reset()
    _reload("relay", 2)
    first = _inspect("relay")
    _reload("relay", 1)
    second = _inspect("relay")
    first_commit = [row for row in first["reloads"] if row["phase"] == "commit"][-1]["scope_digest"]
    second_commit = [row for row in second["reloads"] if row["phase"] == "commit"][-1]["scope_digest"]
    assert first_commit == second_commit
    assert first_commit == _scope_digest(second["rules"])
    _reload("relay", 1)
    third = _inspect("relay")
    third_commit = [row for row in third["reloads"] if row["phase"] == "commit"][-1]["scope_digest"]
    assert third_commit == first_commit
    state_snapshot = _state_path("relay").read_text()
    again = _inspect("relay")
    assert _state_path("relay").read_text() == state_snapshot
    assert again["rules"] == third["rules"]
    assert again["reloads"] == third["reloads"]
    again_commit = [row for row in again["reloads"] if row["phase"] == "commit"][-1]["scope_digest"]
    assert again_commit == third_commit


def test_t05_seeded_stale_rows_absent():
    """Reload from seeded ledger does not resurrect stale generated rows."""
    _reset()
    profile = "yard"
    seed = json.loads(LEDGER.read_text())[profile]
    _state_path(profile).write_text(json.dumps(seed))
    _reload(profile, 2)
    report = _inspect(profile)
    got = _rule_map(report["rules"])
    expected = _rule_map(_winning_rules(profile, 2))
    assert "drain" not in got
    assert got["queue"]["field"] == expected["queue"]["field"]
    assert got["queue"]["observed_authority"] == expected["queue"]["observed_authority"]
    assert got["classlist"]["action"] == expected["classlist"]["action"]
    assert got["classlist"]["field"] == expected["classlist"]["field"]
    assert got["classlist"]["observed_authority"] == expected["classlist"]["observed_authority"]
    commit = [row for row in report["reloads"] if row["phase"] == "commit"][-1]
    assert commit["scope_digest"] == _scope_digest(report["rules"])


def test_t06_second_reload_recovery_selective():
    """A second reload cycle restores accepted rows without resurrecting revoked classes."""
    _reset()
    _reload("yard", 1)
    mid = _inspect("yard")
    assert _rule_map(mid["rules"])["queue"] == _rule_map(_winning_rules("yard", 1))["queue"]
    _reload("yard", 1)
    final = _inspect("yard")
    assert "drain" not in _rule_map(final["rules"])
    assert _rule_map(final["rules"])["queue"] == _rule_map(_winning_rules("yard", 2))["queue"]
    assert _rule_map(final["rules"])["classlist"] == _rule_map(_winning_rules("yard", 2))["classlist"]
    assert len(final["reloads"]) >= len(mid["reloads"])


def test_t07_notes_name_consulted_surfaces():
    """Provenance notes name consulted surfaces without boolean verdict fields."""
    _reset()
    _reload("depot", 2)
    report = _inspect("depot")
    assert report["notes"]
    for row in report["notes"]:
        assert set(row) == {"surface", "detail"}
        assert row["surface"]
        assert row["detail"]
    surfaces = {row["surface"] for row in report["notes"]}
    assert {"input_tree", "durable_state", "emission"}.issubset(surfaces)
    _assert_no_booleans(report)


def test_t08_partial_fix_cannot_satisfy_matrix():
    """Unrelated profiles still require correct generated evidence after partial local edits."""
    _reset()
    _reload("relay", 2)
    relay = _inspect("relay")
    _reload("depot", 2)
    depot = _inspect("depot")
    _reload("yard", 2)
    yard = _inspect("yard")
    relay_got = _rule_map(relay["rules"])
    depot_got = _rule_map(depot["rules"])
    yard_got = _rule_map(yard["rules"])
    relay_exp = _rule_map(_winning_rules("relay", 2))
    yard_exp = _rule_map(_winning_rules("yard", 2))
    assert relay_got["net"]["observed_authority"] == "operator"
    assert relay_got["net"]["field"] == relay_exp["net"]["field"]
    assert relay_got["classlist"]["field"] == relay_exp["classlist"]["field"]
    assert depot_got["worker"]["observed_authority"] == "operator"
    assert "drain" not in yard_got
    assert yard_got["queue"] == yard_exp["queue"]
    assert yard_got["classlist"] == yard_exp["classlist"]
    for report in (relay, depot, yard):
        commit = [row for row in report["reloads"] if row["phase"] == "commit"][-1]
        assert re.fullmatch(r"[0-9a-f]{64}", commit["scope_digest"])
        assert commit["scope_digest"] == _scope_digest(report["rules"])
        surfaces = {row["surface"] for row in report["notes"]}
        assert {"input_tree", "durable_state", "emission"}.issubset(surfaces)
        _assert_no_booleans(report)
