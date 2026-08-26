# Dye-transfer continuum desk — technical overview

Archival dye-transfer restoration desk: climate-corrected densitometry, splice
continuum scoring, and sealed run artifacts.

## Constants

| Symbol | Value |
|--------|-------|
| T0 | 20.0 °C |
| H0 | 50.0 %RH |
| beta | 0.012 |
| alpha (cyan) | 0.0021 |
| alpha (magenta) | 0.0018 |
| alpha (yellow) | 0.0024 |
| alpha (silver) | 0.0010 |
| eps | 1e-9 |
| threshold default (thr) | 0.035 |

## Climate correction

Per sample channel `ch`:

```
D_corr = D_raw * exp(alpha[ch] * (T - T0)) * (1.0 + beta * (RH - H0) / 100.0)
```

Correction is defined on raw sample channel values. Endpoint interpolation and
midtone means are taken over the corrected sample series.

## Endpoint and midtone extraction

After correcting each sample on a reel:

- **start** — linear interpolation of corrected densities at position `0.0`
- **end** — linear interpolation of corrected densities at position `1.0`
- **mid** — mean of corrected samples with position in `[0.40, 0.60]`; if none,
  mean of all corrected samples on that reel

Linear interpolation uses sorted sample positions; segment ratio `t = (p - p0) / (p1 - p0)`.

## Splice continuum gap

For splice from reel A end to reel B start, per channel:

```
gap[ch] = log10(max(D_end_A, eps) / max(mid_A, eps))
        - log10(max(D_start_B, eps) / max(mid_B, eps))
```

`splice_ok` when `|gap[ch]| <= thr` for all channels (cyan, magenta, yellow, silver).

## Output digest canonicalization

Digests use the SHA-256 hash function (Python `hashlib.sha256` / Go `crypto/sha256`).
Gap and climate formulas use standard real arithmetic (`math` / `libm`).

`output_digest` is SHA-256 hex of canonical JSON encoding an array of rows sorted
by `splice_id` ascending. Each row:

```json
{"splice_id": "S1", "gaps": {"cyan": 0.0, "magenta": 0.0, "yellow": 0.0, "silver": 0.0}}
```

Gap values are rounded to **6 decimal places** before serialization. JSON uses
default marshaling (no extra whitespace). Array order follows sorted `splice_id`.

`denscore_digest` is SHA-256 hex of JSON array of per-reel `{reel_id,start,end,mid}`
blocks sorted by `reel_id`.

`cache_digest` is SHA-256 hex of sorted in-memory cache keys (NUL-separated).

## CLI

### cinecont

```
/app/bin/cinecont run --case <file> --out <dir>
```

Default `--out` is `/app/output`. Invalid case input prints to stderr starting with
`invalid continuum case input:` and exits nonzero without writing `continuum_report.json`.

### denscore (`/app/bin/denscore`)

Reads JSON from stdin, writes JSON to stdout:

Input:

```json
{"temp_c": 20.0, "rh_pct": 50.0, "samples": [{"pos": 0.0, "cyan": 0.5, "magenta": 0.4, "yellow": 0.3, "silver": 0.2}]}
```

Output:

```json
{"start": {"cyan": 0.0, "magenta": 0.0, "yellow": 0.0, "silver": 0.0}, "end": {...}, "mid": {...}}
```

`start` = interp@0, `end` = interp@1, `mid` = midtone anchor.

## Case file schema

```json
{
  "case_id": "string",
  "temp_c": 20.0,
  "rh_pct": 50.0,
  "threshold": 0.035,
  "reels": [{"reel_id": "R1", "samples": [{"pos": 0.0, "cyan": 0.5, "magenta": 0.4, "yellow": 0.3, "silver": 0.2}]}],
  "splices": [{"splice_id": "S1", "reel_a": "R1", "reel_b": "R2"}]
}
```

## Artifacts under `--out`

| File | Purpose |
|------|---------|
| `continuum_report.json` | case_id, continuum_verdict (`pass`\|`fail`), splices[], output_digest, denscore_digest |
| `continuum_matrix.csv` | header `splice_id,channel,gap,ok` |
| `continuum_summary.log` | lines `VERDICT=...`, `DIGEST=...`, `EPOCH=...` |
| `continuum_state.json` | epoch, cache_digest, last_output_digest, case_id |
| `continuum_history.jsonl` | append-only run lines |
| `continuum_run_ledger.json` | `runs` array with digests |
| `continuum_density_cache.json` | warm density cache between runs |

Successful runs increment `epoch` by 1. Climate changes with the same `case_id`
must recompute densities (cache keys include quantized climate).

## Stateful fields

`continuum_state.json`:

```json
{"epoch": 1, "cache_digest": "...", "last_output_digest": "...", "case_id": "..."}
```

History line:

```json
{"case_id": "...", "epoch": 1, "output_digest": "...", "continuum_verdict": "pass"}
```

Verifier climate-mutation runs may write a temporary `climate-hot.json` under the out directory.
