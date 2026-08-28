# Batch 01 loss analysis

Generated 2026-08-28T21:20Z from Harbor `jobs/` via `scripts/ingest_lab_jobs.py`.  
`stump_pct = valid_fail / (solved + valid_fail) × 100`. Timeout and infra are excluded. No Caudal/SSB scores. No rubric channel.

## Headlines

- **Frozen batch 01: 10 tasks.** Go oracle-fail `release-still-signs-edge-go-mod-q1-green-while-the-dependenc` (reward 0.0, 5 `TestLiveProxyIntegrity` failures) was dropped and replaced by `i-need-the-offline-binary-cache-closure-planner-in-app-task` (oracle 1.0). See `docs/lab_batch_01_exclusions.json`.
- **Oracle: 10/10 reward 1.0** on the frozen ten.
- **Continuation 2026-08-28T19:30Z:** Harbor was idle. Cheap probes (prefix/length only): Anthropic `claude-opus-5` ping **HTTP 200**; OpenAI chat `gpt-5.6-sol` **HTTP 429 insufficient_quota**. GPT remaining trials were not started.
- **Dyeworks Opus resume** (`harbor job resume -f BadRequestError`) replaced the earlier 7 credit-infra dirs. Got **2 solved + 2 valid_fail**, then Anthropic **credit-balance-too-low** again on 3 trials; the 8th trial (`…__eWdLDth`) was terminated with no `result.json`. **Stop. Remaining 7 packages were not started.** Batch 02 was not started. **Not 160/160.**
- **Frontier agent coverage:** 2 tasks full 8+8 (pendulum, hypersonic); 1 task partial (dyeworks); **7 tasks still oracle-only** (blocked by credits/quota, not a planned skip of remaining work).
- **Frontier recorded slots toward 160: 42/160.** Completed (solved + valid_fail only): **37**. Infra on those slots: 5 (plus incomplete dyeworks Opus 8th trial, not ingested).
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

### Dyeworks — over-aggressive valid reject (GPT 2/3 completed; valid_fail)

Both GPT k=8 valid fails are **8 failed, 39 passed**. The patched reader **rejects the valid corpus**: `test_valid_corpus_parses_cleanly`, `test_indirect_value_still_parses`, `test_deep_tree_still_parses`, `test_lot_ref_still_resolves`, `test_boundary_valid_files_still_parse`, `test_generated_valid_parses`, `test_generated_depth_256_nesting_parses`, `test_generated_max_size_file_parses`. stderr is `dyeworksdef: has_children does not match type` (`…__nAs7nWJ`) or `node: sibling chain lacks null terminator` (`…__6FTvzuL`). Trajectories diagnose real ULEB/sectab holes, then the guard is too strict on legal trees. Third GPT trial (`…__Qf54bTE`) is **infra** (`RuntimeError` / tmux send-keys, not a stump). Job left **3/8** (1 running dir + 4 pending) because OpenAI then returned **insufficient_quota**.

### Dyeworks — alloc overflow accepted (Opus 2/7 completed; valid_fail)

Opus valid fails `…__Au29QTj` and `…__NBB2td6` are identical: **2 failed, 45 passed**. `exploit_alloc.dye` is **accepted (exit 0)** — `test_exploit_alloc_rejected` requires a node-count whose byte size overflows to be rejected. `test_generated_more_nodes_than_count_rejected` also gets exit 0. Two Opus **solves** (`…__uZFqDH3` reward 1.0 after 1800s timeout; `…__B9Z8xMU` 47/47). Three later retries are **credit-balance-too-low** infra (`…__vRaMF4e`, `…__qGvmkvM`, `…__4dYqcT3`). Eighth trial `…__eWdLDth` has **no** `result.json` (worker stopped mid-run).

## Spend and stop state

| Item | State |
| --- | --- |
| Harbor process | **Idle** (do not start a second one). Dyeworks Opus resume finished 2026-08-28T21:10Z |
| Remaining 7 packages | **Not started** — Anthropic credit-too-low again after the dyeworks resume; OpenAI quota already 429 |
| Dyeworks GPT | **3/8** left incomplete; not resumed after OpenAI `insufficient_quota` |
| Batch 02 | **Not started** |
| Harbor-reported spend | **~$49.67** rollup (pendulum ~$18.26, hypersonic ~$15.88, dyeworks Opus $13.02, dyeworks GPT $1.27, smoke ~$1.25) |
| Anthropic | Cheap probe 200, then harbor **400 credit-too-low** again. Remaining Opus **cannot** continue until credits are added |
| OpenAI | Chat completions **429 insufficient_quota**. Remaining GPT **cannot** continue until quota is added |
| Docker / Harbor 0.22 | Up |

## Continuation log (2026-08-28T19:30–21:20Z)

Did not re-run pendulum or hypersonic 8+8. Did not use `scripts/run_agents.ps1`. Did not start batch 02.

1. Harbor not running. Keys present (`sk-ant-` len 108; `sk-proj` len 164).
2. Cheap Anthropic messages ping (`claude-opus-5`, 8+8 tokens) **200**. Cheap OpenAI chat (`gpt-5.6-sol`) **429 insufficient_quota**.
3. Resumed dyeworks Opus only (filter `BadRequestError`). Seven credit dirs removed and retried at `-n 1`.
4. Credits failed again on trials 5–7 of that resume. Stopped immediately. Remaining seven slugs (root-CA mTLS, Apexora, offline binary-cache, Harborlane, stratified k-fold, wildlife counting, booking-slot-merge) **never got a `harbor run`**.
5. Re-ingested. This file updated. Jobs stay gitignored.

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
- Dyeworks: Opus **2 solved / 2 valid_fail / 3 infra** of 7 recorded (8th incomplete); GPT **0 solved / 2 valid_fail / 1 infra** of 3 recorded
- Other seven batch rows: `oracle` only — no k=8 agent rows

The other 90 gallery rows stay **not run**. Refresh the lab after ingest; live `jobs/` is gitignored.
