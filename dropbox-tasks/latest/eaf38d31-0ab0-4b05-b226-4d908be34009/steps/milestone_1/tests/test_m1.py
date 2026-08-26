"""Tests for milestone 1: Canonicalize Release Manifests.

Run alone with: pytest tests/test_m1.py
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

CLI = "/app/transparency/cli.py"


def _run_canonicalize(manifest_obj, tmpdir):
    tmpdir = Path(tmpdir)
    tmpdir.mkdir(parents=True, exist_ok=True)
    src = tmpdir / "manifest.json"
    src.write_text(json.dumps(manifest_obj))
    out = tmpdir / "out"
    subprocess.run(
        [sys.executable, CLI, "canonicalize", str(src), "--out", str(out)],
        check=True,
        capture_output=True,
    )
    canon = (out / "manifest.canonical.json").read_bytes()
    raw = (out / "manifest.sha256").read_text()
    assert raw.endswith("\n"), "digest file must end with a newline"
    digest = raw.strip()
    return canon, digest


class TestMilestone1:
    def test_cli_exists(self):
        """The canonicalize CLI must exist at /app/transparency/cli.py."""
        assert Path(CLI).exists(), f"{CLI} must exist"

    def test_canonical_form_sorted_compact(self, tmp_path):
        """Canonical output sorts keys ascending with compact comma/colon separators and no whitespace."""
        canon, _ = _run_canonicalize({"b": 2, "a": 1, "c": [3, 2, 1]}, tmp_path)
        # sorted keys, compact separators, no whitespace
        assert canon == b'{"a":1,"b":2,"c":[3,2,1]}', f"got {canon!r}"

    def test_hash_matches_canonical_bytes(self, tmp_path):
        """The manifest.sha256 digest equals the SHA-256 of the canonical bytes."""
        canon, digest = _run_canonicalize({"x": 1, "y": "z"}, tmp_path)
        assert digest == hashlib.sha256(canon).hexdigest()

    def test_canonicalization_is_deterministic(self, tmp_path):
        """Manifests differing only in key or nesting order produce byte-identical canonical output and the same digest."""
        # Two manifests with identical data but different key order / nesting order
        a, ha = _run_canonicalize(
            {"name": "p", "version": "1", "meta": {"b": 1, "a": 2}}, tmp_path / "a"
        )
        b, hb = _run_canonicalize(
            {"meta": {"a": 2, "b": 1}, "version": "1", "name": "p"}, tmp_path / "b"
        )
        assert a == b, "canonical bytes must be identical regardless of key order"
        assert ha == hb, "hashes must match for equivalent manifests"

    def test_oracle_artifacts_present(self):
        """The demonstrated run wrote manifest.canonical.json and a matching manifest.sha256 under /app/out."""
        # The demonstrated run on /app/data/manifest.json must have produced outputs.
        canon = Path("/app/out/manifest.canonical.json")
        digest = Path("/app/out/manifest.sha256")
        assert canon.exists() and digest.exists()
        raw = digest.read_text()
        assert raw.endswith("\n"), "digest file must end with a newline"
        assert raw.strip() == hashlib.sha256(canon.read_bytes()).hexdigest()

    def test_canonical_module_exists(self):
        """The canonicalization module must exist at /app/transparency/canonical.py."""
        assert Path("/app/transparency/canonical.py").exists(), \
            "/app/transparency/canonical.py must exist"

    # ----- RFC 8785 (JCS) conformance: ECMA-262 number formatting ----- #
    # These cases are exactly where a stock ``json.dumps`` diverges from JCS.
    ECMA262_VECTORS = [
        ({"v": 100.0}, b'{"v":100}'),          # integer-valued float drops .0
        ({"v": 1.0}, b'{"v":1}'),
        ({"v": -0.0}, b'{"v":0}'),             # negative zero collapses
        ({"v": 1.5}, b'{"v":1.5}'),
        ({"v": 1e-7}, b'{"v":1e-7}'),          # bare exponent, no leading zero
        ({"v": 1e-6}, b'{"v":0.000001}'),      # boundary: E=-6 stays positional
        ({"v": 1e20}, b'{"v":100000000000000000000}'),  # positional, not 1e+20
        ({"v": 1e21}, b'{"v":1e+21}'),         # exponential only past 10^21
        ({"v": [1.0, 2.5, 100.0]}, b'{"v":[1,2.5,100]}'),
    ]

    def test_ecma262_number_formatting(self, tmp_path):
        """Numbers are serialized with the ECMA-262 (JCS) algorithm across the boundary vectors where json.dumps diverges."""
        for i, (obj, expected) in enumerate(self.ECMA262_VECTORS):
            canon, digest = _run_canonicalize(obj, tmp_path / f"num{i}")
            assert canon == expected, f"{obj!r} -> {canon!r}, expected {expected!r}"
            assert digest == hashlib.sha256(expected).hexdigest()

    def test_unicode_emitted_literally(self, tmp_path):
        """Non-ASCII characters are emitted as literal UTF-8, never as backslash-u escapes."""
        # JCS emits non-ASCII as literal UTF-8, never as \uXXXX escapes.
        canon, _ = _run_canonicalize({"name": "café-π"}, tmp_path)
        assert canon == '{"name":"café-π"}'.encode("utf-8"), f"got {canon!r}"
        assert b"\\u" not in canon

    def test_control_chars_escaped(self, tmp_path):
        """C0 control chars use the short escapes where defined and lowercase u00XX hex otherwise, leaving DEL literal."""
        # RFC 8785 string escaping: C0 controls use the short forms
        # \b \t \n \f \r where defined, and \u00XX (lowercase) for the rest.
        # DEL (U+007F) is >= U+0020 and is therefore emitted literally.
        short = {"c": "a\tb\nc\rd\be\ff"}
        canon, _ = _run_canonicalize(short, tmp_path / "short")
        assert canon == b'{"c":"a\\tb\\nc\\rd\\be\\ff"}', f"got {canon!r}"
        other = {"c": "\u0000\u001f\u007f"}
        canon2, _ = _run_canonicalize(other, tmp_path / "other")
        assert canon2 == b'{"c":"\\u0000\\u001f\x7f"}', f"got {canon2!r}"

    def test_keys_sorted_by_code_point_nested(self, tmp_path):
        """Object keys are sorted by Unicode code point at every nesting level."""
        canon, _ = _run_canonicalize(
            {"z": {"b": 1.0, "a": 2.0}, "a": 3.0}, tmp_path
        )
        assert canon == b'{"a":3,"z":{"a":2,"b":1}}', f"got {canon!r}"

    def test_naive_json_dumps_is_rejected(self, tmp_path):
        """A stock compact json.dumps must not match the JCS output, proving real JCS number and string formatting is used."""
        # Negative control: a stock compact json.dumps must NOT match the
        # required JCS output for these values — proving real JCS is required.
        obj = {"size": 100.0, "ratio": 1e-7, "label": "café"}
        canon, _ = _run_canonicalize(obj, tmp_path)
        naive = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
        assert canon != naive, "JCS output must differ from naive json.dumps"
        # And the canonical form must carry the JCS-correct renderings.
        assert b'"size":100' in canon and b'"size":100.0' not in canon
        assert b'"ratio":1e-7' in canon
        assert "café".encode("utf-8") in canon
