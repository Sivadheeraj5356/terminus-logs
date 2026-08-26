# Stage journal and durable cache

Stage root comes from `STAGE_ROOT` in `/app/environment/fixtures/slices/q46.txt`.

## Journal segments

Path: `$STAGE_ROOT/journal/<manifest_id>.frames`

Each successful fold for a `(manifest_id, scope_band)` appends one complete line ending in a newline:

```
GEN=<n>|BAND=<scope_band>|BODY=<unit_tag_without_rev>
```

Example first two lines for manifest `e3-canary` after a clean p7 then p8 fold:

```
GEN=1|BAND=p7|BODY=
GEN=2|BAND=p8|BODY=
```

(with BODY filled from the ordered slot tokens). On disk those lines live at `$STAGE_ROOT/journal/e3-canary.frames`.
`<n>` is the 1-based count of complete lines after the append (prior complete lines + 1). `GEN` values for a manifest must be contiguous starting at 1. Incomplete trailing bytes without a final newline are torn state and must be removed by stage mending before tips are trusted.

`unit_tag` for the certificate is the BODY tokens plus a trailing `rev=<n>` token where `n` equals that line's `GEN`. After the second fold for a manifest, that trailing token is `rev=2`.

Before a fold appends, the journal may already hold complete lines from earlier mixes (including rematerialization under a later set stem, or a prior complete line that survived mending). Those prior lines are part of the lineage that digests and tips must observe.

## Durable cache

Path: `$STAGE_ROOT/cache/<manifest_id>.kv`

KEY=VALUE lines:

- `ANNEX_LAST` — `0` or `1` for the last processed band's annex flag
- `WINDOW_LAST` — integer seal window id last mixed for this manifest
- `EPOCH` — integer ≥ 1

On each mix for a manifest:

1. If no cache file exists, start `EPOCH=1` and store the current annex flag and window id.
2. If `ANNEX_LAST` differs from the current annex flag **or** `WINDOW_LAST` differs from the current window id, increment `EPOCH` by one, then store both.
3. Otherwise keep `EPOCH` unchanged and refresh both last fields.

`cache_epoch` on the row is the epoch after this update.

## Digest wire

Let `tag` be the full `unit_tag` (with `rev=`), `letter` the profile `scope_letter`, `seal` the seal token selected for the current window and GEN (see `docs/seal_windows.md`), `epoch` the decimal cache epoch string, `window_id` the integer seal window id, and `ns` the fixture `namespace` string for that manifest (empty string when absent).

Let `parent_tip` be the 8-hex journal tip (see `docs/tip_chain.md`) over complete lines present in that manifest's journal **before** this fold appends. An empty journal uses the empty-tip value from tip_chain.md (FNV-1a of the empty string → `811c9dc5`).

Wire form (no spaces):

```
<manifest_id>|<tag>|<letter>|W<window_id>
```

The suffix `|W<window_id>` is the literal ASCII character `W` followed by the decimal window id once. Example: window id `2` produces the suffix `|W2`, never `|22` and never `|W` alone.

`canonical_byte_digest` is 16 lowercase hex chars: 8-hex FNV-1a of the wire, concatenated with 8-hex FNV-1a of the secondary string built with no separators:

```
tag + manifest_id + ns + seal + epoch + parent_tip + W + <decimal window_id>
```

Here `W` is again the literal character `W`, and `<decimal window_id>` is the window id written in decimal once. Example pieces for `tag=rev=1`, `manifest_id=e3-canary`, `ns=canary`, `seal=w3xp`, `epoch=1`, `parent_tip=811c9dc5`, `window_id=2`:

```
rev=1e3-canarycanaryw3xp1811c9dc5W2
```

FNV-1a 32-bit: offset basis `2166136261`, prime `16777619`, lowercase hex without `0x`.

Journal tip hashing for `journal_tip_hex` (post-append tip) is defined in `docs/tip_chain.md`. Graded digests depend on `parent_tip` and `ns`; graded tips use the post-append tip. Those two tip values differ whenever the fold appended a line.

## Snapshot reconciliation

An emit represents one observed matrix snapshot, not an unconditional request to
append the same events again. The snapshot identity is computed from:

1. every `.json` set in sorted filename order, including each filename and its
   exact bytes;
2. `profiles/p7.toml` and `profiles/p8.toml`; and
3. `fixtures/slices/q46.txt`.

Each name and byte payload is length-prefixed before concatenation, and the
identity is the 8-hex FNV-1a value of that wire. Absolute directory names are
not part of the identity.

After a successful zero-violation emit, the stage stores the identity and a
copy of the emitted certificate. Re-emitting an identical snapshot must restore
that certificate at the requested `--out` path without changing any journal or
cache bytes. If any identity input changes, normal processing resumes from the
durable journal/cache state, so GEN lineage, parent tips, windows, and epochs
continue from the prior committed snapshot. The newly successful snapshot then
replaces the saved identity and certificate.

The certificate is written through a sibling temporary file and renamed before
the snapshot identity is committed. A failed or non-zero-violation emit must
not advertise the new identity as committed.

## Recoverable changed-snapshot transaction

Before processing a changed snapshot, the driver checkpoints the complete
`journal/` and `cache/` trees plus both committed snapshot artifacts under
`$STAGE_ROOT/.txn/`. The checkpoint must exist before mending or the first
fold mutates durable bytes. It is removed only after the new certificate and
snapshot identity have committed successfully.

At process entry, the presence of `.txn/` means the prior emit did not commit.
The driver must restore the checkpoint exactly, remove new journal/cache files
and temporary snapshot artifacts, and delete `.txn/` before deciding whether
the requested snapshot is unchanged. Recovery is therefore rollback, followed
by a normal retry; partially appended GEN lines and cache epoch changes from
the failed attempt never become parent lineage.

The verifier may set `SPW_FAIL_AFTER_ROWS=<positive integer>`. Immediately
after constructing that many rows for a changed snapshot, the driver exits
with status 86 without writing a new certificate or removing `.txn/`. This is
a deterministic crash boundary for validating rollback. Missing, invalid,
zero, or negative values disable injection. An unchanged snapshot remains a
no-op and does not enter a transaction.
