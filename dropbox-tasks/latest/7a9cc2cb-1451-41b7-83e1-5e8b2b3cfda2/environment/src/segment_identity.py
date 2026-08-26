"""Segment file stem versus embedded segment_id checks."""


def segment_identity_ok(segment_file, segment_data):
    expected = segment_file.replace(".json", "")
    actual = segment_data.get("segment_id")
    return actual == expected
