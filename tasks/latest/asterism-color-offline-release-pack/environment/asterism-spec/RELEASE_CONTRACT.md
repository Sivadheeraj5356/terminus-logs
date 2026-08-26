# Asterism Color release contract

This document defines the production release produced from `/app/foundry-sources`
under the ledger at `/app/asterism-ledger/release.toml`. All paths below are
absolute container paths.

## Build entry point

The integrator supplies `/app/forgectl` with this interface:

```
/app/forgectl [--source-root ABS] [--profile ABS] [--output ABS]
```

Defaults: `--source-root /app/foundry-sources`, `--profile /app/asterism-ledger/release.toml`,
`--output /app/out/colr-crate`. Every argument must be an absolute path; relative paths
exit nonzero. The script runs offline, replaces stale outputs safely, leaves
source inputs byte-identical, and returns zero only after local validation passes.

## Output inventory

Given the default ledger, `/app/out/colr-crate` must contain exactly:

- `/app/out/colr-crate/AsterismColor-VF.ttf`
- `/app/out/colr-crate/AsterismColor-VF.woff2`
- `/app/out/colr-crate/static/AsterismColor-Text.ttf`
- `/app/out/colr-crate/static/AsterismColor-RoundedText.ttf`
- `/app/out/colr-crate/static/AsterismColor-CondensedSemibold.ttf`
- `/app/out/colr-crate/static/AsterismColor-WideBold.ttf`
- `/app/out/colr-crate/subsets/AsterismColor-LatinGreek.woff2`
- `/app/out/colr-crate/subsets/AsterismColor-UISymbols.woff2`
- `/app/out/colr-crate/release-manifest.json`
- `/app/out/colr-crate/AsterismColor-1.0.0.zip`

No other files may remain under `/app/out/colr-crate`.

## Release ledger

`/app/asterism-ledger/release.toml` is authoritative for family name, version,
`source_date_epoch`, variable and static filenames, instance coordinates,
subset codepoint lists, palette-driven color packaging, and archive naming.
Changing the ledger must change outputs without editing forge logic.

## Variable font contract

The variable TrueType font exposes axes `wght` (300–800, default 400),
`wdth` (75–125, default 100), and `ROND` (0–100, default 0). Named instances
match `/app/asterism-ledger/fvar-named-instances.toml`. COLR version 1 and CPAL must
include palettes `Night` and `Dawn` from `/app/foundry-sources/color/palettes.toml`.
Color glyphs `comet`, `eclipse`, `orbit`, and `signal` map to U+E000–U+E003 per
`/app/foundry-sources/color/glyph-map.toml` with paint graphs from
`/app/foundry-sources/color/paintgraph.toml` (including at least one gradient and one
composite transform paint).

OpenType layout from `/app/foundry-sources/features/` must compile: kerning for `A V`,
`liga` for `fi`, `mark`/`mkmk` for combining grave, tabular figures via `tnum`,
stylistic alternate `ss01` for `A`, and language systems for Latin and Greek.

## Static instances and subsets

Each `[[instances]]` entry yields one static font at `/app/out/colr-crate/static/` with
coordinates from the ledger. Static fonts drop variable-only tables unless this
document explicitly allows retention.

OpenType name table for every static instance: nameID 1 equals the ledger
`family` string, and nameID 2 (subfamily / style) must equal that instance's
ledger `name` field exactly (for example, the `Text` instance must have
nameID 2 equal to `Text`). Do not substitute a generic style string such as
`Regular` when the ledger instance name differs.

Subsets read codepoints from the ledger's `codepoints_file`, retain color closure
when `retain_color = true`, and retain or drop layout tables per `retain_layout`.
`.notdef` and shaping closure glyphs required for requested strings must remain.

## Manifest schema

`/app/out/colr-crate/release-manifest.json` is UTF-8 canonical JSON with sorted object keys,
artifact entries sorted by `path`, and one trailing newline. Top-level fields:

- `schema_version` (integer 1)
- `family` (string)
- `version` (string)
- `source_date_epoch` (integer from ledger)
- `profile_sha256` (lowercase hex SHA-256 of ledger bytes)
- `source_tree_sha256` (lowercase hex SHA-256; see protocol below)
- `artifacts` (array of `{path, media_type, size, sha256}` relative to `/app/out/colr-crate`)
- `axes` (array of `{tag, min, default, max}` floats)
- `named_instances` (array of `{name, coordinates}`)
- `palettes` (array of palette name strings)
- `tool_versions` (object of pinned tool version strings)

The manifest lists font outputs included in the archive; it does not list the
archive itself.

### `source_tree_sha256` byte protocol

Hash the source tree rooted at the active `--source-root` (default
`/app/foundry-sources`). Walk every regular file under that root in sorted
relative-path order (POSIX forward slashes). Skip path components named
`.git`, `__pycache__`, or `.cache`. Do not include `/app/out/colr-crate` or
any cache directories outside the source root. For each retained file, update a
SHA-256 hasher with exactly these four concatenations in order — no length or
size field:

1. `relative_path` encoded as UTF-8 bytes
2. a single NUL byte (`0x00`)
3. the raw file bytes
4. a single NUL byte (`0x00`)

Emit the digest as lowercase hex. Reference:

```python
import hashlib
from pathlib import Path

def source_tree_sha256(root: Path) -> str:
    h = hashlib.sha256()
    files = sorted(p for p in root.rglob("*") if p.is_file())
    for p in files:
        if any(part in {".git", "__pycache__", ".cache"} for part in p.parts):
            continue
        rel = p.relative_to(root).as_posix()
        h.update(rel.encode())
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()
```

## Archive rules

`/app/out/colr-crate/<archive_name>` contains finished fonts and the manifest only. Entries
use forward slashes, lexicographic order, normalized timestamps from
`source_date_epoch`, and stable modes. No source tree, caches, or absolute paths
appear inside artifacts or the archive.

## Reproducibility

Export `SOURCE_DATE_EPOCH` from the ledger epoch. Two clean builds with identical
source bytes, ledger bytes, tool versions, and epoch must yield byte-identical
artifacts regardless of build directory, username, or wall clock. Rebuilding over an
existing `/app/out/colr-crate` must be idempotent.

## Source immutability

Files under `/app/foundry-sources`, `/app/asterism-ledger/release.toml`, and companion ledger policy
inputs must remain byte-identical after a successful build. The pipeline reads color,
feature, metadata, and UFO sources; it must not rewrite them.

## Shaping samples

Sample strings under `/app/proof-strings/` illustrate Latin, Greek, marks, ligatures,
tabular figures, and color icons. Additional shaping samples may exercise the same coverage rules;
covered codepoints must shape without `.notdef` fallback when features apply.


## Digests and archives

Manifest digests use hashlib SHA-256 (lowercase hex). Archives are built with zipfile semantics (deterministic timestamps, forward-slash names). Proof corpora files under `/app/proof-strings` include `latin.txt`, `greek.txt`, `figures.txt`, `ligatures.txt`, `combining-marks.txt`, and `color-glyphs.txt`. Temporary validation may use `/tmp` or `/var/tmp`. Mutation examples may retarget `archive_name` to names such as `AsterismColor-HIDDEN.zip` and static `filename` values such as `AsterismColor-HiddenText.ttf`. Subset stems include `AsterismColor-LatinGreek.woff2` and companion lists such as `subset-latin-greek.txt`. Palette sources live in `palettes.toml`. Cache directories under `/app/var/lib/packrun` are optional and must not appear in the crate.

Temporary WOFF2 round-trips may write `in.woff2` and call `woff2_decompress`. Local `.cache` directories may be cleared between forges and must not appear in the crate.

Shaping validation may invoke `hb-shape` with `--features` enabling liga, tnum, and ss01.
Palette renames such as Night to Midnight must appear in manifest palettes.
