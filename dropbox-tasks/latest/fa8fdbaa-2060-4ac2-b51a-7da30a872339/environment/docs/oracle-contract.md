# Oracle HTTP contract

The labyrinth-oracle binary serves the following endpoints once started
with labyrinth-oracle serve --addr host:port.

## GET /health

Returns 200 with a JSON object containing a status field set to ok. Used
by playtest tooling to confirm the process is accepting connections.

## POST /sessions

Creates a new playtest session. The request body is a JSON object with an
optional world_id string (defaults to labyrinth), an optional room_id
string (defaults to that world's start_room), and an optional inventory
array of item id strings (defaults to empty).

Returns 201 with a JSON object containing session_id, world_id, room,
inventory, consumed, and failed. consumed and failed are both empty
arrays for a freshly created session.

Returns 400 if world_id names a world with no reachable world.json (for
example the sentinel value nonexistent-world used by clients probing for
missing fixtures), or if room_id names a room that does not exist in that
world.

Unknown session identifiers such as /sessions/does-not-exist/oracle return
404 from every session-scoped route.

## GET /sessions/{id}/oracle

Runs the full two-stage hint pipeline for a session in one call: it stages
a fresh probe snapshot for the session's current room (see
/app/docs/probe-assemble-pipeline.md) and immediately assembles it into
hints.

Returns 200 with a JSON object containing session_id, room, hints, and
when assembly succeeds route_digest from /app/docs/route-abort-contract.md.
When assembly refuses, refused is true, reason names the refusal cause, and
route_digest is omitted. hints is an array of objects, each with kind,
verb, and target.

## POST /sessions/{id}/probe and POST /sessions/{id}/assemble

Expose the two pipeline stages independently: probe stages a fresh
candidates.json snapshot without assembling hints, and assemble re-verifies
whatever snapshot is currently staged and assembles it into hints without
re-probing first. See /app/docs/probe-assemble-pipeline.md,
/app/docs/snapshot-attestation.md, and /app/docs/route-abort-contract.md for
what each stage writes and checks.

## CLI check

labyrinth-oracle check --session-dir DIR --mode MODE verifies staged scratch
artifacts for digest, route, or abort modes as defined in
/app/docs/route-abort-contract.md. Exit status 0 means the selected check
passed; any other status means it failed.

## POST /sessions/{id}/attempt

Applies one verb/target attempt against a session's current room: taking
an item, moving through an exit, or performing a room action. The request
body is a JSON object with verb and target strings.

An attempt succeeds only if its verb/target trio matches something
physically present in the current room, every item that trio requires is
already held, and no chronicle @RULE forbidden line (see
/app/docs/rules-format.md) matches the room, verb, and target. On success
the session's room, inventory, or consumed set updates accordingly. On
failure the attempt is recorded in the session's failed list and no state
otherwise changes.

Returns 200 with a JSON object containing session_id, room, inventory,
consumed, failed, ok (a boolean), and reason (present and non-empty only
when ok is false).

## Hint validity and sort order

A hint is only included in an oracle or assemble response when every item
in its required_items is currently held, its target has not already been
consumed (for action and move kinds) or already taken (for take kind),
and no chronicle forbidden rule matches its room, verb, and target.

Hints are sorted first by kind, with move ranked before action ranked
before take, then by verb ascending, then by target ascending. This order
is deterministic for a given staged candidate set and session state.
