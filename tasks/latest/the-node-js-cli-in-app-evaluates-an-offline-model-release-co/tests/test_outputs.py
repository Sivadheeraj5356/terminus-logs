import hashlib
import json
import subprocess
from pathlib import Path


APP = Path("/app")


def run_release(tmp_path, payload):
    """Run the model release CLI and return assignments keyed by id."""
    src = tmp_path / "input.json"
    src.write_text(json.dumps(payload), encoding="utf-8")
    completed = subprocess.run(["node", "bin/model-release.js", str(src)], cwd=APP, check=True, text=True, capture_output=True)
    return {item["id"]: item for item in json.loads(completed.stdout)["assignments"]}


def bucket_variant(salt, model, subject, variants, default):
    value = int(hashlib.sha256(f"{salt}|{model}|{subject}".encode()).hexdigest()[:8], 16) / 0x100000000
    acc = 0.0
    for variant in variants:
        acc += variant["weight"]
        if value < acc:
            return variant["id"]
    return default


def test_same_time_release_alias_and_exclusive_override(tmp_path):
    """Later same-time releases win and override until is exclusive."""
    payload = {
        "subjects": [{"id": "s1", "aliases": ["old-s1"], "attrs": {"tier": "gold"}}],
        "releases": [
            {"id": "r-old", "model": "ranker", "effective": 10, "overrides": [{"subject": "s1", "variant": "old"}]},
            {"id": "r-new", "model": "ranker", "effective": 10, "overrides": [{"subject": "s1", "variant": "canary", "until": 20}], "default": "stable"},
        ],
        "queries": [
            {"id": "before", "subject": "old-s1", "model": "ranker", "at": 19},
            {"id": "at-boundary", "subject": "old-s1", "model": "ranker", "at": 20},
        ],
    }
    got = run_release(tmp_path, payload)
    assert got["before"]["status"] == "active"
    assert got["before"]["variant"] == "canary"
    assert got["before"]["source"] == "r-new:override:s1"
    assert got["at-boundary"]["status"] == "active"
    assert got["at-boundary"]["variant"] == "stable"
    assert got["at-boundary"]["source"] == "r-new:default"


def test_prerequisite_mismatch_and_cycle(tmp_path):
    """Prerequisite mismatches and recursive model release dependencies block assignment."""
    payload = {
        "subjects": [{"id": "s1", "attrs": {"tier": "free"}}],
        "releases": [
            {"id": "base", "model": "base", "effective": 1, "default": "control"},
            {"id": "dep", "model": "dep", "effective": 1, "prerequisites": [{"model": "base", "variant": "treat"}], "default": "serve"},
            {"id": "a", "model": "a", "effective": 1, "prerequisites": [{"model": "b", "variant": "x"}], "default": "x"},
            {"id": "b", "model": "b", "effective": 1, "prerequisites": [{"model": "a", "variant": "x"}], "default": "x"},
        ],
        "queries": [
            {"id": "mismatch", "subject": "s1", "model": "dep", "at": 2},
            {"id": "cycle", "subject": "s1", "model": "a", "at": 2},
        ],
    }
    got = run_release(tmp_path, payload)
    assert got["mismatch"]["blockedBy"] == "prerequisite:base"
    assert got["cycle"]["status"] == "blocked"
    assert got["cycle"]["blockedBy"] == "cycle"


def test_cohort_priority_later_tie_and_expired_release(tmp_path):
    """Cohorts use priority plus later-order tie break, and expired releases are missing."""
    payload = {
        "subjects": [{"id": "s1", "attrs": {"region": "apac", "plan": "pro"}}],
        "releases": [
            {"id": "old", "model": "expired", "effective": 1, "expires": 5, "default": "v0"},
            {
                "id": "cohort",
                "model": "score",
                "effective": 1,
                "cohorts": [
                    {"id": "region", "priority": 4, "when": {"region": ["apac", "emea"]}, "variant": "regional"},
                    {"id": "plan", "priority": 4, "when": {"plan": "pro"}, "variant": "pro"},
                ],
                "default": "base",
            },
        ],
        "queries": [
            {"id": "cohort", "subject": "s1", "model": "score", "at": 2},
            {"id": "expired", "subject": "s1", "model": "expired", "at": 5},
        ],
    }
    got = run_release(tmp_path, payload)
    assert got["cohort"]["status"] == "active"
    assert got["cohort"]["variant"] == "pro"
    assert got["cohort"]["source"] == "cohort:cohort:plan"
    assert got["expired"]["status"] == "missing"


def test_rollout_hash_uses_model_and_canonical_subject(tmp_path):
    """Rollout bucket input is salt, model, and canonical subject id."""
    variants = [{"id": "blue", "weight": 0.4}, {"id": "green", "weight": 0.2}]
    expected = bucket_variant("ml", "embedder", "subject-canon", variants, "stable")
    payload = {
        "subjects": [{"id": "subject-canon", "aliases": ["subject-old"], "attrs": {}}],
        "releases": [{"id": "roll", "model": "embedder", "effective": 1, "salt": "ml", "variants": variants, "default": "stable"}],
        "queries": [{"id": "rollout", "subject": "subject-old", "model": "embedder", "at": 2}],
    }
    got = run_release(tmp_path, payload)["rollout"]
    assert got["status"] == "active"
    assert got["variant"] == expected
    assert got["source"] == ("roll:default" if expected == "stable" else "roll:rollout")


def test_later_override_replaces_earlier_matching_override(tmp_path):
    """Multiple matching overrides in one snapshot use the later entry."""
    payload = {
        "subjects": [{"id": "s1", "attrs": {}}],
        "releases": [
            {
                "id": "r1",
                "model": "ranker",
                "effective": 1,
                "overrides": [
                    {"subject": "s1", "variant": "first"},
                    {"subject": "s1", "variant": "second"},
                ],
                "default": "base",
            }
        ],
        "queries": [{"id": "q", "subject": "s1", "model": "ranker", "at": 2}],
    }
    got = run_release(tmp_path, payload)["q"]
    assert got["status"] == "active"
    assert got["variant"] == "second"
    assert got["source"] == "r1:override:s1"
