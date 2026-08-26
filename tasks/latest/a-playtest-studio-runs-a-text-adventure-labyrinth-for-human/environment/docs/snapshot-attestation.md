# Snapshot attestation

The hint snapshot at /app/hint-scratch/{session_id}/candidates.json carries
three hex-encoded SHA-256 digests. This document defines exactly how each
one must be computed, so that a reference implementation outside the Go
binary can recompute the same values.

## candidates.json fields

session_id, room, and world_id echo the session's identity and current
position at the moment probe ran.

gather_seq is the session's gather counter. It starts at 0 for a brand
new session and is incremented by exactly one every time probe writes a
snapshot for that session, regardless of whether the candidate list
changed.

chronicle_sha256, session_state_sha256, and candidate_digest are the three
digests described below.

candidates is the array of raw candidate objects described in
/app/docs/probe-assemble-pipeline.md.

## chronicle_sha256

The SHA-256 digest, as a lowercase hex string drawn from the alphabet
0123456789abcdef, of the raw bytes of the
chronicle file that the session's world_id resolves to (see
/app/docs/world-schema.md). No decoding, re-encoding, or line-ending
normalization is applied; the digest is over the file's bytes exactly as
they exist on disk.

## session_state_sha256

Build a JSON object with exactly five keys, in exactly this order:
world_id, room, inventory, consumed, failed.

world_id and room are the session's current values, unchanged.

inventory is the session's held item ids, sorted ascending as plain
strings.

consumed is the session's consumed target strings, sorted ascending as
plain strings.

failed is the session's failed attempts, each rendered as a JSON object
with exactly two keys verb and target, and the whole array sorted
ascending first by verb then by target.

Serialize that five-key object to JSON using compact separators (no space
after a colon or comma) and do not reorder its top-level keys
alphabetically or any other way: the on-the-wire key order must be
exactly world_id, room, inventory, consumed, failed. Take the SHA-256
digest of the resulting bytes and hex-encode it.

## candidate_digest

Take the exact candidates array staged in this snapshot. Serialize it to
JSON using compact separators (no space after a colon or comma) with
every object's keys sorted alphabetically (kind, order_seq, required_items
then target then verb once sorted; the point is alphabetical key order
within each object, not a fixed field list). Take the SHA-256 digest of
the resulting bytes and hex-encode it.

Because this digest is computed over the candidates array exactly as
staged, assemble recomputes it the same way from the array it reads back
out of candidates.json, and the two must match unless the staged file was
altered after probe wrote it.

## Refusal on mismatch

Assemble recomputes chronicle_sha256 and session_state_sha256 against the
session's current state and chronicle resolution, and candidate_digest
against the staged candidates array itself. Any mismatch against the
recorded values in candidates.json causes assemble to refuse: no
assemble_ack.json or route-seal.json is written, abort.json is written per
/app/docs/route-abort-contract.md, and the response reports an empty hints
array with refused true and a reason field.
