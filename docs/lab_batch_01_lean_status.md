# Batch 01 — lean status (for Raja)

**Updated:** 2026-08-30T18:24Z  
**Decision:** Harbor **not started** on this resume. Dual-provider probe: Anthropic **credit-balance-too-low** (Haiku and Sonnet); OpenAI **429 insufficient_quota** on `gpt-4o-mini`, `gpt-4o`, `gpt-4.1-mini`, `gpt-4.1-nano`, `gpt-3.5-turbo`. Prior stop archived as `docs/lab_batch_01_stop.20260830T182403Z.json`. Chips unchanged. Batches 02–05 stay frozen, not oracled, not measured. Do not invent scores. Do not start a second `harbor run`.

---

## One paragraph

We froze ten Applied Worlds tasks and verified oracle 10/10. Cheap Haiku k=5 (counted = solved + valid_fail + timeout; infra excluded) is complete on pendulum, hypersonic, root-CA, and Apexora. Hypersonic Haiku chip is **4/9** (4 solved on the resume fill4; 1 earlier valid_fail + 4 credit infra). Dyeworks Haiku is **0/5** recorded (2 valid_fail + 3 infra) and still **need 3** counted. Offline-cache Haiku is **0/5** recorded (3 valid_fail + 2 credit infra) and still **need 2** counted. Harborlane, stratified k-fold, wildlife, and booking stay Haiku **0/1**. OpenAI and Sonnet k=5 never launched. **Not 50/50. Not 160/160.** Chips use recorded n, never padded to 5.

---

## Coverage at a glance

Haiku chip = `solved / recorded` (infra included in the denominator). **Need** = remaining counted trials toward k=5.

| Task | Oracle | Opus k=8 | GPT k=8 | Haiku chip | Counted / need |
| --- | ---: | ---: | ---: | --- | --- |
| repair-the-pendulum-motion-solver | ✓ | **8/8** (6s/1f/1i) | **8/8** (1s/7f) | **0/5** | 5/5 |
| hypersonic-fragment-cascade-epoch-atlas | ✓ | **8/8** (7s/1f) | **8/8** (2s/6f) | **4/9** | 5/5 (4 infra not counted) |
| the-dyeworks-tool-is-a-command-line-reader-at-app-environmen | ✓ | **7/8** (2s/2f/3i) | **3/8** (0s/2f/1i) | **0/5** | 2/5 (need 3) |
| the-root-ca-that-signed-our-east-west-mtls-credentials-is-co | ✓ | — | — | **0/5** | 5/5 |
| apexora-global-wave-3-campus-segmentation-is-blocked-across | ✓ | — | — | **0/5** | 5/5 |
| i-need-the-offline-binary-cache-closure-planner-in-app-task | ✓ | — | — | **0/5** | 3/5 (need 2; stop here) |
| the-harborlane-replay-desk-needs-a-reusable-offline-planner | ✓ | — | — | **0/1** | 1/5 (need 4) |
| we-re-putting-together-a-stratified-k-fold-evaluation-kit-un | ✓ | — | — | **0/1** | 1/5 (need 4) |
| wildlife-counting-becomes-a-field-planning-game-when-uncerta | ✓ | — | — | **0/1** timeout | 1/5 (need 4) |
| booking-slot-merge | ✓ | — | — | **0/1** | 1/5 (need 4) |

**Frozen Batch 01:** 10 tasks.  
**Second arm:** not started (`gpt-4o-mini` and `gpt-4o` 429; Sonnet blocked on the same empty Anthropic balance).  
**Batches 02–05:** jsonl only.  
**Stop file:** `docs/lab_batch_01_stop.json` (reason: both cheap providers blocked; `halt_iterate: true`). Prior stops archived as `docs/lab_batch_01_stop.20260830T130452Z.json` and `docs/lab_batch_01_stop.20260830T182403Z.json`.

---

## Spend (Harbor `cost_usd` from job rollups)

| Bucket | Amount |
| --- | ---: |
| Frontier + smoke rollup | **$49.67** |
| All Haiku jobs (1-shots + fills) | **$15.33** |
| **All ingested Harbor jobs** | **$65.00** |

Resume fills (30 Aug): hypersonic fill4 **$0.96** (4/4 solved); dyeworks fill5 **$0.88** (2 valid_fail + reused infra); root-CA fill4 **$1.36**; Apexora fill4 **$2.50**; offline fill4 **$3.23** (2 valid_fail + 2 credit infra). Pendulum Haiku k=5 remains **$1.96**.

OpenAI remains **insufficient_quota** on every probed slug including `gpt-4o`. Anthropic Haiku/Sonnet still **credit balance too low** at 2026-08-30T18:24Z. Do not resume Harbor until credits exist.

---

## Recommendation

1. Harbor is **idle**. Do not start a second run. Batch 01 cheap k=5 + second arm is **not complete**.
2. Batches 02–05 jsonl stay frozen. Oracle/measure were not started.
3. Serve `python3 -m http.server 8765 --bind 0.0.0.0` and open `/lab/index.html?surface=catalog&filter=batch`. Chips match recorded n (hypersonic Haiku **4/9**, not 4/5; booking **0/1**, not 0/5). Spend/Batches show the credit stop.

Full loss themes: `docs/lab_batch_01_loss_analysis.md`.
