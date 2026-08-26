# Formal rules

Observable policy for the offline bond ARP-monitor reconcile. These describe required behavior, not patch locations.

## Membership and rows

1. Active lanes are the identifiers in `/app/environment/docs/member_ids.txt` that also appear in `/app/environment/meta/staging.json`. Staging-only ids (including underscore-prefixed heldouts) must never become rows. All six listed members must survive. **Report row array order is not a contract**; consumers look up rows by `lane_id`. Digest material may use the id-list sequence below without requiring the JSON `rows` array to mirror that order.

## Prep, ARP journal, and membership digest

2. Prep advances `runtime_state.json` epoch by exactly one (1 becomes 2, 2 becomes 3), applies ARP-monitor pressure decay at most once per lane (`pending = max(0, pending - 1)`, so a lane at 1 reaches 0), and writes one `/app/output/arp_journal.jsonl` line per lane carrying epoch, membership digest, and `pending_after_decay`.

3. Membership digest is the first 16 lowercase hex characters of MD5 over `bond|` plus the active lane ids joined by commas in the sequence listed in `member_ids.txt`.

## Seal merge isolation

4. Seal merges journal pressure only when journal epoch **and** membership digest both still match the live state; a lane whose journal line differs in either field is isolated and falls back to `max(fixture, persisted)` without a second decay.

## Session journal epochs

5. Session journal (`/app/output/run_traces/session.journal`) stores `epoch`, `compile_fp`, `membership_digest`, and `replay_ack`, each exactly once — rewrites replace the file, they never append duplicate field lines. Prep writes/updates `epoch` together with the fingerprint fields. Seal with hook replay must leave the same `epoch` readable and set `replay_ack=1` when the fingerprint confirms; a full prep→seal cycle must keep that epoch stable across the seal phase.

## Lineage ledger and settle chain

5a. The durable lineage ledger `/app/environment/meta/lineage.json` stores `pack_epoch`, `settle_epoch`, `seed`, `chain_prev`, `chain_bind`, and `last_matrix`. It survives output resets: clearing `/app/output` does not clear lineage. Prep advances `pack_epoch` by exactly one and records the prep `--variant-seed` in `seed`. A seal can settle only against a prep-recorded seed and `pack_epoch >= 1`.

5b. When a seal settles, `settle_epoch` becomes the current `pack_epoch`. If that settle carries a new matrix digest or a new settle epoch, the chain extends: `chain_prev` takes the previous `chain_bind`, `last_matrix` takes the report `matrix_digest`, and `chain_bind` is MD5[:16] of `fold(chain_prev) + "|" + matrix_digest + "|" + settle_epoch` where the fold carries the previous bind through **unchanged**. An idempotent re-seal (same matrix, same settle epoch) must leave all three chain fields untouched.

5c. The report summary mirrors the ledger: `summary.pack_epoch`, `summary.settle_epoch`, and `summary.chain_bind` must equal the ledger values after a settled seal, with `settle_epoch == pack_epoch >= 1`.

5d. A poisoned ledger — non-empty `chain_bind` that does not recompute from `chain_prev`, `last_matrix`, and `settle_epoch` by the equation in 5b — must refuse to settle until the ledger is reset to the zero lineage (`pack_epoch=0`, `settle_epoch=0`, `seed=-1`, empty chain fields).

## Mismatch in digest

6. `compile_fp` is MD5[:16] of `notes|triple|seed` where `notes` is the comma-joined active lane set (same sequence as `member_ids.txt`), `seed` is the workflow `--variant-seed`, and **`triple` is looked up from `/app/environment/data/rank_tbl.toml` for that same seed** (the `[[triples]]` entry whose `seed` equals `--variant-seed`; its `triple` string is the material). Seal with hook replay must confirm the fingerprint then set `replay_ack=1`. A missing, stale, or mismatched `compile_fp` / `membership_digest` in the session journal must not settle.

## Mismatch in seed

7. Profile aliases: `--profile compile` is equivalent to `prep`; `--profile verify --hook replay` is equivalent to `seal`. Use the same `--variant-seed` for both phases of a workflow. Prep and seal with mismatched seeds produce divergent fingerprints / facets and must not settle as a coherent pair. Verify/seal alone must not settle.

## Facets and matrix digest

8. Row `facet_hex` is MD5[:16] of `canonical|triple|reloc|weight` where canonical strips a trailing `_echo`, reloc is `g{N}` after a flushed generation advance (bundled workflow: start 1, flush once → `g2`), and weight comes from bump/perm tables. **The `triple` in that equation is the same seed-keyed lookup used for `compile_fp`:** read `/app/environment/data/rank_tbl.toml` and take the `triple` for the **current** `--variant-seed` (do not hard-code a host triple or reuse a stale seed's triple). Mirror pairs share identical facets when settled.

9. `summary.matrix_digest` is MD5[:16] over **sorted** `lane_id|facet_hex|loc_rc|img_rc|bind_rc` rows joined by `|`. Sorting by `lane_id` is part of the digest equation so emitters need not place JSON rows in any particular array order. Coherent rows require `lag_code=0` and `loc_rc=img_rc=bind_rc=1`. `span_band` is the max absolute lag. `loc_rc` is 1 only when membership admit succeeds **and** the order gate accepts the miimon/targets byte prefixes `M0|` and `T1|` respectively.

## Seal bindings and gate

10. Seal bindings under `/app/environment/meta/seal.bin` replace in place and
    collapse duplicate permits for the same lane id to a single line; repeated
    workflows must not leave duplicate keys. `bind_rc` is 1 only when exactly one
    live binding matches the emitted facet.

11. Seal gate requires `sync_label=settled`, at least one row with numeric
    `img_rc` equal to 1 (exact integer match — values such as `10` must not
    satisfy the predicate), and a flow digest derived from the session journal
    bytes. A gate that always rejects must leave the report unsettled.

12. Status probe (`bond_probe`) prints `label=<settled|pending> converged=<0|1>`.
    Settled only when the report's `sync_label` is settled **and** at least one
    row has `img_rc` equal to `1` by exact integer field match; otherwise pending.
    Prep-only reports must remain pending.

    The probe and gate consume any valid JSON serialization of the report, not
    only the driver's own output. Field matching must be whitespace-agnostic:
    compact form (`"img_rc":1`, `"sync_label":"settled"`) and spaced form
    (`"img_rc": 1`, `"sync_label": "settled"`) are the same document and must
    evaluate identically. Matching a fixed byte substring of one serialization
    does not satisfy this rule.

## q2m refresh durability

13. Every driver invocation restores policy bodies from `/app/environment/q2m/`
    onto the live trees before rebuild. Policy that does not survive that refresh
    is not durable. Recover via `/app/environment/scripts/v2_recover.sh` must still
    seal cleanly afterward with the same coherent matrix outcome, and — because
    the lineage ledger persists across recover — the first settle after recover
    must extend the existing chain (`chain_prev` equal to the pre-recover
    `chain_bind`), not restart it.

## Existence of vx_run

14. After a successful cmake build (and after recover), `/app/environment/build/vx_bond`,
    `/app/environment/build/bond_probe`, and `/app/bin/vx_run` must exist and be
    executable. `/app/bin/vx_run` is the installed copy of `vx_bond` used by
    `/app/environment/docs/run_cmds.txt`.
