# Stage recovery / mending

Before trusting journal tips or parent tips, stage mending must run against `$STAGE_ROOT`.

Rules:

1. For each `journal/*.frames` file, if the file does not end with a newline, truncate the incomplete trailing line (bytes after the last newline). If there is no newline at all, truncate the file to empty.
2. After step 1, parse complete lines. Each line must match `GEN=<n>|BAND=...|BODY=...`. `GEN` values must be contiguous integers starting at 1. On the first gap or unparsable line, truncate that line and every later byte.
3. Cache files are left untouched by mending; wipe clears both planes.

The matrix driver invokes mending at emit start. A no-op mend leaves torn tails that poison tip chains and parent-tip salts after crash-style partial writes.

Because digests mix `parent_tip`, a torn tail that should have been cleared will change both `journal_tip_hex` and `canonical_byte_digest` for every subsequent fold of that manifest.

Drill fragment used when planting a torn tail for local checks: `BODY=partial-no-newline` with no final newline.

Drill fragment used when planting a surviving prior complete line: a full `GEN=1|BAND=p7|BODY=...` line ending in a newline. The next fold must continue at `GEN=2` with `parent_tip` equal to the tip of that planted line alone.
