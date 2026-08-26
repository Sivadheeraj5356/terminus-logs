"""Reference package exports."""

from .diagnostics import diff_reports
from .protected_inputs import (
    ProtectedInputSnapshot,
    capture_from_dir,
    mutation_detected,
    verify_unchanged,
)
from .report import serialize_report, verify_from_protected

__all__ = [
    "ProtectedInputSnapshot",
    "capture_from_dir",
    "verify_unchanged",
    "mutation_detected",
    "verify_from_protected",
    "serialize_report",
    "diff_reports",
]
