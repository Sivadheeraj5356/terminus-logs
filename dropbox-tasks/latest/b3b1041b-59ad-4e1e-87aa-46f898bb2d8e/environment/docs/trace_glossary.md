# Trace glossary

Status tokens used in sampled traces and fixture HUD:

- `w_ok`: local witness path produced a plan row
- `w_skip`: witness path declined a plan row
- `g_pass`: independent gate accepted
- `g_hold`: independent gate held
- `hud_only`: stage tally, not a graded digest field

Row identity uses `tid`. Key material identity uses `kid`. Epoch tags use `e_tag` values `e_hi` or `e_lo`.

## Rotation journal fold

`/app/environment/data/p39/rot.log` is an append-only JWK rotation journal. Graded gate bands are the fold of that journal, not the scratch `cur` cache.

Event lines are whitespace-separated fields written as `key=value`. Required fields: `evt`, `epoch`, `kid`, `op`, `note`. Comment lines begin with `#`.

Fold rules:

1. Process events in ascending `evt` order.
2. Maintain independent allow and rev sets per `epoch`.
3. Operation `pin` adds `kid` to allow and removes it from rev.
4. Operation `rev` adds `kid` to rev and removes it from allow.
5. Discard an event when `note` matches `slot_N` and `N` modulo 11 equals 7 (poison or noise slots). Those events must not affect allow or rev.
6. `/app/environment/data/p39/pin_table.toml` is a checkpoint of a correct fold for restore and cross-check; live graded acceptance must track the journal. Appending a journal event can change gate outcomes even when the pin table file is unchanged.

Fold results may be cached under `/app/environment/r43/.scratch/fold_cache.json`. Lane bind caches may live under `/app/environment/r43/.scratch/lane`. Cache entries must invalidate when `rot.log` is newer than the cache file (mtime), and after `rst9.sh` clears scratch.
