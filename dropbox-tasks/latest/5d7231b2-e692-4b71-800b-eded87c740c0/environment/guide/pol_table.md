# K7 numeric policy

## Checker

```bash
node /app/environment/tools/drv_k7/drv_k7.js --full-audit --out /app/output/resume_witness.json
```

Oracle and local repair scripts may set ENV to `/app/environment` as the workspace root.

Rebuild first with

```bash
/app/environment/scripts/build_all.sh
```

Profile `strict_pair` means the slower coefficient table with tighter band limits; profile `rapid_k` means the shorter-stride table with extended coefficients.

After the driver phase sequence, `/app/output/.phase` field `last` must read `train-continue`. Field `probe_green` is set to true by warm-probe only and must not be treated as audit success.

## curve_digest

Fnv1a 32-bit (lowercase 8 hex) over the curve byte body — little-endian uint32 length prefix followed by IEEE754 float64 values in tick order. Trace files use a `K7TR` prefix; the digest excludes that prefix and hashes only the body bytes.

Offset basis `0x811c9dc5`, prime `0x01000193`, 32-bit unsigned fold.

## Profiles

Each `[[profile]]` block in `environment/data/lim_k7.toml` includes a `name` field (`strict_pair`, `rapid_k`) plus coefficient table `lv`, stride, and band limits `band_max` / `band_tail`.

Each witness row carries `band_drift` (max absolute tick-wise delta between uninterrupted and resume curves) and `band_tail` (mean delta over the final 30% of ticks). Limits come from the active profile in `environment/data/lim_k7.toml` (`band_max`, `band_tail`).

Agreement requires uninterrupted and resume `curve_digest` hex to match for every fixture/profile pair, with both band fields at or below profile limits.

## Load-bearing training modules

Resume and uninterrupted modes must agree on `curve_digest` only when the
training pipeline keeps these modules on the live require path for packing,
step clock, schedule map, series fold, and finalize seal:

- `/app/environment/n4/q7/src/VelP3.js`
- `/app/environment/n4/q7/src/ClkH8.js`
- `/app/environment/r8/w1/src/ArcM6.js`
- `/app/environment/r8/w1/src/MixZ4.js`
- `/app/environment/t2/y5/src/SealK9.js`

Bypassing, stubbing, or replacing any of these with a non-equivalent path so
that regenerating `/app/output/resume_witness.json` no longer depends on them
is not a valid solution: agreement must come from correct behavior in those
modules under the normal rebuild + full-audit flow.

## Recovery

Idempotent reset before re-audit with

```bash
bash /app/environment/ops/rst7.sh
```

## Driver phases

```bash
node /app/environment/t2/y5/src/main.js warm-probe
node /app/environment/t2/y5/src/main.js train-base
node /app/environment/t2/y5/src/main.js pause-store
node /app/environment/t2/y5/src/main.js train-continue
```

Mid-probe book at `environment/data/snap_k7.json` and `/app/output/stage` headline totals are not graded success surfaces. Warm-probe sets `probe_green` in snap_k7.json; that flag alone does not satisfy the audit.
