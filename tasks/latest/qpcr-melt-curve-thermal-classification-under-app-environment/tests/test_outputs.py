import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest


ENV = Path("/app/environment")
BASE_JOURNAL = ENV / "data" / "assay_journal.jsonl"
BASE_CONFIG = ENV / "data" / "assay_policy.json"
CHANGED_EFFECTS = {"accepted", "superseded", "tombstoned", "rolled_back"}


def _json_files(folder: Path) -> list[Path]:
    return [path for path in folder.iterdir() if path.is_file() and path.suffix == ".json"]


def _only(path: Path) -> list[Path]:
    parent = path.parent
    return [item for item in parent.iterdir() if item == path]


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _permute(items: list, seed: int) -> list:
    out = list(items)
    state = seed & 0x7FFFFFFF
    for index in range(len(out) - 1, 0, -1):
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        swap = state % (index + 1)
        out[index], out[swap] = out[swap], out[index]
    return out


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _write_journal(path: Path, events: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(item, separators=(",", ":")) for item in events) + "\n")


def _run(journal: Path, config: Path, output: Path, cache: Path, check: bool = True):
    command = [
        "npm",
        "run",
        "certify",
        "--",
        "--journal",
        str(journal),
        "--config",
        str(config),
        "--output",
        str(output),
        "--cache-dir",
        str(cache),
    ]
    result = subprocess.run(
        command, cwd=ENV, env=os.environ.copy(), text=True, capture_output=True
    )
    if check:
        assert result.returncode == 0, result.stderr or result.stdout
        return json.loads(output.read_text(encoding="utf-8"))
    return result


@pytest.fixture(scope="session", autouse=True)
def _compiled_stack() -> None:
    subprocess.run([str(ENV / "scripts" / "build_all.sh")], cwd=ENV, check=True)


def _measurement(
    event_id: str,
    assay_id: str,
    seq: int,
    revision: int,
    measured: float,
    uplink: float = 80.0,
) -> dict:
    return {
        "event_id": event_id,
        "assay_id": assay_id,
        "seq": seq,
        "kind": "measurement",
        "revision": revision,
        "measured_tm": measured,
        "uplink_tm": uplink,
        "instrument_run": f"run-{event_id}",
    }


def _policy(tolerance: float = 0.01, stress=None) -> dict:
    return {
        "schema": "qpcr-policy-v2",
        "nonstress_tolerance_c": tolerance,
        "stress_assays": list(stress or []),
    }


def _rows(report: dict) -> dict[str, dict]:
    return {row["assay_id"]: row for row in report["assays"]}

def test_shipped_journal_emits_evidence_package(tmp_path: Path) -> None:
    """Shipped baseline emits schema qpcr-attestation-v2 with expected active events."""
    report = _run(BASE_JOURNAL, BASE_CONFIG, tmp_path / "report.json", tmp_path / "cache")
    assert report["schema"] == "qpcr-attestation-v2"
    assert [row["assay_id"] for row in report["assays"]] == ["A17", "B04", "C09", "D12"]
    assert report["summary"]["assays_total"] == len(report["assays"])
    assert report["summary"]["trace_total"] == len(report["trace"])
    assert sum(
        report["summary"][key] for key in ("within_total", "over_total", "outside_total")
    ) == len(report["assays"])
    assert report["provenance"]["logical_events"] == len(report["trace"])
    assert report["provenance"]["duplicate_events"] == 1
    assert all(len(row["witness"]) == 64 for row in report["assays"])
    rows = _rows(report)
    assert rows["A17"]["policy"] == "strict"
    assert rows["A17"]["classification"] == "within"
    assert rows["A17"]["tolerance_c"] == 0
    assert rows["B04"]["active_event_id"] == "evt-b04-new"
    assert rows["C09"]["classification"] == "within"
    assert rows["D12"]["active_event_id"] == "evt-d12-01"


def test_permutation_and_transport_duplicates_preserve_replay(tmp_path: Path) -> None:
    """Shuffled lines and transport duplicates preserve assays and digests."""
    events = [json.loads(line) for line in BASE_JOURNAL.read_text().splitlines() if line.strip()]
    original = _run(BASE_JOURNAL, BASE_CONFIG, tmp_path / "a.json", tmp_path / "cache-a")
    events = _permute(events, 731)
    events = list(events) + [events[1], events[3]]
    shuffled = tmp_path / "shuffled.jsonl"
    _write_journal(shuffled, events)
    replayed = _run(shuffled, BASE_CONFIG, tmp_path / "b.json", tmp_path / "cache-b")

    assert replayed["assays"] == original["assays"]
    assert replayed["provenance"]["journal_digest"] == original["provenance"]["journal_digest"]
    assert replayed["provenance"]["cache_key"] == original["provenance"]["cache_key"]
    assert [(row["seq"], row["event_id"]) for row in replayed["trace"]] == sorted(
        (row["seq"], row["event_id"]) for row in replayed["trace"]
    )
    assert replayed["provenance"]["duplicate_events"] > original["provenance"]["duplicate_events"]


def test_replay_handles_stale_supersede_tombstone_and_rollback(tmp_path: Path) -> None:
    """Stale, supersede, tombstone, and rollback select the correct active events."""
    events = [
        _measurement("x-base", "X", 2, 1, 80.0),
        _measurement("x-stale", "X", 9, 0, 84.0),
        {
            **_measurement("x-replace", "X", 7, 2, 80.004),
            "kind": "supersede",
            "target_event_id": "x-base",
        },
        _measurement("y-base", "Y", 1, 1, 79.999),
        _measurement("y-transient", "Y", 8, 2, 81.0),
        {"event_id": "y-cut", "assay_id": "Y", "seq": 10, "kind": "rollback", "through_seq": 1},
        _measurement("z-base", "Z", 3, 1, 80.0),
        _measurement("z-drop", "Z", 4, 2, 83.0),
        {
            "event_id": "z-tomb",
            "assay_id": "Z",
            "seq": 6,
            "kind": "tombstone",
            "target_event_id": "z-drop",
        },
    ]
    events = _permute(events, 991)
    journal = tmp_path / "state.jsonl"
    config = tmp_path / "policy.json"
    _write_journal(journal, events)
    _write_json(config, _policy())
    report = _run(journal, config, tmp_path / "report.json", tmp_path / "cache")
    rows = _rows(report)
    assert rows["X"]["active_event_id"] == "x-replace"
    assert rows["Y"]["active_event_id"] == "y-base"
    assert rows["Z"]["active_event_id"] == "z-base"
    effects = {row["event_id"]: row["effect"] for row in report["trace"]}
    assert effects["x-stale"] == "stale"
    assert effects["y-cut"] == "rolled_back"
    assert effects["z-tomb"] == "tombstoned"


def test_forward_reference_supersede_resolves_after_logical_sort(tmp_path: Path) -> None:
    """Supersede may precede its lower-seq target in the file."""
    # File arrival puts the supersede before its lower-seq target.
    earlier = "fwd-earlier"
    later = "fwd-later"
    events = [
        {
            **_measurement(later, "F", 5, 2, 80.003),
            "kind": "supersede",
            "target_event_id": earlier,
        },
        _measurement(earlier, "F", 3, 1, 80.0),
    ]
    journal = tmp_path / "forward.jsonl"
    config = tmp_path / "policy.json"
    _write_journal(journal, events)
    _write_json(config, _policy())
    report = _run(journal, config, tmp_path / "report.json", tmp_path / "cache")
    rows = _rows(report)
    assert rows["F"]["active_event_id"] == later
    assert rows["F"]["revision"] == 2
    effects = {row["event_id"]: row["effect"] for row in report["trace"]}
    assert effects[earlier] == "accepted"
    assert effects[later] == "superseded"
    assert [(row["seq"], row["event_id"]) for row in report["trace"]] == [
        (3, earlier),
        (5, later),
    ]


def test_content_addressed_cache_invalidates_journal_and_policy(tmp_path: Path) -> None:
    """Journal and policy changes select distinct cache keys and classifications."""
    cache = tmp_path / "cache"
    journal_a = tmp_path / "a.jsonl"
    journal_b = tmp_path / "b.jsonl"
    config_a = tmp_path / "a.json"
    config_b = tmp_path / "b.json"
    _write_journal(journal_a, [_measurement("m1", "S", 1, 1, 80.0)])
    _write_journal(journal_b, [_measurement("m1", "S", 1, 1, 80.006)])
    _write_json(config_a, _policy(0.01))
    _write_json(config_b, _policy(0.005))
    first = _run(journal_a, config_a, tmp_path / "one.json", cache)
    changed_journal = _run(journal_b, config_a, tmp_path / "two.json", cache)
    changed_policy = _run(journal_b, config_b, tmp_path / "three.json", cache)
    assert first["provenance"]["cache_key"] != changed_journal["provenance"]["cache_key"]
    assert changed_journal["provenance"]["cache_key"] != changed_policy["provenance"]["cache_key"]
    assert first["provenance"]["cache_key"] != changed_policy["provenance"]["cache_key"]
    assert changed_journal["assays"][0]["classification"] == "within"
    assert changed_policy["assays"][0]["classification"] == "outside"
    assert {item.stem for item in _json_files(cache)} == {
        first["provenance"]["cache_key"],
        changed_journal["provenance"]["cache_key"],
        changed_policy["provenance"]["cache_key"],
    }


def test_malformed_journal_preserves_output_and_cache_atomically(tmp_path: Path) -> None:
    """Truncated JSON fails without mutating prior output or cache bytes."""
    output = tmp_path / "report.json"
    cache = tmp_path / "cache"
    _run(BASE_JOURNAL, BASE_CONFIG, output, cache)
    before = output.read_bytes()
    cache_before = {item.name: item.read_bytes() for item in _json_files(cache)}
    malformed = tmp_path / "truncated.jsonl"
    malformed.write_text('{"event_id":"partial","assay_id":"A","seq":1', encoding="utf-8")
    result = _run(malformed, BASE_CONFIG, output, cache, check=False)
    assert result.returncode != 0
    assert output.read_bytes() == before
    assert {item.name: item.read_bytes() for item in _json_files(cache)} == cache_before


def test_conflicting_event_id_is_rejected_without_mutating_outputs(tmp_path: Path) -> None:
    """Conflicting event id reuse fails without mutating prior output."""
    output = tmp_path / "report.json"
    cache = tmp_path / "cache"
    _run(BASE_JOURNAL, BASE_CONFIG, output, cache)
    before = output.read_bytes()
    conflict = tmp_path / "conflict.jsonl"
    _write_journal(
        conflict,
        [
            _measurement("same", "Q", 1, 1, 80.0),
            {**_measurement("same", "Q", 1, 1, 80.1)},
        ],
    )
    result = _run(conflict, BASE_CONFIG, output, cache, check=False)
    assert result.returncode != 0
    assert output.read_bytes() == before


def test_missing_and_cross_assay_targets_are_rejected(tmp_path: Path) -> None:
    """Missing and cross-assay targets fail without writing output."""
    config = tmp_path / "policy.json"
    _write_json(config, _policy())
    missing = tmp_path / "missing.jsonl"
    _write_journal(
        missing,
        [
            {
                **_measurement("rep", "M", 2, 2, 80.0),
                "kind": "supersede",
                "target_event_id": "gone",
            }
        ],
    )
    cross = tmp_path / "cross.jsonl"
    _write_journal(
        cross,
        [
            _measurement("base", "A", 1, 1, 80.0),
            {
                **_measurement("rep", "B", 2, 2, 80.0),
                "kind": "supersede",
                "target_event_id": "base",
            },
        ],
    )
    for journal in (missing, cross):
        out = tmp_path / f"{journal.stem}.json"
        result = _run(journal, config, out, tmp_path / "cache", check=False)
        assert result.returncode != 0
        assert _only(out) == []


def test_tombstone_without_replacement_leaves_assay_invalid(tmp_path: Path) -> None:
    """Tombstoning the only observation leaves the assay invalid."""
    journal = tmp_path / "empty.jsonl"
    config = tmp_path / "policy.json"
    _write_journal(
        journal,
        [
            _measurement("only", "T", 1, 1, 80.0),
            {
                "event_id": "kill",
                "assay_id": "T",
                "seq": 2,
                "kind": "tombstone",
                "target_event_id": "only",
            },
        ],
    )
    _write_json(config, _policy())
    out = tmp_path / "empty-out.json"
    result = _run(journal, config, out, tmp_path / "cache", check=False)
    assert result.returncode != 0
    assert _only(out) == []


def test_strict_and_band_thermal_policies_diverge(tmp_path: Path) -> None:
    """Stress over-uplink is over with tolerance 0; band uses configured tolerance."""
    events = [
        _measurement("s", "STRESS", 1, 1, 82.000001, 82.0),
        _measurement("nin", "BAND_IN", 1, 1, 82.009, 82.0),
        _measurement("nout", "BAND_OUT", 1, 1, 82.011, 82.0),
    ]
    journal = tmp_path / "thermal.jsonl"
    config = tmp_path / "policy.json"
    _write_journal(journal, events)
    _write_json(config, _policy(0.01, ["STRESS"]))
    rows = _rows(_run(journal, config, tmp_path / "report.json", tmp_path / "cache"))
    assert rows["STRESS"]["classification"] == "over"
    assert rows["STRESS"]["tolerance_c"] == 0
    assert rows["BAND_IN"]["classification"] == "within"
    assert rows["BAND_IN"]["tolerance_c"] == 0.01
    assert rows["BAND_OUT"]["classification"] == "outside"


def test_stress_under_and_equal_uplink_remain_within(tmp_path: Path) -> None:
    """Stress equal and under uplink remain within with tolerance 0."""
    events = [
        _measurement("eq", "EQ", 1, 1, 82.0, 82.0),
        _measurement("under", "UNDER", 1, 1, 81.5, 82.0),
    ]
    journal = tmp_path / "under.jsonl"
    config = tmp_path / "policy.json"
    _write_journal(journal, events)
    _write_json(config, _policy(0.01, ["EQ", "UNDER"]))
    rows = _rows(_run(journal, config, tmp_path / "report.json", tmp_path / "cache"))
    assert rows["EQ"]["classification"] == "within"
    assert rows["UNDER"]["classification"] == "within"
    assert rows["EQ"]["tolerance_c"] == 0
    assert rows["UNDER"]["tolerance_c"] == 0


def test_provenance_and_witnesses_are_cross_language_consistent(tmp_path: Path) -> None:
    """Provenance digests and witnesses match the documented reduction."""
    report = _run(BASE_JOURNAL, BASE_CONFIG, tmp_path / "report.json", tmp_path / "cache")
    config = json.loads(BASE_CONFIG.read_text())
    config_digest = _sha(_canonical(config))
    ordered_trace = sorted(report["trace"], key=lambda row: (row["seq"], row["event_id"]))
    journal_digest = _sha("\n".join(row["event_digest"] for row in ordered_trace))
    cache_key = _sha(f"qpcr-journal-v2\n{journal_digest}\n{config_digest}")
    assert report["provenance"]["config_digest"] == config_digest
    assert report["provenance"]["journal_digest"] == journal_digest
    assert report["provenance"]["cache_key"] == cache_key

    for assay in report["assays"]:
        changed = [
            row["event_digest"]
            for row in ordered_trace
            if row["assay_id"] == assay["assay_id"] and row["effect"] in CHANGED_EFFECTS
        ]
        expected = _sha(f"qpcr-witness-v2\n{config_digest}\n" + "\n".join(changed))
        assert assay["witness"] == expected


def test_successful_reruns_are_byte_identical_and_replace_stale_output(tmp_path: Path) -> None:
    """Successful reruns replace stale output and stay byte-identical."""
    output = tmp_path / "report.json"
    cache = tmp_path / "cache"
    _run(BASE_JOURNAL, BASE_CONFIG, output, cache)
    first = output.read_bytes()
    output.write_text('{"stale":true}\n', encoding="utf-8")
    _run(BASE_JOURNAL, BASE_CONFIG, output, cache)
    assert output.read_bytes() == first
    _run(BASE_JOURNAL, BASE_CONFIG, output, cache)
    assert output.read_bytes() == first


def test_key_reordered_policy_preserves_config_digest(tmp_path: Path) -> None:
    """Policy object key order does not change config digest or assays."""
    journal = tmp_path / "one.jsonl"
    config_a = tmp_path / "a.json"
    config_b = tmp_path / "b.json"
    _write_journal(journal, [_measurement("m", "K", 1, 1, 80.0)])
    config_a.write_text(
        '{"schema":"qpcr-policy-v2","nonstress_tolerance_c":0.01,"stress_assays":[]}\n',
        encoding="utf-8",
    )
    config_b.write_text(
        '{"stress_assays":[],"nonstress_tolerance_c":0.01,"schema":"qpcr-policy-v2"}\n',
        encoding="utf-8",
    )
    left = _run(journal, config_a, tmp_path / "left.json", tmp_path / "cache-a")
    right = _run(journal, config_b, tmp_path / "right.json", tmp_path / "cache-b")
    assert left["provenance"]["config_digest"] == right["provenance"]["config_digest"]
    assert left["assays"] == right["assays"]
