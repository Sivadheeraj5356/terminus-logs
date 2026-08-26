# Playtest oracle workflow

The labyrinth-oracle is a hint engine for human playtesters exploring a
text-adventure world. A playtester's client creates a session against a
world, then repeatedly asks the oracle what to try next and applies
attempts against the session as the playtester moves through rooms,
gathers items, and performs room actions.

## Session lifecycle

POST /sessions creates a session. GET /sessions/{id}/oracle returns sorted
hints for the current room. POST /sessions/{id}/attempt applies a verb and
target. Successful move, take, and action attempts update room, inventory,
or consumed state as described in /app/docs/oracle-contract.md.

## Staged probe and assemble

Forbidden chronicle rules and live session state can diverge between hint
gathering and delivery, so the oracle stages candidates.json first and then
assembles only after attestation checks pass. See
/app/docs/probe-assemble-pipeline.md, /app/docs/snapshot-attestation.md, and
/app/docs/route-abort-contract.md.

## Chronicles as the source of forbidden actions

A world's chronicle is authored as narrative prose with forbidden-rule lines
embedded in that prose (/app/docs/rules-format.md). The chronicle is the
authority for which actions a world disallows; the oracle must honor every
rule it contains for the session's world_id.
