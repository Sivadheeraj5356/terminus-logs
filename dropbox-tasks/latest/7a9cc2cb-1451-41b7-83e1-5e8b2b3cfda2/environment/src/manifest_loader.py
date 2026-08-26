"""Manifest and segment file loading."""

import json
import os


def load_manifest(data_dir):
    manifest_path = os.path.join(data_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        return None, {
            "type": "malformed_record",
            "segment_id": None,
            "event_id": None,
            "details": "manifest.json not found",
        }
    try:
        with open(manifest_path, "r", encoding="utf-8") as handle:
            return json.load(handle), None
    except Exception as exc:
        return None, {
            "type": "malformed_record",
            "segment_id": None,
            "event_id": None,
            "details": f"manifest.json invalid JSON: {exc}",
        }


def load_segment(data_dir, segment_file, segment_id):
    segment_path = os.path.join(data_dir, segment_file)
    if not os.path.exists(segment_path):
        return None, {
            "type": "missing_segment",
            "segment_id": segment_id,
            "event_id": None,
            "details": f"Segment file {segment_file} is missing",
        }
    try:
        with open(segment_path, "r", encoding="utf-8") as handle:
            return json.load(handle), None
    except Exception as exc:
        return None, {
            "type": "malformed_record",
            "segment_id": segment_id,
            "event_id": None,
            "details": f"Invalid segment JSON: {exc}",
        }
