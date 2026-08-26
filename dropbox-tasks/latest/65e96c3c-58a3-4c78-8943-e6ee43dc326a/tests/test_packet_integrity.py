"""Byte-format, confidentiality, and fixed-input integrity checks."""

from __future__ import annotations

import hashlib
import json
import base64
import os
import tempfile
from pathlib import Path
from urllib.parse import quote_from_bytes

import reference
from helpers import APP_DIR, FIXTURE_DIR, OUTPUT_DIR, sha256


def _key_representations(raw_key: bytes) -> tuple[tuple[str, bytes], ...]:
    """Return every retained representation prohibited by the public contract."""

    encoded = {
        ("raw", raw_key),
        ("hex-lower", raw_key.hex().encode("ascii")),
        ("hex-upper", raw_key.hex().upper().encode("ascii")),
        ("base64", base64.b64encode(raw_key)),
        ("base64-unpadded", base64.b64encode(raw_key).rstrip(b"=")),
        ("base64url", base64.urlsafe_b64encode(raw_key)),
        ("base64url-unpadded", base64.urlsafe_b64encode(raw_key).rstrip(b"=")),
        ("base32", base64.b32encode(raw_key)),
        ("base32-unpadded", base64.b32encode(raw_key).rstrip(b"=")),
        ("base32-lower", base64.b32encode(raw_key).lower()),
        ("ascii85", base64.a85encode(raw_key)),
        ("base85", base64.b85encode(raw_key)),
        ("percent", quote_from_bytes(raw_key, safe="").encode("ascii")),
        ("percent-lower", quote_from_bytes(raw_key, safe="").lower().encode("ascii")),
    }
    return tuple(sorted(encoded))


def _matches(blob: bytes, needles: tuple[tuple[str, bytes], ...]) -> set[str]:
    """Return labels for prohibited byte sequences present in one byte string."""

    return {label for label, needle in needles if needle and needle in blob}


def _file_matches(path: Path, needles: tuple[tuple[str, bytes], ...]) -> set[str]:
    """Stream a retained file while preserving matches across chunk boundaries."""

    found: set[str] = set()
    overlap = max(len(needle) for _, needle in needles) - 1
    tail = b""
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            block = tail + chunk
            found.update(_matches(block, needles))
            tail = block[-overlap:] if overlap else b""
    return found


def _retained_key_findings(
    raw_keys: list[bytes], roots: tuple[Path, ...]
) -> list[str]:
    """Inspect retained names, symlink targets, and regular-file bytes fail closed."""

    needles = tuple(
        sorted(
            {
                (f"key-{index}:{label}", value)
                for index, raw_key in enumerate(raw_keys)
                for label, value in _key_representations(raw_key)
            }
        )
    )
    findings: set[str] = set()

    def record(location: str, blob: bytes) -> None:
        for label in _matches(blob, needles):
            findings.add(f"{location}:{label}")

    def visit(directory: Path, root: Path) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: os.fsencode(entry.name))
        except OSError as exc:
            findings.add(f"unreadable-directory:{directory}:{type(exc).__name__}")
            return
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(root).as_posix()
            record(f"name:{root}:{relative}", os.fsencode(entry.name))
            try:
                if entry.is_symlink():
                    record(f"symlink-target:{root}:{relative}", os.fsencode(os.readlink(path)))
                elif entry.is_dir(follow_symlinks=False):
                    visit(path, root)
                elif entry.is_file(follow_symlinks=False):
                    for label in _file_matches(path, needles):
                        findings.add(f"content:{root}:{relative}:{label}")
            except OSError as exc:
                findings.add(f"unreadable-entry:{root}:{relative}:{type(exc).__name__}")

    for root in sorted(set(roots), key=lambda path: os.fsencode(str(path))):
        if not root.exists():
            continue
        record(f"root-name:{root}", os.fsencode(root.name))
        if root.is_dir() and not root.is_symlink():
            visit(root, root)
        else:
            findings.add(f"invalid-scan-root:{root}")
    return sorted(findings)


def test_json_outputs_are_canonical_single_lf_artifacts(packet):
    """Each JSON output must be compact canonical UTF-8 with exactly one final LF."""

    for name in (
        "custody.json",
        "evidence.json",
        "authorization-proof.json",
        "rotation-certificate.json",
    ):
        data = packet[name]
        assert data.endswith(b"\n") and not data.endswith(b"\n\n")
        assert data == reference.artifact_bytes(json.loads(data))


def test_toml_output_has_fixed_order_and_single_lf(expected, packet):
    """The TOML plan must use the contract renderer's fixed ordering and termination."""

    data = packet["ffmpeg-plan.toml"]
    assert data == expected["planToml"]
    assert data.startswith(b'schema = "cipherwave.ffmpeg-plan.v1"\n')
    assert data.endswith(b"\n") and not data.endswith(b"\n\n")


def test_packet_never_serializes_unwrapped_content_keys(expected, packet):
    """No raw or encoded content key may survive in output or temporary paths."""

    raw_keys = [qualified.plaintext for qualified in expected["ring"].values()]
    joined = b"\n".join(packet.values())
    for raw_key in raw_keys:
        for label, needle in _key_representations(raw_key):
            assert needle not in joined, f"{label} content key leaked into final packet"

    # Guard the scanner itself with a retained file and an encoded filename. The
    # temporary tree is removed before inspecting the actual task scopes.
    with tempfile.TemporaryDirectory(prefix="cipherwave-key-leak-regression-") as directory:
        probe = Path(directory)
        (probe / "key.bin").write_bytes(raw_keys[0])
        encoded_name = base64.urlsafe_b64encode(raw_keys[1]).rstrip(b"=").decode("ascii")
        (probe / f"{encoded_name}.tmp").write_bytes(b"non-secret")
        planted = _retained_key_findings(raw_keys, (probe,))
        assert any(finding.startswith("content:") for finding in planted)
        assert any(finding.startswith("name:") for finding in planted)

    scan_roots = {
        APP_DIR / "out",
        OUTPUT_DIR.parent,
        Path("/tmp"),
        Path(tempfile.gettempdir()),
    }
    findings = _retained_key_findings(raw_keys, tuple(scan_roots))
    assert findings == [], "retained content-key material found:\n" + "\n".join(findings)


def test_fixed_authority_files_remain_present_and_unmodified():
    """The audit must leave every immutable incident authority available and unchanged."""

    expected_hashes = {
        "profile.toml": "e5e9917f703e64bc516a8d79d9651510edf8d2d3b6a0cc83e878224e38092451",
        "registry.json": "996415cdd4b142535c8e1068970234d40a19ebfdaf07437cb146b077a2a8b2a9",
        "trust.json": "731d37e83525f22a62139a709b9a8b7ad095a64b24437b1c97a43647d7326a32",
        "catalog.json": "5d3ece74cec6cd96330c7a1553406724d270d93ccdd3f32fbafa097f39005bf4",
        "guardian-trust.json": "0f9c8b5873e60a18b3cab17f1f55030f6a7f786e377cde20c715bae75ca0a577",
        "rollout-ledger.json": "466abb71218fa3d4c3ff093247b69bddae26c376185b270f1523229f672aae1e",
    }
    for name, expected_hash in expected_hashes.items():
        assert sha256((FIXTURE_DIR / name).read_bytes()) == expected_hash

    media_root = FIXTURE_DIR / "media"
    tree_hash = hashlib.sha256()
    files = sorted(
        (path for path in media_root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(media_root).as_posix().encode("utf-8"),
    )
    assert len(files) > 10
    for path in files:
        relative = path.relative_to(media_root).as_posix().encode("utf-8")
        data = path.read_bytes()
        tree_hash.update(len(relative).to_bytes(4, "big"))
        tree_hash.update(relative)
        tree_hash.update(len(data).to_bytes(8, "big"))
        tree_hash.update(data)
    assert tree_hash.hexdigest() == "fccdacd18f2c5b7a9416b4087e7e491f8b23d22e337316e6591e0cc860ffc3cc"
