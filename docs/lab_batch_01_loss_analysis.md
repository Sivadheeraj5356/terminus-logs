# Batch 01 loss analysis

Generated 2026-08-28T18:03Z from Harbor `jobs/` via `scripts/ingest_lab_jobs.py`.  
`stump_pct = valid_fail / (solved + valid_fail) × 100`. Timeout and infra are excluded. No Caudal/SSB scores. No rubric channel.

## Headlines

- **Frozen batch 01: 10 tasks.** Go oracle-fail `release-still-signs-edge-go-mod-q1-green-while-the-dependenc` (reward 0.0, 5 `TestLiveProxyIntegrity` failures) was dropped and replaced by `i-need-the-offline-binary-cache-closure-planner-in-app-task` (oracle 1.0). See `docs/lab_batch_01_exclusions.json`.
- **Oracle: 10/10 reward 1.0** on the frozen ten.
- **Agent trials toward the 160 (10 × 8 Opus + 8 gpt-5.6-sol): 32/160 recorded.** Two tasks have both k=8 groups. Task 3 (dyeworks) Opus k=8 is in flight and is **not** in these 32.
- Smoke extras (not in the 160): 3 pendulum trials (Opus compose solved, Opus first-pass infra, GPT valid fail).
- **Tasks with agent `completed_trials ≥ 1`:** pendulum, hypersonic. The other eight frozen slugs are oracle-only so far — do not read their ingest `stump_pct` 0.0 as a model result.

## Frontier k=8 (the 160)

| Task | Model | n | solved | valid_fail | timeout | infra | stump% |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| repair-the-pendulum-motion-solver | anthropic/claude-opus-5 | 8 | 6 | 1 | 0 | 1 | **14.3** |
| repair-the-pendulum-motion-solver | openai/gpt-5.6-sol | 8 | 1 | 7 | 0 | 0 | **87.5** |
| repair-the-pendulum-motion-solver | both | 16 | 7 | 8 | 0 | 1 | **53.3** |
| hypersonic-fragment-cascade-epoch-atlas | anthropic/claude-opus-5 | 8 | 7 | 1 | 0 | 0 | **12.5** |
| hypersonic-fragment-cascade-epoch-atlas | openai/gpt-5.6-sol | 8 | 2 | 6 | 0 | 0 | **75.0** |
| hypersonic-fragment-cascade-epoch-atlas | both | 16 | 9 | 7 | 0 | 0 | **43.8** |
| **two-task total** | **both** | **32** | **16** | **15** | **0** | **1** | **48.4** |

Eight frozen tasks have **no** k=8 agent rows yet (oracle only): dyeworks (C), root-CA mTLS (C++), Apexora campus (Bash), offline binary-cache (Go), Harborlane replay (Haskell), stratified k-fold (Java), wildlife counting (JavaScript), booking-slot-merge (Rust).

Footnote (reward-first classify, same as `scripts/lab_common.py`): pendulum Opus trial `…__yAuWxNK` has verifier **reward 1.0** and `AgentTimeoutError` after 1800s. It is **solved**, not timeout. Harbor’s job rollup counted two pendulum Opus errors; ingest counts one infra (credit) and this passing timeout as solved.

## What ingest / the lab UI actually stores

`docs/lab_batch_01_results.json` and `lab/corpus.json` union **all** matching Harbor rows (oracle + smoke + k=8). Task-level `stump_pct` therefore includes oracle on mixed rows.

| Slug | Ingest n | solved | valid_fail | timeout | infra | stump% | Agent trials? |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| repair-the-pendulum-motion-solver | 20 | 9 | 9 | 0 | 2 | 50.0 | yes (Opus n=10, GPT n=9) |
| hypersonic-fragment-cascade-epoch-atlas | 17 | 10 | 7 | 0 | 0 | 41.2 | yes (8+8) |
| the-dyeworks-tool-is-a-command-line-reader-at-app-environmen | 1 | 1 | 0 | 0 | 0 | — | no (oracle only; Opus k=8 running) |
| the-root-ca-that-signed-our-east-west-mtls-credentials-is-co | 1 | 1 | 0 | 0 | 0 | — | no |
| apexora-global-wave-3-campus-segmentation-is-blocked-across | 1 | 1 | 0 | 0 | 0 | — | no |
| i-need-the-offline-binary-cache-closure-planner-in-app-task | 1 | 1 | 0 | 0 | 0 | — | no |
| the-harborlane-replay-desk-needs-a-reusable-offline-planner | 1 | 1 | 0 | 0 | 0 | — | no |
| we-re-putting-together-a-stratified-k-fold-evaluation-kit-un | 1 | 1 | 0 | 0 | 0 | — | no |
| wildlife-counting-becomes-a-field-planning-game-when-uncerta | 1 | 1 | 0 | 0 | 0 | — | no |
| booking-slot-merge | 1 | 1 | 0 | 0 | 0 | — | no |

Stump% in this table is omitted for oracle-only rows (`completed` agent trials = 0). Lab chips still show `oracle` for those eight.

## Loss themes (from `verifier/test-stdout.txt` + trajectories)

Every valid-fail ran pytest. None were empty, wrapper-only, or “never ran tests.” Builds (`python recover_motion.py`, `tsc`) succeeded on the failing rows.

### Pendulum — wrong capture cadence (GPT, 7/8 k=8 + smoke)

GPT recovered **0.450 Hz / 0.175 s⁻¹** against ground truth **0.9 Hz / 0.35 s⁻¹** (~50% relative error) on `test_frequency_within_tolerance`, `test_decay_within_tolerance`, and `test_report_stdout_matches_snapshot`. Trajectories repeatedly treat **dt = 0.1 s** as the cadence; that halves frequency and decay versus the seeded 20 fps / 0.05 s world. Agents then declare the run “validated” from their own checks.

The one GPT k=8 **solve** (`…__CKm2C9a`) passed all 8 tests.

### Pendulum — extra Graphviz vertex (Opus 1/8 k=8; some GPT fails too)

Opus fail `…__fzbUafx`: **7 passed, 1 failed** — frequencies/decays were in tolerance (report printed 0.904 / 1.302 / 1.754 / 2.204 Hz) but `test_graph_node_count_matches_edges` saw **193 DOT vertices vs 192 `recovery_edges` rows**. Three GPT fails have the same 193 vs 192 miss stacked on the cadence error.

### Pendulum — infra (excluded from stump)

- Smoke `lab-smoke-opus`: Docker Compose v2 missing (`unknown flag: --project-name`). Later smoke with the plugin installed solved.
- k=8 `…__az2J4Ya`: Anthropic **credit balance too low** (HTTP 400) mid-loop. Later Opus jobs on hypersonic completed, and dyeworks Opus is running, so this was not a hard stop.

### Hypersonic — reference hash / epoch time (GPT 6/8, Opus 1/8)

GPT valid fails are **identical: 5 failed, 15 passed**. Tests that fail:

- `test_bravo_catalog_override_dir` — `ledger_hash` ≠ reference
- `test_alpha_collision_occurs_and_matches_reference` — atlas and/or ledger hash ≠ reference
- `test_flare_absolute_density_scale_not_multiplicative` — hidden `/opt/verifier-fixtures/flare-trap`; `t_sec` **0.05 vs 0.0**
- `test_hidden_chain_reaction_independent_of_bundled` — `ledger_hash` ≠ reference
- `test_ledger_epochs_match_reference_timestamps` — `t_sec` **0.05 vs 0.0**

Agents’ last analyses claim the TypeScript pipeline is complete after checking the **bundled** catalog. Hidden fixtures and epoch timestamps still disagree.

Opus fail `…__24tWaEA`: **19 passed, 1 failed** (`test_alpha_collision_occurs_and_matches_reference`, atlas_hash mismatch only). Two GPT k=8 trials passed all 20 tests.

## Running vs blocked

| Item | State |
| --- | --- |
| Harbor process | **Running** (do not start a second one): `harbor run` Opus k=8 on dyeworks, job `lab01-opus-the-dyeworks-tool-is-a-command-line-`, concurrency 1 |
| Sequential measure | `/tmp/run_lab_measure.py` `STOP_AFTER=3`. After dyeworks Opus it will start dyeworks GPT k=8, then stop. **Batch 02 is not started.** |
| Spend after 2 full tasks | **$34.14** (pendulum ~$18.26, hypersonic ~$15.88). Under the runner’s $40-after-task-2 brake, so task 3 started. 160 remaining overnight is still the wrong claim. |
| Keys | Present in the Harbor shell (not printed). One historical Anthropic credit-low infra; not currently blocking. |
| Docker / Harbor 0.22 | Up. |

## What the founder sees after this ingest

Serve from repo root (`python -m http.server 8765`) and open:

- Batch table: [`/lab/index.html?surface=tasks&filter=batch`](../lab/index.html?surface=tasks&filter=batch)
- Pendulum: [`/lab/index.html?task=repair-the-pendulum-motion-solver`](../lab/index.html?task=repair-the-pendulum-motion-solver)
- Hypersonic: [`/lab/index.html?task=hypersonic-fragment-cascade-epoch-atlas`](../lab/index.html?task=hypersonic-fragment-cascade-epoch-atlas)
- Agents: [`/lab/index.html?surface=agents`](../lab/index.html?surface=agents)

Chips are **solved / 8 planned**, not “recorded / 8”:

- Pendulum: `Opus 5 7/8` (6 k=8 solves + 1 smoke solve) and `GPT-5.6-sol 1/8`
- Hypersonic: `Opus 5 7/8` and `GPT-5.6-sol 2/8`
- Other eight batch rows: `oracle` only until k=8 jobs finish and are ingested again

The other 90 gallery rows stay **not run**. Refresh the lab after the next ingest; live `jobs/` is gitignored and does not appear until classify.
