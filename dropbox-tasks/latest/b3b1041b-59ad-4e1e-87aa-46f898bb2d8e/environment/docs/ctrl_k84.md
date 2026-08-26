# ctrl_k84 contract

## Public checker invocation

```bash
/app/environment/tools/k9_verify --matrix all --witness-out /app/output/replay_witness.json --spec-out /app/output/inferred_spec.json
```

## Graded artifacts

- `/app/output/replay_witness.json` from `--matrix all`
- `/app/output/inferred_spec.json` from the same run

Stage HUD under `/app/output/stage` and `/app/environment/fixtures/hud/w7_stub.json` are not graded.

## replay_witness.json schema

Top-level object with key `grids`. Each grid name (`pocket`, `ridge`, `slate`, `marsh`) maps to an object keyed by profile (`pri_hi`, `pri_lo`). Each profile cell contains:

- `grid` (string)
- `profile` (profile id)
- `rows` (array of observation objects)
- `meta_state` (string: `aligned` when metamorphic remaps agree, else `diverged`)
- `instance_digest` (hex sha256 string)
- `eff_keys` (sorted top-level keys of effective cfg after overlay bind)
- `cfg_fp` (hex sha256 of `eff_keys` joined by commas)

Each row object fields:

- `tid` (token id string)
- `kid` (key id string)
- `plan` (`ok` or `skip`)
- `gate` (`pass` or `hold`)
- `e_tag` (epoch tag string)

## instance_digest

Canonical replay record bytes are UTF-8 JSON with sorted object keys, compact separators (no spaces), over the array of accepted rows where `plan == "ok"` and `gate == "pass"`, sorted by `tid`. `instance_digest` is the lowercase hex sha256 of those bytes.

Tolerance bands (from profile files under `/app/environment/pri/`):

- `pri_hi`: require full 64-hex equality (`tol_prefix = 64`)
- `pri_lo`: require first 48 hex chars equal (`tol_prefix = 48`); remaining suffix may differ only when partial fixture slices are authoritative for that grid

When a grid lists `slice_mode: full`, both bands require full 64-hex equality regardless of profile `tol_prefix`.

## inferred_spec.json schema

```json
{
  "schema": "k84-spec-v1",
  "clauses": [
    {"aid": "A1", "kind": "cfg_iso", "note": "effective cfg keys omit overlay pollution markers"},
    {"aid": "A2", "kind": "w_bind", "note": "accepted witness rows bind the active profile epoch tag"},
    {"aid": "A3", "kind": "rev_iso", "note": "gate acceptance follows per-epoch journal bands"}
  ],
  "band_epoch": {"pri_hi": "e_hi", "pri_lo": "e_lo"}
}
```

Clause `aid`/`kind` pairs above are required. `note` strings must match exactly. `band_epoch` must map profiles to those epoch tags.

## Profile bands

- `pri_hi` selects epoch `e_hi`
- `pri_lo` selects epoch `e_lo`

## Recovery after rst9.sh

`/app/environment/migrations/rst9.sh` clears rotation scratch under `/app/environment/r43/.scratch`. Idempotent recovery:

```bash
bash /app/environment/migrations/rst9.sh --restore-from /app/environment/data/p39/pin_table.toml
```

Re-run build_lab.sh and the public checker after recovery. Annex corpus files under `/app/environment/data/p39/` must remain byte-identical across recovery except when a graded probe intentionally appends to `rot.log`.

## Scenario inputs

Each `/app/environment/scenarios/*.json` file includes `base_cfg`, `overlay`, `tokens`, `meta_remap`, and `slice_mode`. Token ids used in east/west checks include `s01`, `s02`, `m01`, `m02`, and `r02`.

## Pollution keys and fingerprints

Overlay keys marked `__*` and `x_def` must not appear in `eff_keys`. `cfg_fp` is the lowercase hex sha256 of the sorted `eff_keys` joined by commas. Graded ok rows must not use kid `k_root` or any kid starting with `k_evil`.

## Epoch allow tables

Journal fold rules and poison-slot discard live in `/app/environment/docs/trace_glossary.md`. `/app/environment/data/p39/pin_table.toml` is a checkpoint of a correct fold used for scratch restore and cross-check. Live gate acceptance must track `/app/environment/data/p39/rot.log`.
