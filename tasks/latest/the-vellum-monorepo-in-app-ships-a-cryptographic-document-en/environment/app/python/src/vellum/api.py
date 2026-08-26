"""Public Vellum Python API."""

from __future__ import annotations

import json
from typing import Any, Dict, Union

from . import _loader

Document = Union[str, Dict[str, Any], list]


def identity() -> Dict[str, Any]:
    """Return the release identity record of the bundled native library."""
    return json.loads(_loader.identity_json())


def canonical_digest(document: Document) -> str:
    """Return the canonical digest hex string for a document."""
    if isinstance(document, str):
        payload = document
    else:
        payload = json.dumps(document)
    return _loader.canonical_digest(payload)
