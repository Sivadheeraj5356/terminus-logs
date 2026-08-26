# MLflow Maze Recovery Contract

## Published commands

`/app/mlflow-maze/bin/maze-recover recover` accepts each of these options exactly
once, in any order:

```
--tracking-db ABSOLUTE_PATH
--maze-yaml ABSOLUTE_PATH
--puzzles-toml ABSOLUTE_PATH
--output ABSOLUTE_PATH
```

`/app/mlflow-maze/bin/maze-recover replay --manifest ABSOLUTE_PATH` validates and
replays a published manifest. Relative paths, missing or repeated options,
unknown options, extra arguments, and an output path equal to an input path are
invocation errors. Recovery exits 0 on publication, 2 for invocation or syntax
errors, 3 for an inconsistent eligible tracking record, 4 when no complete
solvable level can be selected, and 5 for filesystem or publication errors.
Replay exits 0 only for an internally consistent manifest and 2 otherwise.

Recovery is transactional at the filesystem boundary. It may create temporary
files beside the output, but it replaces `--output` only after every input,
tracking, graph, schema, replay, and digest check succeeds. Every nonzero exit
leaves a file already present at that path byte-for-byte unchanged and removes
its temporary files. The three inputs are never modified. The SQLite store is
opened read-only. Core parsing or database work must not be delegated to
`mlflow`, `sqlite3`, Python, YAML/TOML utilities, or shell commands.

The wrapper `/app/mlflow-maze/scripts/recover-and-replay.sh` takes zero or four
arguments. With no arguments it uses the published tracking store, YAML, TOML,
and `/app/mlflow-maze/out/level-manifest.json`. Four arguments replace those
paths in that order and must be absolute. It runs recovery, validates the result
against `/app/mlflow-maze/schema/level-manifest.schema.json`, and then runs
replay. A failed stage returns nonzero.

## Damaged configuration

The YAML root is a mapping with `format`, `level_id`, `experiment_name`,
`start_room`, `goal_room`, `direction_order`, and `rooms`. Its format is
`mlflow-maze-board-v1`. Identifiers match `[A-Za-z0-9][A-Za-z0-9._-]{0,63}`.
`direction_order` contains each of `north`, `east`, `south`, and `west` exactly
once; this order controls exits and path tie-breaking. `rooms` is a sequence of
unique mappings. A room has an `id`, and may have a string or null `title`, a
string or null `prompt_id`, and an `exits` mapping. Exit values are room IDs or
null. Mapping key order and ordinary YAML quoting do not affect meaning.

The TOML file begins with `format = "mlflow-maze-puzzles-v1"`. Puzzle sections
have the form `[puzzle.ID]` and may contain `prompt` and `answer_sha256` basic
string values. Basic escapes for quote, backslash, newline, carriage return, and
tab have their TOML meanings. Duplicate root keys, sections, or section keys are
invalid. Missing room and puzzle values are expected damage, not syntax errors.

## Eligible MLflow records

The tracking schema is documented in `MLFLOW_STORE.md`. Exactly one active
experiment must have the YAML `experiment_name`. Only its active, `FINISHED`
runs whose `maze.level_id` tag equals the YAML level are eligible. Other
experiments, deleted runs, non-finished runs, and runs tagged for another level
are ignored completely.

Every eligible run is one patch record and must contain exactly one of each
required tag: `maze.level_id`, `maze.record_kind`, `maze.target_id`, and
`maze.patch_sha256`. `maze.record_kind` is `room` or `puzzle`. An optional
`maze.parent_run_id` is either absent or nonempty. It also has exactly one
`maze.revision` parameter containing a strict decimal integer from 1 through
2147483647. Patch parameters are named `maze.patch.000`, `maze.patch.001`, and
so on. They must start at 000, have no duplicate or missing index, and are
concatenated as stored, without separators. At least one chunk is required.
The lowercase SHA-256 of those concatenated UTF-8 bytes must equal the patch tag.

For each run, the authoritative `maze.commit` metric is the row with greatest
timestamp and then greatest SQLite rowid. Its step must equal the revision and
its finite value must be exactly 1. Earlier metric history is not authoritative.
An eligible run with missing, duplicate, malformed, or contradictory metadata,
an invalid patch, or a noncommitted latest metric makes the whole recovery fail
with exit 3; it is not silently skipped.

A revision-1 run has no parent. Every later run names an eligible parent of the
same kind and target at exactly the preceding revision. Parent cycles, missing
parents, cross-target parents, and revision gaps are inconsistent records.
Every run is a possible chain tip, so a later branch may be rejected without
discarding its valid ancestor.

## Recovery selection

The YAML rooms and TOML puzzles form revision zero. Selecting a run tip applies
its complete root-to-tip patch chain in revision order. Patches are JSON objects
with RFC 7396 merge-patch behavior. Room patches may contain only `title`,
`prompt_id`, and `exits`; puzzle patches may contain only `prompt` and
`answer_sha256`. An `exits` patch merges individual directions, and null removes
the named value. A selected patch may introduce a room or puzzle absent from the
damaged configuration. It may not change an entity ID.

One candidate, including revision zero, is selected independently for every
kind/target that has tracking history, but the winning set is chosen globally.
A set is feasible only when the resulting level satisfies all final game rules.
Among feasible sets, maximize the sum of selected tip revisions, then maximize
the sum of their authoritative commit timestamps. If still tied, compare the
tip run IDs in `(kind, target_id)` byte order and choose the lexicographically
smallest vector; revision-zero contributes an empty string. This rule can select
a less preferred local branch when newer choices conflict elsewhere.

In the final level every room has a nonempty title. Every non-null exit direction
appears in `direction_order` and names a room. Every non-null `prompt_id` names a
puzzle with a nonempty prompt and a 64-character lowercase hexadecimal answer
SHA-256. All room and puzzle identifiers remain unique. Every room must be
reachable from `start_room`, every room must be able to reach `goal_room`, and
the goal must be reachable. Otherwise that candidate set is infeasible.

## Walkthrough and manifest

The walkthrough is the minimum-move path from start to goal. Breadth-first ties
are resolved by `direction_order`; room or run lexical order is not a tie-break.
Its `rooms` array includes both endpoints, and `moves[i]` traverses from
`rooms[i]` to `rooms[i+1]`.

The transcript is an array of ASCII lines. It starts with `enter 0 ROOM`. On
entering a room with a prompt, append `prompt STEP ID ANSWER_SHA256`. For each
move, append `move STEP DIRECTION FROM TO`, then `enter STEP TO`, then that
room's prompt line if any. STEP is the destination's zero-based path index.
Finally append `goal STEP ROOM`. The transcript digest is lowercase SHA-256 over
each line followed by one LF byte, including the final line.

The output is one compact UTF-8 JSON object followed by LF. Object keys are
recursively sorted by byte value. Rooms are sorted by ID. Each room's exits are
listed in `direction_order`. Selected-run provenance is sorted by kind, target,
then revision and contains every run in each selected chain. No unselected run
appears. The exact shape is constrained by the supplied JSON Schema. Source
digests are lowercase SHA-256 of the input files as read.

Replay reconstructs transitions from the manifest, checks the walkthrough,
transcript, and digest, then writes each transcript line followed by
`sha256 DIGEST`, all with LF endings. It produces no output for an invalid
manifest.
