"""Behavioral verifier for the campaign constellation workflow."""

import json
import os
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from reference_campaign import (
    assert_canonical_bytes,
    campaign_id,
    canonical,
    digest,
    validate_board,
    validate_brief,
    validate_chronicle_line,
    validate_constellation,
    without,
)

APP = pathlib.Path("/app")
STATE = APP / "state"
OUTPUT = APP / "output"
FIX = APP / "fixtures"


def cmd(*args, env=None, ok=True):
    e = os.environ.copy()
    e.pop("THREATCOMP_FIXTURE_DIR", None)
    if env:
        e.update(env)
    p = subprocess.run(
        ["threatcomp", *args], text=True, capture_output=True, env=e, timeout=20
    )
    if ok:
        assert p.returncode == 0, p.stderr
    return p


def reset():
    shutil.rmtree(STATE, ignore_errors=True)
    shutil.rmtree(OUTPUT, ignore_errors=True)
    STATE.mkdir()
    OUTPUT.mkdir()


def load_canonical(path):
    raw = path.read_bytes()
    obj = json.loads(raw)
    assert_canonical_bytes(raw, obj)
    return obj


def workflow(extra=None):
    reset()
    env = {"THREATCOMP_FIXTURE_DIR": str(extra)} if extra else None
    cmd(
        "adjudicate",
        "--observations",
        str(FIX / "observations.jsonl"),
        "--policy",
        str(FIX / "policy.json"),
        env=env,
    )
    board = load_canonical(STATE / "evidence-board.json")
    cmd("compose")
    c = load_canonical(STATE / "campaign-constellation.json")
    cmd("brief")
    b = load_canonical(OUTPUT / "campaign-brief.json")
    return board, c, b


def rows(board):
    return {x["id"]: x for x in board["observations"]}


def test_adjudicate_normalizes_observations():
    """Adjudication normalizes identity fields and sorts IDs."""
    b, _, _ = workflow()
    assert [x["id"] for x in b["observations"]] == sorted(
        x["id"] for x in b["observations"]
    )
    assert rows(b)["obs-a"]["contractor"] == "zephy-ops"


def test_reliability_discount_uses_three_fifths(tmp_path):
    """A maintenance overlap discounts reliability by exactly three fifths."""
    policy = json.loads((FIX / "policy.json").read_text())
    policy["maintenance_epochs"] = [{"toolcell": "euv-4", "start": 120, "end": 130}]
    p = tmp_path / "p.json"
    p.write_text(json.dumps(policy))
    reset()
    cmd(
        "adjudicate",
        "--observations",
        str(FIX / "observations.jsonl"),
        "--policy",
        str(p),
    )
    b = load_canonical(STATE / "evidence-board.json")
    assert rows(b)["obs-a"]["effective_reliability_bp"] == 5400


def test_half_open_maintenance_boundary():
    """Boundary contact with maintenance does not discount an observation."""
    b, _, _ = workflow()
    assert rows(b)["obs-b"]["effective_reliability_bp"] == 8800


def test_transitive_contractor_alias_hidden():
    """Hidden alias chains are unioned transitively across groups."""
    b, _, _ = workflow(pathlib.Path("/opt/verifier-fixtures/alias-window"))
    assert rows(b)["hid-a"]["contractor"] == rows(b)["hid-b"]["contractor"]


def test_source_independence_blocks_same_source(tmp_path):
    """Two same-source observations cannot form a support edge."""
    data = [
        json.loads(x) for x in (FIX / "observations.jsonl").read_text().splitlines()[:2]
    ]
    data[1]["source"] = data[0]["source"]
    f = tmp_path / "o.jsonl"
    f.write_text("\n".join(map(json.dumps, data)) + "\n")
    reset()
    cmd("adjudicate", "--observations", str(f), "--policy", str(FIX / "policy.json"))
    cmd("compose")
    c = load_canonical(STATE / "campaign-constellation.json")
    assert c["campaigns"] == []


def test_board_schema_and_policy_capture():
    """Evidence board carries its schema and complete captured policy."""
    b, _, _ = workflow()
    assert b["schema"] == "threatcomp.evidence-board/v1"
    assert b["captured_policy"]["edge_threshold_bp"] == 1800


def test_evidence_board_is_durable_staging_snapshot():
    """Adjudicate writes a durable staging snapshot before compose reads it."""
    reset()
    cmd(
        "adjudicate",
        "--observations",
        str(FIX / "observations.jsonl"),
        "--policy",
        str(FIX / "policy.json"),
    )
    staging = STATE / "evidence-board.json"
    assert staging.is_file()
    snapshot = load_canonical(staging)
    assert snapshot["schema"] == "threatcomp.evidence-board/v1"
    assert validate_board(snapshot)
    # Compose must consume the on-disk staging snapshot, not re-ingest raw feeds.
    cmd("compose")
    assert staging.is_file()
    assert load_canonical(staging) == snapshot


def test_board_checksum_and_policy_fingerprint():
    """Independent canonical hashing validates both board digests."""
    b, _, _ = workflow()
    assert validate_board(b)


def test_fixture_directory_must_be_absolute():
    """Relative hidden fixture directories are rejected as input errors."""
    reset()
    p = cmd(
        "adjudicate",
        "--observations",
        str(FIX / "observations.jsonl"),
        "--policy",
        str(FIX / "policy.json"),
        env={"THREATCOMP_FIXTURE_DIR": "relative"},
        ok=False,
    )
    assert p.returncode == 2 and p.stderr.startswith("ERROR INPUT")


def test_commodity_hosting_veto_public():
    """A commodity beacon creates a cut rather than a campaign edge."""
    _, c, _ = workflow()
    assert any(
        x["reason"] == "commodity-hosting-veto"
        and {x["left"], x["right"]} == {"obs-c", "obs-d"}
        for x in c["contradiction_cuts"]
    )


def test_actor_exclusivity_cut_public():
    """Overlapping observations assigned to different actors are cut."""
    _, c, _ = workflow()
    assert any(x["reason"] == "actor-exclusivity" for x in c["contradiction_cuts"])


def test_campaign_membership_and_id():
    """Admissible evidence forms the expected deterministic campaign."""
    _, c, _ = workflow()
    camp = next(x for x in c["campaigns"] if x["members"] == ["obs-a", "obs-b"])
    assert camp["campaign_id"] == campaign_id(camp["members"])


def test_support_witness_citations():
    """Campaign support cites sorted independent source witnesses."""
    _, c, _ = workflow()
    w = c["campaigns"][0]["support_witnesses"][0]
    assert w["sources"] == ["sensor-alpha", "sensor-beta"]


def test_confidence_band_formula():
    """Confidence uses member reliability plus independent witness bonus."""
    _, c, _ = workflow()
    camp = next(x for x in c["campaigns"] if "obs-a" in x["members"])
    assert camp["confidence_bp"] == (9000 + 8800) // 2 + 250
    assert camp["confidence_band"] == "high"


def test_unassigned_frontier_reasons():
    """Frontier distinguishes weak evidence from admissible singletons."""
    _, c, _ = workflow()
    f = {x["observation_id"]: x["reason"] for x in c["unassigned_frontier"]}
    assert f["obs-e"] == "below-reliability"
    assert f["obs-c"] == "no-admissible-support"


def test_constellation_schema_and_checksums():
    """Constellation schema, payload digest, and checksum validate independently."""
    _, c, _ = workflow()
    assert c["schema"] == "threatcomp.campaign-constellation/v1"
    assert validate_constellation(c)


def test_compose_uses_captured_policy_only(tmp_path):
    """Compose binds to captured_policy after live policy and fixtures change."""
    reset()
    obs = tmp_path / "observations.jsonl"
    pol = tmp_path / "policy.json"
    obs.write_text((FIX / "observations.jsonl").read_text())
    policy = json.loads((FIX / "policy.json").read_text())
    pol.write_text(json.dumps(policy))
    cmd("adjudicate", "--observations", str(obs), "--policy", str(pol))
    board = load_canonical(STATE / "evidence-board.json")
    assert board["captured_policy"]["edge_threshold_bp"] == policy["edge_threshold_bp"]
    fixture_policy = FIX / "policy.json"
    original_fixture = fixture_policy.read_text()
    try:
        pol.write_text("{}")
        obs.write_text("not-json\n")
        poisoned = dict(policy)
        poisoned["edge_threshold_bp"] = 999999
        fixture_policy.write_text(json.dumps(poisoned))
        cmd("compose")
        c = load_canonical(STATE / "campaign-constellation.json")
        assert validate_constellation(c)
        assert any(
            camp["members"] == ["obs-a", "obs-b"] for camp in c["campaigns"]
        ), "compose must keep campaigns from captured_policy, not reread fixtures"
    finally:
        fixture_policy.write_text(original_fixture)


def test_chronicle_idempotent_replay():
    """Identical compose replay preserves bytes and chronicle length."""
    _, c, _ = workflow()
    before = (STATE / "campaign-constellation.json").read_bytes()
    chron = STATE / "constellation-chronicle.jsonl"
    chron_raw = chron.read_bytes()
    assert chron_raw.endswith(b"\n")
    lines = chron_raw.decode().splitlines()
    assert len(lines) == 1
    assert validate_chronicle_line(lines[0], c)
    assert lines[0] == canonical(json.loads(lines[0]))
    cmd("compose")
    assert (STATE / "campaign-constellation.json").read_bytes() == before
    assert chron.read_bytes() == chron_raw


def test_chronicle_epoch_changes_monotonically(tmp_path):
    """Changed adjudicated input increments the constellation epoch once."""
    _, c, _ = workflow()
    data = (
        (FIX / "observations.jsonl").read_text()
        + json.dumps(
            {
                "id": "obs-z",
                "indicator": "z",
                "source": "new-source",
                "contractor": "Zephyr Optics",
                "malware": "lumenrat",
                "beacon": "z",
                "toolcell": "euv-4",
                "actor": "actor-red",
                "start": 200,
                "end": 210,
                "reliability_bp": 9000,
            }
        )
        + "\n"
    )
    f = tmp_path / "o.jsonl"
    f.write_text(data)
    cmd("adjudicate", "--observations", str(f), "--policy", str(FIX / "policy.json"))
    cmd("compose")
    n = load_canonical(STATE / "campaign-constellation.json")
    assert n["epoch"] == c["epoch"] + 1
    chron = STATE / "constellation-chronicle.jsonl"
    raw = chron.read_bytes()
    assert raw.endswith(b"\n")
    lines = raw.decode().splitlines()
    assert len(lines) == 2
    assert validate_chronicle_line(lines[-1], n)
    for line in lines:
        assert line == canonical(json.loads(line))


def test_hidden_veto_exclusivity_objective_and_replay():
    """Hidden commodity, exclusivity, objective, and replay interactions remain separated."""
    _, c, _ = workflow(pathlib.Path("/opt/verifier-fixtures/veto-objective"))
    assert any(x["reason"] == "commodity-hosting-veto" for x in c["contradiction_cuts"])
    assert any(x["reason"] == "actor-exclusivity" for x in c["contradiction_cuts"])
    before = (STATE / "constellation-chronicle.jsonl").read_bytes()
    assert before.endswith(b"\n")
    assert validate_chronicle_line(before.decode().splitlines()[0], c)
    cmd("compose")
    assert (STATE / "constellation-chronicle.jsonl").read_bytes() == before


def test_stage_poison_does_not_rescan_inputs(tmp_path):
    """Compose is isolated from poisoned raw observations after adjudication."""
    reset()
    cmd(
        "adjudicate",
        "--observations",
        str(FIX / "observations.jsonl"),
        "--policy",
        str(FIX / "policy.json"),
    )
    poison = tmp_path / "observations.jsonl"
    poison.write_text("not json\n")
    cmd("compose", env={"THREATCOMP_FIXTURE_DIR": str(tmp_path)})
    assert validate_constellation(
        load_canonical(STATE / "campaign-constellation.json")
    )


def test_brief_isolation_from_board_and_raw():
    """Brief succeeds using only a valid constellation artifact."""
    _, c, _ = workflow()
    (STATE / "evidence-board.json").write_text("poison")
    cmd("brief", env={"THREATCOMP_FIXTURE_DIR": "relative"})
    brief = load_canonical(OUTPUT / "campaign-brief.json")
    assert validate_brief(brief, c)


def test_brief_ranking_order(tmp_path):
    """Brief ranks confidence, cohesion, size, then identifier deterministically."""
    _, c, _ = workflow()

    def mk(cid, conf, coh, members, band="medium"):
        return {
            "campaign_id": cid,
            "confidence_bp": conf,
            "confidence_band": band,
            "cohesion_bp": coh,
            "members": members,
            "support_witnesses": [],
        }

    c["campaigns"] = [
        mk("campaign-zzzzzzzzzzzz", 5000, 999, ["a", "b", "c"], "low"),
        mk("campaign-bbbbbbbbbbbb", 9000, 100, ["a", "b"], "high"),
        mk("campaign-aaaaaaaaaaaa", 9000, 200, ["a"], "high"),
        mk("campaign-cccccccccccc", 9000, 200, ["a", "b"], "high"),
        mk("campaign-dddddddddddd", 9000, 200, ["a", "b"], "high"),
    ]
    c["payload_digest"] = digest(without(c, "epoch", "payload_digest", "checksum"))
    c["checksum"] = digest(without(c, "checksum"))
    (STATE / "campaign-constellation.json").write_bytes(
        (canonical(c) + "\n").encode("utf-8")
    )
    cmd("brief")
    b = load_canonical(OUTPUT / "campaign-brief.json")
    assert validate_brief(b, c)
    ranked = [x["campaign_id"] for x in b["ranked_campaigns"]]
    assert ranked == [
        "campaign-cccccccccccc",
        "campaign-dddddddddddd",
        "campaign-aaaaaaaaaaaa",
        "campaign-bbbbbbbbbbbb",
        "campaign-zzzzzzzzzzzz",
    ]


def test_brief_deterministic_and_checksum():
    """Repeated briefs are byte-identical and independently checksummed."""
    _, c, _ = workflow()
    x = (OUTPUT / "campaign-brief.json").read_bytes()
    brief = json.loads(x)
    assert_canonical_bytes(x, brief)
    assert validate_brief(brief, c)
    cmd("brief")
    assert (OUTPUT / "campaign-brief.json").read_bytes() == x


def test_brief_rejects_tampered_constellation():
    """Brief rejects a constellation changed without checksum renewal."""
    workflow()
    c = json.loads((STATE / "campaign-constellation.json").read_text())
    c["epoch"] += 1
    (STATE / "campaign-constellation.json").write_text(json.dumps(c))
    p = cmd("brief", ok=False)
    assert p.returncode == 1 and p.stderr.startswith("ERROR VALIDATION")


def test_brief_malformed_constellation_is_input_error():
    """Malformed constellation JSON exits 2 with an INPUT-prefixed error."""
    reset()
    STATE.mkdir(exist_ok=True)
    (STATE / "campaign-constellation.json").write_text("{not-json")
    p = cmd("brief", ok=False)
    assert p.returncode == 2
    assert p.stderr.startswith("ERROR INPUT")


def test_required_artifact_paths_are_materialized():
    """All four absolute workflow artifacts named by the contract are materialized."""
    workflow()
    assert pathlib.Path("/app/state/evidence-board.json").is_file()
    assert pathlib.Path("/app/state/campaign-constellation.json").is_file()
    assert pathlib.Path("/app/state/constellation-chronicle.jsonl").is_file()
    assert pathlib.Path("/app/output/campaign-brief.json").is_file()


def test_actor_exclusivity_without_commodity_hidden(tmp_path):
    """Actor exclusivity alone cuts an otherwise strong hidden support pair."""
    base = [
        json.loads(x) for x in (FIX / "observations.jsonl").read_text().splitlines()[:2]
    ]
    base[0].update({"id": "actor-a", "actor": "red", "start": 10, "end": 30})
    base[1].update({"id": "actor-b", "actor": "blue", "start": 20, "end": 40})
    path = tmp_path / "actor.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in base) + "\n")
    reset()
    cmd("adjudicate", "--observations", str(path), "--policy", str(FIX / "policy.json"))
    cmd("compose")
    constellation = load_canonical(STATE / "campaign-constellation.json")
    assert any(
        cut["reason"] == "actor-exclusivity"
        for cut in constellation["contradiction_cuts"]
    )


def test_identical_replay_preserves_epoch_number():
    """An identical compose replay leaves the authoritative epoch unchanged."""
    _, constellation, _ = workflow()
    cmd("compose")
    replay = load_canonical(STATE / "campaign-constellation.json")
    assert replay["epoch"] == constellation["epoch"]


def test_commodity_cut_members_remain_frontier():
    """A commodity-only pair stays unassigned after its support edge is vetoed."""
    _, constellation, _ = workflow()
    frontier = {item["observation_id"] for item in constellation["unassigned_frontier"]}
    assert {"obs-c", "obs-d"} <= frontier
