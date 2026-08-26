"""Reference manifest lookup for artifact digest registration."""

from __future__ import annotations

import re
from pathlib import Path

MANIFEST_DIR = Path("/app/registry/manifests")


def _normalize_digest(value: str) -> str:
  prefix, _, body = value.partition(":")
  return f"{prefix.lower()}:{body.lower()}"


def digest_registered(model_id: str, sklearn_pin: str, artifact_digest: str) -> bool:
  """Return whether the digest is registered for the sklearn pin."""
  path = MANIFEST_DIR / f"{model_id}.toml"
  if not path.exists():
    return False
  text = path.read_text()
  target = _normalize_digest(artifact_digest)
  blocks = re.split(r"\[\[release\]\]", text)
  for block in blocks[1:]:
    pin_match = re.search(r'sklearn_pin\s*=\s*"([^"]+)"', block)
    digest_match = re.search(r'artifact_digest\s*=\s*"([^"]+)"', block)
    if pin_match is None or digest_match is None:
      continue
    if pin_match.group(1) == sklearn_pin and _normalize_digest(digest_match.group(1)) == target:
      return True
  return False
