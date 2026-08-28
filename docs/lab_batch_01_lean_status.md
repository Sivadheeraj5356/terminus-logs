# Batch 01 — lean status (for Raja)

**Updated:** 2026-08-28T21:20Z  
**Decision:** Stop remaining frontier 8+8. Continuation resumed dyeworks Opus, then Anthropic **credit-balance-too-low** again; OpenAI already **insufficient_quota**. Remaining seven packages were **not started** because credits/quota blocked them — not because measure was cancelled as a plan.

---

## One paragraph

We froze ten Applied Worlds tasks, verified oracle 10/10, and ran frontier Opus + GPT-5.6-sol k=8 on pendulum and hypersonic. Dyeworks is partial: Opus 7/8 after a credit-failure resume (2 solved, 2 valid_fail, 3 credit infra, 8th incomplete); GPT 3/8 then OpenAI quota 429. A continuation cheap-probed both APIs, resumed dyeworks Opus, and **stopped when Anthropic 400 credit-too-low returned**. The other seven frozen slugs stay oracle-only because remaining Opus/GPT jobs cannot run until credits/quota are restored. Harbor-reported spend is ~$50. **Not 160/160.** No batch 02.

---

## Coverage at a glance

| Task | Oracle | Opus k=8 | GPT k=8 | Notes |
| --- | ---: | ---: | ---: | --- |
| repair-the-pendulum-motion-solver | ✓ | **8/8** (6s/1f/1i) | **8/8** (1s/7f) | Full frontier |
| hypersonic-fragment-cascade-epoch-atlas | ✓ | **8/8** (7s/1f) | **8/8** (2s/6f) | Full frontier |
| the-dyeworks-tool-is-a-command-line-reader-at-app-environmen | ✓ | **7/8** (2s/2f/3i) | **3/8** (0s/2f/1i) | Partial; Anthropic credit exhausted |
| the-root-ca-that-signed-our-east-west-mtls-credentials-is-co | ✓ | — | — | Oracle only (credits/quota blocked) |
| apexora-global-wave-3-campus-segmentation-is-blocked-across | ✓ | — | — | Oracle only (credits/quota blocked) |
| i-need-the-offline-binary-cache-closure-planner-in-app-task | ✓ | — | — | Oracle only (credits/quota blocked) |
| the-harborlane-replay-desk-needs-a-reusable-offline-planner | ✓ | — | — | Oracle only (credits/quota blocked) |
| we-re-putting-together-a-stratified-k-fold-evaluation-kit-un | ✓ | — | — | Oracle only (credits/quota blocked) |
| wildlife-counting-becomes-a-field-planning-game-when-uncerta | ✓ | — | — | Oracle only (credits/quota blocked) |
| booking-slot-merge | ✓ | — | — | Oracle only (credits/quota blocked) |

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

Harbor is **idle**. Remaining Opus cannot continue until Anthropic credits are added. Remaining GPT cannot continue until OpenAI quota is added.

---

## Recommendation

1. Remaining seven k=8×2 jobs need **new Anthropic credits and OpenAI quota** before they can run. Do not claim 160/160.
2. Dyeworks is still incomplete (Opus 7/8 recorded, GPT 3/8). Resume only after both providers accept a cheap probe.
3. Re-ingest is done. Lab shows real counts — no fake 8/8 on unmeasured tasks.

Full loss themes: `docs/lab_batch_01_loss_analysis.md`.
