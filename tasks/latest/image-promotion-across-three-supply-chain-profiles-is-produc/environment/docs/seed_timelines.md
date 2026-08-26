# Profile seed timelines

Each profile directory `/app/environment/fixtures/seed/<profile>/seed_steps.json` drives one promotion scenario. Profile ids are `p1`, `p2`, and `p3`.

## Seed document fields

| Field | Type | Notes |
|-------|------|-------|
| `image_tag` | string | Object store tag resolved through `fixtures/store/catalog.json`. |
| `targets_gen` | integer | Default generation; select `targets.v1.json` when `1`, else `targets.v2.json`. |
| `expiry` | integer | Default Unix seconds delegation window. |
| `proxy_required` | integer | `1` when gate and walk transports must use proxy mode `1`. |
| `walk_mode` | integer | Walk-stage transport mode when no proxy override applies. |
| `pull_mode` | integer | Gate-stage transport mode. |
| `admission_snap` | string | Admission snapshot label folded into gate transcripts. |
| `replica_flip` | boolean | When true, replica storage may rewrite tag bytes beneath API immutability. |
| `steps` | array | Timeline entries with `idx`, `label`, and `mirror_tier`. Step entries may override generation, expiry, admission, or transport modes for that run only. |

## Mirror tier and replica semantics

Probe-stage readiness compares an effective mirror tier against collection tier `2`. When `replica_flip` is true and the catalog lists a replica for `image_tag`, effective tier is `1` for every step of that profile. See `stage_contract.md` for promotion epoch, mirror-view recovery, and persistence rules.

## Profile constants

| Profile | `image_tag` | Defaults | `proxy_required` | `replica_flip` | Steps |
|---------|-------------|----------|------------------|----------------|-------|
| `p1` | `acme/app:v3` | targets `2`, expiry `1893456000`, snap `node`, pull/walk `0` | `0` | false | step `0`: tier `2`, targets `1`, expiry `1893455800`, snap `steady` |
| `p2` | `beta/svc:rel` | targets `2`, expiry `1893456000`, snap `node`, pull/walk `1` | `1` | false | step `0`: tier `2`, targets `1`, expiry `1893455900`, snap `inspect`; step `1`: tier `2`, targets `2`, expiry `1893456000`, snap `node` |
| `p3` | `gamma/img:prod` | targets `2`, expiry `1893456000`, snap `node`, pull/walk `0` | `0` | true | step `0`: tier `2`, targets `1`, expiry `1893455700`, snap `drift`; step `1`: tier `2`, targets `2`, expiry `1893456000`, snap `node` |

## Store catalog helpers

`fixtures/store/catalog.json` exposes `objects`, `tags`, and optional `replicas`. Each object entry includes a `bytes_ref` string that names the blob file under `fixtures/store/blobs/` (without the `.bin` suffix). Metadata files under `fixtures/meta/` include a `signed` object with integer `version` for generation bumps.
