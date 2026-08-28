# Batch 01 loss analysis

Generated 2026-08-28T21:10Z from Harbor `jobs/` via `scripts/ingest_lab_jobs.py`.  
`stump_pct = valid_fail / (solved + valid_fail) × 100`. Timeout and infra are excluded. No Caudal/SSB scores. No rubric channel.

## Headlines

- **Frozen batch 01: 10 tasks.** Go oracle-fail `release-still-signs-edge-go-mod-q1-green-while-the-dependenc` (reward 0.0, 5 `TestLiveProxyIntegrity` failures) was dropped and replaced by `i-need-the-offline-binary-cache-closure-planner-in-app-task` (oracle 1.0). See `docs/lab_batch_01_exclusions.json`.
- **Oracle: 10/10 reward 1.0** on the frozen ten.
- **Frontier 8+8 stopped by budget decision.** Cap hit mid-task-3 (dyeworks). Harbor resume worker killed; no batch 02; no remaining 7×16 frontier jobs.
- **Frontier agent coverage:** 2 tasks full 8+8 (pendulum, hypersonic); 1 task partial (dyeworks); **7 tasks oracle-only** (deliberately unmeasured on frontier).
- **Frontier completed trials:** 37 of 160 planned (solved + valid_fail only).
- Smoke extras (not in the 160): 2 pendulum smoke trials (Opus compose solved, GPT valid fail) plus 1 failed Opus smoke (compose plugin missing, infra).

## Frontier k=8 (stopped at 37/160 completed)

| Task | Model | n | solved | valid_fail | timeout | infra | stump% |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| repair-the-pendulum-motion-solver | anthropic/claude-opus-5 | 8 | 6 | 1 | 0 | 1 | **14.3** |
| repair-the-pendulum-motion-solver | openai/gpt-5.6-sol | 8 | 1 | 7 | 0 | 0 | **87.5** |
| repair-the-pendulum-motion-solver | both | 16 | 7 | 8 | 0 | 1 | **53.3** |
| hypersonic-fragment-cascade-epoch-atlas | anthropic/claude-opus-5 | 8 | 7 | 1 | 0 | 0 | **12.5** |
| hypersonic-fragment-cascade-epoch-atlas | openai/gpt-5.6-sol | 8 | 2 | 6 | 0 | 0 | **75.0** |
| hypersonic-fragment-cascade-epoch-atlas | both | 16 | 9 | 7 | 0 | 0 | **43.8** |
| the-dyeworks-tool-is-a-command-line-reader-at-app-environmen | anthropic/claude-opus-5 | 7 | 2 | 2 | 0 | 3 | **50.0** |
| the-dyeworks-tool-is-a-command-line-reader-at-app-environmen | openai/gpt-5.6-sol | 3 | 0 | 2 | 0 | 1 | **100.0** |
| the-dyeworks-tool-is-a-command-line-reader-at-app-environmen | both (partial) | 10 | 2 | 4 | 0 | 4 | **66.7** |
| **measured total** | **both** | **42 slots** | **18** | **19** | **0** | **5** | **51.4** |

Seven frozen tasks have **no** frontier k=8 rows (oracle only, lean): root-CA mTLS (C++), Apexora campus (Bash), offline binary-cache (Go), Harborlane replay (Haskell), stratified k-fold (Java), wildlife counting (JavaScript), booking-slot-merge (Rust).

Footnote (reward-first classify, same as `scripts/lab_common.py`): pendulum Opus trial `…__yAuWxNK` has verifier **reward 1.0** and `AgentTimeoutError` after 1800s. It is **solved**, not timeout. Dyeworks Opus trial `…__uZFqDH3` similarly scored reward 1.0 with timeout after solve.

## What ingest / the lab UI actually stores

`docs/lab_batch_01_results.json` and `lab/corpus.json` union **all** matching Harbor rows (oracle + smoke + k=8). Task-level `stump_pct` therefore includes oracle on mixed rows.

| Slug | Ingest n | solved | valid_fail | timeout | infra | stump% | Agent trials? |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| repair-the-pendulum-motion-solver | 20 | 9 | 9 | 0 | 2 | 50.0 | yes (Opus n=10, GPT n=9) |
| hypersonic-fragment-cascade-epoch-atlas | 17 | 10 | 7 | 0 | 0 | 41.2 | yes (8+8) |
| the-dyeworks-tool-is-a-command-line-reader-at-app-environmen | 11 | 3 | 4 | 0 | 4 | 57.1 | partial (Opus 7, GPT 3) |
| the-root-ca-that-signed-our-east-west-mtls-credentials-is-co | 1 | 1 | 0 | 0 | 0 | — | no (oracle only) |
| apexora-global-wave-3-campus-segmentation-is-blocked-across | 1 | 1 | 0 | 0 | 0 | — | no |
| i-need-the-offline-binary-cache-closure-planner-in-app-task | 1 | 1 | 0 | 0 | 0 | — | no |
| the-harborlane-replay-desk-needs-a-reusable-offline-planner | 1 | 1 | 0 | 0 | 0 | — | no |
| we-re-putting-together-a-stratified-k-fold-evaluation-kit-un | 1 | 1 | 0 | 0 | 0 | — | no |
| wildlife-counting-becomes-a-field-planning-game-when-uncerta | 1 | 1 | 0 | 0 | 0 | — | no |
| booking-slot-merge | 1 | 1 | 0 | 0 | 0 | — | no |

Stump% in this table is omitted for oracle-only rows (`completed` agent trials = 0). Lab chips show `oracle` for those seven — not fake 8/8.

## Loss themes (from `verifier/test-stdout.txt` + trajectories)

Every valid-fail ran pytest (or equivalent). None were empty, wrapper-only, or “never ran tests.” Builds succeeded on the failing rows.

### Pendulum — wrong capture cadence (GPT, 7/8 k=8 + smoke)

GPT recovered **0.450 Hz / 0.175 s⁻¹** against ground truth **0.9 Hz / 0.35 s⁻¹** (~50% relative error) on `test_frequency_within_tolerance`, `test_decay_within_tolerance`, and `test_report_stdout_matches_snapshot`. Trajectories repeatedly treat **dt = 0.1 s** as the cadence; that halves frequency and decay versus the seeded 20 fps / 0.05 s world. Agents then declare the run “validated” from their own checks.

The one GPT k=8 **solve** (`…__CKm2C9a`) passed all 8 tests.

### Pendulum — extra Graphviz vertex (Opus 1/8 k=8; some GPT fails too)

Opus fail `…__fzbUafx`: **7 passed, 1 failed** — frequencies/decays were in tolerance (report printed 0.904 / 1.302 / 1.754 / 2.204 Hz) but `test_graph_node_count_matches_edges` saw **193 DOT vertices vs 192 `recovery_edges` rows**. Three GPT fails have the same 193 vs 192 miss stacked on the cadence error.

### Pendulum — infra (excluded from stump)

- Smoke `lab-smoke-opus`: Docker Compose v2 missing (`unknown flag: --project-name`). Later smoke with the plugin installed solved.
- k=8 `…__az2J4Ya`: Anthropic **credit balance too low** (HTTP 400) mid-loop.

### Hypersonic — reference hash / epoch time (GPT 6/8, Opus 1/8)

GPT valid fails are **identical: 5 failed, 15 passed**. Tests that fail:

- `test_bravo_catalog_override_dir` — `ledger_hash` ≠ reference
- `test_alpha_collision_occurs_and_matches_reference` — atlas and/or ledger hash ≠ reference
- `test_flare_absolute_density_scale_not_multiplicative` — hidden `/opt/verifier-fixtures/flare-trap`; `t_sec` **0.05 vs 0.0**
- `test_hidden_chain_reaction_independent_of_bundled` — `ledger_hash` ≠ reference
- `test_ledger_epochs_match_reference_timestamps` — `t_sec` **0.05 vs 0.0**

Agents’ last analyses claim the TypeScript pipeline is complete after checking the **bundled** catalog. Hidden fixtures and epoch timestamps still disagree.

Opus fail `…__24tWaEA`: **19 passed, 1 failed** (`test_alpha_collision_occurs_and_matches_reference`, atlas_hash mismatch only). Two GPT k=8 trials passed all 20 tests.

### Dyeworks — parser bounds / section validation (partial; GPT 2/3 valid fail)

GPT valid fails (2 of 3 completed): agents identify real gaps (ULEB decoders ignore section bounds, missing container-version check, duplicate section names, offset+size vs file length, uint32 overflow in node allocation, unbounded tree depth) but patches do not pass hidden invalid fixtures. Trajectories show correct diagnosis of `sectab.c` and `uleb.c` weaknesses; verifier still rejects malformed inputs.

Opus: 2 solves (including one post-timeout reward 1.0), 2 valid fails, 3 **credit-balance-too-low** infra (excluded from stump). Job stopped at 7/8 Opus; GPT job stopped at 3/8.

## Spend and stop state

| Item | State |
| --- | --- |
| Harbor frontier measure | **Stopped** — resume worker killed 2026-08-28T21:10Z |
| Remaining 7 packages | **Not measured** on frontier (lean; by choice) |
| Batch 02 | **Not started** |
| Harbor-reported spend | **~$49.67** (~$48 measure jobs + ~$2 smoke) |
| Anthropic credits | **Exhausted** for new Opus jobs; skip new Anthropic until budget reset |
| Docker / Harbor 0.22 | Up |

## Recommendation

- **Stop frontier 8+8.** Mid-band variance thesis does not justify 8+8 on all ten at this budget; stats from 32 full + partial dyeworks are sufficient for a founder draft.
- **BPO proof** = frozen worlds + oracle 10/10 + reproducible stumps on pendulum/hypersonic + partial C security signal — not 160 Opus jobs.
- **Optional later:** 1-trial cheap-model probe (Sonnet/Haiku or gpt-4o-mini) per oracle-only task if language breadth is needed.
- **Applied Worlds R&D** can wait until profitable; this batch is not required for a BPO.

## What the founder sees after this ingest

Serve from repo root (`python -m http.server 8765`) and open:

- Batch table: [`/lab/index.html?surface=tasks&filter=batch`](../lab/index.html?surface=tasks&filter=batch)
- Pendulum: [`/lab/index.html?task=repair-the-pendulum-motion-solver`](../lab/index.html?task=repair-the-pendulum-motion-solver)
- Hypersonic: [`/lab/index.html?task=hypersonic-fragment-cascade-epoch-atlas`](../lab/index.html?task=hypersonic-fragment-cascade-epoch-atlas)
- Dyeworks: [`/lab/index.html?task=the-dyeworks-tool-is-a-command-line-reader-at-app-environmen`](../lab/index.html?task=the-dyeworks-tool-is-a-command-line-reader-at-app-environmen)
- Agents: [`/lab/index.html?surface=agents`](../lab/index.html?surface=agents)

Chips reflect **recorded** trials, not planned 8/8:

- Pendulum: Opus 7/8 k=8 solves + 1 smoke solve; GPT 1/8 k=8
- Hypersonic: Opus 7/8; GPT 2/8
- Dyeworks: Opus 2/7 completed (partial); GPT 0/3 completed (partial)
- Other seven batch rows: `oracle` only

The other 90 gallery rows stay **not run**. Refresh the lab after ingest; live `jobs/` is gitignored.
