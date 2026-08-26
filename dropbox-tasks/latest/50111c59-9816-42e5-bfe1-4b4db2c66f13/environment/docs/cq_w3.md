# CQ W3: PKI timeline ledger contract

Offline mTLS PKI dump reconstruction for trust-epoch forensics. The sealed
timeline ledger at `/app/output/tl.json` must clear the closed fixture algebra
for every evidence pack and every metamorphic transform arm listed under
`/app/corp/arms.toml`.

## Obligation

Principals are the `pid` strings in the sqlite journals and material index.
Authority boundary outcomes are the role strings after generation-keyed folding,
PEM or material binding, revocation and handshake sync, and seal. Barrier-style
violations must stay at zero across arms.

Live inputs include sqlite journals under `/app/corp/sql/` (`issue_rows`,
`revoke_rows`), material inventory `/app/corp/mat/inventory_index.toml` plus PEM
files under `/app/corp/mat/gen_XX/`, handshake JSONL packs under `/app/corp/hs/`,
generation anchors in `/app/corp/anchors.toml`, and arm table
`/app/corp/arms.toml`.

Intermediate files under `/app/output/stage` may look settled early. Only the
sealed ledger regenerated through `x7` counts.

## Generation-keyed folding

`issue_rows` may contain multiple rows per `(pid, gen)` and wall-clock `ts`
order is not authoritative. Fold candidates by `(pid, gen)` using the generation
keys from `/app/corp/anchors.toml`. When several issue rows share the same
`(pid, gen)`, keep the row with the greatest `ts` for that pair. Do not prefer
an older generation because it has a later wall-clock stamp. Rows whose `gen`
is absent from the anchor list are out of scope for folding.

Each fold candidate carries `pid`, `gen`, `scp`, and `role` from the chosen issue
row. Folding may attach a provisional `tag` via `tag_of(pid, scp, role, gen)` in
`/app/tools/digest_pack.py`; that call uses the issue-row `role`.

Transforms that pre-collapse redundant `(pid, gen)` issue rows before folding
must preserve the same greatest-`ts` survivor the fold itself would select.

## Material and anchor binding

Join each candidate to the material row in `inventory_index.toml` with the same
`pid` and `gen`. Bound role comes from the material `role` field for that pair
(not from the raw issue row) unless the active arm remaps roles (see arms). Bound
fingerprint comes from the material `fp`. At bind time, recompute `tag` as
`tag_of(pid, scp, bound_role, gen)` using that bound material `role`, not the
issue-row `role` or any provisional tag carried from folding. Trust windows and
`hex_lane` use this bound `role` and recomputed `tag`. Anchors in `anchors.toml`
restrict which generation ids are eligible; candidates whose `gen` is absent from
the anchor list are dropped.

Arm `perm_a` rotates material roles one step across principals
(`p_alpha` gets `p_beta` role, `p_beta` gets `p_gamma` role, `p_gamma` gets
`p_alpha` role). Arm `perm_b` rotates two steps. Arm `hostile_role` widens
`p_beta` material role to `svc.mesh.escalate` for violation pressure. Arm
`reenc_pem` re-encodes PEM file bytes without changing fingerprints in the
index; binding must still follow the index `fp` and `role`.

## Revocation and handshake sync

For each bound view, load `revoke_rows` for the exact `(pid, gen)` pair. Nonzero
`revoked` means revoked. If no row exists for that pair, treat revoked as false.
A revoked row for the same `pid` at a different `gen` must not apply.

Handshake fragments from the pack named by the active arm must include a line
with matching `pid` and `gen` and `ok` true. Missing or `ok` false counts as a
handshake failure flag on the trust window. Fragments for other generations of
the same principal must not decide the flag.

Arm `reorder_j` reorders journal read order; folding must remain generation
keyed. Arm `drop_snap` drops redundant same-`(pid,gen)` issue rows before fold;
the greatest-`ts` ordering must still select the surviving row.

## Violation count

`viol_n` for a `(pack_id, arm_id)` row sums independent checks. Add one for
every trust window with `revoked` true. Add one for every bound view whose role
differs from the arm-adjusted material role for the same `(pid, gen)`. Add one
for every trust window with handshake failure.

## Digest construction

Process arms in `/app/corp/arms.toml` file order. For each arm, build trust
windows, then digests via `/app/tools/digest_pack.py` (`tag_of`, `hex_lane`,
`seal_hex`, and the closed predicate documented there). Digests use sha256
(SHA-256). Each window contributes pid, gen, bound `role`, bound `tag`
(recomputed at material bind), revoked bit, and hs_fail bit (handshake failure)
into `hex_lane` as documented in that helper module. Window order inside
`hex_lane` is by `pid` ascending only.

Early tips under `/app/output/stage` may use `*.mark` or `*.tip` filenames. They are
not authoritative for `hex_lane`, but a sealed regenerate still writes those
stage files as part of normal emit. Do not drop `*.mark` or `*.tip` writes when
fixing the bridge.

`seal_ok` is `1` when the row seal material is exactly 32 raw bytes (hex length
64).

## CLI

Rebuild with `/app/tools/build_x7.sh`. Emit the sealed ledger with

`/app/bin/x7 --evidence /app/corp --out /app/output/tl.json`

Flags `--evidence` and `--out` select the corp dump root and output path.

Every arm id listed in `arms.toml`, including `reorder_j`, `drop_snap`,
`reenc_pem`, `perm_a`, `perm_b`, `hostile_role`, `base`, `alt_base`,
`alt_reorder`, `alt_drop`, and `alt_perm`, must clear the closed fixture algebra
with zero violations. Correct reconstruction applies the arm role remaps during
material binding so bound roles match the arm-adjusted expected roles.

## Ledger schema

`/app/output/tl.json` object layout. `schema_ver` (integer) must be value `1`.
`rows` is an array of objects, each with `pack_id` (string), `arm_id` (string),
`hex_lane` (string, 64 lowercase hex characters), `viol_n` (integer,
non-negative), `seal_ok` (integer `0` or `1`), and `stage_mark` (integer `0`
or `1`). After a successful sealed regenerate through `x7`, every row must
carry `stage_mark` value `1` (the field stays set for sealed arms; it is not
left at `0`). Top-level `seal_hex` is a string of 64 lowercase hex characters.
`closed_ok` is integer `0` or `1` when every row clears checks and seal
materials match `digest_pack` construction.
