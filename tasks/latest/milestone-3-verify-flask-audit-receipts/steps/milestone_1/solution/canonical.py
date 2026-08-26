"""Deterministic RFC 8785 (JCS) canonicalization and hashing for release manifests.

Canonical form rules (RFC 8785 JSON Canonicalization Scheme):
- object keys sorted ascending by Unicode code point
- no insignificant whitespace (compact ``,``/``:`` separators)
- strings emitted with minimal JSON escaping, non-ASCII emitted literally (UTF-8)
- numbers serialized via the ECMAScript ``Number::toString`` algorithm
  (RFC 8785 §3.2.2 / ECMA-262 §6.1.6.1.20) — NOT Python ``repr``/``json``: e.g.
  ``100.0`` -> ``100``, ``1e-7`` (not ``1e-07``), ``1e20`` ->
  ``100000000000000000000``, ``-0.0`` -> ``0``
- no trailing newline

The canonical bytes are stable regardless of input key order or whitespace, so
hashing them yields a deterministic manifest digest.
"""

import hashlib
import json
import math
from typing import Any


def es_number_to_string(x: float) -> str:
    """ECMAScript ``Number::toString`` (radix 10), as required by RFC 8785 §3.2.2.

    The shortest decimal string that round-trips to the IEEE-754 double ``x``,
    formatted with the exact ECMA-262 §6.1.6.1.20 rules (fixed vs exponential
    thresholds, sign of the exponent, no superfluous zeros). Deliberately *not*
    Python ``repr``: ``repr`` yields ``1e-07`` / ``1e+20`` where ECMAScript (and
    JCS) require ``1e-7`` / ``100000000000000000000``.
    """
    if x != x:
        raise ValueError("NaN is not permitted in canonical()")
    if x in (math.inf, -math.inf):
        raise ValueError("Infinity is not permitted in canonical()")
    if x == 0:
        return "0"  # also collapses -0.0 -> "0"
    if x < 0:
        return "-" + es_number_to_string(-x)
    # CPython's correctly-rounded shortest repr is used only as the digit source;
    # all *formatting* below is the ECMA-262 algorithm.
    r = repr(x)
    if "e" in r or "E" in r:
        mant, exp_part = r.lower().split("e")
        exp = int(exp_part)
    else:
        mant, exp = r, 0
    if "." in mant:
        int_part, frac_part = mant.split(".")
    else:
        int_part, frac_part = mant, ""
    digits = (int_part + frac_part).lstrip("0") or "0"
    exp -= len(frac_part)
    stripped = digits.rstrip("0") or "0"
    exp += len(digits) - len(stripped)
    s = stripped
    k = len(s)
    n = exp + k
    if k <= n <= 21:
        return s + "0" * (n - k)
    if 0 < n <= 21:
        return s[:n] + "." + s[n:]
    if -6 < n <= 0:
        return "0." + "0" * (-n) + s
    e = n - 1
    sign = "+" if e >= 0 else "-"
    if k == 1:
        return s + "e" + sign + str(abs(e))
    return s[0] + "." + s[1:] + "e" + sign + str(abs(e))


def _canonical_serialize(value: Any) -> str:
    """Serialize ``value`` to its canonical compact-JSON string form (RFC 8785).

    Object keys are sorted ascending by Unicode code point; separators are ``,``
    and ``:`` with no whitespace; non-ASCII is emitted literally. ``float`` is
    rendered via :func:`es_number_to_string`. ``bool`` is handled before ``int``.
    """
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, float):
        return es_number_to_string(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ",".join(_canonical_serialize(v) for v in value) + "]"
    if isinstance(value, dict):
        for k in value:
            if not isinstance(k, str):
                raise TypeError("canonical() object keys must be strings")
        items = sorted(value.items(), key=lambda kv: kv[0])
        return (
            "{"
            + ",".join(
                json.dumps(k, ensure_ascii=False) + ":" + _canonical_serialize(v)
                for k, v in items
            )
            + "}"
        )
    raise TypeError(f"unserializable type for canonical(): {type(value).__name__}")


def canonicalize(obj: Any) -> bytes:
    """Return the canonical RFC 8785 UTF-8 byte encoding of a JSON value."""
    return _canonical_serialize(obj).encode("utf-8")


def canonical_hash(obj: Any) -> str:
    """Return the lowercase hex SHA-256 digest of the canonical encoding."""
    return hashlib.sha256(canonicalize(obj)).hexdigest()


def load_manifest(path: str) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)
