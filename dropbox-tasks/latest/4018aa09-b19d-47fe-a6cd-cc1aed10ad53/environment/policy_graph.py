"""Public vocabulary helpers for trust-policy graph implementations."""

AUTHORITY_ORDER = (
    "ratified_standard",
    "signed_amendment",
    "incident_directive",
    "release_note",
    "operator_note",
    "archive",
)


def authority_rank(source):
    """Return the public precedence rank for a known authority source."""
    return AUTHORITY_ORDER.index(source)
