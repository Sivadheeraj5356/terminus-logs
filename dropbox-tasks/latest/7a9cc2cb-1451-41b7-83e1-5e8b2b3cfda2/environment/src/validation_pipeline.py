"""End-to-end audit log validation orchestration."""

from chain_tracker import ChainTracker
from hash_utils import is_valid_sha256
from manifest_loader import load_manifest, load_segment
from manifest_validator import verify_manifest_signature
from report_writer import build_report
from segment_processor import process_segment


def run_validation(data_dir):
    manifest, manifest_error = load_manifest(data_dir)
    if manifest_error is not None:
        return build_report([manifest_error], 0, 0)

    segments = manifest.get("segments", [])
    signature = manifest.get("signature")
    chain = ChainTracker()
    errors = []
    segments_checked = 0
    records_checked = 0
    manifest_roots = []
    missing_segments = False

    for segment_file in segments:
        segment_id = segment_file.replace(".json", "")
        segment_data, segment_error = load_segment(data_dir, segment_file, segment_id)
        if segment_error is not None:
            errors.append(segment_error)
            if segment_error["type"] == "missing_segment":
                missing_segments = True
            continue

        segments_checked += 1
        findings = process_segment(segment_data, segment_id, chain)
        errors.extend(findings["errors"])
        records_checked += findings["records_checked"]
        stored_root = segment_data.get("merkle_root")
        if stored_root is not None:
            manifest_roots.append(stored_root)

    if not missing_segments and len(manifest_roots) == len(segments):
        if signature is None or not is_valid_sha256(signature):
            errors.append({
                "type": "malformed_hash",
                "segment_id": None,
                "event_id": None,
                "details": f"Manifest signature format invalid: {signature}",
            })
        else:
            ok, failure = verify_manifest_signature(manifest_roots, signature)
            if not ok:
                if failure == "malformed_hash":
                    errors.append({
                        "type": "malformed_hash",
                        "segment_id": None,
                        "event_id": None,
                        "details": f"Manifest signature format invalid: {signature}",
                    })
                else:
                    errors.append({
                        "type": "bad_manifest_signature",
                        "segment_id": None,
                        "event_id": None,
                        "details": "Manifest signature mismatch",
                    })

    return build_report(errors, segments_checked, records_checked)
