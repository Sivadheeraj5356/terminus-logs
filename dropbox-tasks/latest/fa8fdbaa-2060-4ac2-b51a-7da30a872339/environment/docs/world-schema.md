# World schema

Every world the oracle can load is described by one world.json file plus
one chronicle markdown file.

## world.json layout

world.json is a single JSON object with five top-level keys:

world_id is the string identifier of the world, for example labyrinth or
catacombs.

start_room is the room id a brand new session begins in.

rooms is an array of objects, each with an id string and a title string.

exits is an array of objects, each with an id string, a from room id, a to
room id, a verb string, and a required_items array of item id strings. An
exit with an empty required_items array is always usable once its from
room is reached.

items is an array of objects, each with an id string (the item's own name,
for example lantern or brass-key) and a room_id string naming the room the
item is seeded in.

actions is an array of objects, each with an id string, a room_id string,
a verb string, a target string, and a required_items array of item id
strings.

## On-disk order versus gather order

The exits, items, and actions arrays are written to world.json in
descending order of their own id field. This is an authoring convention
only. Any code that reads a world's exits, items, or actions for a given
room must sort by id ascending before treating the result as an ordered
sequence; relying on array position as written is not a valid substitute
for that sort. The oracle's per-room gather order documented in
/app/docs/probe-assemble-pipeline.md is defined in terms of this ascending
sort, not on-disk order.

## Chronicle path per world

Each world_id resolves to exactly one chronicle markdown file, described
in /app/docs/rules-format.md. The labyrinth world (and the default empty
world_id) resolves to the chronicle bundled at /app/docs/gm-chronicle.md.
Every other world_id resolves to a chronicle.md file that ships alongside
that world's own world.json.

## World locations

The labyrinth world ships inside the image at
/app/data/worlds/labyrinth/world.json. Other worlds are not bundled with
the agent image; a session created against an unbundled world_id will
only succeed once that world's fixtures are present on disk at
/opt/verifier-fixtures/worlds/{world_id}/world.json alongside
/opt/verifier-fixtures/worlds/{world_id}/chronicle.md.
