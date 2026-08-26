# Coverage map artifact notes

The binary `/app/bin/lane_matrix` regenerates `/app/output/coverage_map.json` from `/app/fixtures` and `/app/spec`.

## Build

Build the release binary from fixed sources under `/app/environment` using the cargo release invocation below.

```
cargo build --release --manifest-path /app/environment/Cargo.toml
```

Copy the resulting `lane_matrix` binary into `/app/bin/lane_matrix`. Prefer the helper script below.

```
bash /app/environment/tools/rebuild_bin.sh
```

Digest helpers used by operators live in `/app/environment/tools/digest_ops.py` (module `digest_ops`). Always run the rebuild helper before invoking the CLI.

## Command

```
/app/bin/lane_matrix --fixtures /app/fixtures --spec /app/spec --out /app/output/coverage_map.json
```

## Top-level shape

The coverage map is a JSON object with two top-level members.

- `violation_count`  -  integer; must be zero after a correct regeneration
- `instances`  -  object keyed by fixture pack id; each value holds a `rows` array

Every fixture pack id under `train/` and `held_out/` must appear as an instance key.

## Row fields

Each row object carries these members.

- `visits`  -  array of integers; visit counts, one slot per bay cell in pack order
- `residual_risk`  -  number; unmet annex-edge ratio for zones touched by the pack
- `witness`  -  string; lowercase hex digest binding `visits` to the annex edge hash
- `seal_ok`  -  boolean; true only when `witness` is not the all-zero digest
- `frontier_ids`  -  array of integers; expanded cell indices used for the pack
- `cells`  -  array of strings; bay cell labels in pack order

## Frontier obligation

`frontier_ids` must include every observed cell index for the pack. It must also include every annex edge target whose `from_zone` is touched by the pack observations. Each missing annex target increments `violation_count` by one (counted once per pack that misses at least one required target). After a correct regeneration, `violation_count` is zero.

## Residual risk

Take the annex edges in `/app/spec/pin43/bonds.bin.meta.json` whose `from_zone` is touched by the pack observations; call that set E. Let U be how many of those edges have a zero visit count at `to_ix`. When E is empty, `residual_risk` is zero. Otherwise `residual_risk` is the ratio of U to the size of E.

Held-out packs must drive `residual_risk` to zero (every touched annex target has a positive visit count).

## Edge hash

Sort annex edges by the UTF-8 line formed from `from`, a tab, and `to`, using the `from` and `to` name strings from `bonds.bin.meta.json`. Join those lines with newlines. The edge hash is the sha256 of that blob (32 raw bytes).

## Witness digest

Concatenate each visit count as a little-endian `u16` into `visits_bytes`. The `witness` field is the lowercase hex encoding of sha256 over `visits_bytes` followed by the edge hash bytes. `seal_ok` is true exactly when that raw digest is not thirty-two zero bytes.

## Idempotent rewrite

Running the same command twice must leave `/app/output/coverage_map.json` byte-identical and must not change `violation_count`.

## Splits

`/app/fixtures/train` may look complete under greedy emission scoring. `/app/fixtures/held_out` adds annex side targets that training-green policies miss. Both splits are in scope for `violation_count` and residual checks.
