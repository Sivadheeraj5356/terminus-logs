# Route seal and abort ticket

After assemble finishes, two optional scratch files describe the outcome for
offline CLI checks. Paths are under /app/hint-scratch/{session_id}/.

## abort.json (assemble refused)

When assemble refuses (digest mismatch or missing snapshot), it must write
abort.json and must not write assemble_ack.json or route-seal.json.

Fields:

- session_id: session identifier
- gather_seq: gather_seq from the staged candidates.json when present, otherwise 0
- reason: same refusal reason string returned in the HTTP body
- abort_digest: lowercase hex SHA-256 of the UTF-8 string
  session_id + ":" + gather_seq + ":" + reason
  where gather_seq is decimal with no spaces

A later successful assemble must delete abort.json before writing ack and route seal.

## route-seal.json and assemble_ack.json (assemble succeeded)

On success, assemble writes assemble_ack.json and route-seal.json and deletes
any prior abort.json.

assemble_ack.json fields:

- session_id
- gather_seq (from the staged snapshot)
- assembled_at (RFC3339 UTC clock string)
- hints: the sorted hint objects that were returned (kind, verb, target)
- route_digest: digest defined below

route-seal.json fields:

- session_id
- gather_seq
- hint_count: length of the hints array
- candidate_digest: copy of candidate_digest from the staged candidates.json
- route_digest: same value as in assemble_ack.json

## route_digest

Serialize each returned hint as kind + ":" + verb + ":" + target on its own
line, in the same order the hints array is returned (kind rank move, then
action, then take; then verb ascending; then target ascending). Join lines
with a single newline and no trailing newline when the list is empty. Take
the lowercase hex SHA-256 of those UTF-8 bytes.

HTTP GET /sessions/{id}/oracle and POST /sessions/{id}/assemble include
route_digest in the JSON body when refused is not true.

## CLI check

labyrinth-oracle check --session-dir DIR --mode MODE

DIR is a session scratch directory such as /app/hint-scratch/{session_id}.
MODE is one of digest, route, or abort.

digest: recompute candidate_digest from candidates.json and exit 0 only when
it equals the stored candidate_digest.

route: recompute route_digest from assemble_ack.json hints and exit 0 only when
it equals both assemble_ack.route_digest and route-seal.route_digest, and
route-seal.gather_seq equals assemble_ack.gather_seq.

abort: when abort.json is absent, exit 0. When present, exit 0 only when
abort_digest matches the recomputed value from session_id, gather_seq, and
reason.
