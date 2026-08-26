#!/usr/bin/env python3
"""Gateway sanitizer. Several normalization and audit bugs remain in this version."""

import argparse
import hashlib
import json
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def clean_string(value):
    value = unicodedata.normalize("NFKC", value)
    return "".join(character for character in value if ord(character) >= 32)


def sanitize_payload(value, policy):
    if isinstance(value, str):
        return clean_string(value)
    if isinstance(value, list):
        return [sanitize_payload(item, policy) for item in value]
    if not isinstance(value, dict):
        return value

    blocked = {item.lower() for item in policy["blocked_keys"]}
    url_keys = {item.lower() for item in policy["url_keys"]}
    allowed = {item.lower() for item in policy["allowed_schemes"]}
    result = {}
    for key, item in value.items():
        normalized_key = unicodedata.normalize("NFKC", key)
        folded_key = normalized_key.lower()
        if folded_key in blocked or normalized_key.startswith("$"):
            continue
        cleaned = sanitize_payload(item, policy)
        if folded_key in url_keys and isinstance(cleaned, str):
            parsed = urlsplit(cleaned)
            if parsed.scheme and parsed.scheme.lower() not in allowed:
                cleaned = None
        result[normalized_key] = cleaned
    return result


def process(input_path, output_path, rejected_path, policy_path):
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    accepted = []
    rejected = []
    for line_number, line in enumerate(input_path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            envelope = json.loads(line)
        except json.JSONDecodeError:
            rejected.append({"line": line_number, "reason": "invalid_json"})
            continue

        if not isinstance(envelope, dict) or set(envelope) != {"id", "payload"}:
            rejected.append({"line": line_number, "reason": "invalid_envelope"})
            continue
        payload = sanitize_payload(envelope["payload"], policy)
        material = canonical_json({"id": envelope["id"], "payload": payload}).encode()
        accepted.append({"digest": hashlib.sha256(material).hexdigest(), "id": envelope["id"], "payload": payload})

    output_path.write_text("".join(canonical_json(row) + "\n" for row in accepted), encoding="utf-8")
    rejected_path.write_text("".join(canonical_json(row) + "\n" for row in rejected), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="/app/input.jsonl")
    parser.add_argument("--output", default="/app/output.jsonl")
    parser.add_argument("--rejected", default="/app/rejected.jsonl")
    parser.add_argument("--policy", default="/app/policy.json")
    args = parser.parse_args()
    process(Path(args.input), Path(args.output), Path(args.rejected), Path(args.policy))


if __name__ == "__main__":
    main()
