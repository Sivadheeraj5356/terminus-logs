# Mount slice byte layout (64 bytes)

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | magic `OVG1` |
| 4 | 1 | flags (bit0 whiteout merge, bit1 opaque, bit2 nested bind) |
| 5 | 2 | id_a (u16 LE) |
| 7 | 2 | id_b (u16 LE) |
| 9 | 2 | id_c (u16 LE) |
| 11 | 2 | pair_gap (u16 LE) |
| 13 | 16 | anchor bytes |
| 29 | 32 | payload |
| 61 | 3 | reserved zero |

Authoritative slices live at `/app/environment/kit/blk/tc.mnt` and `/app/environment/kit/blk/td.mnt`.
Log tails under `kit/logs/` are partial excerpts only.
