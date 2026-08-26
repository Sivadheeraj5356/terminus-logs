A playtest studio runs a text-adventure labyrinth for human testers and
needs a hint oracle that lists every valid next action for a live session
state. Sessions track room, inventory, consumed targets, and failed
attempts. World geography lives in plain JSON files. Forbidden actions are
embedded as @RULE lines inside each world's game-master chronicle.

The working Go service at /app/bin/labyrinth-oracle already ships under /app with session
creation, world loading, attempt handling, and the HTTP surface. Operators
must implement the remaining playtest lanes documented under /app/docs so
that probe snapshots, hint assembly, attestation digests, multi-rule
chronicle parsing, inventory gates, route seals, abort tickets, and
per-world chronicle resolution all match the contracts for both the bundled
labyrinth world and reviewer-only worlds under /opt/verifier-fixtures/worlds.

Hint lists must be deterministic and identical for equivalent session
states. Candidate gather sequence is a hard invariant: exits, then actions,
then items, each ascending by id. Attestation digests are documented
SHA-256 hashes over fixed field order and compact JSON so an independent
reference can recompute them byte for byte.

Contracts live in /app/docs/oracle-contract.md (HTTP surface, CLI check,
hint validity, and sort order), /app/docs/world-schema.md (JSON layout,
ascending id gather order, and chronicle path selection),
/app/docs/rules-format.md (forbidden @RULE grammar),
/app/docs/probe-assemble-pipeline.md (probe then assemble),
/app/docs/snapshot-attestation.md (byte-exact digests and refusal),
/app/docs/route-abort-contract.md (route-seal.json, abort.json, and check
modes), and /app/docs/playtest-workflow.md (end-to-end client scenario).

There is no database: every world is a world.json file plus a markdown
chronicle read directly from disk.

Service sources live under /app/internal and /app/cmd. Probe stage output is
/app/hint-scratch/{session_id}/candidates.json. Successful assemble writes
/app/hint-scratch/{session_id}/assemble_ack.json and
/app/hint-scratch/{session_id}/route-seal.json. Refused assemble writes
/app/hint-scratch/{session_id}/abort.json. The package under
/app/internal/decoyguide is not on the oracle path.

Pytest boots the binary through tests/conftest.py, opens an ephemeral local
port with socket, drives HTTP with httpx, and recomputes SHA-256 digests with
Python hashlib via tests/verifier-support/labyrinth_verifier_refs.py and the
operator helper /app/scripts/sha256_hex.py.
