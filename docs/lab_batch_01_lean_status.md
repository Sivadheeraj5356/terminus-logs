# Batch 01 — lean status (for Raja)

**Updated:** 2026-08-28T21:10Z  
**Decision:** Stop frontier 8+8. Cap hit (~$20 Anthropic budget). Remaining seven packages deliberately **not** frontier-measured.

---

## One paragraph

We froze ten Applied Worlds tasks, verified oracle 10/10, and ran frontier Opus + GPT-5.6-sol k=8 on three tasks before the credit cap stopped spend. Two tasks (pendulum, hypersonic) have full 8+8 with clear loss themes; dyeworks is partial (7 Opus + 3 GPT, heavy credit infra). Seven tasks are oracle-only by choice — not missing data, a budget decision. Harbor-reported spend is ~$50 total (~$48 measure + ~$2 smoke). That is enough for a strong founder draft: worlds are real, oracle is clean, frontier stumps are reproducible on two domains with mid-band variance, and loss analysis names concrete verifier gaps. No batch 02, no remaining 7×16 frontier jobs. Optional later: one cheap-model probe per task (Sonnet/Haiku or gpt-4o-mini, k=1) if we want broader language coverage without Opus burn.

---

## Coverage at a glance

| Task | Oracle | Opus k=8 | GPT k=8 | Notes |
| --- | ---: | ---: | ---: | --- |
| repair-the-pendulum-motion-solver | ✓ | **8/8** (6s/1f/1i) | **8/8** (1s/7f) | Full frontier |
| hypersonic-fragment-cascade-epoch-atlas | ✓ | **8/8** (7s/1f) | **8/8** (2s/6f) | Full frontier |
| the-dyeworks-tool-is-a-command-line-reader-at-app-environmen | ✓ | **7/8** (2s/2f/3i) | **3/8** (0s/2f/1i) | Partial; Anthropic credit exhausted |
| the-root-ca-that-signed-our-east-west-mtls-credentials-is-co | ✓ | — | — | Oracle only (lean) |
| apexora-global-wave-3-campus-segmentation-is-blocked-across | ✓ | — | — | Oracle only (lean) |
| i-need-the-offline-binary-cache-closure-planner-in-app-task | ✓ | — | — | Oracle only (lean) |
| the-harborlane-replay-desk-needs-a-reusable-offline-planner | ✓ | — | — | Oracle only (lean) |
| we-re-putting-together-a-stratified-k-fold-evaluation-kit-un | ✓ | — | — | Oracle only (lean) |
| wildlife-counting-becomes-a-field-planning-game-when-uncerta | ✓ | — | — | Oracle only (lean) |
| booking-slot-merge | ✓ | — | — | Oracle only (lean) |

**Frozen:** 10 tasks (one Go oracle-fail dropped; replacement passes).  
**Frontier completed trials** (solved + valid_fail, infra excluded): **37** of 160 planned.  
**Stump formula:** `valid_fail / (solved + valid_fail)` — timeouts and infra (including credit-balance errors) excluded.

---

## Spend

| Bucket | Harbor `cost_usd` |
| --- | ---: |
| Pendulum Opus | $15.90 |
| Hypersonic Opus | $12.82 |
| Dyeworks Opus | $13.02 |
| Hypersonic GPT | $3.05 |
| Pendulum GPT | $2.36 |
| Dyeworks GPT (partial) | $1.27 |
| Smoke (Opus + GPT) | ~$1.25 |
| **Total** | **~$49.67** |

Measure script and Harbor resume worker are **stopped**. No second Harbor job will start.

---

## Recommendation

1. **Ship the draft report** from pendulum + hypersonic + partial dyeworks + oracle 10/10. BPO proof is worlds + oracle + partial frontier signal, not 160 Opus jobs.
2. **Do not** resume frontier 8+8 on the remaining seven packages.
3. **Optional later:** 1-trial cheap-model smoke (Sonnet/Haiku or gpt-4o-mini) on oracle-only tasks if language breadth matters — only after budget reset.
4. **UI:** Re-ingest is done (`python3 scripts/ingest_lab_jobs.py`). Lab shows real counts — no fake 8/8 on unmeasured tasks.

Full loss themes: `docs/lab_batch_01_loss_analysis.md`.
