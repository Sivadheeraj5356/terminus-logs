# Inspect command contract

Binary `pnpmfix`. `pnpmfix --version` prints exactly `pnpmfix 0.8.6`.

## CLI flags (exact)

```
pnpmfix inspect \
  --lane <name> \
  --edges <path> --artifacts <path> --deps <path> \
  --mirrors <path> --pins <path> --xor <path> --bans <path> \
  --forbidden-hosts <path> \
  --retention-hops <int> \
  --out <path>
```

**`--lane` is always required and always meaningful**, including when CSV paths are absolute/temp files rather than a packaged bundle:
1. Echo `--lane` into the output JSON `lane` field (never leave `lane` empty).
2. Filter `edges` / `artifacts` / `deps` / `xor` rows to that lane before analysis.
3. Do **not** infer the lane from CSV path directories or filenames.

Example: `pnpmfix inspect --lane edge --deps /tmp/mut/deps.csv … --out /tmp/out.json`
must produce `"lane":"edge"` and only evaluate `edge` rows from those CSVs.

## Output schema (exact)

Top-level keys **exactly** (no extras): `lane`, `retention_hops`, `artifacts`, `totals`.

**`artifacts` MUST be sorted ascending by `coordinate`**. Each artifact object keys exactly:
`coordinate`, `status`, `holds`, `risk_score`.
`holds` is a list of **plain strings** (not objects).
`status` is `release` iff `holds` empty else `hold`.

Edges after lane filter: parent,child,edge_kind. Soft never conflicts/cascades.
When `retention_hops` is `0`, no cascades are emitted.

Hold emission (per artifact):
If the same hold string is emitted more than once, keep one copy and take the **max** risk for that string.
Then `risk_score` for the artifact is the **sum** of those unique hold risks (not max-of-all holds).
`risk_score_total` is the sum of every artifact's `risk_score`.

## Cascade routing (hard)

Only these local hold prefixes cascade: `ban:`, `remote:`, `xor:`, `provcollide:`.
**Do not cascade** `hashdrift:`, `versiondrift:`, `mirrormiss:`, or `missingpin:`.

Walk **reverse hard edges only**. Soft edges never participate.

For each cascading origin hold, pick the best reverse-hard route to each reachable ancestor within `retention_hops`:

1. shorter hop distance `d` wins;
2. if `d` ties, lexicographically smaller **via** wins.

`via` is intermediates between origin and target (excluding both ends), joined with `/`.
If `d == 1`, `via` is `-`.

Emit one cascade per `(target, origin, original_hold)`:

- hold string: `cascade:<d>:<origin_coord>@<via>:<original_hold_string>`
- risk: `max(1, origin_hold_risk - 13 * d)`

Edge lane includes a longer spine (`spine:a`→`spine:b`→`spine:c`) under retention hops 3, so hop-3 spine routes must lose to hop-2 diamond routes into `svc:app`.

## Local holds

1. Remote URL: dep `source_url` **or** `patch_url` contains a forbidden host substring OR does not start with `file:///`:
   `remote:<coord>:<field>` field is `source` or `patch`, risk 47 on the dep coordinate.
   Empty `patch_url` does **not** emit a remote hold. Non-empty remote patches always do.
2. Hash drift: pin sha256 for dep != dep source_hash after normalizing both sides (strip an optional leading `sha256:` for **comparison only**):
   `hashdrift:<coord>:<expected>:<actual>` risk 43
   `<expected>` and `<actual>` in the hold string are the **stripped** lowercase hex digests (no `sha256:` prefix).
3. Version drift: pin version for dep != dep version string:
   `versiondrift:<coord>:<pin_version>:<dep_version>` risk 36
4. Mirror miss: mirror inventory lacks the basename implied by source_url path:
   `mirrormiss:<coord>:<basename>` risk 40
5. Provide collision: two deps in lane claim same provide name:
   `provcollide:<provide>:<dep_a>|<dep_b>` (deps sorted) risk 45 on both
6. XOR: xor.csv (lane,group,provide). If ≥2 provides from same group appear among lane dep provides:
   Map provide->dep coordinate; hold `xor:<group>:<p1>|<p2>` risk 52 on each dep coordinate that supplies those provides
7. Missing pin: dep has no pin row:
   `missingpin:<coord>` risk 38
8. Ban: coordinate in bans -> `ban:<coord>` risk 55
9. Cascade: ban/remote/xor/provcollide only, as above

## Totals counters (exact)

Totals keys: release,hold,remotes,hashdrifts,versiondrifts,mirrormisses,provcollides,xors,missingpins,bans,cascades,risk_score_total.

`totals.hold` (and manifest `hold_count`) is the count of artifacts with `status` equal to `hold` — **not** the number of hold strings.

Each hold-prefix counter (`remotes`, `provcollides`, `xors`, `cascades`, …) counts **unique hold strings after per-artifact max-risk dedupe**, then sums across artifacts:
- If `dep:jsonA` and `dep:jsonB` each carry the same xor hold string, `totals.xors` is **2**, not 1.
- Likewise a shared `provcollide:…` string on two artifacts contributes **2** to `totals.provcollides`.
Do **not** count once-per-group / once-per-collision.

Lane `lab` with `retention_hops=0` must surface poison hashdrift+versiondrift locally with **no** cascade holds on `mid:hop` / `svc:lab`.
Soft edges never cascade: `trace:soft` on lane `edge` must not receive cascade holds.

CSV shapes:
deps.csv: lane,coordinate,provide,version,source_url,source_hash,patch_url
mirrors.csv: basename
pins.csv: wrap,version,sha256  (wrap column is the dep basename, keyed as dep:<wrap>)
xor.csv: lane,group,provide
forbidden-hosts.csv: host
bans.csv: coordinate
artifacts.csv coordinates are dep names like dep:fmt
