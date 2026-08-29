# Batch 01 — lean status (for Raja)

**Updated:** 2026-08-29T01:45Z  
**Decision:** Frontier 8+8 stays stopped (Anthropic credit-too-low on Opus; OpenAI 429 insufficient_quota). Cheap protocol is Haiku k=5 + Sonnet fallback (OpenAI still 429). Pendulum Haiku **0/5** is ingested. Hypersonic Haiku `-k 5` is in flight. Do not resume Opus/gpt-5.6-sol 8+8.

---

## One paragraph

We froze ten Applied Worlds tasks and verified oracle 10/10. Frontier Opus + GPT-5.6-sol k=8 exists only on pendulum and hypersonic; dyeworks is partial. Cheap Anthropic haiku is **HTTP 200**; OpenAI `gpt-4o-mini` remains **429 insufficient_quota**, so the second arm is `anthropic/claude-sonnet-4-5` after Haiku. Pendulum Haiku k=5 finished **0/5 valid_fail** (~$1.96). Six other slugs still have haiku **0/1** (wildlife timeout) until remaining `-k 4` fills run. Booking stays **0/1**. **Not 160/160.** Chips use recorded n.

---

## Coverage at a glance

| Task | Oracle | Opus k=8 | GPT k=8 | Haiku | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| repair-the-pendulum-motion-solver | ✓ | **8/8** (6s/1f/1i) | **8/8** (1s/7f) | **0/5** valid_fail | Cheap k=5 ingested 2026-08-29T01:44Z |
| hypersonic-fragment-cascade-epoch-atlas | ✓ | **8/8** (7s/1f) | **8/8** (2s/6f) | — | Full frontier |
| the-dyeworks-tool-is-a-command-line-reader-at-app-environmen | ✓ | **7/8** (2s/2f/3i) | **3/8** (0s/2f/1i) | — | Partial; Anthropic credit exhausted |
| the-root-ca-that-signed-our-east-west-mtls-credentials-is-co | ✓ | — | — | **0/1** valid_fail | Schedule not exact optimum (3 fixtures) |
| apexora-global-wave-3-campus-segmentation-is-blocked-across | ✓ | — | — | **0/1** valid_fail | Config not authoritative; 7 fail + 263 errors |
| i-need-the-offline-binary-cache-closure-planner-in-app-task | ✓ | — | — | **0/1** valid_fail | Proof `seal` mismatch |
| the-harborlane-replay-desk-needs-a-reusable-offline-planner | ✓ | — | — | **0/1** valid_fail | Plan.hs segment order vs segments.tsv |
| we-re-putting-together-a-stratified-k-fold-evaluation-kit-un | ✓ | — | — | **0/1** valid_fail | stdout JSON + extra path line |
| wildlife-counting-becomes-a-field-planning-game-when-uncerta | ✓ | — | — | timeout | AgentTimeoutError 1800s; not a stump |
| booking-slot-merge | ✓ | — | — | **0/1** valid_fail | Epoch fence / report SPAN; chip **0/1** not 0/8 |

**Frozen Batch 01:** 10 tasks (one Go oracle-fail dropped; replacement passes).  
**Frontier completed trials** (solved + valid_fail, infra excluded): **37** of 160 planned.  
**Cheap haiku:** pendulum **0/5**; six 1-shots + booking 0/1 still short of k=5. OpenAI 429 — second arm is Sonnet after Haiku.  
**Stump formula:** `valid_fail / (solved + valid_fail)` — timeouts and infra excluded.

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

OpenAI remains **insufficient_quota**. Anthropic haiku completed; do not resume Opus 8+8.

---

## Recommendation

1. Pendulum Haiku is **0/5**. Do not pad other chips to /5 until those trials exist.
2. Iterate is filling remaining Haiku (hypersonic `-k 5` in flight), then Sonnet k=5. Do not start a second Harbor.
3. Serve `python3 -m http.server 8765 --bind 0.0.0.0` and open `/lab/index.html?surface=catalog&filter=batch` (10 of 100).

Full loss themes: `docs/lab_batch_01_loss_analysis.md`.
