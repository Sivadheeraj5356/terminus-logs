"""Independent authoring reference for the Cipherwave security task.

This module is deliberately independent from the submitted Go program.  It is used
by fixture generation and verifier-side tests to derive security decisions from raw
inputs.  It never shells out to, imports, or otherwise treats agent code as truth.

The public artifact dictionaries mirror ``_authoring/SPEC.md``.  Canonical JSON is
always computed without a newline; artifact files append exactly one LF.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import itertools
import json
import posixpath
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


KEY_HANDLE_DOMAIN = b"Cipherwave key handle v1\x00"
CERT_CONFIRM_DOMAIN = b"Cipherwave certificate confirmation v1\x00"
CERT_SEAL_DOMAIN = b"Cipherwave rotation certificate v1\x00"
PLAN_IV_DOMAIN = b"Cipherwave plan IV v1\x00"
REGISTRY_DIGEST_DOMAIN = b"Cipherwave registry digest v1\x00"
ROLLOUT_RECORD_DOMAIN = b"Cipherwave rollout record v1\x00"
ROLLOUT_CHECKPOINT_DOMAIN = b"Cipherwave rollout checkpoint v1\x00"

KEY_REASONS = (
    "missing",
    "malformed",
    "wrong_profile",
    "wrong_generation",
    "unknown_issuer",
    "issuer_out_of_era",
    "issuer_compromised",
    "bad_signature",
    "not_yet_valid",
    "expired",
    "revoked",
    "invalid_uri",
    "untrusted_spki",
    "unwrap_failed",
    "qualified",
)

SURFACE_REASONS = (
    "absent",
    "catalog_invalid",
    "playlist_malformed",
    "unsupported_method",
    "unknown_key",
    "uri_mismatch",
    "invalid_iv",
    "mixed_generation",
    "cipher_digest_mismatch",
    "cipher_length",
    "decrypt_failed",
    "padding_invalid",
    "plaintext_digest_mismatch",
    "valid",
)

RENDITION_STATES = ("old", "staged", "advertised", "published", "broken")
DECISIONS = (
    "quarantine",
    "finish_commit",
    "commit",
    "rollback_pending",
    "hold_current",
)

_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_LOWER_HEX_64_RE = re.compile(r"^[0-9a-f]{64}$")


class ReferenceError(ValueError):
    """Base class for independent-reference validation errors."""


class ContractError(ReferenceError):
    """Malformed public input or artifact contract."""


class IntegrityError(ReferenceError):
    """Canonical predecessor or cryptographic binding failure."""


@dataclass(frozen=True)
class QualifiedKey:
    role: str
    key_id: str
    generation: int
    key_uri: str
    spki_sha256: str
    handle: str
    plaintext: bytes
    aad: bytes


@dataclass(frozen=True)
class ParsedSegment:
    method: str
    uri: str
    iv_text: str | None
    media_sequence: int
    sequence: int
    path: str
    distinct_key_uris: frozenset[str]


def _reject_floats(value: Any, path: str = "$") -> None:
    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return
    if isinstance(value, float):
        raise ContractError(f"floats are forbidden at {path}")
    if isinstance(value, list):
        for index, item in enumerate(value):
            _reject_floats(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ContractError(f"non-string object key at {path}")
            _reject_floats(item, f"{path}.{key}")
        return
    raise ContractError(f"unsupported JSON value {type(value).__name__} at {path}")


def canonical_json(value: Any) -> bytes:
    """Return recursively key-sorted compact UTF-8 JSON without a trailing LF."""

    _reject_floats(value)
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ContractError(f"value is not canonical-JSON encodable: {exc}") from exc
    return text.encode("utf-8")


def artifact_bytes(value: Any) -> bytes:
    return canonical_json(value) + b"\n"


def decode_canonical_artifact(data: bytes) -> dict[str, Any]:
    if not data.endswith(b"\n") or data.endswith(b"\n\n"):
        raise IntegrityError("artifact must end in exactly one LF")
    body = data[:-1]
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IntegrityError("artifact is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict) or artifact_bytes(value) != data:
        raise IntegrityError("artifact is not canonical JSON")
    return value


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def semantic_hash(value: Any) -> str:
    """Hash the canonical semantic value used by supplied Go loaders."""

    return sha256_hex(canonical_json(value))


def registry_digest(registry_records: Mapping[str, bytes]) -> str:
    """Hash logical registry entries independently of transport layout."""

    digest = hashlib.sha256()
    digest.update(REGISTRY_DIGEST_DOMAIN)
    for key in sorted(registry_records, key=lambda item: item.encode("utf-8")):
        key_bytes = key.encode("utf-8")
        value = registry_records[key]
        if len(key_bytes) >= 1 << 32 or len(value) >= 1 << 64:
            raise ContractError("registry entry is too large")
        digest.update(len(key_bytes).to_bytes(4, "big"))
        digest.update(key_bytes)
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)
    return digest.hexdigest()


def normalized_profile_value(profile: Mapping[str, Any]) -> dict[str, Any]:
    p = _profile_normalized(profile)
    return {
        "schema": p["schema"],
        "profileId": p["profile_id"],
        "auditUnix": p["audit_unix"],
        "currentKeyId": p["current_key_id"],
        "currentGeneration": p["current_generation"],
        "candidateKeyId": p["candidate_key_id"],
        "candidateGeneration": p["candidate_generation"],
        "renditions": list(p["renditions"]),
        "allowedKeyHosts": list(p["allowed_key_hosts"]),
        "trustedSpkiSha256": list(p["trusted_spki_sha256"]),
        "renderSegmentCount": p["render_segment_count"],
    }


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: Any, *, length: int | None = None) -> bytes:
    if not isinstance(text, str) or not text or "=" in text:
        raise ContractError("expected nonempty unpadded base64url")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", text):
        raise ContractError("invalid base64url alphabet")
    try:
        result = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (ValueError, base64.binascii.Error) as exc:
        raise ContractError("invalid base64url encoding") from exc
    if b64url_encode(result) != text:
        raise ContractError("noncanonical base64url encoding")
    if length is not None and len(result) != length:
        raise ContractError(f"decoded value must be {length} bytes")
    return result


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ContractError(f"{label} members differ: missing={missing}, extra={extra}")


def _int(value: Any, label: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise ContractError(f"{label} must be >= {minimum}")
    return value


def _token(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _TOKEN_RE.fullmatch(value):
        raise ContractError(f"{label} must be a nonempty ASCII token")
    return value


def _profile_value(profile: Mapping[str, Any], snake: str) -> Any:
    """Read profile values, accepting the TOML spelling and Go JSON spelling.

    Authoring inputs originate as TOML (snake case); generated contract fixtures can
    also use the Go-facing camel-case representation.  Ambiguous duplicates fail.
    """

    parts = snake.split("_")
    camel = parts[0] + "".join(part.title() for part in parts[1:])
    present = [name for name in dict.fromkeys((snake, camel)) if name in profile]
    if len(present) != 1:
        raise ContractError(f"profile must contain exactly one of {snake!r}/{camel!r}")
    return profile[present[0]]


def _profile_normalized(profile: Mapping[str, Any]) -> dict[str, Any]:
    fields = (
        "schema",
        "profile_id",
        "audit_unix",
        "current_key_id",
        "current_generation",
        "candidate_key_id",
        "candidate_generation",
        "renditions",
        "allowed_key_hosts",
        "trusted_spki_sha256",
        "render_segment_count",
    )
    result = {field: _profile_value(profile, field) for field in fields}
    if result["schema"] != "cipherwave.profile.v2":
        raise ContractError("unsupported profile schema")
    result["profile_id"] = _token(result["profile_id"], "profile_id")
    result["audit_unix"] = _int(result["audit_unix"], "audit_unix", minimum=0)
    result["current_key_id"] = _token(result["current_key_id"], "current_key_id")
    result["candidate_key_id"] = _token(result["candidate_key_id"], "candidate_key_id")
    if result["current_key_id"] == result["candidate_key_id"]:
        raise ContractError("current and candidate key IDs must differ")
    result["current_generation"] = _int(
        result["current_generation"], "current_generation", minimum=1
    )
    result["candidate_generation"] = _int(
        result["candidate_generation"], "candidate_generation", minimum=1
    )
    if result["candidate_generation"] != result["current_generation"] + 1:
        raise ContractError("candidate generation must immediately follow current")
    renditions = result["renditions"]
    if not isinstance(renditions, list) or not renditions:
        raise ContractError("renditions must be a nonempty array")
    if renditions != sorted(set(renditions)):
        raise ContractError("renditions must be sorted and unique")
    for rendition in renditions:
        _token(rendition, "rendition")
    hosts = result["allowed_key_hosts"]
    if not isinstance(hosts, list) or not hosts or hosts != sorted(set(hosts)):
        raise ContractError("allowed_key_hosts must be sorted, unique, and nonempty")
    if any(not isinstance(host, str) or host != host.lower() for host in hosts):
        raise ContractError("allowed key hosts must be lowercase strings")
    pins = result["trusted_spki_sha256"]
    if not isinstance(pins, list) or not pins or pins != sorted(set(pins)):
        raise ContractError("trusted_spki_sha256 must be sorted, unique, and nonempty")
    if any(
        not isinstance(pin, str) or not _LOWER_HEX_64_RE.fullmatch(pin) for pin in pins
    ):
        raise ContractError("SPKI pins must be lowercase SHA-256 hex")
    count = _int(result["render_segment_count"], "render_segment_count", minimum=1)
    if count > 4:
        raise ContractError("render_segment_count must be <= 4")
    return result


def key_aad(record: Mapping[str, Any]) -> bytes:
    return canonical_json(
        {
            "schema": "cipherwave.key-aad.v1",
            "profileId": record["profileId"],
            "keyId": record["keyId"],
            "generation": record["generation"],
            "keyUri": record["keyUri"],
            "spkiSha256": record["spkiSha256"],
        }
    )


_KEY_RECORD_FIELDS = {
    "schema",
    "keyId",
    "profileId",
    "generation",
    "issuerId",
    "notBeforeUnix",
    "notAfterUnix",
    "revokedAtUnix",
    "keyUri",
    "spkiSha256",
    "nonce",
    "wrappedKey",
    "signature",
}


def _parse_record(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("key record is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ContractError("key record must be an object")
    _exact_keys(value, _KEY_RECORD_FIELDS, "key record")
    if canonical_json(value) != raw:
        raise ContractError("key record bytes must be canonical JSON")
    if value["schema"] != "cipherwave.key-record.v1":
        raise ContractError("unsupported key-record schema")
    for field in ("keyId", "profileId", "issuerId"):
        _token(value[field], field)
    _int(value["generation"], "generation", minimum=1)
    for field in ("notBeforeUnix", "notAfterUnix"):
        _int(value[field], field, minimum=0)
    if value["notAfterUnix"] <= value["notBeforeUnix"]:
        raise ContractError("key record validity interval is empty")
    revoked = value["revokedAtUnix"]
    if revoked is not None:
        _int(revoked, "revokedAtUnix", minimum=0)
    if not isinstance(value["keyUri"], str) or not value["keyUri"]:
        raise ContractError("keyUri must be nonempty")
    if not isinstance(value["spkiSha256"], str) or not _LOWER_HEX_64_RE.fullmatch(
        value["spkiSha256"]
    ):
        raise ContractError("spkiSha256 must be lowercase SHA-256 hex")
    b64url_decode(value["nonce"], length=12)
    b64url_decode(value["wrappedKey"], length=32)
    b64url_decode(value["signature"], length=64)
    return value


def _issuer_map(trust: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    issuers = trust.get("issuers")
    if not isinstance(issuers, list):
        raise ContractError("trust issuers must be an array")
    result: dict[str, list[Mapping[str, Any]]] = {}
    previous_sort_key: tuple[str, int] | None = None
    for issuer in issuers:
        if not isinstance(issuer, dict):
            raise ContractError("issuer must be an object")
        issuer_id = _token(issuer.get("issuerId"), "issuerId")
        b64url_decode(issuer.get("publicKey"), length=32)
        not_before = _int(
            issuer.get("notBeforeUnix"), "issuer.notBeforeUnix", minimum=0
        )
        not_after = _int(issuer.get("notAfterUnix"), "issuer.notAfterUnix", minimum=0)
        if not_after <= not_before:
            raise ContractError("issuer validity interval is empty")
        sort_key = (issuer_id, not_before)
        if previous_sort_key is not None and sort_key <= previous_sort_key:
            raise ContractError("issuer eras are not in canonical order")
        prior_eras = result.setdefault(issuer_id, [])
        if prior_eras and prior_eras[-1]["notAfterUnix"] > not_before:
            raise ContractError("issuer eras overlap")
        compromised = issuer.get("compromisedAtUnix")
        if compromised is not None:
            _int(compromised, "issuer.compromisedAtUnix", minimum=0)
        prior_eras.append(issuer)
        previous_sort_key = sort_key
    return result


def _uri_is_allowed(uri: str, allowed_hosts: Sequence[str]) -> bool:
    try:
        parsed = urlsplit(uri)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        return False
    if parsed.scheme.lower() != "https" or parsed.scheme != "https":
        return False
    if (
        not parsed.netloc
        or host is None
        or parsed.username is not None
        or parsed.password is not None
    ):
        return False
    if parsed.fragment or port is not None and not 1 <= port <= 65535:
        return False
    return host.lower() in allowed_hosts


def _empty_custody_row(
    role: str, key_id: str, generation: int, reason: str
) -> dict[str, Any]:
    return {
        "role": role,
        "keyId": key_id,
        "generation": generation,
        "qualified": False,
        "reason": reason,
        "keyUri": None,
        "spkiSha256": None,
        "keyHandle": None,
    }


def _qualify_record(
    *,
    role: str,
    expected_key_id: str,
    expected_generation: int,
    profile: Mapping[str, Any],
    trust: Mapping[str, Any],
    issuers: Mapping[str, Sequence[Mapping[str, Any]]],
    raw: bytes | None,
) -> tuple[dict[str, Any], QualifiedKey | None]:
    if raw is None:
        return _empty_custody_row(
            role, expected_key_id, expected_generation, "missing"
        ), None
    try:
        record = _parse_record(raw)
    except ContractError:
        return _empty_custody_row(
            role, expected_key_id, expected_generation, "malformed"
        ), None

    row = _empty_custody_row(role, expected_key_id, expected_generation, "malformed")
    if record["keyId"] != expected_key_id:
        return row, None
    if record["profileId"] != profile["profile_id"]:
        row["reason"] = "wrong_profile"
        return row, None
    if record["generation"] != expected_generation:
        row["reason"] = "wrong_generation"
        return row, None
    issuer_eras = issuers.get(record["issuerId"])
    if issuer_eras is None:
        row["reason"] = "unknown_issuer"
        return row, None
    audit = profile["audit_unix"]
    matching_eras = [
        issuer
        for issuer in issuer_eras
        if issuer["notBeforeUnix"] <= audit < issuer["notAfterUnix"]
    ]
    if len(matching_eras) != 1:
        row["reason"] = "issuer_out_of_era"
        return row, None
    issuer = matching_eras[0]
    compromised = issuer.get("compromisedAtUnix")
    if compromised is not None and compromised <= audit:
        row["reason"] = "issuer_compromised"
        return row, None
    signed = dict(record)
    signature = b64url_decode(signed.pop("signature"), length=64)
    try:
        Ed25519PublicKey.from_public_bytes(
            b64url_decode(issuer["publicKey"], length=32)
        ).verify(signature, canonical_json(signed))
    except (InvalidSignature, ValueError):
        row["reason"] = "bad_signature"
        return row, None
    if audit < record["notBeforeUnix"]:
        row["reason"] = "not_yet_valid"
        return row, None
    if audit >= record["notAfterUnix"]:
        row["reason"] = "expired"
        return row, None
    revoked = record["revokedAtUnix"]
    if revoked is not None and revoked <= audit:
        row["reason"] = "revoked"
        return row, None
    if not _uri_is_allowed(record["keyUri"], profile["allowed_key_hosts"]):
        row["reason"] = "invalid_uri"
        return row, None
    if record["spkiSha256"] not in profile["trusted_spki_sha256"]:
        row["reason"] = "untrusted_spki"
        return row, None
    try:
        kek = b64url_decode(trust.get("keyEncryptionKey"), length=32)
        aad = key_aad(record)
        plaintext = AESGCM(kek).decrypt(
            b64url_decode(record["nonce"], length=12),
            b64url_decode(record["wrappedKey"], length=32),
            aad,
        )
        if len(plaintext) != 16:
            raise InvalidTag
    except (ContractError, InvalidTag, ValueError):
        row["reason"] = "unwrap_failed"
        return row, None
    handle = hmac.new(plaintext, KEY_HANDLE_DOMAIN + aad, hashlib.sha256).hexdigest()
    row.update(
        {
            "qualified": True,
            "reason": "qualified",
            "keyUri": record["keyUri"],
            "spkiSha256": record["spkiSha256"],
            "keyHandle": handle,
        }
    )
    return row, QualifiedKey(
        role=role,
        key_id=expected_key_id,
        generation=expected_generation,
        key_uri=record["keyUri"],
        spki_sha256=record["spkiSha256"],
        handle=handle,
        plaintext=plaintext,
        aad=aad,
    )


def build_custody(
    profile: Mapping[str, Any],
    trust: Mapping[str, Any],
    registry_records: Mapping[str, bytes],
    *,
    profile_bytes: bytes,
    registry_bytes: bytes,
    trust_bytes: bytes,
) -> tuple[dict[str, Any], dict[str, QualifiedKey]]:
    """Derive the custody artifact and the private verifier-only key ring."""

    p = _profile_normalized(profile)
    issuers = _issuer_map(trust)
    rows: list[dict[str, Any]] = []
    ring: dict[str, QualifiedKey] = {}
    for role in ("current", "candidate"):
        key_id = p[f"{role}_key_id"]
        generation = p[f"{role}_generation"]
        row, key = _qualify_record(
            role=role,
            expected_key_id=key_id,
            expected_generation=generation,
            profile=p,
            trust=trust,
            issuers=issuers,
            raw=registry_records.get(key_id),
        )
        rows.append(row)
        if key is not None:
            ring[role] = key
    report = {
        "schema": "cipherwave.custody.v1",
        "profileId": p["profile_id"],
        "auditUnix": p["audit_unix"],
        "sources": {
            "profileSha256": semantic_hash(normalized_profile_value(profile)),
            "registrySha256": registry_digest(registry_records),
            "trustSha256": semantic_hash(trust),
        },
        "ready": len(ring) == 2,
        "keys": rows,
    }
    return report, ring


def _split_attribute_list(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    position = 0
    while position < len(text):
        start = position
        while position < len(text) and (
            "A" <= text[position] <= "Z"
            or "0" <= text[position] <= "9"
            or text[position] == "-"
        ):
            position += 1
        if position == start or position >= len(text) or text[position] != "=":
            raise ContractError("expected NAME=value HLS attribute")
        name = text[start:position]
        if name in result:
            raise ContractError("duplicate HLS attribute")
        position += 1
        if position < len(text) and text[position] == '"':
            position += 1
            start = position
            while position < len(text) and text[position] != '"':
                if text[position] in "\r\n":
                    raise ContractError("newline in quoted HLS attribute")
                position += 1
            if position >= len(text):
                raise ContractError("unterminated quoted HLS attribute")
            value = text[start:position]
            position += 1
        else:
            start = position
            while position < len(text) and text[position] != ",":
                position += 1
            value = text[start:position]
            if not value or value.strip() != value:
                raise ContractError("empty or padded HLS attribute")
        result[name] = value
        if position == len(text):
            break
        if text[position] != ",":
            raise ContractError("expected comma between HLS attributes")
        position += 1
        if position == len(text):
            raise ContractError("trailing HLS attribute comma")
    return result


def parse_playlist(
    data: bytes, playlist_path: str, target_segment_path: str
) -> ParsedSegment:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractError("playlist is not UTF-8") from exc
    lines = [line.removesuffix("\r") for line in text.splitlines()]
    header_seen = False
    media_sequence_seen = False
    media_sequence = 0
    pending_segment = False
    current_key: dict[str, str] | None = None
    segments: list[tuple[str, int, dict[str, str] | None]] = []
    for line in lines:
        if not line:
            continue
        if not header_seen:
            if line != "#EXTM3U":
                raise ContractError("playlist lacks EXTM3U header")
            header_seen = True
            continue
        if line.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            if media_sequence_seen or segments or pending_segment:
                raise ContractError("misplaced or duplicate media sequence")
            raw = line.partition(":")[2]
            if not raw.isdigit():
                raise ContractError("invalid media sequence")
            media_sequence = int(raw)
            media_sequence_seen = True
        elif line.startswith("#EXT-X-KEY:"):
            current_key = _split_attribute_list(line.partition(":")[2])
            if not current_key.get("METHOD"):
                raise ContractError("HLS key tag has no METHOD")
        elif line.startswith("#EXTINF:"):
            if pending_segment:
                raise ContractError("prior EXTINF has no segment URI")
            pending_segment = True
        elif line.startswith("#"):
            continue
        else:
            if not pending_segment:
                raise ContractError("segment URI has no EXTINF")
            if line.strip() != line or "\x00" in line:
                raise ContractError("invalid segment URI")
            segments.append(
                (
                    line,
                    media_sequence + len(segments),
                    dict(current_key) if current_key is not None else None,
                )
            )
            pending_segment = False
    if not header_seen:
        raise ContractError("playlist is empty")
    if pending_segment:
        raise ContractError("final EXTINF has no segment URI")

    playlist_dir = posixpath.dirname(playlist_path)
    found: tuple[str, int, dict[str, str] | None] | None = None
    for segment in segments:
        candidate = posixpath.normpath(posixpath.join(playlist_dir, segment[0]))
        if candidate == target_segment_path:
            if found is not None:
                raise ContractError("target segment appears multiple times")
            found = segment
    if found is None or found[2] is None:
        raise ContractError("target segment or effective key is absent")
    found_key = found[2]
    distinct_uris = {
        key["URI"] for _, _, key in segments if key is not None and key.get("URI")
    }
    return ParsedSegment(
        method=found_key.get("METHOD", ""),
        uri=found_key.get("URI", ""),
        iv_text=found_key.get("IV"),
        media_sequence=media_sequence,
        sequence=found[1],
        path=target_segment_path,
        distinct_key_uris=frozenset(distinct_uris),
    )


def _safe_media_path(path: Any) -> str:
    if not isinstance(path, str) or not path or "\\" in path:
        raise ContractError("media path must be a nonempty POSIX path")
    value = PurePosixPath(path)
    if value.is_absolute() or any(part in ("", ".", "..") for part in value.parts):
        raise ContractError("media path escapes media root")
    return str(value)


def _catalog_rows(
    catalog: Mapping[str, Any], trust: Mapping[str, Any], profile_id: str
) -> tuple[bool, dict[tuple[str, str], list[dict[str, Any]]]]:
    """Validate the signed catalog and group its fragment rows by surface."""

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    try:
        if catalog.get("schema") != "cipherwave.catalog.v1":
            raise ContractError("unsupported catalog schema")
        if catalog.get("profileId") != profile_id:
            raise ContractError("catalog belongs to another profile")
        rows = catalog.get("rows")
        if not isinstance(rows, list):
            raise ContractError("catalog rows must be an array")
        seen: set[tuple[str, str, str, str, int]] = set()
        previous_sort_key: tuple[str, int, int, str, str] | None = None
        for row in rows:
            if not isinstance(row, dict):
                raise ContractError("catalog row must be an object")
            rendition = _token(row.get("rendition"), "catalog rendition")
            surface = row.get("surface")
            if surface not in ("published", "staged"):
                raise ContractError("invalid catalog surface")
            playlist_path = _safe_media_path(row.get("playlistPath"))
            segment_path = _safe_media_path(row.get("segmentPath"))
            _token(row.get("keyId"), "catalog keyId")
            _int(row.get("generation"), "catalog generation", minimum=1)
            sequence = _int(row.get("sequence"), "catalog sequence", minimum=0)
            for digest_field in ("ciphertextSha256", "plaintextSha256"):
                digest = row.get(digest_field)
                if not isinstance(digest, str) or not _LOWER_HEX_64_RE.fullmatch(
                    digest
                ):
                    raise ContractError("catalog digest must be lowercase SHA-256 hex")
            identity = (
                rendition,
                surface,
                playlist_path,
                segment_path,
                sequence,
            )
            if identity in seen:
                raise ContractError("duplicate catalog fragment")
            seen.add(identity)
            sort_key = (
                rendition,
                0 if surface == "published" else 1,
                sequence,
                playlist_path,
                segment_path,
            )
            if previous_sort_key is not None and sort_key <= previous_sort_key:
                raise ContractError("catalog rows are not in canonical order")
            previous_sort_key = sort_key
            grouped.setdefault((rendition, surface), []).append(row)

        signer = trust.get("catalogSigner")
        if not isinstance(signer, dict) or catalog.get("signerId") != signer.get(
            "signerId"
        ):
            raise ContractError("unknown catalog signer")
        signed = dict(catalog)
        signature = b64url_decode(signed.pop("signature"), length=64)
        Ed25519PublicKey.from_public_bytes(
            b64url_decode(signer.get("publicKey"), length=32)
        ).verify(signature, canonical_json(signed))
        return True, grouped
    except (ContractError, InvalidSignature, ValueError):
        return False, grouped


def _empty_evidence_row(rendition: str, surface: str, reason: str) -> dict[str, Any]:
    return {
        "rendition": rendition,
        "surface": surface,
        "present": reason not in ("absent", "catalog_invalid"),
        "valid": False,
        "reason": reason,
        "keyId": None,
        "generation": None,
        "mediaSequence": None,
        "fragments": [],
    }


def _parse_iv(iv_text: str | None, sequence: int) -> bytes:
    if iv_text is None:
        if sequence < 0 or sequence >= 1 << 128:
            raise ContractError("implicit IV sequence is outside uint128")
        return sequence.to_bytes(16, "big")
    if not re.fullmatch(r"0x[0-9A-Fa-f]{32}", iv_text):
        raise ContractError("explicit IV must be exactly 128-bit hex")
    return bytes.fromhex(iv_text[2:])


def _empty_fragment(catalog_row: Mapping[str, Any], reason: str) -> dict[str, Any]:
    return {
        "sequence": catalog_row["sequence"],
        "playlistPath": catalog_row["playlistPath"],
        "segmentPath": catalog_row["segmentPath"],
        "keyUri": None,
        "ivHex": None,
        "ciphertextSha256": "",
        "plaintextSha256": None,
        "valid": False,
        "reason": reason,
    }


def _validate_fragment(
    *,
    catalog_row: Mapping[str, Any],
    media: Mapping[str, bytes],
    ring: Mapping[str, QualifiedKey],
) -> tuple[dict[str, Any], int | None, frozenset[str]]:
    result = _empty_fragment(catalog_row, "playlist_malformed")
    playlist_path = str(catalog_row["playlistPath"])
    segment_path = str(catalog_row["segmentPath"])
    playlist = media.get(playlist_path)
    ciphertext = media.get(segment_path)
    if playlist is None or ciphertext is None:
        return result, None, frozenset()
    result["ciphertextSha256"] = sha256_hex(ciphertext)
    try:
        parsed = parse_playlist(playlist, playlist_path, segment_path)
    except ContractError:
        return result, None, frozenset()
    result["keyUri"] = parsed.uri or None
    if parsed.method != "AES-128":
        result["reason"] = "unsupported_method"
        return result, parsed.media_sequence, parsed.distinct_key_uris
    key = next(
        (
            candidate
            for candidate in ring.values()
            if candidate.key_id == catalog_row["keyId"]
            and candidate.generation == catalog_row["generation"]
        ),
        None,
    )
    if key is None:
        result["reason"] = "unknown_key"
        return result, parsed.media_sequence, parsed.distinct_key_uris
    if parsed.uri != key.key_uri:
        result["reason"] = "uri_mismatch"
        return result, parsed.media_sequence, parsed.distinct_key_uris
    try:
        iv = _parse_iv(parsed.iv_text, parsed.sequence)
    except ContractError:
        result["reason"] = "invalid_iv"
        return result, parsed.media_sequence, parsed.distinct_key_uris
    result["ivHex"] = iv.hex()
    if len(parsed.distinct_key_uris) > 1:
        result["reason"] = "mixed_generation"
        return result, parsed.media_sequence, parsed.distinct_key_uris
    cipher_digest = sha256_hex(ciphertext)
    result["ciphertextSha256"] = cipher_digest
    if cipher_digest != catalog_row["ciphertextSha256"]:
        result["reason"] = "cipher_digest_mismatch"
        return result, parsed.media_sequence, parsed.distinct_key_uris
    if not ciphertext or len(ciphertext) % 16:
        result["reason"] = "cipher_length"
        return result, parsed.media_sequence, parsed.distinct_key_uris
    try:
        decryptor = Cipher(algorithms.AES(key.plaintext), modes.CBC(iv)).decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()
    except ValueError:
        result["reason"] = "decrypt_failed"
        return result, parsed.media_sequence, parsed.distinct_key_uris
    try:
        unpadder = padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded) + unpadder.finalize()
    except ValueError:
        result["reason"] = "padding_invalid"
        return result, parsed.media_sequence, parsed.distinct_key_uris
    plain_digest = sha256_hex(plaintext)
    result["plaintextSha256"] = plain_digest
    if plain_digest != catalog_row["plaintextSha256"]:
        result["reason"] = "plaintext_digest_mismatch"
        return result, parsed.media_sequence, parsed.distinct_key_uris
    if parsed.sequence != catalog_row["sequence"]:
        result["reason"] = "playlist_malformed"
        return result, parsed.media_sequence, parsed.distinct_key_uris
    result["reason"] = "valid"
    result["valid"] = True
    return result, parsed.media_sequence, parsed.distinct_key_uris


def _validate_surface(
    *,
    rendition: str,
    surface: str,
    catalog_valid: bool,
    catalog_rows: Sequence[Mapping[str, Any]],
    media: Mapping[str, bytes],
    ring: Mapping[str, QualifiedKey],
) -> dict[str, Any]:
    if not catalog_valid:
        return _empty_evidence_row(rendition, surface, "catalog_invalid")
    if not catalog_rows:
        return _empty_evidence_row(rendition, surface, "absent")
    result = _empty_evidence_row(rendition, surface, "catalog_invalid")
    result["present"] = True

    identities = {(row["keyId"], row["generation"]) for row in catalog_rows}
    if len(identities) != 1:
        result["reason"] = "mixed_generation"
        return result
    key_id, generation = next(iter(identities))
    result["keyId"] = key_id
    result["generation"] = generation

    # Authenticated rows cannot grant authority over absent material.  A missing
    # playlist or segment is a catalog trust failure for the whole claimed
    # surface, not a syntactic playlist failure for an invented fragment.
    if any(
        row["playlistPath"] not in media or row["segmentPath"] not in media
        for row in catalog_rows
    ):
        return result

    fragments: list[dict[str, Any]] = []
    media_sequences: set[int] = set()
    distinct_uris: set[str] = set()
    for catalog_row in catalog_rows:
        fragment, media_sequence, fragment_uris = _validate_fragment(
            catalog_row=catalog_row,
            media=media,
            ring=ring,
        )
        fragments.append(fragment)
        if media_sequence is not None:
            media_sequences.add(media_sequence)
        distinct_uris.update(fragment_uris)
    result["fragments"] = fragments
    surface_failures: list[str] = []
    if len(media_sequences) == 1:
        result["mediaSequence"] = next(iter(media_sequences))
    elif len(media_sequences) > 1:
        surface_failures.append("playlist_malformed")
    if len(distinct_uris) > 1:
        surface_failures.append("mixed_generation")
    surface_failures.extend(
        fragment["reason"] for fragment in fragments if not fragment["valid"]
    )
    if surface_failures:
        result["reason"] = min(surface_failures, key=SURFACE_REASONS.index)
        return result
    result["valid"] = True
    result["reason"] = "valid"
    return result


def build_evidence(
    profile: Mapping[str, Any],
    trust: Mapping[str, Any],
    catalog: Mapping[str, Any],
    media: Mapping[str, bytes],
    ring: Mapping[str, QualifiedKey],
    *,
    custody_bytes: bytes,
    expected_custody: Mapping[str, Any] | None = None,
    catalog_bytes: bytes,
) -> dict[str, Any]:
    p = _profile_normalized(profile)
    custody = decode_canonical_artifact(custody_bytes)
    if expected_custody is not None and custody != expected_custody:
        raise IntegrityError("custody predecessor does not match re-derived custody")
    if (
        custody.get("schema") != "cipherwave.custody.v1"
        or custody.get("profileId") != p["profile_id"]
    ):
        raise IntegrityError(
            "custody predecessor belongs to a different contract/profile"
        )
    catalog_valid, catalog_rows = _catalog_rows(catalog, trust, p["profile_id"])
    rows: list[dict[str, Any]] = []
    for rendition in p["renditions"]:
        for surface in ("published", "staged"):
            rows.append(
                _validate_surface(
                    rendition=rendition,
                    surface=surface,
                    catalog_valid=catalog_valid,
                    catalog_rows=catalog_rows.get((rendition, surface), []),
                    media=media,
                    ring=ring,
                )
            )
    return {
        "schema": "cipherwave.evidence.v1",
        "profileId": p["profile_id"],
        "auditUnix": p["audit_unix"],
        "sources": {
            "profileSha256": custody["sources"]["profileSha256"],
            "registrySha256": custody["sources"]["registrySha256"],
            "trustSha256": custody["sources"]["trustSha256"],
            "catalogSha256": semantic_hash(catalog),
            "custodySha256": sha256_hex(custody_bytes),
        },
        "rows": rows,
    }


def classify_rendition(
    published: Mapping[str, Any],
    staged: Mapping[str, Any],
    *,
    current_generation: int,
    candidate_generation: int,
    candidate_published_globally: bool = False,
) -> str:
    pub_valid = published.get("reason") == "valid"
    staged_valid = staged.get("reason") == "valid"
    pub_generation = published.get("generation")
    staged_generation = staged.get("generation")

    if pub_valid and pub_generation == candidate_generation:
        if staged.get("present") and not staged_valid:
            return "broken"
        return "published"
    if pub_valid and pub_generation == current_generation:
        if not staged.get("present") and staged.get("reason") == "absent":
            return "broken" if candidate_published_globally else "old"
        if staged_valid and staged_generation == candidate_generation:
            return "staged"
        return "broken"

    candidate_visible = (
        published.get("present") and pub_generation == candidate_generation
    )
    if candidate_visible and published.get("reason") in {
        "catalog_invalid",
        "playlist_malformed",
        "cipher_length",
    }:
        return "advertised"
    return "broken"


def _decision_and_actions(
    p: Mapping[str, Any],
    custody: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> tuple[str, list[dict[str, str]], list[dict[str, str]]]:
    indexed = {
        (row["rendition"], row["surface"]): row
        for row in evidence.get("rows", [])
        if isinstance(row, dict)
    }
    candidate_published_globally = any(
        row.get("surface") == "published"
        and row.get("present")
        and row.get("generation") == p["candidate_generation"]
        for row in evidence.get("rows", [])
        if isinstance(row, dict)
    )
    state_rows: list[tuple[str, str]] = []
    for rendition in p["renditions"]:
        published = indexed.get((rendition, "published"))
        staged = indexed.get((rendition, "staged"))
        if published is None or staged is None:
            state = "broken"
        else:
            state = classify_rendition(
                published,
                staged,
                current_generation=p["current_generation"],
                candidate_generation=p["candidate_generation"],
                candidate_published_globally=candidate_published_globally,
            )
        state_rows.append((rendition, state))
    states = [state for _, state in state_rows]
    if not custody.get("ready") or any(
        state in ("broken", "advertised") for state in states
    ):
        decision = "quarantine"
    elif "published" in states:
        decision = (
            "finish_commit"
            if all(state in ("published", "staged") for state in states)
            else "quarantine"
        )
    elif states and all(state == "staged" for state in states):
        decision = "commit"
    elif "staged" in states and all(state in ("staged", "old") for state in states):
        decision = "rollback_pending"
    elif states and all(state == "old" for state in states):
        decision = "hold_current"
    else:
        decision = "quarantine"

    actions: list[dict[str, str]] = []
    for rendition, state in state_rows:
        if decision == "quarantine":
            action = "quarantine"
        elif decision == "finish_commit":
            action = "retain_candidate" if state == "published" else "publish_candidate"
        elif decision == "commit":
            action = "publish_candidate"
        elif decision == "rollback_pending":
            action = "remove_staged" if state == "staged" else "retain_current"
        else:
            action = "retain_current"
        actions.append({"rendition": rendition, "action": action})
    classifications = [
        {"rendition": rendition, "state": state} for rendition, state in state_rows
    ]
    return decision, classifications, actions


def _validate_guardian_trust(
    value: Mapping[str, Any], *, audit_unix: int
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Validate the rollout guardian authority and return normalized indexes."""

    if not isinstance(value, Mapping):
        raise ContractError("guardian trust must be an object")
    _exact_keys(value, {"schema", "checkpointPolicy", "guardians"}, "guardian trust")
    if value["schema"] != "cipherwave.guardian-trust.v2":
        raise ContractError("unsupported guardian trust schema")
    raw_policy = value["checkpointPolicy"]
    if not isinstance(raw_policy, Mapping):
        raise ContractError("checkpointPolicy must be an object")
    policy_fields = {
        "signatureThreshold",
        "organizationThreshold",
        "requiredCoverageMask",
        "minimumTrustWeight",
        "coverageAfterOrganizationLoss",
        "minSelectedOrganizations",
        "maxSelectedPerOrganization",
    }
    _exact_keys(raw_policy, policy_fields, "checkpointPolicy")
    policy = {
        key: _int(raw_policy[key], f"checkpointPolicy.{key}", minimum=1)
        for key in sorted(policy_fields - {"requiredCoverageMask"})
    }
    required_mask = raw_policy["requiredCoverageMask"]
    if not isinstance(required_mask, str) or not re.fullmatch(r"[0-9a-f]{4}", required_mask):
        raise ContractError("checkpointPolicy.requiredCoverageMask must be four lowercase hex digits")
    policy["requiredCoverageMask"] = int(required_mask, 16)
    policy["requiredCoverageMaskText"] = required_mask
    raw_guardians = value["guardians"]
    if not isinstance(raw_guardians, list) or not raw_guardians:
        raise ContractError("guardians must be a nonempty array")
    if raw_guardians != sorted(raw_guardians, key=lambda row: row.get("guardianId", "")):
        raise ContractError("guardians must be sorted by guardianId")
    guardians: dict[str, dict[str, Any]] = {}
    organizations: set[str] = set()
    checkpoint_operators: set[str] = set()
    guardian_fields = {
        "guardianId",
        "organization",
        "checkpointOperator",
        "status",
        "publicKey",
        "notBeforeUnix",
        "notAfterUnix",
        "compromisedAtUnix",
        "coverageMask",
        "trustWeight",
    }
    for index, raw in enumerate(raw_guardians):
        if not isinstance(raw, Mapping):
            raise ContractError(f"guardians[{index}] must be an object")
        _exact_keys(raw, guardian_fields, f"guardians[{index}]")
        guardian_id = _token(raw["guardianId"], f"guardians[{index}].guardianId")
        organization = _token(raw["organization"], f"guardians[{index}].organization")
        checkpoint_operator = _token(
            raw["checkpointOperator"], f"guardians[{index}].checkpointOperator"
        )
        status = raw["status"]
        if status not in ("active", "inactive"):
            raise ContractError("guardian status must be active or inactive")
        if guardian_id in guardians:
            raise ContractError("guardianId values must be unique")
        public_key = b64url_decode(raw["publicKey"], length=32)
        not_before = _int(raw["notBeforeUnix"], "guardian notBeforeUnix", minimum=0)
        not_after = _int(raw["notAfterUnix"], "guardian notAfterUnix", minimum=1)
        if not_before >= not_after:
            raise ContractError("guardian validity window must be nonempty")
        compromised = raw["compromisedAtUnix"]
        if compromised is not None:
            compromised = _int(compromised, "guardian compromisedAtUnix", minimum=0)
        coverage_mask = raw["coverageMask"]
        if not isinstance(coverage_mask, str) or not re.fullmatch(
            r"[0-9a-f]{4}", coverage_mask
        ):
            raise ContractError("guardian coverageMask must be four lowercase hex digits")
        trust_weight = _int(raw["trustWeight"], "guardian trustWeight", minimum=1)
        guardians[guardian_id] = {
            "guardianId": guardian_id,
            "organization": organization,
            "checkpointOperator": checkpoint_operator,
            "status": status,
            "publicKey": public_key,
            "notBeforeUnix": not_before,
            "notAfterUnix": not_after,
            "compromisedAtUnix": compromised,
            "coverageMask": int(coverage_mask, 16),
            "coverageMaskText": coverage_mask,
            "trustWeight": trust_weight,
            "availableAtAudit": status == "active"
            and not_before <= audit_unix < not_after
            and (compromised is None or audit_unix < compromised),
        }
        organizations.add(organization)
        checkpoint_operators.add(checkpoint_operator)
    if policy["signatureThreshold"] > len(guardians):
        raise ContractError("signature threshold exceeds guardian count")
    if policy["organizationThreshold"] > len(checkpoint_operators):
        raise ContractError("organization threshold exceeds organization count")
    if policy["minSelectedOrganizations"] > len(organizations):
        raise ContractError("minimum selected organizations exceeds organization count")
    return guardians, policy


def _rollout_record_without_signature(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in record if key != "signature"}


def _rollout_record_hash(record: Mapping[str, Any]) -> str:
    return sha256_hex(canonical_json(record))


def _rollout_merkle_root(records: Sequence[Mapping[str, Any]]) -> str:
    level = [hashlib.sha256(b"\x00" + canonical_json(row)).digest() for row in records]
    if not level:
        raise ContractError("rollout ledger cannot be empty")
    while len(level) > 1:
        next_level: list[bytes] = []
        for offset in range(0, len(level), 2):
            if offset + 1 == len(level):
                next_level.append(level[offset])
            else:
                next_level.append(
                    hashlib.sha256(b"\x01" + level[offset] + level[offset + 1]).digest()
                )
        level = next_level
    return level[0].hex()


def _checkpoint_message(
    *,
    profile_id: str,
    candidate_generation: int,
    checkpoint: Mapping[str, Any],
    signed_at: int,
) -> bytes:
    core = {
        "schema": "cipherwave.rollout-checkpoint.v2",
        "profileId": profile_id,
        "candidateGeneration": candidate_generation,
        "treeSize": checkpoint["treeSize"],
        "rootSha256": checkpoint["rootSha256"],
        "issuedAtUnix": checkpoint["issuedAtUnix"],
    }
    return (
        ROLLOUT_CHECKPOINT_DOMAIN
        + canonical_json(core)
        + b"\x00"
        + signed_at.to_bytes(8, "big")
    )


def _validate_rollout_ledger(
    value: Mapping[str, Any],
    *,
    profile: Mapping[str, Any],
    guardians: Mapping[str, Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    """Authenticate the append-only ledger, checkpoint, and amendment heads."""

    if not isinstance(value, Mapping):
        raise ContractError("rollout ledger must be an object")
    _exact_keys(
        value,
        {"schema", "profileId", "candidateGeneration", "records", "checkpoint"},
        "rollout ledger",
    )
    if value["schema"] != "cipherwave.rollout-ledger.v2":
        raise ContractError("unsupported rollout ledger schema")
    profile_id = _token(value["profileId"], "rollout ledger profileId")
    candidate_generation = _int(
        value["candidateGeneration"], "rollout ledger candidateGeneration", minimum=1
    )
    if (
        profile_id != profile["profile_id"]
        or candidate_generation != profile["candidate_generation"]
    ):
        raise IntegrityError("rollout ledger does not name the active candidate")
    records = value["records"]
    if not isinstance(records, list) or not records:
        raise ContractError("rollout records must be a nonempty array")
    record_fields = {
        "recordId",
        "sequence",
        "previousRecordSha256",
        "approvalId",
        "revision",
        "predecessorRecordId",
        "guardianId",
        "profileId",
        "candidateGeneration",
        "operation",
        "scopes",
        "riskCost",
        "signature",
    }
    previous_hash = "0" * 64
    heads: dict[str, dict[str, Any]] = {}
    normalized_records: list[dict[str, Any]] = []
    for index, raw in enumerate(records):
        if not isinstance(raw, Mapping):
            raise ContractError(f"records[{index}] must be an object")
        _exact_keys(raw, record_fields, f"records[{index}]")
        record = dict(raw)
        record_id = _token(record["recordId"], f"records[{index}].recordId")
        approval_id = _token(record["approvalId"], f"records[{index}].approvalId")
        guardian_id = _token(record["guardianId"], f"records[{index}].guardianId")
        if guardian_id not in guardians:
            raise IntegrityError("rollout record names an unknown guardian")
        if not guardians[guardian_id]["availableAtAudit"]:
            raise IntegrityError("rollout record guardian is unavailable at audit time")
        if _int(record["sequence"], "rollout sequence", minimum=0) != index:
            raise IntegrityError("rollout record sequence is not contiguous")
        if record["previousRecordSha256"] != previous_hash:
            raise IntegrityError("rollout record previous-hash linkage is invalid")
        if not isinstance(record["previousRecordSha256"], str) or not _LOWER_HEX_64_RE.fullmatch(
            record["previousRecordSha256"]
        ):
            raise ContractError("previousRecordSha256 must be lowercase SHA-256 hex")
        revision = _int(record["revision"], "rollout revision", minimum=1)
        predecessor = record["predecessorRecordId"]
        prior = heads.get(approval_id)
        if prior is None:
            if revision != 1 or predecessor is not None:
                raise IntegrityError("an approval chain must begin at revision one")
        else:
            if (
                revision != prior["revision"] + 1
                or predecessor != prior["recordId"]
                or guardian_id != prior["guardianId"]
            ):
                raise IntegrityError("approval amendment chain is invalid")
        record_profile = _token(record["profileId"], "rollout record profileId")
        record_generation = _int(
            record["candidateGeneration"], "rollout record generation", minimum=1
        )
        operation = record["operation"]
        if operation not in ("grant", "revoke"):
            raise ContractError("rollout operation must be grant or revoke")
        raw_scopes = record["scopes"]
        if not isinstance(raw_scopes, list):
            raise ContractError("rollout scopes must be an array")
        scopes: list[dict[str, str]] = []
        for scope_index, raw_scope in enumerate(raw_scopes):
            if not isinstance(raw_scope, Mapping):
                raise ContractError("rollout scope must be an object")
            _exact_keys(raw_scope, {"rendition", "action"}, "rollout scope")
            rendition = _token(raw_scope["rendition"], "rollout scope rendition")
            action = raw_scope["action"]
            if action not in ("publish_candidate", "retain_candidate"):
                raise ContractError("rollout scope action is unsupported")
            scopes.append({"rendition": rendition, "action": action})
        if scopes != sorted(scopes, key=lambda row: (row["rendition"], row["action"])):
            raise ContractError("rollout scopes must be canonically sorted")
        if len({(row["rendition"], row["action"]) for row in scopes}) != len(scopes):
            raise ContractError("rollout scopes must be unique")
        risk_cost = _int(record["riskCost"], "rollout riskCost", minimum=0)
        if operation == "grant" and not scopes:
            raise ContractError("grant records require at least one scope")
        if operation == "revoke" and (scopes or risk_cost != 0):
            raise ContractError("revoke records require empty scopes and zero riskCost")
        signature = b64url_decode(record["signature"], length=64)
        try:
            Ed25519PublicKey.from_public_bytes(guardians[guardian_id]["publicKey"]).verify(
                signature,
                ROLLOUT_RECORD_DOMAIN
                + canonical_json(_rollout_record_without_signature(record)),
            )
        except (InvalidSignature, ValueError) as exc:
            raise IntegrityError("rollout record signature is invalid") from exc
        normalized = {
            **record,
            "recordId": record_id,
            "approvalId": approval_id,
            "guardianId": guardian_id,
            "profileId": record_profile,
            "candidateGeneration": record_generation,
            "revision": revision,
            "operation": operation,
            "scopes": scopes,
            "riskCost": risk_cost,
        }
        normalized_records.append(normalized)
        heads[approval_id] = normalized
        previous_hash = _rollout_record_hash(record)

    checkpoint = value["checkpoint"]
    if not isinstance(checkpoint, Mapping):
        raise ContractError("rollout checkpoint must be an object")
    _exact_keys(
        checkpoint,
        {"treeSize", "rootSha256", "issuedAtUnix", "signatures"},
        "rollout checkpoint",
    )
    if _int(checkpoint["treeSize"], "checkpoint treeSize", minimum=1) != len(records):
        raise IntegrityError("checkpoint tree size does not cover the complete ledger")
    root = checkpoint["rootSha256"]
    if not isinstance(root, str) or not _LOWER_HEX_64_RE.fullmatch(root):
        raise ContractError("checkpoint root must be lowercase SHA-256 hex")
    if root != _rollout_merkle_root(records):
        raise IntegrityError("checkpoint Merkle root is invalid")
    issued_at = _int(checkpoint["issuedAtUnix"], "checkpoint issuedAtUnix", minimum=0)
    if issued_at > profile["audit_unix"]:
        raise IntegrityError("checkpoint is issued after the audit instant")
    signatures = checkpoint["signatures"]

    def signature_sort(row: Any) -> tuple[bytes, int, bytes]:
        if not isinstance(row, Mapping):
            return b"", -1, b""
        raw_signed_at = row.get("signedAtUnix", -1)
        return (
            str(row.get("guardianId", "")).encode("utf-8"),
            raw_signed_at if type(raw_signed_at) is int else -1,
            str(row.get("signature", "")).encode("ascii", "ignore"),
        )

    if not isinstance(signatures, list) or signatures != sorted(signatures, key=signature_sort):
        raise ContractError("checkpoint signatures must be a sorted array")
    valid_signers: list[str] = []
    valid_organizations: set[str] = set()
    endorsement_rows: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    seen_signers: set[str] = set()
    for index, raw_signature in enumerate(signatures):
        if not isinstance(raw_signature, Mapping):
            raise ContractError("checkpoint signature must be an object")
        _exact_keys(
            raw_signature,
            {"guardianId", "signedAtUnix", "signature"},
            "checkpoint signature",
        )
        guardian_id = _token(raw_signature["guardianId"], "checkpoint guardianId")
        signed_at = _int(
            raw_signature["signedAtUnix"], "checkpoint signature signedAtUnix", minimum=0
        )
        reason = "valid"
        if guardian_id in seen_signers:
            reason = "duplicate_guardian"
        seen_signers.add(guardian_id)
        guardian = guardians.get(guardian_id)
        signature: bytes | None = None
        try:
            signature = b64url_decode(raw_signature["signature"], length=64)
        except ContractError:
            if reason == "valid":
                reason = "bad_signature"
        if reason == "valid" and guardian is None:
            reason = "unknown_guardian"
        if reason == "valid" and guardian["status"] != "active":
            reason = "guardian_inactive"
        if reason == "valid" and not (
            guardian["notBeforeUnix"] <= signed_at < guardian["notAfterUnix"]
        ):
            reason = "guardian_out_of_window"
        if (
            reason == "valid"
            and guardian["compromisedAtUnix"] is not None
            and signed_at >= guardian["compromisedAtUnix"]
        ):
            reason = "guardian_compromised"
        if reason == "valid":
            try:
                Ed25519PublicKey.from_public_bytes(guardian["publicKey"]).verify(
                    signature,
                    _checkpoint_message(
                        profile_id=profile_id,
                        candidate_generation=candidate_generation,
                        checkpoint=checkpoint,
                        signed_at=signed_at,
                    ),
                )
            except (InvalidSignature, ValueError, TypeError):
                reason = "bad_signature"
        valid = reason == "valid"
        organization = str(guardian["checkpointOperator"]) if valid else None
        coverage_text = str(guardian["coverageMaskText"]) if valid else None
        trust_weight = int(guardian["trustWeight"]) if valid else None
        lag = max(0, issued_at - signed_at) if valid else None
        endorsement_rows.append(
            {
                "guardianId": guardian_id,
                "signedAtUnix": signed_at,
                "valid": valid,
                "reason": reason,
                "organization": organization,
                "coverageMask": coverage_text,
                "trustWeight": trust_weight,
                "lagSeconds": lag,
            }
        )
        if valid:
            valid_signers.append(guardian_id)
            valid_organizations.add(organization)
            candidates.append(
                {
                    "guardianId": guardian_id,
                    "organization": organization,
                    "coverageMask": int(guardian["coverageMask"]),
                    "trustWeight": trust_weight,
                    "lagSeconds": lag,
                }
            )
    if len(valid_signers) < policy["signatureThreshold"]:
        raise IntegrityError("checkpoint does not meet the signature threshold")
    if len(valid_organizations) < policy["organizationThreshold"]:
        raise IntegrityError("checkpoint does not meet the organization threshold")
    return (
        list(heads.values()),
        {
            "treeSize": len(records),
            "rootSha256": root,
            "issuedAtUnix": issued_at,
            "validSignerIds": valid_signers,
            "validOrganizations": sorted(valid_organizations),
            "endorsements": endorsement_rows,
        },
        candidates,
    )


def _frontier_objective(state: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        state["selectedCount"],
        state["totalLag"],
        -state["totalWeight"],
        tuple(value.encode("utf-8") for value in state["guardianIds"]),
    )


def _checkpoint_frontier(
    candidates: Sequence[Mapping[str, Any]],
    *,
    required_mask: int,
    minimum_weight: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Compute every coalesced operator-distinct coverage/weight coordinate."""

    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for candidate in candidates:
        grouped.setdefault(str(candidate["organization"]), []).append(candidate)
    states: dict[tuple[int, int], dict[str, Any]] = {
        (0, 0): {
            "guardianIds": [],
            "selectedCount": 0,
            "totalLag": 0,
            "totalWeight": 0,
        }
    }
    for organization in sorted(grouped, key=lambda value: value.encode("utf-8")):
        options: list[Mapping[str, Any] | None] = [None] + sorted(
            grouped[organization], key=lambda row: str(row["guardianId"]).encode("utf-8")
        )
        next_states: dict[tuple[int, int], dict[str, Any]] = {}
        for (coverage, capped_weight), state in states.items():
            for option in options:
                if option is None:
                    coordinate = (coverage, capped_weight)
                    proposed = dict(state)
                else:
                    coordinate = (
                        (coverage | int(option["coverageMask"])) & required_mask,
                        min(minimum_weight, capped_weight + int(option["trustWeight"])),
                    )
                    proposed = {
                        "guardianIds": sorted(
                            [*state["guardianIds"], str(option["guardianId"])],
                            key=lambda value: value.encode("utf-8"),
                        ),
                        "selectedCount": int(state["selectedCount"]) + 1,
                        "totalLag": int(state["totalLag"]) + int(option["lagSeconds"]),
                        "totalWeight": int(state["totalWeight"])
                        + int(option["trustWeight"]),
                    }
                current = next_states.get(coordinate)
                if current is None or _frontier_objective(proposed) < _frontier_objective(
                    current
                ):
                    next_states[coordinate] = proposed
        states = next_states
    rows: list[dict[str, Any]] = []
    for (coverage, capped_weight), state in sorted(states.items()):
        base = {
            "coverageMask": f"{coverage:04x}",
            "cappedWeight": capped_weight,
            "guardianIds": state["guardianIds"],
            "selectedCount": state["selectedCount"],
            "totalLag": state["totalLag"],
            "totalWeight": state["totalWeight"],
        }
        rows.append({**base, "rowDigest": sha256_hex(canonical_json(base))})
    selected = states.get((required_mask, minimum_weight))
    if selected is None:
        raise IntegrityError("checkpoint frontier has no qualifying coordinate")
    selected_base = {
        "coverageMask": f"{required_mask:04x}",
        "cappedWeight": minimum_weight,
        "guardianIds": selected["guardianIds"],
        "selectedCount": selected["selectedCount"],
        "totalLag": selected["totalLag"],
        "totalWeight": selected["totalWeight"],
    }
    selected_row = {
        **selected_base,
        "rowDigest": sha256_hex(canonical_json(selected_base)),
    }
    frontier_bytes = b"".join(canonical_json(row) + b"\n" for row in rows)
    state_digest = sha256_hex(
        b"".join(bytes.fromhex(str(row["rowDigest"])) for row in rows)
    )
    return rows, {
        "requiredCoverageMask": f"{required_mask:04x}",
        "minimumTrustWeight": minimum_weight,
        "stateCount": len(rows),
        "stateDigest": state_digest,
        "frontierSha256": sha256_hex(frontier_bytes),
        "selectedWitness": selected_row,
    }


def _select_rollout_witness(
    candidates: Sequence[Mapping[str, Any]],
    *,
    targets: Sequence[tuple[str, str]],
    organizations: Sequence[str],
    policy: Mapping[str, int],
) -> tuple[list[Mapping[str, Any]], list[dict[str, Any]]] | None:
    """Select the exact minimum-risk organization-loss-resistant witness."""

    ordered = sorted(candidates, key=lambda row: str(row["approvalId"]).encode("utf-8"))
    if len(ordered) > 22:
        raise ContractError("at most 22 operative rollout approvals are supported")
    best_key: tuple[int, int, tuple[str, ...]] | None = None
    best_rows: list[Mapping[str, Any]] | None = None
    for count in range(1, len(ordered) + 1):
        for selected_tuple in itertools.combinations(ordered, count):
            selected = list(selected_tuple)
            ids = tuple(str(row["approvalId"]) for row in selected)
            risk = sum(int(row["riskCost"]) for row in selected)
            if best_key is not None and (risk, count) > best_key[:2]:
                continue
            guardian_ids = [str(row["guardianId"]) for row in selected]
            if len(set(guardian_ids)) != len(guardian_ids):
                continue
            org_loads = {
                organization: sum(row["organization"] == organization for row in selected)
                for organization in organizations
            }
            if any(
                load > policy["maxSelectedPerOrganization"]
                for load in org_loads.values()
            ):
                continue
            if sum(load > 0 for load in org_loads.values()) < policy["minSelectedOrganizations"]:
                continue
            coverage_rows: list[dict[str, Any]] = []
            feasible = True
            for rendition, action in targets:
                covering = [
                    row
                    for row in selected
                    if (rendition, action) in row["scopeSet"]
                ]
                survivors = []
                for organization in organizations:
                    surviving = sum(row["organization"] != organization for row in covering)
                    survivors.append(
                        {"organization": organization, "survivingApprovals": surviving}
                    )
                    if surviving < policy["coverageAfterOrganizationLoss"]:
                        feasible = False
                coverage_rows.append(
                    {
                        "rendition": rendition,
                        "action": action,
                        "selectedApprovals": len(covering),
                        "organizationLoads": [
                            {
                                "organization": organization,
                                "selected": sum(
                                    row["organization"] == organization for row in covering
                                ),
                            }
                            for organization in organizations
                        ],
                        "survivorsAfterLoss": survivors,
                    }
                )
            if not feasible:
                continue
            objective = (risk, count, ids)
            if best_key is None or objective < best_key:
                best_key = objective
                best_rows = selected
                best_coverage = coverage_rows
    if best_rows is None:
        return None
    return best_rows, best_coverage


def build_authorization_proof(
    profile: Mapping[str, Any],
    guardian_trust: Mapping[str, Any],
    rollout_ledger: Mapping[str, Any],
    *,
    proposed_decision: str,
    proposed_actions: Sequence[Mapping[str, str]],
    custody_bytes: bytes,
    evidence_bytes: bytes,
) -> tuple[dict[str, Any], bytes]:
    """Replay authenticated approvals and construct the exact rollout witness."""

    p = _profile_normalized(profile)
    guardians, policy = _validate_guardian_trust(guardian_trust, audit_unix=p["audit_unix"])
    heads, checkpoint_with_endorsements, checkpoint_candidates = _validate_rollout_ledger(
        rollout_ledger, profile=p, guardians=guardians, policy=policy
    )
    frontier_rows, frontier_summary = _checkpoint_frontier(
        checkpoint_candidates,
        required_mask=int(policy["requiredCoverageMask"]),
        minimum_weight=int(policy["minimumTrustWeight"]),
    )
    frontier_bytes = b"".join(canonical_json(row) + b"\n" for row in frontier_rows)
    checkpoint_endorsements = checkpoint_with_endorsements["endorsements"]
    checkpoint = {
        key: value
        for key, value in checkpoint_with_endorsements.items()
        if key != "endorsements"
    }
    targets = sorted(
        {
            (str(row["rendition"]), str(row["action"]))
            for row in proposed_actions
            if row["action"] in ("publish_candidate", "retain_candidate")
        }
    )
    required = proposed_decision in ("commit", "finish_commit") and bool(targets)
    target_set = set(targets)
    head_rows: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for head in sorted(heads, key=lambda row: str(row["approvalId"]).encode("utf-8")):
        guardian = guardians[str(head["guardianId"])]
        scope_set = {
            (str(scope["rendition"]), str(scope["action"])) for scope in head["scopes"]
        }
        if head["operation"] == "revoke":
            reason = "revoked"
        elif head["profileId"] != p["profile_id"]:
            reason = "stale_profile"
        elif head["candidateGeneration"] != p["candidate_generation"]:
            reason = "stale_generation"
        elif not scope_set or not scope_set.issubset(target_set):
            reason = "scope_mismatch"
        else:
            reason = "operative"
        row = {
            "approvalId": head["approvalId"],
            "recordId": head["recordId"],
            "revision": head["revision"],
            "guardianId": head["guardianId"],
            "organization": guardian["organization"],
            "operation": head["operation"],
            "reason": reason,
            "scopes": head["scopes"],
            "riskCost": head["riskCost"],
            "recordSha256": _rollout_record_hash(head),
        }
        head_rows.append(row)
        if reason == "operative":
            candidates.append({**row, "scopeSet": scope_set})
    organizations = sorted({str(row["organization"]) for row in guardians.values()})
    selected: list[Mapping[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    ready = True
    if required:
        result = _select_rollout_witness(
            candidates, targets=targets, organizations=organizations, policy=policy
        )
        ready = result is not None
        if result is not None:
            selected, coverage = result
    selected_ids = [str(row["approvalId"]) for row in selected]
    selected_organizations = sorted({str(row["organization"]) for row in selected})
    total_risk = sum(int(row["riskCost"]) for row in selected)
    selection_value = {
        "requestedActions": [
            {"rendition": rendition, "action": action} for rendition, action in targets
        ],
        "selectedApprovalIds": selected_ids,
        "selectedOrganizations": selected_organizations,
        "totalRisk": total_risk,
        "coverage": coverage,
    }
    proof_without_digest = {
        "schema": "cipherwave.authorization-proof.v2",
        "profileId": p["profile_id"],
        "auditUnix": p["audit_unix"],
        "candidateGeneration": p["candidate_generation"],
        "sources": {
            "guardianTrustSha256": semantic_hash(guardian_trust),
            "rolloutLedgerSha256": semantic_hash(rollout_ledger),
            "custodySha256": sha256_hex(custody_bytes),
            "evidenceSha256": sha256_hex(evidence_bytes),
            "checkpointFrontierSha256": sha256_hex(frontier_bytes),
        },
        "proposedDecision": proposed_decision,
        "required": required,
        "ready": ready,
        "requestedActions": selection_value["requestedActions"],
        "checkpoint": checkpoint,
        "checkpointEndorsements": checkpoint_endorsements,
        "checkpointFrontier": frontier_summary,
        "policy": {
            "requiredCoverageMask": policy["requiredCoverageMaskText"],
            "minimumTrustWeight": policy["minimumTrustWeight"],
            "coverageAfterOrganizationLoss": policy["coverageAfterOrganizationLoss"],
            "minSelectedOrganizations": policy["minSelectedOrganizations"],
            "maxSelectedPerOrganization": policy["maxSelectedPerOrganization"],
        },
        "heads": head_rows,
        "selectedApprovalIds": selected_ids,
        "selectedOrganizations": selected_organizations,
        "selectedCount": len(selected_ids),
        "totalRisk": total_risk,
        "coverage": coverage,
        "selectionDigest": sha256_hex(canonical_json(selection_value)),
    }
    proof = {
        **proof_without_digest,
        "proofDigest": sha256_hex(canonical_json(proof_without_digest)),
    }
    return proof, frontier_bytes


def _qualified_row(custody: Mapping[str, Any], role: str) -> Mapping[str, Any] | None:
    for row in custody.get("keys", []):
        if (
            isinstance(row, dict)
            and row.get("role") == role
            and row.get("reason") == "qualified"
        ):
            return row
    return None


def build_authorization(
    profile: Mapping[str, Any],
    ring: Mapping[str, QualifiedKey],
    *,
    guardian_trust: Mapping[str, Any],
    rollout_ledger: Mapping[str, Any],
    custody_bytes: bytes,
    evidence_bytes: bytes,
    expected_custody: Mapping[str, Any] | None = None,
    expected_evidence: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], bytes]:
    p = _profile_normalized(profile)
    custody = decode_canonical_artifact(custody_bytes)
    evidence = decode_canonical_artifact(evidence_bytes)
    if expected_custody is not None and custody != expected_custody:
        raise IntegrityError("custody predecessor does not match re-derived custody")
    if expected_evidence is not None and evidence != expected_evidence:
        raise IntegrityError("evidence predecessor does not match re-derived evidence")
    if evidence.get("sources", {}).get("custodySha256") != sha256_hex(custody_bytes):
        raise IntegrityError("evidence does not bind exact custody bytes")
    if (
        custody.get("profileId") != p["profile_id"]
        or evidence.get("profileId") != p["profile_id"]
    ):
        raise IntegrityError("predecessor profile mismatch")

    proposed_decision, classifications, proposed_actions = _decision_and_actions(
        p, custody, evidence
    )
    authorization, checkpoint_frontier_bytes = build_authorization_proof(
        profile,
        guardian_trust,
        rollout_ledger,
        proposed_decision=proposed_decision,
        proposed_actions=proposed_actions,
        custody_bytes=custody_bytes,
        evidence_bytes=evidence_bytes,
    )
    authorization_bytes = artifact_bytes(authorization)
    if authorization["required"] and not authorization["ready"]:
        decision = "quarantine"
        actions = [
            {"rendition": row["rendition"], "action": "quarantine"}
            for row in proposed_actions
        ]
    else:
        decision = proposed_decision
        actions = list(proposed_actions)
    current = _qualified_row(custody, "current")
    candidate = _qualified_row(custody, "candidate")
    current_meta = (
        {
            "keyId": p["current_key_id"],
            "generation": p["current_generation"],
            "keyUri": current["keyUri"],
            "spkiSha256": current["spkiSha256"],
            "keyHandle": current["keyHandle"],
        }
        if current is not None
        else None
    )
    candidate_meta = (
        {
            "keyId": p["candidate_key_id"],
            "generation": p["candidate_generation"],
            "keyUri": candidate["keyUri"],
            "spkiSha256": candidate["spkiSha256"],
            "keyHandle": candidate["keyHandle"],
        }
        if candidate is not None
        else None
    )
    enabled = decision in ("commit", "finish_commit") and candidate_meta is not None

    certificate_core = {
        "schema": "cipherwave.rotation-core.v1",
        "profileId": p["profile_id"],
        "auditUnix": p["audit_unix"],
        "sources": {
            "custodySha256": sha256_hex(custody_bytes),
            "evidenceSha256": sha256_hex(evidence_bytes),
            "authorizationSha256": sha256_hex(authorization_bytes),
        },
        "decision": decision,
        "currentKey": current_meta,
        "candidateKey": candidate_meta,
        "renditions": classifications,
        "actions": actions,
    }
    core_bytes = canonical_json(certificate_core)
    core_sha256 = sha256_hex(core_bytes)
    explicit_iv = (
        hmac.new(
            ring["candidate"].plaintext,
            PLAN_IV_DOMAIN + core_bytes,
            hashlib.sha256,
        ).digest()[:16]
        if enabled
        else b""
    )
    plan_body = {
        "schema": "cipherwave.ffmpeg-plan.v1",
        "profileId": p["profile_id"],
        "decision": decision,
        "enabled": enabled,
        "certificateCoreSha256": core_sha256,
        "keyId": candidate_meta["keyId"] if enabled else "",
        "generation": candidate_meta["generation"] if enabled else 0,
        "keyUri": candidate_meta["keyUri"] if enabled else "",
        "spkiSha256": candidate_meta["spkiSha256"] if enabled else "",
        "ivHex": explicit_iv.hex() if enabled else "",
        "renderSegmentCount": p["render_segment_count"],
        "renditions": list(p["renditions"]),
        "actions": actions,
    }
    certificate_without_confirmations = {
        "schema": "cipherwave.rotation-certificate.v1",
        "profileId": p["profile_id"],
        "auditUnix": p["audit_unix"],
        "sources": certificate_core["sources"],
        "decision": decision,
        "currentKey": current_meta,
        "candidateKey": candidate_meta,
        "renditions": classifications,
        "actions": actions,
        "planBodySha256": sha256_hex(canonical_json(plan_body)),
    }
    confirmations = {
        role: (
            hmac.new(
                ring[role].plaintext, CERT_CONFIRM_DOMAIN + core_bytes, hashlib.sha256
            ).hexdigest()
            if role in ring
            else None
        )
        for role in ("current", "candidate")
    }
    without_seal = {
        **certificate_without_confirmations,
        "keyConfirmations": confirmations,
    }
    certificate = {
        **without_seal,
        "seal": sha256_hex(CERT_SEAL_DOMAIN + canonical_json(without_seal)),
    }
    certificate_bytes = artifact_bytes(certificate)
    plan = {
        "schema": plan_body["schema"],
        "profileId": plan_body["profileId"],
        "decision": plan_body["decision"],
        "enabled": plan_body["enabled"],
        "certificateCoreSha256": plan_body["certificateCoreSha256"],
        "certificateSha256": sha256_hex(certificate_bytes),
        "keyId": plan_body["keyId"],
        "generation": plan_body["generation"],
        "keyUri": plan_body["keyUri"],
        "spkiSha256": plan_body["spkiSha256"],
        "ivHex": plan_body["ivHex"],
        "renderSegmentCount": plan_body["renderSegmentCount"],
        "renditions": plan_body["renditions"],
        "actions": plan_body["actions"],
    }
    return certificate, plan, authorization, checkpoint_frontier_bytes


def render_plan_toml(plan: Mapping[str, Any]) -> bytes:
    """Render the intentionally small supplied-plan TOML deterministically."""

    def quoted(value: str) -> str:
        return json.dumps(value, ensure_ascii=False)

    lines = [
        f"schema = {quoted(str(plan['schema']))}",
        f"profile_id = {quoted(str(plan['profileId']))}",
        f"decision = {quoted(str(plan['decision']))}",
        f"enabled = {'true' if plan['enabled'] else 'false'}",
        f"certificate_core_sha256 = {quoted(str(plan['certificateCoreSha256']))}",
        f"certificate_sha256 = {quoted(str(plan['certificateSha256']))}",
        f"key_id = {quoted(str(plan['keyId']))}",
        f"generation = {int(plan['generation'])}",
        f"key_uri = {quoted(str(plan['keyUri']))}",
        f"spki_sha256 = {quoted(str(plan['spkiSha256']))}",
        f"iv_hex = {quoted(str(plan['ivHex']))}",
        f"render_segment_count = {int(plan['renderSegmentCount'])}",
    ]
    rendered_renditions = ", ".join(quoted(item) for item in plan["renditions"])
    lines.append(f"renditions = [{rendered_renditions}]")
    for action in plan["actions"]:
        lines.extend(
            (
                "[[actions]]",
                f"rendition = {quoted(str(action['rendition']))}",
                f"action = {quoted(str(action['action']))}",
            )
        )
    return ("\n".join(lines) + "\n").encode("utf-8")


def pkcs7_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    if len(key) != 16 or len(iv) != 16:
        raise ContractError("AES-128-CBC key and IV must each be 16 bytes")
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return encryptor.update(padded) + encryptor.finalize()


def load_media_tree(root: "Any") -> dict[str, bytes]:
    """Load a materialized media directory without following paths outside it."""

    from pathlib import Path

    base = Path(root).resolve()
    result: dict[str, bytes] = {}
    for path in sorted(base.rglob("*")):
        if path.is_file():
            resolved = path.resolve()
            try:
                relative = resolved.relative_to(base)
            except ValueError as exc:
                raise ContractError("media tree contains an escaping path") from exc
            result[relative.as_posix()] = resolved.read_bytes()
    return result


def derive_all(
    *,
    profile: Mapping[str, Any],
    trust: Mapping[str, Any],
    registry_records: Mapping[str, bytes],
    catalog: Mapping[str, Any],
    guardian_trust: Mapping[str, Any],
    rollout_ledger: Mapping[str, Any],
    media: Mapping[str, bytes],
    profile_bytes: bytes,
    trust_bytes: bytes,
    registry_bytes: bytes,
    catalog_bytes: bytes,
) -> dict[str, Any]:
    """Convenience entry point used by authoring parity and hidden-world tests."""

    custody, ring = build_custody(
        profile,
        trust,
        registry_records,
        profile_bytes=profile_bytes,
        registry_bytes=registry_bytes,
        trust_bytes=trust_bytes,
    )
    custody_data = artifact_bytes(custody)
    evidence = build_evidence(
        profile,
        trust,
        catalog,
        media,
        ring,
        custody_bytes=custody_data,
        expected_custody=custody,
        catalog_bytes=catalog_bytes,
    )
    evidence_data = artifact_bytes(evidence)
    certificate, plan, authorization, checkpoint_frontier_bytes = build_authorization(
        profile,
        ring,
        guardian_trust=guardian_trust,
        rollout_ledger=rollout_ledger,
        custody_bytes=custody_data,
        evidence_bytes=evidence_data,
        expected_custody=custody,
        expected_evidence=evidence,
    )
    return {
        "custody": custody,
        "evidence": evidence,
        "authorization": authorization,
        "checkpointFrontierBytes": checkpoint_frontier_bytes,
        "certificate": certificate,
        "plan": plan,
        "planToml": render_plan_toml(plan),
        "ring": ring,
    }
