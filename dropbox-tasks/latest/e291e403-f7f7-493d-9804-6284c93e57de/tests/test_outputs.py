import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path


APP_DIR = Path(os.environ.get("APP_DIR", "/app"))
ENGINE = APP_DIR / "sanitizer.py"
DEFAULT_INPUT = APP_DIR / "input.jsonl"
DEFAULT_OUTPUT = APP_DIR / "output.jsonl"
DEFAULT_REJECTED = APP_DIR / "rejected.jsonl"
DEFAULT_POLICY = APP_DIR / "policy.json"
DEFAULT_AUDIT_DB = APP_DIR / "security_audit.sqlite"
HIDDEN_DATA = Path(__file__).parent / "hidden_data"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def chained_records(items):
    previous = bytes(32)
    records = []
    for identifier, payload in items:
        material = canonical({"id": identifier, "payload": payload}).encode("utf-8")
        previous = hashlib.sha256(previous + material).digest()
        records.append({"digest": previous.hex(), "id": identifier, "payload": payload})
    return records


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def read_fixture_lines(name):
    lines = (HIDDEN_DATA / name).read_text(encoding="utf-8").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def read_fixture_json(name):
    return json.loads((HIDDEN_DATA / name).read_text(encoding="utf-8"))


def read_security_events(path):
    with sqlite3.connect(path) as connection:
        columns = connection.execute("PRAGMA table_info(security_events)").fetchall()
        rows = connection.execute(
            "SELECT line, event_id, decision, reason, digest FROM security_events ORDER BY line"
        ).fetchall()
    assert [(column[1], column[2]) for column in columns] == [
        ("line", "INTEGER"),
        ("event_id", "TEXT"),
        ("decision", "TEXT"),
        ("reason", "TEXT"),
        ("digest", "TEXT"),
    ]
    return rows


def run_engine(tmp_path, lines, policy=None):
    input_path = tmp_path / "input.jsonl"
    output_path = tmp_path / "output.jsonl"
    rejected_path = tmp_path / "rejected.jsonl"
    policy_path = tmp_path / "policy.json"
    audit_db_path = tmp_path / "security_audit.sqlite"
    input_path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    if policy is None:
        policy_path.write_text(DEFAULT_POLICY.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        policy_path.write_text(json.dumps(policy), encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            str(ENGINE),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--rejected",
            str(rejected_path),
            "--policy",
            str(policy_path),
            "--audit-db",
            str(audit_db_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return output_path, rejected_path, audit_db_path


def test_default_gateway_run_routes_every_attack_line_and_writes_ledger():
    """The supplied gateway traffic must accept safe events, reject attacks, and log decisions."""
    subprocess.run([sys.executable, str(ENGINE)], cwd=APP_DIR, check=True)
    accepted = read_jsonl(DEFAULT_OUTPUT)
    rejected = read_jsonl(DEFAULT_REJECTED)
    expected_payloads = [
        {"Display": "Hello", "url": "https://example.com/a"},
        {"nested": {"name": "Alice"}, "redirect": None},
        {"URL": None, "visible": "OK"},
    ]
    assert accepted == chained_records(
        [
            ("evt-1", expected_payloads[0]),
            ("evt-2", expected_payloads[1]),
            ("evt-3", expected_payloads[2]),
        ]
    )
    assert rejected == [
        {"line": 4, "reason": "duplicate_key"},
        {"line": 5, "reason": "invalid_json"},
        {"line": 6, "reason": "invalid_envelope"},
    ]
    assert read_security_events(DEFAULT_AUDIT_DB) == [
        (1, "evt-1", "accepted", None, accepted[0]["digest"]),
        (2, "evt-2", "accepted", None, accepted[1]["digest"]),
        (3, "evt-3", "accepted", None, accepted[2]["digest"]),
        (4, None, "rejected", "duplicate_key", None),
        (5, None, "rejected", "invalid_json", None),
        (6, None, "rejected", "invalid_envelope", None),
    ]


def test_duplicate_keys_are_rejected_after_normalization_at_any_depth(tmp_path):
    """Exact, case-folded, and compatibility-equivalent key collisions must reject the event."""
    lines = [
        '{"id":"a","id":"b","payload":{}}',
        '{"id":"b","payload":{"meta":{"Role":1,"role":2}}}',
        '{"id":"c","payload":{"Name":1,"ｎａｍｅ":2}}',
    ]
    output, rejected, _ = run_engine(tmp_path, lines)
    assert output.read_text(encoding="utf-8") == ""
    assert read_jsonl(rejected) == [
        {"line": 1, "reason": "duplicate_key"},
        {"line": 2, "reason": "duplicate_key"},
        {"line": 3, "reason": "duplicate_key"},
    ]


def test_envelope_aliases_hidden_by_controls_are_duplicate_keys(tmp_path):
    """Envelope keys also need canonical duplicate detection before envelope validation."""
    lines = [
        '{"i\\u202ed":"shadow","id":"visible","payload":{}}',
        '{"id":"ok","p\\u0085ayload":1,"payload":2}',
        '{"i\\u202ed":"accepted","payload":{"safe":true}}',
    ]
    output, rejected, audit_db = run_engine(tmp_path, lines)
    assert read_jsonl(output) == chained_records([("accepted", {"safe": True})])
    assert read_jsonl(rejected) == [
        {"line": 1, "reason": "duplicate_key"},
        {"line": 2, "reason": "duplicate_key"},
    ]
    accepted = read_jsonl(output)
    assert read_security_events(audit_db) == [
        (1, None, "rejected", "duplicate_key", None),
        (2, None, "rejected", "duplicate_key", None),
        (3, "accepted", "accepted", None, accepted[0]["digest"]),
    ]


def test_accepted_ids_are_normalized_in_output_digest_and_ledger(tmp_path):
    """Compatibility and control characters in IDs must not survive accepted audit artifacts."""
    normalized_line = json.dumps(
        {"id": "ＥＶＴ\u202e\u0085-９", "payload": {"message": "ok"}},
        ensure_ascii=False,
    )
    empty_after_normalization = json.dumps(
        {"id": "\u202e\u0085", "payload": {"message": "bad"}},
        ensure_ascii=False,
    )
    output, rejected, audit_db = run_engine(tmp_path, [normalized_line, empty_after_normalization])
    expected = chained_records([("EVT-9", {"message": "ok"})])
    accepted = read_jsonl(output)
    assert accepted == expected
    assert read_jsonl(rejected) == [{"line": 2, "reason": "invalid_envelope"}]
    assert read_security_events(audit_db) == [
        (1, "EVT-9", "accepted", None, expected[0]["digest"]),
        (2, None, "rejected", "invalid_envelope", None),
    ]


def test_controlled_keys_are_canonicalized_before_security_decisions(tmp_path):
    """Controls and bidi marks in keys must not hide duplicates, blocked names, operators, or URL fields."""
    duplicate_line = json.dumps(
        {"id": "dup", "payload": {"nested": {"to\u202eken": "a", "TOKEN": "b"}}},
        ensure_ascii=False,
    )
    payload = {
        "$\u202ewhere": "drop operator",
        "ＳＥＣ\u0085ＲＥＴ": "drop blocked",
        "Ｕ\u202eＲＬ": "jav&#x61;script:alert(1)",
        "safe\u202dName": "Ａ\u202eB",
    }
    clean_line = json.dumps({"id": "clean", "payload": payload}, ensure_ascii=False)
    output, rejected, audit_db = run_engine(tmp_path, [duplicate_line, clean_line])
    assert read_jsonl(output) == chained_records([("clean", {"URL": None, "safeName": "AB"})])
    assert read_jsonl(rejected) == [{"line": 1, "reason": "duplicate_key"}]
    digest = read_jsonl(output)[0]["digest"]
    assert read_security_events(audit_db) == [
        (1, None, "rejected", "duplicate_key", None),
        (2, "clean", "accepted", None, digest),
    ]


def test_recursive_policy_and_unicode_cleanup_cover_arrays_and_objects(tmp_path):
    """Blocked and operator keys disappear recursively while retained keys and strings are normalized."""
    payload = {
        "ＰＡＳＳＷＯＲＤ": "leak",
        "items": [
            {"$where": "sleep(9)", "Ｓｅｃｒｅｔ": 3, "label": "Ａ\u202e\u007f\u0085B\n"},
            "Ｃ\u061cD",
        ],
    }
    line = json.dumps({"id": "recursive", "payload": payload}, ensure_ascii=False)
    output, rejected, _ = run_engine(tmp_path, [line])
    cleaned = {"items": [{"label": "AB"}, "CD"]}
    assert read_jsonl(output) == chained_records([("recursive", cleaned)])
    assert rejected.read_text(encoding="utf-8") == ""


def test_url_policy_detects_nested_obfuscation_without_damaging_safe_urls(tmp_path):
    """URL fields must distinguish safe absolute and relative targets from encoded active schemes."""
    payload = {
        "url": "HTTPS://example.com/a",
        "href": "docs/page?q=1",
        "src": "//evil.example/x",
        "redirect": "java%2573cript:alert(1)",
        "nested": [
            {"url": "jav&#x61;script:alert(1)"},
            {"href": "  h t t p ://evil.example"},
            {"src": "/images/logo.png"},
            {"redirect": "https:missing-authority"},
            {"url": "h%2574tps://example.com/encoded"},
            {"ＵＲＬ": "data:text/html,boom"},
        ],
    }
    line = json.dumps({"id": "urls", "payload": payload})
    output, _, _ = run_engine(tmp_path, [line])
    cleaned = {
        "url": "HTTPS://example.com/a",
        "href": "docs/page?q=1",
        "src": None,
        "redirect": None,
        "nested": [
            {"url": None},
            {"href": None},
            {"src": "/images/logo.png"},
            {"redirect": None},
            {"url": "h%2574tps://example.com/encoded"},
            {"URL": None},
        ],
    }
    assert read_jsonl(output) == chained_records([("urls", cleaned)])


def test_url_probe_repeats_decoding_until_entities_and_escapes_stabilize(tmp_path):
    """Models that decode only once must miss active schemes split across percent and HTML layers."""
    payload = {
        "url": "jav%2526%2523x61%253Bscript:alert(1)",
        "href": "j%2520a%2520v%2520a%2520s%2520c%2520r%2520i%2520p%2520t:alert(1)",
        "src": "&#x68;ttps://safe.example/app",
        "redirect": "%252Faccount%252Fsettings",
    }
    line = json.dumps({"id": "deep-url", "payload": payload})
    output, rejected, _ = run_engine(tmp_path, [line])
    assert read_jsonl(output) == chained_records(
        [
            (
                "deep-url",
                {
                    "url": None,
                    "href": None,
                    "src": "&#x68;ttps://safe.example/app",
                    "redirect": "%252Faccount%252Fsettings",
                },
            )
        ]
    )
    assert rejected.read_text(encoding="utf-8") == ""


def test_malformed_url_parser_failures_null_only_that_field(tmp_path):
    """A parser-hostile URL must not crash the gateway or stop later accepted events."""
    lines = [
        json.dumps(
            {
                "id": "bad-url",
                "payload": {
                    "url": "https://[broken",
                    "href": "docs/continue",
                    "nested": {"redirect": "https://[also-broken"},
                },
            }
        ),
        json.dumps({"id": "after-url", "payload": {"url": "https://example.com/ok"}}),
    ]
    output, rejected, audit_db = run_engine(tmp_path, lines)
    expected = chained_records(
        [
            (
                "bad-url",
                {
                    "url": None,
                    "href": "docs/continue",
                    "nested": {"redirect": None},
                },
            ),
            ("after-url", {"url": "https://example.com/ok"}),
        ]
    )
    accepted = read_jsonl(output)
    assert accepted == expected
    assert rejected.read_text(encoding="utf-8") == ""
    assert read_security_events(audit_db) == [
        (1, "bad-url", "accepted", None, accepted[0]["digest"]),
        (2, "after-url", "accepted", None, accepted[1]["digest"]),
    ]


def test_custom_policy_changes_keys_and_allowed_schemes(tmp_path):
    """CLI-selected policy files must drive filtering and URL decisions instead of hardcoded defaults."""
    policy = {
        "blocked_keys": ["api_key"],
        "url_keys": ["endpoint"],
        "allowed_schemes": ["ftp"],
    }
    payload = {
        "API_KEY": "drop",
        "token": "keep",
        "endpoint": "ftp://files.example/a",
        "nested": {"endpoint": "https://example.com", "url": "javascript:kept-as-text"},
    }
    line = json.dumps({"id": "policy", "payload": payload})
    output, rejected, _ = run_engine(tmp_path, [line], policy)
    cleaned = {
        "token": "keep",
        "endpoint": "ftp://files.example/a",
        "nested": {"endpoint": None, "url": "javascript:kept-as-text"},
    }
    assert read_jsonl(output) == chained_records([("policy", cleaned)])
    assert rejected.read_text(encoding="utf-8") == ""


def test_rfc_json_and_envelope_errors_have_precise_reasons(tmp_path):
    """Non-RFC constants and syntax errors differ from valid JSON with an invalid envelope."""
    lines = [
        '{"id":"nan","payload":NaN}',
        "",
        "[]",
        '{"id":7,"payload":{}}',
        '{"id":"","payload":null}',
        '{"id":"extra","payload":{},"extra":1}',
    ]
    output, rejected, _ = run_engine(tmp_path, lines)
    assert output.read_text(encoding="utf-8") == ""
    assert read_jsonl(rejected) == [
        {"line": 1, "reason": "invalid_json"},
        {"line": 2, "reason": "invalid_json"},
        {"line": 3, "reason": "invalid_envelope"},
        {"line": 4, "reason": "invalid_envelope"},
        {"line": 5, "reason": "invalid_envelope"},
        {"line": 6, "reason": "invalid_envelope"},
    ]


def test_rejected_lines_do_not_interrupt_or_advance_the_hash_chain(tmp_path):
    """Accepted ordering and digest state must be unchanged by malformed attacks between good events."""
    first = canonical({"id": "first", "payload": {"v": 1}})
    second = canonical({"id": "second", "payload": {"v": 2}})
    output, rejected, audit_db = run_engine(tmp_path, [first, "{bad", second])
    assert read_jsonl(output) == chained_records([("first", {"v": 1}), ("second", {"v": 2})])
    assert read_jsonl(rejected) == [{"line": 2, "reason": "invalid_json"}]
    accepted = read_jsonl(output)
    assert read_security_events(audit_db) == [
        (1, "first", "accepted", None, accepted[0]["digest"]),
        (2, None, "rejected", "invalid_json", None),
        (3, "second", "accepted", None, accepted[1]["digest"]),
    ]


def test_security_ledger_is_recreated_instead_of_appended(tmp_path):
    """A second run against the same database must replace stale incident rows."""
    input_path = tmp_path / "input.jsonl"
    output_path = tmp_path / "output.jsonl"
    rejected_path = tmp_path / "rejected.jsonl"
    policy_path = tmp_path / "policy.json"
    audit_db_path = tmp_path / "security_audit.sqlite"
    policy_path.write_text(DEFAULT_POLICY.read_text(encoding="utf-8"), encoding="utf-8")

    input_path.write_text(canonical({"id": "old", "payload": {"v": 1}}) + "\n", encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            str(ENGINE),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--rejected",
            str(rejected_path),
            "--policy",
            str(policy_path),
            "--audit-db",
            str(audit_db_path),
        ],
        check=True,
    )
    assert read_security_events(audit_db_path)[0][1] == "old"

    input_path.write_text(canonical({"id": "new", "payload": {"v": 2}}) + "\n{bad\n", encoding="utf-8")
    subprocess.run(
        [
            sys.executable,
            str(ENGINE),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--rejected",
            str(rejected_path),
            "--policy",
            str(policy_path),
            "--audit-db",
            str(audit_db_path),
        ],
        check=True,
    )
    accepted = read_jsonl(output_path)
    assert read_security_events(audit_db_path) == [
        (1, "new", "accepted", None, accepted[0]["digest"]),
        (2, None, "rejected", "invalid_json", None),
    ]


def test_audit_outputs_are_compact_sorted_utf8_with_exact_fields(tmp_path):
    """Accepted and rejected audit artifacts must use canonical serialization without extra fields."""
    line = json.dumps({"id": "utf8", "payload": {"z": "café", "a": 1}}, ensure_ascii=False)
    output, rejected, _ = run_engine(tmp_path, [line, "not-json"])
    expected_record = chained_records([("utf8", {"z": "café", "a": 1})])[0]
    assert output.read_text(encoding="utf-8") == canonical(expected_record) + "\n"
    assert rejected.read_text(encoding="utf-8") == canonical({"line": 2, "reason": "invalid_json"}) + "\n"
    assert set(expected_record) == {"digest", "id", "payload"}


def test_every_json_payload_type_is_accepted(tmp_path):
    """Payload recursion must leave valid primitive roots intact as well as arrays and objects."""
    payloads = [None, True, 17, 2.5, "Ａ\u0000B", ["Ｃ", {"name": "Ｄ"}], {}]
    lines = [json.dumps({"id": f"p{index}", "payload": payload}) for index, payload in enumerate(payloads)]
    output, rejected, _ = run_engine(tmp_path, lines)
    cleaned = [None, True, 17, 2.5, "AB", ["C", {"name": "D"}], {}]
    assert read_jsonl(output) == chained_records([(f"p{index}", value) for index, value in enumerate(cleaned)])
    assert rejected.read_text(encoding="utf-8") == ""


def test_empty_input_creates_both_empty_outputs(tmp_path):
    """No gateway traffic is valid and must truncate or create both JSONL files and the ledger."""
    output, rejected, audit_db = run_engine(tmp_path, [])
    assert output.exists() and output.read_text(encoding="utf-8") == ""
    assert rejected.exists() and rejected.read_text(encoding="utf-8") == ""
    assert audit_db.exists()
    assert read_security_events(audit_db) == []


def test_hidden_default_policy_fixture_chains_deep_security_decisions(tmp_path):
    """Hidden traffic combines operator stripping, constructor blocking, nested URL smuggling, and faults."""
    lines = read_fixture_lines("default_policy_probe.input.jsonl")
    expected_pairs = read_fixture_json("default_policy_probe.expected_payloads.json")
    expected_rejected = read_fixture_json("default_policy_probe.expected_rejected.json")

    output, rejected, audit_db = run_engine(tmp_path, lines)
    accepted = read_jsonl(output)
    assert accepted == chained_records(expected_pairs)
    assert read_jsonl(rejected) == expected_rejected
    assert read_security_events(audit_db) == [
        (1, "h1", "accepted", None, accepted[0]["digest"]),
        (2, None, "rejected", "duplicate_key", None),
        (3, None, "rejected", "invalid_json", None),
        (4, "h4", "accepted", None, accepted[1]["digest"]),
        (5, None, "rejected", "invalid_envelope", None),
    ]


def test_hidden_custom_policy_fixture_keeps_security_rules_policy_driven(tmp_path):
    """Hidden custom policy traffic catches hardcoded URL keys, one-pass decoders, and ledger ordering."""
    lines = read_fixture_lines("custom_policy_probe.input.jsonl")
    policy = read_fixture_json("custom_policy_probe.policy.json")
    expected_pairs = read_fixture_json("custom_policy_probe.expected_payloads.json")
    expected_rejected = read_fixture_json("custom_policy_probe.expected_rejected.json")

    output, rejected, audit_db = run_engine(tmp_path, lines, policy)
    accepted = read_jsonl(output)
    assert accepted == chained_records(expected_pairs)
    assert read_jsonl(rejected) == expected_rejected
    assert read_security_events(audit_db) == [
        (1, "p1", "accepted", None, accepted[0]["digest"]),
        (2, "p2", "accepted", None, accepted[1]["digest"]),
        (3, None, "rejected", "duplicate_key", None),
        (4, None, "rejected", "invalid_json", None),
        (5, "p4", "accepted", None, accepted[2]["digest"]),
    ]
