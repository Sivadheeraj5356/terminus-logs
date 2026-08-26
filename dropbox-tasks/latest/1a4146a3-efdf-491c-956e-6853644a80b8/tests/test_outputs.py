"""Behavioral verifier for zone-publisher DNS publication gate."""

from __future__ import annotations

import json
from pathlib import Path

from conftest import run_publisher, run_publisher_args
from fixture_builder import (
    base_zone,
    change_obj,
    canonical_report,
    dump_canonical,
    make_blocked_freeze_bundle,
    make_composite_delegation_wildcard,
    make_composite_serial_freeze_exception,
    make_large_journal_bundle,
    make_publishable_bundle,
    soa_rdata,
    write_inputs,
)


def _paths(bundle: dict[str, Path]) -> tuple[Path, Path, Path, Path, Path]:
    return bundle["zone"], bundle["journal"], bundle["freezes"], bundle["exceptions"], bundle["report"]


"""Missing required CLI flags are fatal and do not create a report."""
def test_missing_required_flag_exits_two_without_report(tmp_path: Path) -> None:
    """Missing required CLI flags are fatal and do not create a report."""
    b = make_publishable_bundle(tmp_path / "m")
    report = b["report"]
    assert not report.exists()
    proc = run_publisher_args(
        ["--zone", str(b["zone"]), "--journal", str(b["journal"]), "--freezes", str(b["freezes"]), "--exceptions", str(b["exceptions"])]
    )
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr.strip() != ""
    assert not report.exists()


"""Unknown CLI flags are fatal contract errors with no report output."""
def test_unknown_flag_exits_two_without_report(tmp_path: Path) -> None:
    """Unknown CLI flags are fatal contract errors with no report output."""
    b = make_publishable_bundle(tmp_path / "u")
    z, j, f, e, r = _paths(b)
    proc = run_publisher_args(
        ["--zone", str(z), "--journal", str(j), "--freezes", str(f), "--exceptions", str(e), "--report", str(r), "--debug", "1"]
    )
    assert proc.returncode == 2
    assert not r.exists()


"""Duplicate CLI flags are fatal contract errors."""
def test_duplicate_flag_exits_two_without_report(tmp_path: Path) -> None:
    """Duplicate CLI flags are fatal contract errors."""
    b = make_publishable_bundle(tmp_path / "d")
    z, j, f, e, r = _paths(b)
    proc = run_publisher_args(
        [
            "--zone",
            str(z),
            "--zone",
            str(z),
            "--journal",
            str(j),
            "--freezes",
            str(f),
            "--exceptions",
            str(e),
            "--report",
            str(r),
        ]
    )
    assert proc.returncode == 2
    assert not r.exists()


"""Stdout stays empty for both publishable and blocked valid inputs."""
def test_stdout_empty_on_publishable_and_blocked_runs(tmp_path: Path) -> None:
    """Stdout stays empty for both publishable and blocked valid inputs."""
    pub = make_publishable_bundle(tmp_path / "p")
    blocked = make_blocked_freeze_bundle(tmp_path / "b")
    for bundle, expected in ((pub, 0), (blocked, 1)):
        z, j, f, e, r = _paths(bundle)
        proc = run_publisher(z, j, f, e, r)
        assert proc.returncode == expected
        assert proc.stdout == ""


"""Blocked valid runs do not write progress text to stderr."""
def test_stderr_only_for_fatal_errors(tmp_path: Path) -> None:
    """Blocked valid runs do not write progress text to stderr."""
    b = make_blocked_freeze_bundle(tmp_path / "s")
    z, j, f, e, r = _paths(b)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 1
    assert proc.stderr == ""


"""Freeze CSV headers must be exact and ordered."""
def test_malformed_freeze_header_exits_two(tmp_path: Path) -> None:
    """Freeze CSV headers must be exact and ordered."""
    b = make_publishable_bundle(tmp_path / "fh")
    bad = tmp_path / "fh" / "bad_freezes.csv"
    bad.write_text("zone,freeze_id,owner_suffix,record_type,start_utc,end_utc,reason\n")
    z, j, _, e, r = _paths(b)
    proc = run_publisher(z, j, bad, e, r)
    assert proc.returncode == 2
    assert "header" in proc.stderr.lower() or "freeze" in proc.stderr.lower()


"""Invalid non-UTC timestamps are rejected as fatal input errors."""
def test_invalid_non_utc_timestamp_exits_two(tmp_path: Path) -> None:
    """Invalid non-UTC timestamps are rejected as fatal input errors."""
    zone = "example.com."
    bundle = write_inputs(
        tmp_path / "ts",
        base_zone(zone, 1),
        [
            change_obj(
                "c1",
                1,
                "replace",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(2),
                "2026-03-01T12:00:00+00:00",
            )
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 2


"""Malformed NDJSON journal records are fatal input errors."""
def test_journal_bad_ndjson_exits_two(tmp_path: Path) -> None:
    """Malformed NDJSON journal records are fatal input errors."""
    b = make_publishable_bundle(tmp_path / "nd")
    j = tmp_path / "nd" / "bad.ndjson"
    j.write_text("{not-json\n")
    z, _, f, e, r = _paths(b)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 2


"""Unknown DNS record types are fatal input errors."""
def test_unknown_record_type_exits_two(tmp_path: Path) -> None:
    """Unknown DNS record types are fatal input errors."""
    zone = "example.com."
    bundle = write_inputs(
        tmp_path / "urt",
        base_zone(zone, 1),
        [
            change_obj("c1", 1, "add", zone, f"x.{zone}", 300, "SPF", "v=spf1", "2026-03-01T12:00:00Z"),
            change_obj(
                "soa",
                1,
                "replace",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(2),
                "2026-03-01T12:00:00Z",
            ),
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 2


"""Fatal runs preserve an existing report byte-for-byte."""
def test_atomic_report_keeps_old_file_on_fatal(tmp_path: Path) -> None:
    """Fatal runs preserve an existing report byte-for-byte."""
    b = make_publishable_bundle(tmp_path / "at")
    z, j, f, e, r = _paths(b)
    sentinel = b'{"keep":"me","nonce":"dns-zone-freeze"}\n'
    r.write_bytes(sentinel)
    bad_journal = tmp_path / "at" / "bad.ndjson"
    bad_journal.write_text("{broken\n")
    proc = run_publisher(z, bad_journal, f, e, r)
    assert proc.returncode == 2
    assert r.read_bytes() == sentinel


"""Publishable reports use canonical top-level key order and empty arrays."""
def test_byte_exact_publishable_report_shape(tmp_path: Path) -> None:
    """Publishable reports use canonical top-level key order and empty arrays."""
    b = make_publishable_bundle(tmp_path / "be1")
    z, j, f, e, r = _paths(b)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 0
    expected = dump_canonical(canonical_report(z, j, f, e))
    assert r.read_text() == expected
    assert list(json.loads(expected).keys()) == [
        "format_version",
        "inputs",
        "summary",
        "findings",
        "suppressed",
        "candidate",
    ]
    assert '"findings": []' in expected
    assert expected.endswith("\n")


"""Blocked reports are byte-stable with canonical finding keys and sort order."""
def test_byte_exact_blocked_report_sorting_and_key_order(tmp_path: Path) -> None:
    """Blocked reports are byte-stable with canonical finding keys and sort order."""
    zone = "sort.example."
    bundle = write_inputs(
        tmp_path / "be2",
        base_zone(zone, 5),
        [
            change_obj(
                "soa",
                1,
                "replace",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(6, f"ns1.{zone}", f"hostmaster.{zone}"),
                "2026-04-01T00:00:00Z",
            ),
            change_obj("a", 1, "add", zone, f"b.{zone}", 300, "A", "192.0.2.2", "2026-04-01T00:00:00Z"),
            change_obj("b", 1, "add", zone, f"a.{zone}", 300, "A", "192.0.2.3", "2026-04-01T00:00:00Z"),
        ],
        freeze_rows=[
            ["FZ1", zone, zone, "A", "2026-04-01T00:00:00Z", "2026-04-02T00:00:00Z", "all a"],
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 1
    expected = dump_canonical(canonical_report(z, j, f, e))
    assert r.read_text() == expected
    findings = json.loads(expected)["findings"]
    assert findings
    assert list(findings[0].keys()) == ["zone", "owner", "record_type", "code", "severity", "evidence"]
    owners = [x["owner"] for x in findings]
    assert owners == sorted(owners)


"""Candidate summary fields and the single trailing newline are byte-exact."""
def test_byte_exact_candidate_summary_and_newline(tmp_path: Path) -> None:
    """Candidate summary fields and the single trailing newline are byte-exact."""
    b = make_publishable_bundle(tmp_path / "be3")
    z, j, f, e, r = _paths(b)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 0
    body = r.read_bytes()
    assert body.endswith(b"\n")
    assert not body.endswith(b"\n\n")
    obj = json.loads(body)
    assert list(obj["candidate"].keys()) == ["zone", "soa_serial", "record_count", "delegation_count"]
    assert obj["candidate"]["soa_serial"] == 101


"""Repeated runs on the same valid inputs produce byte-identical reports."""
def test_repeated_valid_run_is_byte_identical(tmp_path: Path) -> None:
    """Repeated runs on the same valid inputs produce byte-identical reports."""
    b = make_blocked_freeze_bundle(tmp_path / "rep")
    z, j, f, e, r = _paths(b)
    proc1 = run_publisher(z, j, f, e, r)
    body1 = r.read_bytes()
    proc2 = run_publisher(z, j, f, e, r)
    body2 = r.read_bytes()
    assert proc1.returncode == proc2.returncode == 1
    assert body1 == body2


"""SOA serial advancement uses 32-bit wraparound arithmetic."""
def test_soa_serial_wraparound_is_advanced(tmp_path: Path) -> None:
    """SOA serial advancement uses 32-bit wraparound arithmetic."""
    zone = "example.com."
    bundle = write_inputs(
        tmp_path / "wrap1",
        base_zone(zone, 4294967295),
        [
            change_obj(
                "soa",
                1,
                "replace",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(1),
                "2026-03-01T12:00:00Z",
            )
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 0
    obj = json.loads(r.read_text())
    assert obj["summary"]["publishable"] is True
    assert obj["candidate"]["soa_serial"] == 1


"""Wrapped serials that look smaller as integers can still be advanced."""
def test_soa_serial_normal_integer_comparison_is_not_enough(tmp_path: Path) -> None:
    """Wrapped serials that look smaller as integers can still be advanced."""
    zone = "example.com."
    # original 4000000000, candidate 100 — integer < but serial advanced
    bundle = write_inputs(
        tmp_path / "wrap2",
        base_zone(zone, 4000000000),
        [
            change_obj(
                "soa",
                1,
                "replace",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(100),
                "2026-03-01T12:00:00Z",
            )
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 0
    assert json.loads(r.read_text())["summary"]["publishable"] is True


"""SOA serials exactly half the 32-bit space ahead are not advanced."""
def test_soa_serial_half_range_boundary_is_not_advanced(tmp_path: Path) -> None:
    """SOA serials exactly half the 32-bit space ahead are not advanced."""
    zone = "example.com."
    bundle = write_inputs(
        tmp_path / "wrap_boundary",
        base_zone(zone, 10),
        [
            change_obj(
                "soa",
                1,
                "replace",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(2_147_483_658),
                "2026-03-01T12:00:00Z",
            )
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    expected = canonical_report(z, j, f, e)
    assert proc.returncode == 1
    assert r.read_text() == dump_canonical(expected)
    assert expected["findings"][0]["code"] == "SERIAL_NOT_ADVANCED"


"""The candidate apex must contain exactly one SOA record."""
def test_exactly_one_apex_soa_required(tmp_path: Path) -> None:
    """The candidate apex must contain exactly one SOA record."""
    zone = "example.com."
    bundle = write_inputs(
        tmp_path / "soa_count",
        base_zone(zone, 10),
        [
            change_obj(
                "soa2",
                1,
                "add",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(11),
                "2026-03-01T12:00:00Z",
            )
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 1
    codes = {x["code"] for x in json.loads(r.read_text())["findings"]}
    assert "SOA_COUNT" in codes


"""A CNAME at the zone apex produces a blocking finding."""
def test_apex_cname_is_blocking(tmp_path: Path) -> None:
    """A CNAME at the zone apex produces a blocking finding."""
    zone = "example.com."
    bundle = write_inputs(
        tmp_path / "apex",
        base_zone(zone, 10),
        [
            change_obj(
                "soa",
                1,
                "replace",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(11),
                "2026-03-01T12:00:00Z",
            ),
            change_obj(
                "cn",
                1,
                "add",
                zone,
                zone,
                300,
                "CNAME",
                f"other.{zone}",
                "2026-03-01T12:00:00Z",
            ),
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 1
    codes = {x["code"] for x in json.loads(r.read_text())["findings"]}
    assert "APEX_CNAME" in codes


"""CNAME owners may only coexist with documented DNSSEC side records."""
def test_cname_conflict_allows_only_dnssec_side_records(tmp_path: Path) -> None:
    """CNAME owners may only coexist with documented DNSSEC side records."""
    zone = "example.com."
    bundle = write_inputs(
        tmp_path / "cnc",
        base_zone(zone, 10),
        [
            change_obj(
                "soa",
                1,
                "replace",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(11),
                "2026-03-01T12:00:00Z",
            ),
            change_obj(
                "cn",
                1,
                "add",
                zone,
                f"www2.{zone}",
                300,
                "CNAME",
                f"www.{zone}",
                "2026-03-01T12:00:00Z",
            ),
            change_obj(
                "mx",
                1,
                "add",
                zone,
                f"www2.{zone}",
                300,
                "MX",
                f"10 mail.{zone}",
                "2026-03-01T12:00:00Z",
            ),
            change_obj(
                "ok",
                1,
                "add",
                zone,
                f"secure.{zone}",
                300,
                "CNAME",
                f"www.{zone}",
                "2026-03-01T12:00:00Z",
            ),
            change_obj(
                "nsec",
                1,
                "add",
                zone,
                f"secure.{zone}",
                300,
                "NSEC",
                f"www.{zone} A",
                "2026-03-01T12:00:00Z",
            ),
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 1
    findings = json.loads(r.read_text())["findings"]
    conflicts = [x for x in findings if x["code"] == "CNAME_CONFLICT"]
    assert any(x["owner"] == f"www2.{zone}" for x in conflicts)
    assert not any(x["owner"] == f"secure.{zone}" and x["code"] == "CNAME_CONFLICT" for x in findings)


"""Deleting a record absent from the candidate produces UNKNOWN_DELETE."""
def test_unknown_delete_becomes_blocking_finding(tmp_path: Path) -> None:
    """Deleting a record absent from the candidate produces UNKNOWN_DELETE."""
    zone = "example.com."
    bundle = write_inputs(
        tmp_path / "udel",
        base_zone(zone, 10),
        [
            change_obj(
                "soa",
                1,
                "replace",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(11),
                "2026-03-01T12:00:00Z",
            ),
            change_obj(
                "del",
                1,
                "delete",
                zone,
                f"missing.{zone}",
                0,
                "A",
                "192.0.2.9",
                "2026-03-01T12:00:00Z",
            ),
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 1
    assert any(x["code"] == "UNKNOWN_DELETE" for x in json.loads(r.read_text())["findings"])


"""Replace actions remove existing records with the same owner and type before adding."""
def test_replace_action_removes_existing_record_type_before_add(tmp_path: Path) -> None:
    """Replace actions remove existing records with the same owner and type before adding."""
    zone = "example.com."
    bundle = write_inputs(
        tmp_path / "repl",
        base_zone(zone, 10),
        [
            change_obj(
                "soa",
                1,
                "replace",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(11),
                "2026-03-01T12:00:00Z",
            ),
            change_obj(
                "www",
                1,
                "replace",
                zone,
                f"www.{zone}",
                300,
                "A",
                "192.0.2.99",
                "2026-03-01T12:00:00Z",
            ),
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 0
    # record_count unchanged vs base (replace www A, replace SOA)
    obj = json.loads(r.read_text())
    assert obj["candidate"]["record_count"] == 4


"""Journal actions are applied by change_id order rather than input row order."""
def test_journal_application_order_is_sorted_by_change_id(tmp_path: Path) -> None:
    """Journal actions are applied by change_id order rather than input row order."""
    zone = "example.com."
    bundle = write_inputs(
        tmp_path / "apply_order",
        base_zone(zone, 10),
        [
            change_obj(
                "0-soa",
                1,
                "replace",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(11),
                "2026-03-01T12:00:00Z",
            ),
            change_obj(
                "b-add",
                1,
                "add",
                zone,
                f"late.{zone}",
                300,
                "A",
                "192.0.2.44",
                "2026-03-01T12:00:00Z",
            ),
            change_obj(
                "a-delete",
                1,
                "delete",
                zone,
                f"late.{zone}",
                0,
                "A",
                "192.0.2.44",
                "2026-03-01T12:00:00Z",
            ),
        ],
        shuffle_journal=False,
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    expected = canonical_report(z, j, f, e)
    assert proc.returncode == 1
    assert r.read_text() == dump_canonical(expected)
    assert any(x["code"] == "UNKNOWN_DELETE" and x["owner"] == f"late.{zone}" for x in expected["findings"])
    assert expected["candidate"]["record_count"] == 5


"""Delete actions remove only the exact owner, type, and rdata match."""
def test_delete_action_removes_only_exact_rdata(tmp_path: Path) -> None:
    """Delete actions remove only the exact owner, type, and rdata match."""
    zone = "example.com."
    bundle = write_inputs(
        tmp_path / "delete_exact",
        base_zone(zone, 10),
        [
            change_obj(
                "0-soa",
                1,
                "replace",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(11),
                "2026-03-01T12:00:00Z",
            ),
            change_obj(
                "a-add-new",
                1,
                "add",
                zone,
                f"www.{zone}",
                300,
                "A",
                "192.0.2.11",
                "2026-03-01T12:00:00Z",
            ),
            change_obj(
                "b-delete-old",
                1,
                "delete",
                zone,
                f"www.{zone}",
                0,
                "A",
                "192.0.2.10",
                "2026-03-01T12:00:00Z",
            ),
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    expected = canonical_report(z, j, f, e)
    assert proc.returncode == 0
    assert r.read_text() == dump_canonical(expected)
    assert expected["candidate"]["record_count"] == 4


"""Delegated in-zone nameservers require matching glue records."""
def test_in_zone_delegation_requires_glue(tmp_path: Path) -> None:
    """Delegated in-zone nameservers require matching glue records."""
    zone = "example.com."
    bundle = write_inputs(
        tmp_path / "glue_in",
        base_zone(zone, 10),
        [
            change_obj(
                "soa",
                1,
                "replace",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(11),
                "2026-03-01T12:00:00Z",
            ),
            change_obj(
                "del",
                1,
                "add",
                zone,
                f"sub.{zone}",
                3600,
                "NS",
                f"ns.sub.{zone}",
                "2026-03-01T12:00:00Z",
            ),
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 1
    assert any(x["code"] == "DELEGATION_GLUE_MISSING" for x in json.loads(r.read_text())["findings"])


"""Out-of-zone delegated nameservers do not require glue."""
def test_out_of_zone_delegation_does_not_require_glue(tmp_path: Path) -> None:
    """Out-of-zone delegated nameservers do not require glue."""
    zone = "example.com."
    bundle = write_inputs(
        tmp_path / "glue_out",
        base_zone(zone, 10),
        [
            change_obj(
                "soa",
                1,
                "replace",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(11),
                "2026-03-01T12:00:00Z",
            ),
            change_obj(
                "del",
                1,
                "add",
                zone,
                f"sub.{zone}",
                3600,
                "NS",
                "ns.other.net.",
                "2026-03-01T12:00:00Z",
            ),
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 0
    assert json.loads(r.read_text())["summary"]["publishable"] is True


"""Wildcard records below a delegated child zone cut are blocking."""
def test_wildcard_below_delegation_is_blocking(tmp_path: Path) -> None:
    """Wildcard records below a delegated child zone cut are blocking."""
    zone = "example.com."
    bundle = write_inputs(
        tmp_path / "wild",
        base_zone(zone, 10),
        [
            change_obj(
                "soa",
                1,
                "replace",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(11),
                "2026-03-01T12:00:00Z",
            ),
            change_obj(
                "del",
                1,
                "add",
                zone,
                f"child.{zone}",
                3600,
                "NS",
                "ns.external.net.",
                "2026-03-01T12:00:00Z",
            ),
            change_obj(
                "w",
                1,
                "add",
                zone,
                f"*.child.{zone}",
                300,
                "A",
                "192.0.2.7",
                "2026-03-01T12:00:00Z",
            ),
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 1
    assert any(x["code"] == "WILDCARD_BELOW_DELEGATION" for x in json.loads(r.read_text())["findings"])


"""Freeze findings apply only when zone, suffix, type, and time match."""
def test_freeze_window_matches_zone_suffix_type_and_time(tmp_path: Path) -> None:
    """Freeze findings apply only when zone, suffix, type, and time match."""
    zone = "example.com."
    bundle = write_inputs(
        tmp_path / "fz",
        base_zone(zone, 10),
        [
            change_obj(
                "soa",
                1,
                "replace",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(11),
                "2026-03-01T12:00:00Z",
            ),
            change_obj(
                "hit",
                1,
                "add",
                zone,
                f"api.{zone}",
                300,
                "A",
                "192.0.2.5",
                "2026-03-01T12:00:00Z",
            ),
            change_obj(
                "miss_time",
                1,
                "add",
                zone,
                f"api.{zone}",
                300,
                "AAAA",
                "2001:db8::1",
                "2026-04-01T12:00:00Z",
            ),
            change_obj(
                "miss_owner",
                1,
                "add",
                zone,
                f"other.{zone}",
                300,
                "A",
                "192.0.2.6",
                "2026-03-01T12:00:00Z",
            ),
        ],
        freeze_rows=[
            ["FZ1", zone, f"api.{zone}", "A", "2026-03-01T00:00:00Z", "2026-03-02T00:00:00Z", "api A only"],
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 1
    freezes = [x for x in json.loads(r.read_text())["findings"] if x["code"] == "FREEZE_WINDOW"]
    assert len(freezes) == 1
    assert freezes[0]["owner"] == f"api.{zone}"
    assert freezes[0]["record_type"] == "A"


"""Exceptions suppress only matching code, zone, suffix, type, and time."""
def test_exception_suppresses_only_matching_scope(tmp_path: Path) -> None:
    """Exceptions suppress only matching code, zone, suffix, type, and time."""
    zone = "example.com."
    bundle = write_inputs(
        tmp_path / "ex",
        base_zone(zone, 10),
        [
            change_obj(
                "soa",
                1,
                "replace",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(11),
                "2026-03-01T12:00:00Z",
            ),
            change_obj(
                "a1",
                1,
                "add",
                zone,
                f"api.{zone}",
                300,
                "A",
                "192.0.2.5",
                "2026-03-01T12:00:00Z",
            ),
            change_obj(
                "a2",
                1,
                "add",
                zone,
                f"web.{zone}",
                300,
                "A",
                "192.0.2.6",
                "2026-03-01T12:00:00Z",
            ),
        ],
        freeze_rows=[
            ["FZ1", zone, zone, "A", "2026-03-01T00:00:00Z", "2026-03-02T00:00:00Z", "broad"],
        ],
        exception_rows=[
            [
                "EX1",
                zone,
                f"api.{zone}",
                "A",
                "FREEZE_WINDOW",
                "2026-03-01T00:00:00Z",
                "2026-03-02T00:00:00Z",
                "api only",
            ],
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 1
    obj = json.loads(r.read_text())
    assert any(x["owner"] == f"api.{zone}" for x in obj["suppressed"])
    assert any(x["owner"] == f"web.{zone}" and x["code"] == "FREEZE_WINDOW" for x in obj["findings"])


"""Exceptions for non-freeze findings use the matching owner/type mutation time."""
def test_exception_suppresses_cname_conflict_by_owner_mutation_time(tmp_path: Path) -> None:
    """Exceptions for non-freeze findings use the matching owner/type mutation time."""
    zone = "example.com."
    bundle = write_inputs(
        tmp_path / "ex_cname_time",
        base_zone(zone, 20),
        [
            change_obj(
                "soa",
                1,
                "replace",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(21),
                "2026-01-01T00:00:00Z",
            ),
            change_obj(
                "cn",
                1,
                "add",
                zone,
                f"edge.{zone}",
                300,
                "CNAME",
                f"www.{zone}",
                "2026-08-15T09:30:00Z",
            ),
            change_obj(
                "mx",
                1,
                "add",
                zone,
                f"edge.{zone}",
                300,
                "MX",
                f"10 mail.{zone}",
                "2026-08-15T09:35:00Z",
            ),
        ],
        exception_rows=[
            [
                "EX-CN",
                zone,
                f"edge.{zone}",
                "CNAME",
                "CNAME_CONFLICT",
                "2026-08-15T00:00:00Z",
                "2026-08-16T00:00:00Z",
                "edge migration approved",
            ],
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    expected = canonical_report(z, j, f, e)
    assert proc.returncode == 0
    assert r.read_text() == dump_canonical(expected)
    assert expected["summary"] == {"publishable": True, "findings": 0, "suppressed": 1, "active_changes": 3}
    assert expected["suppressed"][0]["exception_id"] == "EX-CN"


"""Exceptions do not convert fatal input errors into findings."""
def test_exception_does_not_suppress_fatal_input(tmp_path: Path) -> None:
    """Exceptions do not convert fatal input errors into findings."""
    zone = "example.com."
    bundle = write_inputs(
        tmp_path / "exf",
        base_zone(zone, 10),
        [
            change_obj(
                "bad",
                1,
                "add",
                zone,
                f"x.{zone}",
                300,
                "SPF",
                "v=spf1",
                "2026-03-01T12:00:00Z",
            )
        ],
        exception_rows=[
            [
                "EX1",
                zone,
                zone,
                "*",
                "TTL_OUT_OF_RANGE",
                "2020-01-01T00:00:00Z",
                "2030-01-01T00:00:00Z",
                "irrelevant",
            ],
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 2
    assert not r.exists()


"""Journal corrections use the highest sequence, not row order."""
def test_change_correction_uses_highest_sequence(tmp_path: Path) -> None:
    """Journal corrections use the highest sequence, not row order."""
    zone = "example.com."
    # Highest seq (5) has canonical TXT; a later lower-seq row is non-canonical.
    # Row-order / last-wins implementations keep the non-canonical TXT and block.
    rows = [
        change_obj(
            "soa",
            1,
            "replace",
            zone,
            zone,
            3600,
            "SOA",
            soa_rdata(11),
            "2026-03-01T12:00:00Z",
        ),
        change_obj(
            "txt",
            5,
            "add",
            zone,
            f"info.{zone}",
            300,
            "TXT",
            '"alpha" "beta"',
            "2026-03-01T12:00:00Z",
        ),
        change_obj(
            "txt",
            1,
            "add",
            zone,
            f"info.{zone}",
            300,
            "TXT",
            '"alpha"   "beta"',
            "2026-03-01T12:00:00Z",
        ),
        change_obj(
            "fix",
            8,
            "replace",
            zone,
            f"info.{zone}",
            300,
            "TXT",
            '"alpha" "beta"',
            "2026-03-01T12:00:00Z",
            correction_of="txt",
            reason="canonicalize",
        ),
        change_obj(
            "fix",
            2,
            "replace",
            zone,
            f"info.{zone}",
            300,
            "TXT",
            '"alpha"    "beta"',
            "2026-03-01T12:00:00Z",
            correction_of="txt",
            reason="stale spaced",
        ),
    ]
    # Highest-seq rows first; stale lower-seq rows last (tempting for last-wins code).
    ordered = [rows[0], rows[1], rows[3], rows[2], rows[4]]
    bundle = write_inputs(tmp_path / "corr", base_zone(zone, 10), ordered, shuffle_journal=False)
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 0
    expected = canonical_report(z, j, f, e)
    assert expected["summary"]["publishable"] is True
    assert expected["summary"]["findings"] == 0
    assert r.read_text() == dump_canonical(expected)
    assert expected["summary"]["active_changes"] == 2
    # Ensure the journal still contains the stale lower-seq TXT payload.
    assert "stale spaced" in j.read_text()


"""TXT canonical checks preserve escaped quotes and quoted internal spacing."""
def test_txt_canonical_preserves_escaped_quotes_and_internal_spacing(tmp_path: Path) -> None:
    """TXT canonical checks preserve escaped quotes and quoted internal spacing."""
    zone = "example.com."
    bundle = write_inputs(
        tmp_path / "txt_escape",
        base_zone(zone, 10),
        [
            change_obj(
                "soa",
                1,
                "replace",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(11),
                "2026-03-01T12:00:00Z",
            ),
            change_obj(
                "txt",
                1,
                "add",
                zone,
                f"quote.{zone}",
                300,
                "TXT",
                r'"alpha\"  beta" "gamma"',
                "2026-03-01T12:00:00Z",
            ),
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    expected = canonical_report(z, j, f, e)
    assert proc.returncode == 0
    assert r.read_text() == dump_canonical(expected)
    assert "TXT_CANONICAL" not in {x["code"] for x in expected["findings"]}


"""Duplicate active changes with the same id and sequence are fatal."""
def test_duplicate_change_same_sequence_is_fatal(tmp_path: Path) -> None:
    """Duplicate active changes with the same id and sequence are fatal."""
    zone = "example.com."
    row = change_obj(
        "dup",
        3,
        "add",
        zone,
        f"x.{zone}",
        300,
        "A",
        "192.0.2.1",
        "2026-03-01T12:00:00Z",
    )
    bundle = write_inputs(
        tmp_path / "dup",
        base_zone(zone, 10),
        [
            change_obj(
                "soa",
                1,
                "replace",
                zone,
                zone,
                3600,
                "SOA",
                soa_rdata(11),
                "2026-03-01T12:00:00Z",
            ),
            row,
            dict(row),
        ],
    )
    z, j, f, e, r = _paths(bundle)
    proc = run_publisher(z, j, f, e, r)
    assert proc.returncode == 2


"""Wrapped serials, freeze windows, and scoped exceptions interact correctly."""
def test_composite_serial_wrap_freeze_and_exception_scope(tmp_path: Path) -> None:
    """Wrapped serials, freeze windows, and scoped exceptions interact correctly."""
    b = make_composite_serial_freeze_exception(tmp_path / "comp1")
    z, j, f, e, r = _paths(b)
    proc = run_publisher(z, j, f, e, r)
    expected = canonical_report(z, j, f, e)
    assert proc.returncode == (0 if expected["summary"]["publishable"] else 1)
    assert r.read_text() == dump_canonical(expected)
    obj = expected
    assert obj["candidate"]["soa_serial"] == 1
    assert any(x["code"] == "FREEZE_WINDOW" for x in obj["suppressed"])
    assert not any(x["owner"].startswith("other.") and x["code"] == "FREEZE_WINDOW" for x in obj["findings"])
    assert obj["summary"]["publishable"] is True


"""Delegation checks combine wildcard boundaries and in-zone glue rules."""
def test_composite_delegation_wildcard_and_glue(tmp_path: Path) -> None:
    """Delegation checks combine wildcard boundaries and in-zone glue rules."""
    b = make_composite_delegation_wildcard(tmp_path / "comp2")
    z, j, f, e, r = _paths(b)
    proc = run_publisher(z, j, f, e, r)
    expected = canonical_report(z, j, f, e)
    assert proc.returncode == 1
    assert r.read_text() == dump_canonical(expected)
    codes = {x["code"] for x in expected["findings"]}
    assert "DELEGATION_GLUE_MISSING" in codes
    assert "WILDCARD_BELOW_DELEGATION" in codes
    # out-of-zone ext NS must not produce glue finding for ns.external.net.
    glue = [x for x in expected["findings"] if x["code"] == "DELEGATION_GLUE_MISSING"]
    assert all("external.net" not in x["evidence"] for x in glue)
    assert glue[0]["evidence"] == "in-zone delegated nameserver lacks glue ns.child.cut.example."
    assert glue[0]["record_type"] == "NS"
    wild = [x for x in expected["findings"] if x["code"] == "WILDCARD_BELOW_DELEGATION"]
    assert wild[0]["record_type"] == "A"
    assert wild[0]["evidence"] == "wildcard owner lies below a delegated zone cut"


"""Large reordered journals preserve CNAME, TXT, and correction semantics."""
def test_composite_cname_txt_and_large_journal_ordering(tmp_path: Path) -> None:
    """Large reordered journals preserve CNAME, TXT, and correction semantics."""
    b = make_large_journal_bundle(tmp_path / "comp3", lines=10000)
    z, j, f, e, r = _paths(b)
    # also emit a second 10k scale companion used only for byte-stability of digests path
    b2 = make_large_journal_bundle(tmp_path / "comp3b", lines=2000)
    proc = run_publisher(z, j, f, e, r)
    expected = canonical_report(z, j, f, e)
    assert proc.stdout == ""
    assert proc.returncode == (0 if expected["summary"]["publishable"] else 1)
    assert r.read_text() == dump_canonical(expected)
    # ensure scale
    assert expected["summary"]["active_changes"] >= 1000
    assert sum(1 for _ in j.open()) >= 5000
    # TXT should be canonical so no TXT_CANONICAL; CNAME without MX
    codes = {x["code"] for x in expected["findings"]}
    assert "TXT_CANONICAL" not in codes
    assert "CNAME_CONFLICT" not in codes
    # companion fixture builds independently (anti-hardcode)
    _ = canonical_report(b2["zone"], b2["journal"], b2["freezes"], b2["exceptions"])
    assert b2["journal"].stat().st_size > 1000
