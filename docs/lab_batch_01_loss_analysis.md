# Batch 01 loss analysis

Generated 2026-08-28T21:20Z from Harbor `jobs/` via `scripts/ingest_lab_jobs.py`.  
Updated **2026-08-30T16:14Z** after the cheap k=5 resume hit Anthropic credit-too-low again.  
Re-probed **2026-08-30T18:24Z**: both cheap providers still blocked; **no new Harbor trials**.  
`stump_pct = valid_fail / (solved + valid_fail) × 100`. Timeout and infra are excluded. No Caudal/SSB scores. No rubric channel.

## Headlines

- **Frozen batch 01: 10 tasks.** Go oracle-fail `release-still-signs-edge-go-mod-q1-green-while-the-dependenc` (reward 0.0, 5 `TestLiveProxyIntegrity` failures) was dropped and replaced by `i-need-the-offline-binary-cache-closure-planner-in-app-task` (oracle 1.0). See `docs/lab_batch_01_exclusions.json`.
- **Oracle: 10/10 reward 1.0** on the frozen ten.
- **Resume 2026-08-30T18:24Z:** `iterate_lab_batches.py --start-batch 1 --end-batch 5 --resume` archived `lab_batch_01_stop.json` → `lab_batch_01_stop.20260830T182403Z.json`. Probe: Anthropic Haiku **HTTP 400 credit-balance-too-low**; OpenAI **429 insufficient_quota** on `gpt-4o-mini`, `gpt-4o`, `gpt-4.1-mini`, `gpt-4.1-nano`, `gpt-3.5-turbo`. Sonnet would also fail (same Anthropic balance). **No Harbor started. No invented scores.** Chips unchanged from the 16:14Z ingest.
- **Resume 2026-08-30T13:04–16:14Z:** Probe Anthropic Haiku **HTTP 200**, OpenAI `gpt-4o-mini` **429 insufficient_quota**. Second arm must be `anthropic/claude-sonnet-4-5`. Iterate filled remaining Haiku k (infra does not count). **Stopped** on credit-too-low during offline binary-cache Haiku `-k 4` (trials `…__Y4vX24v`, `…__DXyWUSd`). Harbor idle. **No second `harbor run`.** Sonnet never started. Batches 02–05 not oracled. **Not 50/50.**
- **Cheap Haiku chips (solved/recorded, not padded):** pendulum **0/5**; hypersonic **4/9** (4 solved on fill4 + 1 valid_fail + 4 prior credit infra); dyeworks **0/5** (2 valid_fail + 3 infra, still need 3 counted); root-CA **0/5**; Apexora **0/5**; offline-cache **0/5** (3 valid_fail + 2 credit infra, still need 2 counted); Harborlane / k-fold / wildlife / booking **0/1**.
- **Continuation 2026-08-28T19:30Z:** Harbor was idle. Cheap probes (prefix/length only): Anthropic `claude-opus-5` ping **HTTP 200**; OpenAI chat `gpt-5.6-sol` **HTTP 429 insufficient_quota**. GPT remaining trials were not started.
- **Dyeworks Opus resume** (`harbor job resume -f BadRequestError`) replaced the earlier 7 credit-infra dirs. Got **2 solved + 2 valid_fail**, then Anthropic **credit-balance-too-low** again on 3 trials; the 8th trial (`…__eWdLDth`) was terminated with no `result.json`. **Stop. Remaining 7 packages were not started.** Batch 02 was not started. **Not 160/160.**
- **Frontier agent coverage:** 2 tasks full 8+8 (pendulum, hypersonic); 1 task partial (dyeworks). **Cheap haiku k=1 (2026-08-28T23:31–00:54Z):** six remaining slugs measured; booking already 0/1.
- **Cheap haiku k=5 first pass (2026-08-29T00:54–01:59Z):** pendulum fill finished **0/5** valid_fail (~$1.96). Hypersonic haiku `-k 5` recorded **0 solved / 1 valid_fail / 4 infra**. Dyeworks haiku fill aborted (**3 infra**). Remaining fills stopped on credit-too-low.
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
| repair-the-pendulum-motion-solver | 25 | 9 | 14 | 0 | 2 | 60.9 | yes (Opus n=10, GPT n=9, haiku n=5 chip 0/5) |
| hypersonic-fragment-cascade-epoch-atlas | 26 | 14 | 8 | 0 | 4 | 36.4 | yes (8+8 + haiku chip 4/9: 4 solved + 1 vf + 4 infra) |
| the-dyeworks-tool-is-a-command-line-reader-at-app-environmen | 16 | 3 | 6 | 0 | 7 | 66.7 | partial frontier + haiku chip 0/5 (2 vf + 3 infra) |
| the-root-ca-that-signed-our-east-west-mtls-credentials-is-co | 6 | 1 | 5 | 0 | 0 | 83.3 | yes (haiku chip 0/5) |
| apexora-global-wave-3-campus-segmentation-is-blocked-across | 6 | 1 | 5 | 0 | 0 | 83.3 | yes (haiku chip 0/5) |
| i-need-the-offline-binary-cache-closure-planner-in-app-task | 6 | 1 | 3 | 0 | 2 | 75.0 | yes (haiku chip 0/5; 2 credit infra; stop) |
| the-harborlane-replay-desk-needs-a-reusable-offline-planner | 2 | 1 | 1 | 0 | 0 | 50.0 | yes (haiku n=1 valid_fail + oracle) |
| we-re-putting-together-a-stratified-k-fold-evaluation-kit-un | 2 | 1 | 1 | 0 | 0 | 50.0 | yes (haiku n=1 valid_fail + oracle) |
| wildlife-counting-becomes-a-field-planning-game-when-uncerta | 2 | 1 | 0 | 1 | 0 | 0.0 | yes (haiku timeout; excluded from stump) |
| booking-slot-merge | 2 | 1 | 1 | 0 | 0 | 50.0 | yes (haiku n=1 valid_fail + oracle) |

Stump% in this table is omitted only when there are no completed agent trials. Lab chips use **solved / recorded** — haiku 1-trials show `0/1`, not `0/8`. Wildlife timeout does not count as stump.

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

### Pendulum — cheap Haiku k=5 (0/5; all valid_fail)

`anthropic/claude-haiku-4-5` terminus-2, job `lab01-haiku-repair-the-pendulum-motion-s-fill5`, Harbor `cost_usd` **$1.96**. Chip is **0/5**, not padded. Every trial ran pytest (reward 0.0, no timeout/credit).

| Trial | pytest | Named misses |
| --- | --- | --- |
| `…__wfyqT5z` | 4 failed, 4 passed | job 1 frequency **1.352 Hz vs 0.9 Hz** (~50%); rejected segments 4 vs 5 |
| `…__RdSP7V2` | 7 failed, 1 passed | incomplete jobs (report covers 1,3,4); rejected 45 vs 5 |
| `…__unA34oZ` | 8 failed (no summary line) | `fit_results` missing `frequency_hz`; graph artifacts incomplete |
| `…__CvnG43i` | 4 failed, 4 passed | job 1 frequency **1.317 Hz vs 0.9 Hz** (~46%); rejected 0 vs 5 |
| `…__XPVNNFV` | 4 failed, 4 passed | job 1 frequency **2.701 Hz vs 0.9 Hz** (~200%); DOT **48 vertices vs 192** edges |

Haiku did not reproduce the GPT half-cadence 0.450 Hz cluster. Failures are wrong recovered Hz, reject counts, and graph vertex/edge mismatch.

### Hypersonic — reference hash / epoch time (GPT 6/8, Opus 1/8)

GPT valid fails are **identical: 5 failed, 15 passed**. Tests that fail:

- `test_bravo_catalog_override_dir` — `ledger_hash` ≠ reference
- `test_alpha_collision_occurs_and_matches_reference` — atlas and/or ledger hash ≠ reference
- `test_flare_absolute_density_scale_not_multiplicative` — hidden `/opt/verifier-fixtures/flare-trap`; `t_sec` **0.05 vs 0.0**
- `test_hidden_chain_reaction_independent_of_bundled` — `ledger_hash` ≠ reference
- `test_ledger_epochs_match_reference_timestamps` — `t_sec` **0.05 vs 0.0**

Agents’ last analyses claim the TypeScript pipeline is complete after checking the **bundled** catalog. Hidden fixtures and epoch timestamps still disagree.

Opus fail `…__24tWaEA`: **19 passed, 1 failed** (`test_alpha_collision_occurs_and_matches_reference`, atlas_hash mismatch only). Two GPT k=8 trials passed all 20 tests.

### Hypersonic — cheap Haiku (chip 4/9; counted 5/5)

`anthropic/claude-haiku-4-5`. First pass job `lab01-haiku-hypersonic-fragment-cascade--fill5`: 1 valid_fail + 4 credit infra. Resume job `lab01-haiku-hypersonic-fragment-cascade--fill4` (**2026-08-30**): **4/4 solved**, Harbor `cost_usd` **$0.96**. Chip is **4/9** (recorded n includes the four infra). Counted toward k=5: 4 solved + 1 valid_fail.

- `…__AUY7bRz` **valid_fail**: 1 failed, 19 passed. `test_alpha_collision_occurs_and_matches_reference` — `ledger_hash` `259971c0…` vs reference `1779998e…`.
- `…__KLvpf4E`, `…__AFs2NXw`, `…__Q9Yoc4P`, `…__vLMHRvJ` **infra** (`BadRequestError`, Anthropic **credit balance too low**). Not stumps.
- Fill4 `…__S7TMAmw`, `…__Zq6MnPb`, `…__qgU2hSW`, `…__ZJnN3vf` **solved** (reward 1.0).

### Dyeworks — cheap Haiku (chip 0/5; counted 2/5)

Job `lab01-haiku-the-dyeworks-tool-is-a-comma-fill5` reused yesterday's aborted dir. 30 Aug added two **valid_fail** (`…__VYo2xQJ`, `…__iebEKBw`, reward 0.0). Three older trials remain **infra** (2 `BadRequestError` credit-too-low + 1 `CancelledError`). Chip **0/5**, not padded. Counted attempts **2**; remaining k=3 not run because iterate had already moved to the next slug, then credits died later on offline-cache.

Both GPT k=8 valid fails are **8 failed, 39 passed**. The patched reader **rejects the valid corpus**: `test_valid_corpus_parses_cleanly`, `test_indirect_value_still_parses`, `test_deep_tree_still_parses`, `test_lot_ref_still_resolves`, `test_boundary_valid_files_still_parse`, `test_generated_valid_parses`, `test_generated_depth_256_nesting_parses`, `test_generated_max_size_file_parses`. stderr is `dyeworksdef: has_children does not match type` (`…__nAs7nWJ`) or `node: sibling chain lacks null terminator` (`…__6FTvzuL`). Trajectories diagnose real ULEB/sectab holes, then the guard is too strict on legal trees. Third GPT trial (`…__Qf54bTE`) is **infra** (`RuntimeError` / tmux send-keys, not a stump). Job left **3/8** (1 running dir + 4 pending) because OpenAI then returned **insufficient_quota**.

### Dyeworks — alloc overflow accepted (Opus 2/7 completed; valid_fail)

Opus valid fails `…__Au29QTj` and `…__NBB2td6` are identical: **2 failed, 45 passed**. `exploit_alloc.dye` is **accepted (exit 0)** — `test_exploit_alloc_rejected` requires a node-count whose byte size overflows to be rejected. `test_generated_more_nodes_than_count_rejected` also gets exit 0. Two Opus **solves** (`…__uZFqDH3` reward 1.0 after 1800s timeout; `…__B9Z8xMU` 47/47). Three later retries are **credit-balance-too-low** infra (`…__vRaMF4e`, `…__qGvmkvM`, `…__4dYqcT3`). Eighth trial `…__eWdLDth` has **no** `result.json` (worker stopped mid-run).

### Dyeworks — over-aggressive valid reject (GPT 2/3 completed; valid_fail)

Both GPT k=8 valid fails are **8 failed, 39 passed**. The patched reader **rejects the valid corpus**: `test_valid_corpus_parses_cleanly`, `test_indirect_value_still_parses`, `test_deep_tree_still_parses`, `test_lot_ref_still_resolves`, `test_boundary_valid_files_still_parse`, `test_generated_valid_parses`, `test_generated_depth_256_nesting_parses`, `test_generated_max_size_file_parses`. stderr is `dyeworksdef: has_children does not match type` (`…__nAs7nWJ`) or `node: sibling chain lacks null terminator` (`…__6FTvzuL`). Trajectories diagnose real ULEB/sectab holes, then the guard is too strict on legal trees. Third GPT trial (`…__Qf54bTE`) is **infra** (`RuntimeError` / tmux send-keys, not a stump). Job left **3/8** (1 running dir + 4 pending) because OpenAI then returned **insufficient_quota**.

### Booking Slot Merge — epoch fence / report span (haiku 0/1; valid_fail)

Haiku trial `…__5SqDRHH` (~$0.15, ~3.5 min): **3 failed, 24 passed**. Merge and most check/stats tests passed. Failures:

- `test_report_span_respects_epoch_fence` — SPAN printed **201** vs expected **200** (inclusive end vs fenced interval length)
- `test_report_exact_layout` — column widths and SPAN off by one (`151` vs `150`, TOTAL `192` vs `190`)
- `test_check_epoch_regression_across_files` — expected exit **2** (epoch regression across files), got **0** / `ok`

This is a recorded **0/1**, not 0/8.

### Root CA mTLS — schedule not exact optimum (haiku chip 0/5)

Trial `…__9cdUGV4` (~$0.25, ~11 min) plus fill4 four more valid_fails (job `lab01-haiku-the-root-ca-that-signed-our--fill4`, **$1.36**). Chip **0/5**. Counted 5/5. First trial: **3 failed, 6 passed**; all three `test_schedule_is_the_exact_optimum` fixtures missed. Fill4 trials also failed schema/optimum checks. No solves. No credit infra on this slug.

### Apexora campus — config not authoritative (haiku chip 0/5)

Trial `…__9zWrbgo` (~$0.80) plus fill4 four more valid_fails (job `lab01-haiku-apexora-global-wave-3-campus-fill4`, **$2.50**). Chip **0/5**. Counted 5/5. Setup/identity still asserts `configuration not yet authoritative`. Not infra.

### Offline binary-cache — proof seal mismatch, then credit stop (haiku chip 0/5)

Trial `…__zMsM6oX` (~$0.82): **3 failed, 2 passed**; `proof.seal` differed on public/generated/copied-root. Fill4 (`lab01-haiku-i-need-the-offline-binary-ca-fill4`, **$3.23**) added two valid_fail (`…__5UJ6gho`, `…__i5h4um2`) then two **credit-too-low** infra (`…__Y4vX24v`, `…__DXyWUSd`). Chip **0/5**. Counted **3/5**. Harbor stopped here.

### Harborlane replay — Plan.hs row order (haiku 0/1; valid_fail)

Trial `…__BR39Uag` (~$0.80): **2 failed, 2 passed**. `test_public_root_is_solved_and_schema_is_canonical` — Haskell payload segment ids start at `seg-ea-02` vs expected `seg-no-00` (118 extra items). Compatibility matrix failed the same ordering/schema check.

### Stratified k-fold — extra stdout line (haiku 0/1; valid_fail)

Trial `…__EEz3v7j` (~$0.28): **173 errors, 0 passed**. `setup_method` JSON-decodes assemble stdout; the tool printed a JSON object then `/app/var/fold_work/cohort_staged.csv`, so `JSONDecodeError: Extra data`. Reward 0.0 with no exception — valid_fail, not infra.

### Wildlife counting — agent timeout (haiku; excluded from stump)

Trial `…__ASNhuY6` (~$0.60, 1800s): **`AgentTimeoutError`**. Classified **timeout**, not valid_fail. Verifier still ran after the cutoff: **12 failed, 4 passed** (`test_census_case` cases 01–12). Agent spent the budget writing/playing Node game runners.

## Spend and stop state

| Item | State |
| --- | --- |
| Harbor process | **Stopped** 2026-08-30T18:24Z dual-provider probe (no Harbor started). Anthropic credit-too-low; all probed OpenAI slugs 429. See `docs/lab_batch_01_stop.json`. |
| Cheap pendulum haiku | Chip **0/5** valid_fail. Counted 5/5. ~$1.96. |
| Cheap hypersonic haiku | Chip **4/9**. Counted 5/5 (4 fill4 solves + 1 vf; 4 infra). Fill4 **$0.96**. |
| Cheap dyeworks haiku | Chip **0/5**. Counted 2/5 (need 3). |
| Cheap root-CA / Apexora haiku | Chips **0/5** / **0/5**. Counted 5/5 each. |
| Cheap offline-cache haiku | Chip **0/5**. Counted 3/5. Stopped mid fill4. **$3.23** this job. |
| Harborlane / k-fold / wildlife / booking | Haiku chips **0/1** (wildlife timeout). Remaining k=4 **not run**. |
| Second arm (Sonnet / gpt-4o / gpt-4o-mini) | **Not started.** OpenAI 429 on mini, gpt-4o, 4.1-mini, 4.1-nano, 3.5-turbo; Anthropic credits exhausted so Sonnet fallback is blocked too. |
| Batches 02–05 | Frozen jsonl on disk. **Not oracled, not measured.** |
| OpenAI | Chat completions **429 insufficient_quota** (`gpt-4o-mini`, `gpt-4o`, `gpt-4.1-mini`, `gpt-4.1-nano`, `gpt-3.5-turbo` pings at 18:24Z). |
| All ingested Harbor `cost_usd` | **$65.00** (frontier+smoke **$49.67**, Haiku **$15.33**) |
| Docker / Harbor 0.22 | Up |

## What the founder sees after this ingest

Serve from repo root (`python -m http.server 8765`) and open:

- Batch table: [`/lab/index.html?surface=catalog&filter=batch`](../lab/index.html?surface=catalog&filter=batch)
- Pendulum: [`/lab/index.html?task=repair-the-pendulum-motion-solver`](../lab/index.html?task=repair-the-pendulum-motion-solver)
- Hypersonic: [`/lab/index.html?task=hypersonic-fragment-cascade-epoch-atlas`](../lab/index.html?task=hypersonic-fragment-cascade-epoch-atlas)
- Spend / Batches: `?surface=spend` · `?surface=batches`

Chips reflect **recorded** trials, never padded to 5 or 8:

- Pendulum: **haiku 0/5**
- Hypersonic: **haiku 4/9**
- Dyeworks / root-CA / Apexora / offline-cache: **haiku 0/5**
- Harborlane / k-fold / wildlife / booking: **haiku 0/1**
- Second arm: no chips
- Batches 02–05: not run

## Cheap k=5 protocol (30 Aug 2026 18:24Z stop)

Frontier 8+8 stays historical. 18:24Z `--resume` archived the 16:14Z stop, probed Haiku + every cheap OpenAI slug including `gpt-4o`, and **did not start Harbor** (`halt_iterate: true`). Sonnet second arm remains unstarted. Live cheap notes: [`lab_batch_01_cheap_notes.md`](lab_batch_01_cheap_notes.md). Stop file: [`lab_batch_01_stop.json`](lab_batch_01_stop.json). Batches 02–05 remain frozen in `docs/lab_batch_02.jsonl` … `05.jsonl` with **no Harbor measure**.

Catalog deep links use `?surface=catalog` (`surface=tasks` still works). Runs / Traces / Failures / Stump / Spend / Batches are first-class surfaces.
