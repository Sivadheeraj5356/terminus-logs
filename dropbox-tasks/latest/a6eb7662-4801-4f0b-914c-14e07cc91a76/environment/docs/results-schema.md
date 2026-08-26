# Results schema

## /app/output/composition-results.json

```
{
  "schema_version": 1,
  "coins": [
    {
      "coin_id": "<id>",
      "status": "feasible" | "inconsistent" | "density_only" | "insufficient_data",
      "reason": null | "missing_density" | "missing_xrf_uncertainty" | "empty_intersection",
      "feasible_region": null | {
        "f_au_min": number, "f_au_max": number,
        "f_ag_min": number, "f_ag_max": number,
        "f_cu_min": number, "f_cu_max": number
      }
    }
  ]
}
```

Coins are ordered by coin_id ascending.

## /app/output/derivation-trace.json

Per coin: density_band (point count and fraction extremes over density-satisfying grid points, or null), xrf_bound (six directional bounds or null), intersection_point_count.

## /app/output/inconsistent-coins.json

```
{ "schema_version": 1, "coin_ids": ["..."] }
```

Only status == "inconsistent", sorted ascending.

## /app/output/audit.json

```
{
  "schema_version": 1,
  "coin_count": number,
  "feasible_count": number,
  "inconsistent_count": number,
  "density_only_count": number,
  "insufficient_count": number,
  "assay_bind": "<hex>",
  "ingest_seq": number
}
```
