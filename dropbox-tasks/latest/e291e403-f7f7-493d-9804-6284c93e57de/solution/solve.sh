#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
mkdir -p "$APP_DIR"

python3 - "$APP_DIR" <<'PY'
import sys
from pathlib import Path


app_dir = Path(sys.argv[1])
source = r'''#!/usr/bin/env python3
import argparse
import hashlib
import html
import json
import sqlite3
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit


BIDI_CONTROLS = {
    "\u061c",
    "\u200e",
    "\u200f",
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2066",
    "\u2067",
    "\u2068",
    "\u2069",
}


class DuplicateKey(ValueError):
    pass


def normalize_key(value):
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(
        character
        for character in normalized
        if not (ord(character) <= 0x1F or 0x7F <= ord(character) <= 0x9F)
        and character not in BIDI_CONTROLS
    )


def key_identity(value):
    return normalize_key(value).casefold()


def checked_object(pairs):
    result = {}
    seen = set()
    for key, value in pairs:
        identity = key_identity(key)
        if identity in seen:
            raise DuplicateKey(identity)
        seen.add(identity)
        result[normalize_key(key)] = value
    return result


def reject_constant(value):
    raise ValueError(f"non-RFC constant: {value}")


def load_untrusted(line):
    return json.loads(
        line,
        object_pairs_hook=checked_object,
        parse_constant=reject_constant,
    )


def canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def clean_string(value):
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(
        character
        for character in normalized
        if not (ord(character) <= 0x1F or 0x7F <= ord(character) <= 0x9F)
        and character not in BIDI_CONTROLS
    )


def url_probe(value):
    probe = unicodedata.normalize("NFKC", value)
    while True:
        decoded = unicodedata.normalize("NFKC", html.unescape(unquote(probe)))
        if decoded == probe:
            break
        probe = decoded
    return "".join(character for character in probe if not character.isspace())


def safe_url(value, allowed_schemes):
    try:
        probe = url_probe(value)
        if probe.startswith("//"):
            return False
        parsed = urlsplit(probe)
        if not parsed.scheme and not parsed.netloc:
            return True
        return parsed.scheme.casefold() in allowed_schemes and bool(parsed.netloc)
    except (TypeError, ValueError, UnicodeError):
        return False


def sanitize(value, policy, parent_key=None):
    if isinstance(value, str):
        cleaned = clean_string(value)
        if parent_key in policy["url_keys"] and not safe_url(cleaned, policy["allowed_schemes"]):
            return None
        return cleaned
    if isinstance(value, list):
        return [sanitize(item, policy) for item in value]
    if not isinstance(value, dict):
        return value

    result = {}
    for key, item in value.items():
        normalized_key = normalize_key(key)
        identity = normalized_key.casefold()
        if normalized_key.startswith("$") or identity in policy["blocked_keys"]:
            continue
        result[normalized_key] = sanitize(item, policy, identity)
    return result


def load_policy(path):
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        "blocked_keys": {key_identity(value) for value in raw["blocked_keys"]},
        "url_keys": {key_identity(value) for value in raw["url_keys"]},
        "allowed_schemes": {
            unicodedata.normalize("NFKC", value).casefold()
            for value in raw["allowed_schemes"]
        },
    }


def initialize_audit_db(path):
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE security_events (
            line INTEGER,
            event_id TEXT,
            decision TEXT,
            reason TEXT,
            digest TEXT
        )
        """
    )
    return connection


def log_audit(connection, line_number, event_id, decision, reason, digest):
    connection.execute(
        """
        INSERT INTO security_events (line, event_id, decision, reason, digest)
        VALUES (?, ?, ?, ?, ?)
        """,
        (line_number, event_id, decision, reason, digest),
    )


def process(input_path, output_path, rejected_path, policy_path, audit_db_path):
    policy = load_policy(policy_path)
    previous_digest = bytes(32)

    with initialize_audit_db(audit_db_path) as audit_connection:
        with (
            input_path.open("r", encoding="utf-8") as source,
            output_path.open("w", encoding="utf-8") as accepted,
            rejected_path.open("w", encoding="utf-8") as rejected,
        ):
            for line_number, line in enumerate(source, 1):
                try:
                    envelope = load_untrusted(line)
                except DuplicateKey:
                    rejected.write(canonical_json({"line": line_number, "reason": "duplicate_key"}) + "\n")
                    log_audit(audit_connection, line_number, None, "rejected", "duplicate_key", None)
                    continue
                except (json.JSONDecodeError, ValueError, UnicodeError):
                    rejected.write(canonical_json({"line": line_number, "reason": "invalid_json"}) + "\n")
                    log_audit(audit_connection, line_number, None, "rejected", "invalid_json", None)
                    continue

                if (
                    not isinstance(envelope, dict)
                    or set(envelope) != {"id", "payload"}
                    or not isinstance(envelope["id"], str)
                    or not envelope["id"]
                ):
                    rejected.write(canonical_json({"line": line_number, "reason": "invalid_envelope"}) + "\n")
                    log_audit(audit_connection, line_number, None, "rejected", "invalid_envelope", None)
                    continue

                event_id = clean_string(envelope["id"])
                if not event_id:
                    rejected.write(canonical_json({"line": line_number, "reason": "invalid_envelope"}) + "\n")
                    log_audit(audit_connection, line_number, None, "rejected", "invalid_envelope", None)
                    continue

                payload = sanitize(envelope["payload"], policy)
                material = canonical_json({"id": event_id, "payload": payload}).encode("utf-8")
                digest_bytes = hashlib.sha256(previous_digest + material).digest()
                previous_digest = digest_bytes
                digest = digest_bytes.hex()
                record = {
                    "digest": digest,
                    "id": event_id,
                    "payload": payload,
                }
                accepted.write(canonical_json(record) + "\n")
                log_audit(audit_connection, line_number, event_id, "accepted", None, digest)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="/app/input.jsonl")
    parser.add_argument("--output", default="/app/output.jsonl")
    parser.add_argument("--rejected", default="/app/rejected.jsonl")
    parser.add_argument("--policy", default="/app/policy.json")
    parser.add_argument("--audit-db", default="/app/security_audit.sqlite")
    args = parser.parse_args()
    process(
        Path(args.input),
        Path(args.output),
        Path(args.rejected),
        Path(args.policy),
        Path(args.audit_db),
    )


if __name__ == "__main__":
    main()
'''

engine = app_dir / "sanitizer.py"
engine.write_text(source, encoding="utf-8")
engine.chmod(0o755)
PY

if [[ "$APP_DIR" == "/app" ]]; then
    cd /app
    python3 /app/sanitizer.py
else
    python3 "$APP_DIR/sanitizer.py" \
        --input "$APP_DIR/input.jsonl" \
        --output "$APP_DIR/output.jsonl" \
        --rejected "$APP_DIR/rejected.jsonl" \
        --policy "$APP_DIR/policy.json" \
        --audit-db "$APP_DIR/security_audit.sqlite"
fi

test -f "$APP_DIR/output.jsonl"
test -f "$APP_DIR/rejected.jsonl"
test -f "$APP_DIR/security_audit.sqlite"
