# Portfall Operations Manual

Portfall is a terminal puzzle about moving through stacked shipping containers in a storm-damaged freight yard. A transcript is a chronological record of player commands. The adjudicator replays that transcript against a container layout and emits canonical adjudication data for the game master.

## Inputs

The container specification has a `startContainer` and a `containers` array. Containers use canonical ids and include layout, seal, hazard, connection, stack, and optional entry-requirement metadata. Specs may also provide command aliases for containers, seals, and hazards. Aliases are accepted in transcript commands, but output state is recorded with canonical ids.

Transcripts are line-oriented. Blank lines and comment lines are ignored. Repeat blocks use `repeat N {` and a closing `}` on their own lines. Repeat blocks expand before adjudication, including nested blocks, and the expanded inner commands keep their own command text in output records.

## Commands

The supported commands are `move`, `inspect`, `unlock`, `break-seal`, `scan`, `secure`, `reroute`, `pathfind`, `beacon`, and `recall`. Commands that target containers use canonical ids or container aliases. `secure <room>` marks the named current room or a directly connected reachable room for the next legal entry; `secure` without a room argument is malformed, and `secure <room>` for any other room is rejected with `not reachable`. `recall <room>` consumes a previously placed beacon at the named room as a one-use direct movement; `recall` without a room argument is malformed, and `recall <room>` without a beacon at that room is rejected with `beacon absent`. Unknown or malformed commands are rejected without changing game state. Rejected actions must preserve the command text and use the stable reasons `unknown command`, `no connection`, `no path`, `not reachable`, `route not anchored`, `beacon absent`, `entry blocked`, `seal not present`, or `seal not unlocked`.

Movement commands update room state, transition records, first-visit ordering, hazards, stack movement, and any one-use route/brace/beacon state. Pathfinding follows available directed routes, including temporary routes, and must respect entry requirements while computing and applying the path; when shortest paths tie, choose the lexicographically earliest next room at each search step. Recall uses a previously placed beacon as a one-use direct movement. Beacon placement is accepted only for the current room or a directly connected reachable room. Reroute uses `reroute <from> <to>` and creates a one-use directed connection only when `<from>` is the current room and `<to>` is a known room.

Seal commands operate only on seals attached to the current room. A scan stores one active hazard id, replacing any earlier scan, and suppresses the next matching hazard when a room is entered. A hazard is recorded at most once for a given room, so re-entering a room does not add duplicate hazard entries for hazards already triggered there. Securing a room suppresses hazards for the next legal entry into that room. Ventilated rooms do not trigger their listed hazards. Entry requirements can depend on prior canonical room visits and prior canonical broken seals.

## Scoring And Canonical Output

Scores are deterministic and are derived from distinct rooms visited, distinct seals broken, triggered hazards, legal stack moves, consumed braces, consumed temporary routes, and consumed recall beacons. Use `+10` per distinct visited room, `+25` per distinct broken seal, `-15` per triggered room hazard, `-5` per legal stack move, `+7` per consumed secure brace, `+4` per consumed temporary route, and `+6` per consumed recall beacon. The score breakdown keys are `roomsVisited`, `sealsBroken`, `hazardPenalty`, `stackMovePenalty`, `securedRooms`, `temporaryRoutesUsed`, and `beaconsUsed`; zero-valued score components are omitted. Output arrays preserve adjudication order; object key order is not semantically significant.

The result schema for a single transcript is defined in `/app/src/types.ts`. Public transcript/golden pairs under `/app/transcripts` and `/app/golden/adjudications` show representative canonical output.

## League Summary

`summarizePortfallLeague(containerSpec, transcripts)` takes a container spec and a `Record<string, Transcript>` keyed by player name. It adjudicates each named transcript independently from a fresh starting state, returns each case under the same player name, ranks players by higher score, then fewer rejected actions, then lexicographic player name, and reports aggregate room/hazard/seal totals. Ranking and aggregate shapes are defined by the TypeScript schema.

## Audit Pack Files

`writePortfallAuditPack(containerSpec, transcriptFiles, outputDir)` takes `transcriptFiles` as a `Record<string, string>` keyed by player name with filesystem paths as values. It reads those named transcript files, builds the same league summary, writes deterministic case, leaderboard, hazard, and manifest artifacts below `outputDir`, and returns the manifest object. It writes one canonical JSON file per player under `cases/<player>.json`, a CSV file named `leaderboard.csv`, a JSON file named `hazards.json`, and `manifest.json`. `hazards.json` has exactly two top-level keys: `byPlayer`, mapping each player name to that player's ordered `hazardsTriggered` list, and `uniqueHazardsTriggered`, the sorted unique hazard ids across the league. The manifest `artifacts` list is sorted alphabetically by relative path and includes `manifest.json` itself. The leaderboard CSV header is `rank,player,score,finalRoom,brokenSeals,rejectedActions`. Artifact paths are relative to the output directory, generated data is canonicalized, and digests are SHA256 values over the generated artifact bytes.
