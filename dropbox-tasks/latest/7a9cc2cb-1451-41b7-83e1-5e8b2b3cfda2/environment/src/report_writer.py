"""Validation report assembly and deterministic sorting."""


def sort_errors(errors):
    def sort_key(error):
        segment_id = error.get("segment_id")
        event_id = error.get("event_id")
        error_type = error.get("type")
        return (
            segment_id is None,
            segment_id or "",
            event_id is None,
            event_id or "",
            error_type is None,
            error_type or "",
        )

    errors.sort(key=sort_key)
    return errors


def build_report(errors, segments_checked, records_checked):
    errors = sort_errors(errors)
    return {
        "valid": len(errors) == 0,
        "summary": {
            "segments_checked": segments_checked,
            "records_checked": records_checked,
            "error_count": len(errors),
        },
        "errors": errors,
    }


def write_report(report, report_path):
    import json
    import os

    directory = os.path.dirname(report_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
