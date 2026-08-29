# Batch 01 — lean status (for Raja)

**Updated:** 2026-08-29T01:59Z  
**Decision:** Harbor **stopped** on Anthropic **credit-balance-too-low** during Batch 01 cheap Haiku fills. OpenAI `gpt-4o-mini` remains **429 insufficient_quota**. Sonnet second arm was **not started**. Batches 02–05 stay frozen, not run. Do not resume Opus/gpt-5.6-sol 8+8. Do not invent scores.

---

## One paragraph

We froze ten Applied Worlds tasks and verified oracle 10/10. Frontier Opus + GPT-5.6-sol k=8 exists only on pendulum and hypersonic; dyeworks is partial. Cheap Haiku k=5 finished on pendulum (**0/5 valid_fail**). Hypersonic Haiku recorded **0/5** (1 valid_fail + 4 credit infra). Dyeworks Haiku was aborted (**0/3 infra**). Seven other slugs remain haiku **0/1** or wildlife timeout. Booking stays **0/1**. Second arm never started. **Not 50/50. Not 160/160.** Chips use recorded n.

---

## Coverage at a glance

| Task | Oracle | Opus k=8 | GPT k=8 | Haiku | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| repair-the-pendulum-motion-solver | ✓ | **8/8** (6s/1f/1i) | **8/8** (1s/7f) | **0/5** valid_fail | Cheap k=5 ingested |
| hypersonic-fragment-cascade-epoch-atlas | ✓ | **8/8** (7s/1f) | **8/8** (2s/6f) | **0/5** (1 vf + 4 infra) | Credit-too-low on 4 trials |
| the-dyeworks-tool-is-a-command-line-reader-at-app-environmen | ✓ | **7/8** (2s/2f/3i) | **3/8** (0s/2f/1i) | **0/3** infra | Fill aborted; chip 0/3 |
| the-root-ca-that-signed-our-east-west-mtls-credentials-is-co | ✓ | — | — | **0/1** valid_fail | Remain 4 not run |
| apexora-global-wave-3-campus-segmentation-is-blocked-across | ✓ | — | — | **0/1** valid_fail | Remain 4 not run |
| i-need-the-offline-binary-cache-closure-planner-in-app-task | ✓ | — | — | **0/1** valid_fail | Remain 4 not run |
| the-harborlane-replay-desk-needs-a-reusable-offline-planner | ✓ | — | — | **0/1** valid_fail | Remain 4 not run |
| we-re-putting-together-a-stratified-k-fold-evaluation-kit-un | ✓ | — | — | **0/1** valid_fail | Remain 4 not run |
| wildlife-counting-becomes-a-field-planning-game-when-uncerta | ✓ | — | — | timeout | Remain 4 not run |
| booking-slot-merge | ✓ | — | — | **0/1** valid_fail | Chip **0/1** not 0/5 |

**Frozen Batch 01:** 10 tasks.  
**Frontier completed trials** (solved + valid_fail, infra excluded): **37** of 160 planned.  
**Cheap Haiku:** pendulum 0/5; hypersonic 0/5 recorded (4 infra); dyeworks 0/3 infra; six others 0/1. **Sonnet k=5 not started.**  
**Stump formula:** `valid_fail / (solved + valid_fail)` — timeouts and infra excluded.  
**Stop file:** `docs/lab_batch_01_stop.json`.

---

## Spend (Harbor `cost_usd`)

| Bucket | Amount |
| --- | ---: |
| Frontier rollup (prior) | ~$49.67 |
| Haiku booking (prior) | $0.15 |
| Haiku root-CA | $0.25 |
| Haiku Apexora | $0.80 |
| Haiku offline binary-cache | $0.82 |
| Haiku Harborlane | $0.80 |
| Haiku stratified k-fold | $0.28 |
| Haiku wildlife (timeout) | $0.60 |
| **Cheap six + booking** | **~$3.70** |
| Haiku pendulum k=5 | $1.96 |
| Haiku hypersonic k=5 (1 vf + 4 infra) | $0.75 |

OpenAI remains **insufficient_quota**. Anthropic Haiku hit **credit balance too low**. Do not resume Harbor until credits exist.

---

## Recommendation

1. Harbor is **idle**. Do not start a second run. Batch 01 cheap k=5 + second arm is **not complete**.
2. Batches 02–05 jsonl stay frozen. Oracle/measure were not started.
3. Serve `python3 -m http.server 8765 --bind 0.0.0.0` and open `/lab/index.html?surface=catalog&filter=batch`. Chips match recorded n. Spend/Batches show the credit stop.

Full loss themes: `docs/lab_batch_01_loss_analysis.md`.
