import hashlib
import json
import os
import subprocess


REPORT_PATH = "/app/output/report.json"
BINARY_PATH = "/app/bin/marcrec"
EXPECTED_REPORT_DIGEST = "0de1da0b53eb53e5"
SCHEMA_VERSION = "marc-classifier-v1"

VERDICT_ENUM = [
    "CONTROL_FIELD_ACCEPTED",
    "DATA_FIELD_ACCEPTED",
    "LEADER_DECODED",
    "SUBFIELD_DELIMITER_MISSING",
    "TAG_OUT_OF_RANGE",
    "INDICATOR_NONBLANK_REJECTED",
    "ENCODING_PIN_RESCUED",
    "DUPLICATE_TAG_DROPPED",
    "CASCADE_QUARANTINED",
    "LEADER_BASE_ADDR_INVALID",
]

EXPECTED_BY_VERDICT = {
    "CASCADE_QUARANTINED": 1,
    "CONTROL_FIELD_ACCEPTED": 2,
    "DATA_FIELD_ACCEPTED": 7,
    "DUPLICATE_TAG_DROPPED": 1,
    "ENCODING_PIN_RESCUED": 1,
    "INDICATOR_NONBLANK_REJECTED": 1,
    "LEADER_BASE_ADDR_INVALID": 1,
    "LEADER_DECODED": 7,
    "SUBFIELD_DELIMITER_MISSING": 1,
    "TAG_OUT_OF_RANGE": 3,
}

SHELVES = {
    "alpha": "/app/shelves/catalog_alpha.mrk",
    "beta": "/app/shelves/catalog_beta.ndj",
    "gamma": "/app/shelves/catalog_gamma.fwt",
}


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_report():
    with open(REPORT_PATH) as fh:
        return json.load(fh)


def _find(rows, **kwargs):
    for row in rows:
        if all(row.get(k) == v for k, v in kwargs.items()):
            return row
    return None


def test_report_file_exists_and_is_valid_json():
    """The classifier writes a parseable JSON envelope to /app/output/report.json."""
    assert os.path.isfile(REPORT_PATH), f"missing {REPORT_PATH}"
    with open(REPORT_PATH) as fh:
        json.load(fh)


def test_top_level_keys_present_and_in_order():
    """report.json top level keys are report_digest, schema_version, records, by_verdict, summary in that declared order."""
    with open(REPORT_PATH) as fh:
        data = json.load(fh)
    assert list(data.keys()) == [
        "report_digest",
        "schema_version",
        "records",
        "by_verdict",
        "summary",
    ]


def test_schema_version_is_marc_classifier_v1():
    """schema_version field carries the pinned marc-classifier-v1 string."""
    data = _load_report()
    assert data["schema_version"] == SCHEMA_VERSION


def test_report_digest_matches_expected_sha256_prefix():
    """report_digest is the first 16 hex chars of sha256 over Go json marshal of records, by_verdict, summary in struct declaration order."""
    data = _load_report()
    assert data["report_digest"] == EXPECTED_REPORT_DIGEST


def test_total_records_is_twenty_five():
    """Twenty five classification rows in total: alpha contributes 9, beta contributes 9, gamma contributes 7 (one extra DATA accept between the two TAG_OUT_OF_RANGE fields)."""
    data = _load_report()
    assert data["summary"]["total_records"] == 25
    assert len(data["records"]) == 25


def test_by_verdict_zero_fill_and_full_enum():
    """by_verdict carries every one of the ten canonical verdicts as a key, none missing, none extra."""
    data = _load_report()
    assert set(data["by_verdict"].keys()) == set(VERDICT_ENUM)


def test_by_verdict_counts_match_per_verdict_oracle():
    """Verdict counts match the oracle distribution across all twenty five rows."""
    data = _load_report()
    assert data["by_verdict"] == EXPECTED_BY_VERDICT


def test_pin_consumed_count_is_one():
    """summary.pin_consumed_count is one because only beta record two's leader is rescued via HMAC seal."""
    data = _load_report()
    assert data["summary"]["pin_consumed_count"] == 1


def test_cascade_arms_total_is_one():
    """summary.cascade_arms_total is one because gamma reaches the two cumulative TAG_OUT_OF_RANGE threshold exactly once."""
    data = _load_report()
    assert data["summary"]["cascade_arms_total"] == 1


def test_alpha_record_one_leader_then_control_then_two_data_admits():
    """alpha record_seq 1: f1 LEADER_DECODED, f2 tag 001 CONTROL_FIELD_ACCEPTED, f3 tag 245 DATA_FIELD_ACCEPTED, f4 tag 260 DATA_FIELD_ACCEPTED."""
    rows = _load_report()["records"]
    a1 = [r for r in rows if r["shard"] == "alpha" and r["record_seq"] == 1]
    assert len(a1) == 4
    assert a1[0]["tag"] == "LDR" and a1[0]["verdict"] == "LEADER_DECODED"
    assert a1[1]["tag"] == "001" and a1[1]["verdict"] == "CONTROL_FIELD_ACCEPTED"
    assert a1[2]["tag"] == "245" and a1[2]["verdict"] == "DATA_FIELD_ACCEPTED"
    assert a1[3]["tag"] == "260" and a1[3]["verdict"] == "DATA_FIELD_ACCEPTED"


def test_alpha_record_two_245_with_bang_bang_indicator_rejected():
    """alpha record_seq 2 field 245 carries indicator !! which is not space, digit, or lower alpha so it scores INDICATOR_NONBLANK_REJECTED."""
    rows = _load_report()["records"]
    row = _find(rows, shard="alpha", record_seq=2, field_seq=2)
    assert row is not None
    assert row["tag"] == "245"
    assert row["verdict"] == "INDICATOR_NONBLANK_REJECTED"


def test_alpha_record_three_back_to_back_245_drops_second():
    """alpha record_seq 3 emits 245 twice back to back: first DATA_FIELD_ACCEPTED, second DUPLICATE_TAG_DROPPED."""
    rows = _load_report()["records"]
    a3 = [r for r in rows if r["shard"] == "alpha" and r["record_seq"] == 3]
    assert len(a3) == 3
    assert a3[1]["tag"] == "245" and a3[1]["verdict"] == "DATA_FIELD_ACCEPTED"
    assert a3[2]["tag"] == "245" and a3[2]["verdict"] == "DUPLICATE_TAG_DROPPED"


def test_beta_record_two_leader_encoding_q_demoted_via_hmac_seal():
    """beta record_seq 2 has leader position nine equal to q which is invalid, but the seal at /app/seals/pin_keys.tsv matches the first sixteen hex of HMAC-SHA256 of key marc-pin-v1 over preimage beta|2 so the leader scores ENCODING_PIN_RESCUED with pin_consumed true."""
    rows = _load_report()["records"]
    row = _find(rows, shard="beta", record_seq=2, field_seq=1)
    assert row is not None
    assert row["verdict"] == "ENCODING_PIN_RESCUED"
    assert row["pin_consumed"] is True


def test_beta_record_three_245_with_no_subfields_missing_delimiter():
    """beta record_seq 3 carries tag 245 with an empty subfields list, so no dollar delimiter appears in the body and verdict is SUBFIELD_DELIMITER_MISSING."""
    rows = _load_report()["records"]
    row = _find(rows, shard="beta", record_seq=3, field_seq=2)
    assert row is not None
    assert row["tag"] == "245"
    assert row["verdict"] == "SUBFIELD_DELIMITER_MISSING"


def test_beta_record_four_tag_AAA_is_out_of_range():
    """beta record_seq 4 carries tag AAA whose chars are non digit so it falls outside both the control 001-009 and data 010-999 ranges and scores TAG_OUT_OF_RANGE."""
    rows = _load_report()["records"]
    row = _find(rows, shard="beta", record_seq=4, field_seq=2)
    assert row is not None
    assert row["tag"] == "AAA"
    assert row["verdict"] == "TAG_OUT_OF_RANGE"


def test_gamma_record_one_emits_two_tag_out_of_range_separated_by_an_accepted_data_field():
    """gamma record_seq 1 emits TAG_OUT_OF_RANGE for tag BBB at field_seq 3, then a clean DATA_FIELD_ACCEPTED for tag 246 at field_seq 4, then a second TAG_OUT_OF_RANGE for tag CCC at field_seq 5; the two TAG_OUT_OF_RANGE rows are NOT consecutive."""
    rows = _load_report()["records"]
    g1 = [r for r in rows if r["shard"] == "gamma" and r["record_seq"] == 1]
    assert len(g1) == 5
    assert g1[2]["tag"] == "BBB" and g1[2]["verdict"] == "TAG_OUT_OF_RANGE"
    assert g1[3]["tag"] == "246" and g1[3]["verdict"] == "DATA_FIELD_ACCEPTED"
    assert g1[4]["tag"] == "CCC" and g1[4]["verdict"] == "TAG_OUT_OF_RANGE"


def test_cascade_arms_on_cumulative_count_not_consecutive_count():
    """gamma record_seq 2 field_seq 2 is CASCADE_QUARANTINED even though the two TAG_OUT_OF_RANGE rows in gamma record_seq 1 (BBB at f3 and CCC at f5) are separated by a clean DATA_FIELD_ACCEPTED (246 at f4); cumulative-per-shelf semantics arm the cascade, consecutive semantics would not."""
    rows = _load_report()["records"]
    row = _find(rows, shard="gamma", record_seq=2, field_seq=2)
    assert row is not None
    assert row["tag"] == "245"
    assert row["verdict"] == "CASCADE_QUARANTINED"


def test_gamma_record_two_leader_base_addr_Z_invalid_then_cascade_quarantined():
    """gamma record_seq 2 has leader position 15 equal to Z which makes positions 12-16 non digit, so the leader scores LEADER_BASE_ADDR_INVALID; the 245 that follows would normally be DATA_FIELD_ACCEPTED but the armed cascade demotes it to CASCADE_QUARANTINED."""
    rows = _load_report()["records"]
    g2 = [r for r in rows if r["shard"] == "gamma" and r["record_seq"] == 2]
    assert len(g2) == 2
    assert g2[0]["verdict"] == "LEADER_BASE_ADDR_INVALID"
    assert g2[1]["tag"] == "245" and g2[1]["verdict"] == "CASCADE_QUARANTINED"


def test_records_sorted_by_shard_then_record_seq_then_field_seq():
    """records appear in shelf order alpha, beta, gamma, then record_seq ascending, then field_seq ascending."""
    rows = _load_report()["records"]
    shard_rank = {"alpha": 0, "beta": 1, "gamma": 2}
    prev_key = (-1, -1, -1)
    for r in rows:
        key = (shard_rank[r["shard"]], r["record_seq"], r["field_seq"])
        assert key > prev_key, f"sort violation at {r}"
        prev_key = key


def test_only_ten_canonical_verdicts_appear_in_records_column():
    """No row uses a verdict outside the ten name closed enum from /app/catalog/report_shape.json."""
    rows = _load_report()["records"]
    seen = {r["verdict"] for r in rows}
    assert seen.issubset(set(VERDICT_ENUM))


def test_every_leader_row_uses_tag_literal_LDR():
    """Every row at field_seq one carries the literal three letter tag LDR regardless of shelf or verdict."""
    rows = _load_report()["records"]
    for r in rows:
        if r["field_seq"] == 1:
            assert r["tag"] == "LDR", f"non-LDR leader row {r}"


def test_field_seq_is_one_indexed_per_record_and_leader_is_one():
    """Within each record field_seq starts at one for the leader and increments by one per subsequent field with no gaps."""
    rows = _load_report()["records"]
    by_rec = {}
    for r in rows:
        by_rec.setdefault((r["shard"], r["record_seq"]), []).append(r["field_seq"])
    for (shard, rseq), seqs in by_rec.items():
        assert seqs == list(range(1, len(seqs) + 1)), f"gap in {shard} rec {rseq}: {seqs}"


def test_pin_consumed_true_only_when_verdict_is_encoding_pin_rescued():
    """pin_consumed is true only on rows whose verdict is ENCODING_PIN_RESCUED, false everywhere else."""
    rows = _load_report()["records"]
    for r in rows:
        if r["verdict"] == "ENCODING_PIN_RESCUED":
            assert r["pin_consumed"] is True
        else:
            assert r["pin_consumed"] is False


def test_alpha_records_count_is_three_and_field_count_is_nine():
    """alpha shelf contributes exactly three records totalling nine rows in the records array."""
    rows = _load_report()["records"]
    alpha = [r for r in rows if r["shard"] == "alpha"]
    assert len(alpha) == 9
    assert len({(r["record_seq"]) for r in alpha}) == 3


def test_re_run_is_idempotent_via_make_run_and_digest_stable():
    """Running the binary a second time via make run rewrites /app/output/report.json with byte identical content; report_digest stays at the pinned value."""
    first = _load_report()
    digest_before = _sha256_file(REPORT_PATH)
    subprocess.run(["make", "-C", "/app", "run"], check=True, capture_output=True)
    second = _load_report()
    digest_after = _sha256_file(REPORT_PATH)
    assert first == second
    assert digest_before == digest_after
    assert second["report_digest"] == EXPECTED_REPORT_DIGEST


def test_shelves_input_files_are_unchanged_after_runs():
    """Each of the three input shelf files keeps its original sha256 across runs; the binary never mutates inputs."""
    before = {name: _sha256_file(path) for name, path in SHELVES.items()}
    subprocess.run(["make", "-C", "/app", "run"], check=True, capture_output=True)
    after = {name: _sha256_file(path) for name, path in SHELVES.items()}
    assert before == after


def test_binary_exists_and_is_elf_executable():
    """The Go binary at /app/bin/marcrec exists, is non empty, and carries the ELF magic prefix indicating real compiled code."""
    assert os.path.isfile(BINARY_PATH)
    with open(BINARY_PATH, "rb") as fh:
        head = fh.read(4)
    assert head == b"\x7fELF", f"binary magic prefix is {head!r}"
