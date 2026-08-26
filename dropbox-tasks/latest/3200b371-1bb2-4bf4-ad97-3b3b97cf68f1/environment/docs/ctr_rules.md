# Closed-row rules (row_v3)

Long-form offline field notes live in `corpus_note.md` under this docs tree. They are reference reading for held-out rotations; closed-row algebra in this file still wins over smoke notes.


Offline fixture desk under `/app/environment`. Emit a hardened policy pack at
`/app/output/policy_pack/` by running `/app/h7p/pp_run` as documented in
`operator_cmds.txt`.

Operator smoke notes in `operator_notes.md` describe CI shortcuts that keep
ledger totals green. Those shortcuts are not authoritative for held-out
rotations. When they conflict with this file, this file wins.

## Artifacts

Required members under `/app/output/policy_pack/`:

- `pack.json` — schema `row_v3` object matching `/app/environment/schemas/row_v3.schema.json`
- `rows.tsv` — TSV mirror of `pack.json` rows (header + one line per closed edge)
- `lock.tsv` — TSV mirror of lock entries (`rotation_id`, `tok`, `asv`)
- `prov.sha` — 16 lowercase hex chars equal to `pack.json` field `prov`
- `ledger.sum` — TSV mirror of ledger totals (`rotation_id`, `tot`)

`rows.tsv` header:

```
rotation_id	slice_id	peer	tok	asv	band_lo	band_hi
```

## Rotation table

The rotation table file `rot_tbl.toml` under `/app/environment/data/` lists every
graded rotation. Each `[[row]]` has:

- `id` — rotation id
- `corpus` — comma-separated slice ids active for that row
- `lane` — `base` or `held`
- `step` — integer step index

Field `lane` marks fixture stress class. Every row must survive a full rebuild.
Matching aggregate ledger totals is necessary but not sufficient for closure.
Field `step` participates in closed band algebra (below); it is not decorative.

## Sum table

`/app/environment/data/fix_stash/sum_tbl.tsv` columns: `slice_id`, `sum_val`,
`base_ref`. For a rotation, ledger `tot` equals the sum of `sum_val` over the
active corpus slices.

## Band contraction algebra

For each active slice with `sum_val = S` on a rotation whose `step` is `K`:

- field `band_lo` is computed as `(S + K) mod 13`
- field `band_hi` is computed as `band_lo + (S mod 17) + 3`

The closed span identity is `band_hi - band_lo = (S mod 17) + 3`.

A common near-miss is to drop `K` and use `S mod 13` alone. That reading matches
only rotations where `K` happens to be `0` (for example `r01`), and fails once
`step` is nonzero.

## Rotation pin seed

After bands for a rotation are known, form the pin seed:

1. Sort active slices by `slice_id` ascending.
2. Emit one ASCII line per slice: `slice_id|band_lo` followed by a single
   newline (`\n`).
3. `pin_seed` = first 8 lowercase hex chars of `sha256` over that byte stream.

`pin_seed` is a carrier shared by later pin emit. Recomputing bands differently
in a later phase without regenerating `pin_seed` from those bands breaks tok
closure even when individual band fields look plausible.

## Mux edges (preamble lock peers)

Each corpus blob `/app/environment/data/corpus/<slice>_blob.dbc` declares
`PEER <other_slice>` lines. For a rotation, an edge exists from `src` to `dst`
when:

1. `src` is in the active corpus set
2. the `src` blob lists a **preamble** `PEER dst`
3. `dst` is also in the active corpus set

Preamble means: within that blob file, only `PEER` lines that appear **before
the first line that begins with `;`** count as lock peers. `PEER` lines that
appear after that first `;` comment are calibration noise and must not enter
the closed edge set, even when both endpoints are active.

Every preamble edge that satisfies (1)-(3) must appear as a closed row. Keeping
only the first preamble peer per source is not closure. Taking every `PEER` in
the file (including calibration-body peers) is also not closure.

## Row token and asv (dual key)

For each closed edge `(src, dst)` with the `src` band values and the rotation
`pin_seed` above:

- `tok` = first 8 lowercase hex chars of `sha256` over the ASCII bytes
  `t|<src>|<dst>|<band_lo>|<pin_seed>` (literal pipe separators, no trailing
  newline). The same digest may be produced with `sha256sum` on those bytes.
- `asv = (byte_sum(slice_id) + lo) % 64` where `byte_sum(slice_id)` is the sum of
  UTF-8 code units in `src` and `lo` is that slice's `band_lo`

Dual-key rule: `pin_seed` mixes into `tok` and must **not** mix into `asv`.
Folding `pin_seed` (or its length) into `asv` is a near-miss that keeps some
smoke totals green while breaking lock pins.

## Provenance seal

Sort every row by the tuple `(rotation_id, slice_id, peer)`. Emit one
`tok|asv` record per row, each terminated by a single newline (`\n`). Hash
that byte stream:

`prov = first 16 lowercase hex chars of sha256(utf-8 bytes)`

Empty row sets hash the empty byte stream. `prov.sha` and `pack.json["prov"]`
must match that digest. Sealing from ledger totals alone is not provenance
closure.

## Idempotent rebuild

Two consecutive `/app/h7p/pp_run rebuild` runs with unchanged fixtures must
produce identical `prov.sha` and identical `rows.tsv` bytes.

## Health probe

`/app/h7p/pp_run health` may report green when ledger totals match `sum_tbl`.
That probe does not prove row closure, preamble peer coverage, pin-seed
coupling, or provenance seal.
