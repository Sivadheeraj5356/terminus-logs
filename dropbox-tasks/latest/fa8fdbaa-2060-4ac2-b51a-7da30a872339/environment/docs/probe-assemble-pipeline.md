# Probe / assemble snapshot pipeline

Every hint response is produced by two stages that communicate only
through a file on disk, never through an in-process shortcut.

## Stage one: probe

Probe gathers every exit, action, and item physically present in the
session's current room, with no filtering by inventory, consumed state,
or chronicle forbidden rules. It orders candidates by walking exits
first, then actions, then items, sorting each category by its own id
ascending (see /app/docs/world-schema.md) before assigning each candidate
a strictly increasing order_seq starting at 1.

Each candidate is an object with kind (move, action, or take), verb,
target, required_items, and order_seq. A move candidate's verb and target
come from an exit's verb and to room. An action candidate's verb and
target come from the action's own verb and target. A take candidate has
verb take and a target equal to the item's id.

Probe then computes the session's attestation digests (see
/app/docs/snapshot-attestation.md) and writes the whole snapshot,
including those digests and the candidate list itself, to
/app/hint-scratch/{session_id}/candidates.json. Writing this file always
advances the session's gather_seq counter by one, even if the resulting
candidate list is identical to the previous probe.

## Stage two: assemble

Assemble reads whatever candidates.json is currently staged for the
session. It does not re-run probe. It recomputes three digests fresh from
current state, the staged candidate list, and the chronicle file the
session's world_id resolves to, and compares each against the value
recorded in the staged snapshot:

candidate_digest catches a candidates.json that was edited or replaced
after probe wrote it.

session_state_sha256 catches a session whose room, inventory, consumed,
or failed list changed after probe staged its snapshot (for example, an
attempt applied between the probe and assemble calls).

chronicle_sha256 catches a chronicle file that changed, or a chronicle
resolution that has begun pointing somewhere new, after probe staged its
snapshot.

If any of the three digests fail to match, assemble refuses: it returns an
empty hints array with refused set to true and a reason naming which
digest mismatched, and it does not write assemble_ack.json.

If all three match, assemble filters the staged candidates by current
inventory, consumed state, and the chronicle's forbidden rules, sorts the
surviving hints per /app/docs/oracle-contract.md, writes
/app/hint-scratch/{session_id}/assemble_ack.json and
/app/hint-scratch/{session_id}/route-seal.json per
/app/docs/route-abort-contract.md, deletes any prior abort.json, and returns
the sorted hints.

If any digest check fails, assemble writes abort.json instead (same document)
and returns refused without writing ack or route seal.

## Independent probe and assemble calls

Because probe and assemble only communicate through candidates.json, a
caller that invokes POST /sessions/{id}/probe and POST
/sessions/{id}/assemble as two separate calls (instead of the combined GET
/sessions/{id}/oracle) can inspect or mutate the session, or the staged
file itself, between the two stages and observe exactly which digest
assemble refuses on.
