# Interval enclosure policy (i9_enclose)

Invariant emission uses a bounded lane buffer before YAML serialization. The runtime lane limit is read from `lane_limit_runtime` in `/app/environment/data/cfg_d9.yaml` during obligation checks.

## Arm budgets

Arm strength bytes occupy offsets 128-130 of each 140-byte tag block. Normalization divides by the sum before MI greedy selection.

## Lane capacity

| field | value | role |
|-------|-------|------|
| lane_limit_runtime | 16 | active emission cap during fold |
| lane_limit_publish | 8 | compile-time publish header only |
| lane_limit_compile | 8 | static target in emitter |

The stock scaffold may read the publish header or compile constant and truncate obligation recs silently when the closure basis exceeds eight elements. Full walk basis size is seven for bundled class codes 10, 11, and 12.

## Enclosure stress

The `q9_cycle` metamorphic loop permutes arm strength bytes and expects non-negative o8 scores and stable row_digest values across cycles.
