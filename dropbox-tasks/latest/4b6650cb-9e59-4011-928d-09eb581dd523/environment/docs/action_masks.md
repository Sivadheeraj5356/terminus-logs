# Action masks and preserve quiesce

Records carry an `action_mask` describing sweep intent. The high bit `PRESERVE` (`0x80000000`) marks entries that must be stripped before overlap testing against the effective sweep mask.

A record is included when `(action_mask & ~PRESERVE) & effective_mask != 0`, where `effective_mask = sweep_mask & overlay_mask` from `/app/environment/ops/overlays/<profile>.json`.
