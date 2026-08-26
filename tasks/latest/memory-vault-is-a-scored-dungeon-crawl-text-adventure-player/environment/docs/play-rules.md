# Memory Vault play rules

This is a scored dungeon crawl. Players explore rooms, manage inventory,
seal watched chambers, scrub leak chambers, and EXIT the vault with the key.

## Map

Directed edges: atrium→buffer→heap→canary, heap→leak, canary→vault,
leak→mirror→buffer. Playthroughs begin in `atrium` with an empty inventory.
`visited` always starts with `atrium` and appends each successful room entry
in order (revisits are recorded). `path_summary.unique_rooms` is the count of
distinct rooms in `visited`.

## Chamber ledgers

Watched rooms come from `/app/environment/traces/watch-chambers.log`. Later
primed watch markers for a room override earlier ones. Structured watch rows
and prose watch notes both count; field order on a structured row may vary.
Leak rooms come from `/app/environment/traces/scrub-chambers.txt` wherever
`room=<name> requires=scrub` appears, including inside markup snippets.
Ignore `requires=none`. Notes under `/app/environment/policy/` are not
in-game inputs and must not blank hazards.

Hazard generation is computed once at campaign start from the live ledger
bytes and bound into the epoch file, save-log `GEN` record, transcripts, and
manifest. Every adventure in the campaign shares that generation.

## Commands

MOVE, TAKE, DROP, WAIT, SEAL, SCRUB, and EXIT are the gameplay verbs.
Illegal moves stay put and record an invalid-room violation. Entering an
unsealed watched room is refused: record a watch violation and stay put.
Items are room-gated. Seal readiness is earned only by waiting in the buffer
while holding the patch. Scrubbing a leak requires standing in that leak room
with the torch. The first EXIT ends the adventure: unpaid leak visits become
leak violations, and standing in the vault without the key adds an exit-key
violation. Later commands after EXIT are ignored for both state and the save
log.

## Outcomes

WIN requires a processed EXIT in the vault while holding the key with no
violations. LOSE applies when any watch violation exists or total violations
exceed two. Otherwise PARTIAL. Score is
`100 - moves*2 - violations*17` plus status bonus WIN 25 / PARTIAL 5 /
LOSE -20. `moves` counts filtered command lines up to and including the first
EXIT only.

Transcripts include case id, status, score, moves, visited, lexically sorted
inventory, violations in play order, a 16-hex `trace_hash` bound to the case
and hazard sets, `path_summary`, and the campaign `generation`. Inventory,
seals, scrub flags, readiness, visited rooms, and violations stay isolated
per adventure.
