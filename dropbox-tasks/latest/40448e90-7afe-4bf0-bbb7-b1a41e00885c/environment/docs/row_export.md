# `kv_export.json` layout

Path: `/app/output/kv_export.json`

```json
{
  "profiles": ["p1", "p2"],
  "runs": [
    {
      "profile": "p1",
      "run_index": 0,
      "role_version": 2,
      "content_digest": "<64-char lowercase hex>",
      "delegation_expiry": 1893456000,
      "stage_transcript_hex": "<64-char lowercase hex>"
    }
  ],
  "report_digest": "<64-char lowercase hex>"
}
```

## Top-level fields

| Field | Type | Notes |
|-------|------|-------|
| `profiles` | string array | Sorted unique profile ids touched in the session. |
| `runs` | array | Run observations appended across the session. |
| `report_digest` | string | Digest of the canonical JSON array of all run rows. |

## Run row fields

| Field | Type | Notes |
|-------|------|-------|
| `profile` | string | Profile id (`p1`, `p2`, or `p3`). |
| `run_index` | integer | Zero-based index of this profile within the session. |
| `role_version` | integer | `signed.version` from targets metadata selected on the walk stage for this run step. |
| `content_digest` | string | 64-char lowercase hex fingerprint of bound gate material. |
| `delegation_expiry` | integer | Unix seconds for the active delegation window on this run step. |
| `stage_transcript_hex` | string | 64-char lowercase hex over gate, probe, walk, and admission material. |

Binding formulas, mirror promotion epoch rules, lane quorum, and transcript encoding are in `/app/environment/docs/stage_contract.md`. Profile timelines are in `/app/environment/docs/seed_timelines.md`.
