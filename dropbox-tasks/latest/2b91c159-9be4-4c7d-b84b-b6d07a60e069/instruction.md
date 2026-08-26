The lab's checkpointed integrator ships a broken `demo_engine` binary under `/app/build`. Coupled defects across checkpoint restore, pair-evaluation ledger accounting, periodic wrap crossing tally, journal CRC folding, and wrap-epoch reduction leave recovery reports off-spec. Repair the C++ sources under `/app/environment` so a clean CMake release rebuild produces a deterministic emitter again.

Run `/app/build/demo_engine emit <scene_token> /app/output/recovery_report.json` after rebuilding from `/app/environment`. Nine bundled trials use scene tokens `Q0` through `Q8`. Each emitted JSON must echo the requested `scene_token` and include integer fields `ledger_tail`, `wrap_epoch`, `refresh_stamp`, `segment_generation`, `journal_crc32`, plus floating `scalar_near` and `addon_aux`.

Checkpoint trials also support journal replay:

```bash
/app/build/demo_engine journal freeze <QTOKEN> /tmp/snap.bin
/app/build/demo_engine journal thaw <QTOKEN> /tmp/snap.bin /tmp/report.json
```

Thawed reports must byte-match direct `emit` output for the same token.

## Pass condition

The verifier rebuilds your tree, reruns every scene token under scrambled order, rebuild isolation, journal thaw replay, trace/emit cross-checks, and composite digest locks, then compares each report field against an independently computed expected model. **Exact numeric agreement is required on all eight fields for every token.**

**Partial repairs fail.** Fixing only ledger accounting while leaving journal CRC, wrap epoch, or segment generation wrong produces plausible monotonic ordering on some fields while individual tokens still fail. Treat any got/want mismatch as an incomplete repair and keep investigating across the subsystems documented in `/app/environment/docs/integrator_semantics.md` until all nine tokens pass in one rebuild cycle.

## Required verification

Use the mounted evaluator gate — do not stop after manual spot checks or self-authored substitutes:

```bash
bash /tests/test.sh
```

`/tests/test.sh` is mounted during agent execution and is the only authoritative pass gate. Do not write a replacement `/tests/test.sh` or hardcode expected field values from your own binary output.

For quick iteration while editing:

```bash
bash /app/environment/scripts/emit_matrix.sh
```

Normative field semantics, checkpoint schedules, journal CRC rules, and ledger formulas live in `/app/environment/docs/integrator_semantics.md` and `/app/environment/docs/runtime_contract.txt`. Trial horizons are fixed per scene token in those docs — repair accounting semantics there; do not retune step counts to chase scalar mismatches.

## Observable constraints

- `ledger_tail` accumulates neighbor-list and wrap accounting across each trial's full horizon. After a correct repair it strictly decreases from `Q0` through `Q8`; exact per-token integers are required, not approximate ordering.
- Trials `Q1`, `Q3`, `Q4`, `Q5`, `Q6`, `Q7`, and `Q8` checkpoint mid-horizon and resume; `Q0` and `Q2` run uninterrupted. Pause/resume trials must report `segment_generation` of 1 after restore.
- `scalar_near` is the min-image pair-distance sum at the final wrapped geometry (cutoff 36.0 on squared distance, box edge 11.0). It follows each token's configured step count documented in `/app/environment/docs/integrator_semantics.md` — shorter horizons such as `Q8` (110 steps) can yield lower sums than longer trials despite a higher token index.
- `addon_aux` must be zero for every trial except `Q5`, where post-resume churn drives a nonzero encode of the final body positions.
- `journal_crc32` folds ledger tail, orbit crossings, refresh stamp, and segment generation — ledger-only fixes leave this field wrong on checkpoint trials.
- `wrap_epoch` mixes folded orbit crossings with segment generation; it is not a raw crossing count.

Hand-writing `/app/output/recovery_report.json`, editing `/tests`, or wrapper-only changes are insufficient — the normal rebuild-and-emit pipeline must regenerate matching reports on every run and output path.
