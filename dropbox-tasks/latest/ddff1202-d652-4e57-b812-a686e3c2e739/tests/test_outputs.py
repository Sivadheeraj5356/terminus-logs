"""
Verifier tests for the legacy-record-decoder bundle.

The graded artifact is /app/output/legacy_record_bundle.json produced by:

    /app/environment/scripts/build_all.sh
    /app/environment/tools/bin/xscope --all-samples \
        --bundle-out /app/output/legacy_record_bundle.json
"""

import json
from pathlib import Path

BUNDLE_PATH = Path("/app/output/legacy_record_bundle.json")
FIXTURE_EXPORT_A = Path("/app/environment/fixtures/text/set_a.txt")
FIXTURE_EXPORT_B = Path("/app/environment/fixtures/text/set_b.txt")

# State/kind constants — defined here so test assertions don't embed literals.
_STATE_COMPATIBLE = "compatible"
_STATE_DIVERGED = "diverged"
_STATE_MALFORMED = "malformed"
_KIND_RESERVED = "reserved_bit_set"
_GROUP_A = "set_a"
_GROUP_B = "set_b"


def load_bundle():
    assert BUNDLE_PATH.exists(), (
        f"Bundle not found at {BUNDLE_PATH}. "
        "Run build_all.sh then xscope --all-samples --bundle-out "
        f"{BUNDLE_PATH} first."
    )
    with open(BUNDLE_PATH) as f:
        return json.load(f)


def parse_export_file(path):
    """Parse an export file into a dict keyed by seq_id."""
    records = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",", 5)
        if len(parts) < 5:
            continue
        seq_id = int(parts[0])
        records[seq_id] = {
            "seq_id": seq_id,
            "datum_len": int(parts[1]),
            "checksum": int(parts[2]),
            "status_nibble": int(parts[3]),
            "revision_tag": int(parts[4]),
            "label": parts[5].strip() if len(parts) > 5 and parts[5].strip() else None,
        }
    return records


class TestBundleSchema:
    """Verify the bundle has all required top-level sections."""

    def test_bundle_exists_and_is_valid_json(self):
        """Bundle file must exist and parse as valid JSON."""
        assert BUNDLE_PATH.exists(), f"Missing bundle at {BUNDLE_PATH}"
        with open(BUNDLE_PATH) as f:
            data = json.load(f)
        assert isinstance(data, dict), "Bundle root must be a JSON object"

    def test_required_top_level_keys(self):
        """Bundle must contain records, compatibility_trace, error_classification, artifacts."""
        bundle = load_bundle()
        for key in ("records", "compatibility_trace", "error_classification", "artifacts"):
            assert key in bundle, f"Missing required key '{key}' in bundle"

    def test_records_is_nonempty_list(self):
        """records section must be a non-empty list."""
        bundle = load_bundle()
        assert isinstance(bundle["records"], list), "'records' must be a list"
        assert len(bundle["records"]) > 0, "'records' must not be empty"

    def test_compatibility_trace_is_list(self):
        """compatibility_trace section must be a list."""
        bundle = load_bundle()
        assert isinstance(bundle["compatibility_trace"], list)

    def test_error_classification_is_list(self):
        """error_classification section must be a list."""
        bundle = load_bundle()
        assert isinstance(bundle["error_classification"], list)

    def test_artifacts_is_nonempty_list(self):
        """artifacts section must be a non-empty list."""
        bundle = load_bundle()
        assert isinstance(bundle["artifacts"], list)
        assert len(bundle["artifacts"]) > 0, "'artifacts' must not be empty"


class TestRecordFields:
    """Verify canonical record views match the authoritative export values."""

    def test_record_schema_has_required_fields(self):
        """Each record must have the required canonical-view fields."""
        bundle = load_bundle()
        required = {"seq_id", "datum_len", "checksum", "status_nibble", "revision_tag", "label"}
        for rec in bundle["records"]:
            missing = required - set(rec.keys())
            assert not missing, f"Record missing fields {missing}: {rec}"

    def test_sample_a_records_match_export(self):
        """Binary-decoded records for sample group set_a must match the export file field-for-field."""
        bundle = load_bundle()
        export_a = parse_export_file(FIXTURE_EXPORT_A)

        # Collect set_a records from bundle (seq_ids 1-4).
        bundle_by_seq = {r["seq_id"]: r for r in bundle["records"]
                         if r["seq_id"] in (1, 2, 3, 4)}

        for seq_id in sorted(export_a):
            expected = export_a[seq_id]
            assert seq_id in bundle_by_seq, (
                f"seq_id={seq_id} from set_a export not found in bundle records"
            )
            actual = bundle_by_seq[seq_id]
            assert actual["datum_len"] == expected["datum_len"], (
                f"seq_id={seq_id}: datum_len mismatch "
                f"(got {actual['datum_len']}, expected {expected['datum_len']}). "
                "Check the binary field-offset reading in the src/ decoder."
            )
            assert actual["checksum"] == expected["checksum"], (
                f"seq_id={seq_id}: checksum mismatch "
                f"(got {actual['checksum']}, expected {expected['checksum']})"
            )
            assert actual["status_nibble"] == expected["status_nibble"], (
                f"seq_id={seq_id}: status_nibble mismatch"
            )
            assert actual["revision_tag"] == expected["revision_tag"], (
                f"seq_id={seq_id}: revision_tag mismatch"
            )
            assert actual["label"] == expected["label"], (
                f"seq_id={seq_id}: label mismatch"
            )

    def test_first_record_datum_len_and_checksum_not_swapped(self):
        """datum_len for seq_id=1 must be 6720, not 1234 (the checksum value)."""
        bundle = load_bundle()
        rec1 = next((r for r in bundle["records"] if r["seq_id"] == 1), None)
        assert rec1 is not None, "seq_id=1 not found in records"
        assert rec1["datum_len"] == 6720, (
            f"datum_len={rec1['datum_len']} — looks like datum_len/checksum bytes are swapped"
        )
        assert rec1["checksum"] == 1234, (
            f"checksum={rec1['checksum']} — expected 1234"
        )


class TestCompatibilityTrace:
    """Verify the compatibility trace correctly classifies pairs."""

    def test_trace_entries_have_required_fields(self):
        """Each trace entry must have seq_id, state, and diverged_fields."""
        bundle = load_bundle()
        required_fields = {"seq_id", "state", "diverged_fields"}
        for entry in bundle["compatibility_trace"]:
            missing = required_fields - set(entry.keys())
            assert not missing, f"Trace entry missing fields {missing}: {entry}"

    def test_valid_state_values(self):
        """state must be one of compatible, diverged, or malformed."""
        bundle = load_bundle()
        valid_states = {_STATE_COMPATIBLE, _STATE_DIVERGED, _STATE_MALFORMED}
        for entry in bundle["compatibility_trace"]:
            assert entry["state"] in valid_states, (
                f"Invalid state '{entry['state']}' for seq_id={entry.get('seq_id')}"
            )

    def test_sample_a_pairs_are_compatible(self):
        """After fixing the binary reader, all set_a pairs must be compatible."""
        bundle = load_bundle()
        # set_a seq_ids are 1-4.
        sample_a_trace = [e for e in bundle["compatibility_trace"] if e["seq_id"] in (1, 2, 3, 4)]
        assert len(sample_a_trace) >= 4, "Expected at least 4 set_a trace entries"
        for entry in sample_a_trace:
            assert entry["state"] == _STATE_COMPATIBLE, (
                f"set_a seq_id={entry['seq_id']} should be compatible "
                f"but got state='{entry['state']}' with diverged_fields={entry.get('diverged_fields')}. "
                "Fix the compatibility comparison to check all normalised fields."
            )
            assert entry["diverged_fields"] == [], (
                f"Compatible entry should have empty diverged_fields: {entry}"
            )

    def test_reserved_nibble_record_is_malformed(self):
        """set_b has a record with reserved bits set; it must be classified as malformed."""
        bundle = load_bundle()
        reserved_errors = [
            e for e in bundle["error_classification"]
            if e.get("kind") == _KIND_RESERVED
        ]
        assert len(reserved_errors) >= 1, (
            "Expected at least one reserved_bit_set error classification. "
            "Fix the status-byte classifier in src/ to detect non-zero high nibbles."
        )

    def test_compatible_entries_have_empty_diverged_fields(self):
        """Trace entries with state=compatible must have diverged_fields=[]."""
        bundle = load_bundle()
        for entry in bundle["compatibility_trace"]:
            if entry["state"] == _STATE_COMPATIBLE:
                assert entry["diverged_fields"] == [], (
                    f"Compatible entry seq_id={entry.get('seq_id')} "
                    f"has non-empty diverged_fields: {entry['diverged_fields']}"
                )


class TestErrorClassification:
    """Verify malformed inputs are classified rather than silently normalised."""

    def test_error_entries_have_required_fields(self):
        """Each error entry must have seq_id, kind, and detail."""
        bundle = load_bundle()
        required_fields = {"seq_id", "kind", "detail"}
        for entry in bundle["error_classification"]:
            missing = required_fields - set(entry.keys())
            assert not missing, f"Error entry missing fields {missing}: {entry}"

    def test_valid_error_kinds(self):
        """kind must be one of the documented error categories."""
        bundle = load_bundle()
        valid_kinds = {
            "truncated_header", "invalid_checksum",
            "overflow_field", "reserved_bit_set", "unknown",
        }
        for entry in bundle["error_classification"]:
            assert entry["kind"] in valid_kinds, (
                f"Unknown kind '{entry['kind']}' for seq_id={entry.get('seq_id')}"
            )

    def test_reserved_nibble_error_kind_present(self):
        """At least one error of kind reserved_bit_set must be present."""
        bundle = load_bundle()
        kinds = {e["kind"] for e in bundle["error_classification"]}
        assert _KIND_RESERVED in kinds, (
            "No reserved_bit_set classification found. "
            "The error_classification section must include reserved_bit_set entries."
        )

    def test_error_classified_records_are_marked_malformed(self):
        """Records with error_classification entries must have state=malformed in trace."""
        bundle = load_bundle()
        error_seq_ids = {e["seq_id"] for e in bundle["error_classification"]}
        for entry in bundle["compatibility_trace"]:
            if entry["seq_id"] in error_seq_ids:
                actual_state = entry["state"]
                assert entry["state"] == _STATE_MALFORMED, (
                    f"seq_id={entry['seq_id']} has an error_classification entry "
                    f"but trace state='{actual_state}' instead of the malformed state. "
                    "Malformed records must not be silently normalised."
                )


class TestRoundTrip:
    """Verify round-trip consistency for compatible records."""

    def test_compatible_records_match_export_canonical_view(self):
        """For each compatible trace entry, the records section must contain
        a canonical view that agrees field-for-field with the export file."""
        bundle = load_bundle()
        export_a = parse_export_file(FIXTURE_EXPORT_A)
        export_b = parse_export_file(FIXTURE_EXPORT_B)
        all_exports = {**export_a, **export_b}

        records_by_seq = {r["seq_id"]: r for r in bundle["records"]}

        compatible_entries = [
            e for e in bundle["compatibility_trace"] if e["state"] == _STATE_COMPATIBLE
        ]
        assert len(compatible_entries) > 0, (
            "No compatible trace entries found; expected at least some compatible pairs."
        )

        for entry in compatible_entries:
            sid = entry["seq_id"]
            if sid not in all_exports:
                continue
            expected = all_exports[sid]
            actual = records_by_seq.get(sid)
            assert actual is not None, (
                f"Compatible seq_id={sid} in trace but not in records section"
            )
            for field in ("datum_len", "checksum", "status_nibble", "revision_tag", "label"):
                assert actual[field] == expected[field], (
                    f"Round-trip failure for seq_id={sid} field '{field}': "
                    f"got {actual[field]!r}, expected {expected[field]!r}"
                )

    def test_artifacts_cover_both_sample_groups(self):
        """The artifacts section must reference both sample groups."""
        bundle = load_bundle()
        group_names = {a["group"] for a in bundle["artifacts"]}
        assert _GROUP_A in group_names, "artifacts must include set_a group"
        assert _GROUP_B in group_names, "artifacts must include set_b group"

    def test_artifacts_have_positive_record_counts(self):
        """Each artifact entry must report a positive record_count."""
        bundle = load_bundle()
        for art in bundle["artifacts"]:
            assert art.get("record_count", 0) > 0, (
                f"Group {art.get('group')} has zero or missing record_count"
            )
