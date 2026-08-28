# Applied Work Worlds Lab spec

**Date:** 28 August 2026  
**Brand:** Applied Work (appliedwork.ai)  
**Repo surfaces:** `lab/index.html`, `docs/lab_mvp_100.jsonl`, `docs/lab_batch_01.jsonl`  
**Runtime:** private Harbor 0.22 + terminus-2 / oracle. Not Snorkel, not stb, not Portkey.

This is the working spec for the Worlds Lab. It is not a Caudal clone. Caudal’s eight tabs, 4/8 · 8/8 chips, GRPO playground, and “Post-Training Signal Lab” chrome stay theirs. Ours leads with **worlds + verifier + valid-fail stump**.

---

## 1. Direct answers

**Can we ship a Caudal-style lab?**  
Gallery: already yes — 100 unique Harbor packages at `lab/index.html`. Measured signal lab: only after private Harbor rollouts exist. Do not copy Caudal scores onto these packages.

**Why Caudal published 51, not ~100k.**  
Caudal’s company-scale “tasks delivered” is a **services volume** number. The public lab is a **measured, audited slice**: originally authored Terminal-Bench 2.1 worlds, digest-pinned, 16 terminus-2 runs each (8 Opus 5 + 8 gpt-5.6-sol), three reward channels, an 816-run integrity pass, and five tasks **removed** (not footnoted) after Opus-only scaffold voids. The variance thesis is mid-band `p` so `p(1-p)` is usable for group estimators. One hundred thousand unlabeled or once-run items cannot sit in that UI.

**How many we add.**  
Keep **100** as the public *package* set. Grow the *measured* set in **tens**: 10 → 20 → 30. After three clean batches (~480 frontier runs), decide whether to stop near 30, match Caudal’s 51, or continue toward 100. Do not run 448×16, and do not claim a 100-task signal lab until groups exist and scaffold voids are dropped.

**This batch.**  
10 tasks × 8 Opus 5 × 8 gpt-5.6-sol = **160** terminus-2 jobs, plus oracle (and optional empty/`nop`) integrity. Then stop. Do not auto-start batch 2. If spend spikes after task 2–3, stop and report.

---

## 2. Differentiation (do not clone Caudal tabs)

| Applied Work surface | Instead of copying | Data we need |
| --- | --- | --- |
| Worlds | Introduction | Package contract, offline, expert time, Harbor 0.22 |
| Coverage | (new) | Domain × language matrix vs Caudal 51 and vs public TB2 |
| Corpus | Corpus | 100 gallery now; measured rows highlighted only when jobs exist |
| Traces | Trajectories | Harbor `trajectory.json` / trial logs after runs |
| Verifier | Integrity-first | Oracle, empty submission = 0, timeout ≠ fail |
| Stump | Reward-signal clone | `valid_fail / completed_trials`; infra/timeout excluded |
| Failure map | Rubric-only copy | Taxonomy from traces + tests; rubric only if we author one |
| Harness | Harness | terminus-2 + Harbor 0.22 named; no fake Claude-Code estimates |

Do **not** ship an SFT/SDFT/RFT/DPO/GRPO/PPO playground until real 8-run groups exist, and even then as a short “group math” note, not their UI.

Format references only (not chrome to copy): [tbench Challenges](https://www.tbench.ai/news/terminal-bench-challenges), [Harbor](https://harborframework.com/docs), [AirDawg](https://www.airdawglabs.com/), OSWorld / long-horizon Terminal-Bench papers (horizon, not visual design).

---

## 3. Worlds

A world is a Harbor package under `tasks/latest/<slug>/`:

| File | Role |
| --- | --- |
| `instruction.md` | Agent prompt. No hints, no test names, no solution path in the lab copy. |
| `task.toml` | Category, languages, timeouts, `allow_internet` (these worlds are offline). |
| `environment/` | Docker world the agent actually edits. |
| `solution/` | Oracle / reference solve. |
| `tests/` | Verifier. Harbor binary reward is 0 or 1. |
| `summary.md` | Author notes; keeps the submission UUID after the slug rename. |

Gallery identity is the **slug**. The UUID stays in `summary.md` and in catalog `uuid` / `sid`. Expert-time estimates live on catalog cards (`expert_time_estimate_min`); they are author metadata, not measured wall clock.

The Worlds surface states the contract: authored, offline, oracle+tests present, Harbor 0.22 locally. It does not claim a measured solve rate.

---

## 4. Coverage

Public package set: **100**, Hamilton-proportional to the 448 inventory (see `docs/AppliedWork_Lab_Build_Plan.md`).

Measured set: grow in tens. Batch 01 is **10** rows chosen to maximize **category × primary language** from the 100.

| Seat rule | Count |
| --- | ---: |
| scientific-computing | 2 |
| security | 2 |
| system-administration | 1 |
| build-and-dependency-management | 1 |
| data-processing | 1 |
| machine-learning | 1 |
| games | 1 |
| debugging | 1 |
| **Total** | **10** |

Primary language = first `task.toml` / catalog language, normalized (`cpp`→C++, `go`→Go, `shell`→Bash). The 100 is Go/Rust-heavy (33 Go, 23 Rust primaries). Batch 01 therefore prefers rare primaries so the eight named languages (Go, Rust, Python, TypeScript, C, C++, Java, Bash) are all present, with Haskell and JavaScript as extra distinct primaries.

**Vs Caudal 51 (their lab, not ours):** 8 domains and 10 languages on a *measured* slice. We do not copy their per-language counts or scores. **Vs public TB2:** this inventory is a private authored dump, not the public GitHub 89-task set. Do not mix public canaries into Applied Work copy.

The Coverage surface is a domain × language matrix over the 100, with batch-01 selection marked, and **measured** cells lit only after Harbor jobs exist.

---

## 5. Corpus

The Corpus surface is the existing gallery: name, category, languages, deep link `lab/index.html?task=<slug>`.

- 100 unique packages stay listed.
- **Measured chips** appear only on tasks that have ingested Harbor jobs.
- No fake 8/8 rollout chips on the other 90.
- Batch 01 membership is a selection fact, not a score.

Frozen lists:

- Gallery: `docs/lab_mvp_100.jsonl`
- First 10: `docs/lab_batch_01.jsonl`

Rebuild:

```text
python scripts/select_lab_batch.py          # freeze / rewrite lab_batch_01.jsonl
python scripts/select_lab_batch.py --check  # assert freeze matches the selector
python scripts/build_lab_corpus.py          # lab/corpus.json + lab/corpus.js
python scripts/ingest_lab_jobs.py           # merge jobs/ into those 10 only
```

---

## 6. Traces

After terminus-2 trials, Harbor writes `trajectory.json` (and/or `trial.log`) under gitignored `jobs/`. The Traces surface lists, per measured task:

- model slug
- classification (`solved` / `valid_fail` / `timeout` / `infra_error`)
- a short step summary from the trajectory

Until those files exist, Traces is an honest empty state: “No private Harbor trials are recorded.” Do not paste another lab’s step inspector.

---

## 7. Verifier

Integrity-first, not a scoreboard.

| Check | Rule |
| --- | --- |
| Oracle | `harbor run -a oracle -k 1` on the frozen 10. Drop any package that is not reward 1.0 and recompute batch 01. |
| Empty submission | Harbor `nop` agent scores 0 if the run is cheap enough to add. A world that rewards empty work is a scaffold void — remove it from the measured set (Caudal’s removal rule: drop, do not footnote). |
| Timeout | `timeout` ≠ `valid_fail`. Timeouts are excluded from stump. |
| Infra | Auth, Docker, missing reward file, 401 — `infra_error`, excluded from stump. |
| Agent fail | Reward 0.0 with no timeout/infra exception — `valid_fail`. That is the stump numerator. |

Binary channel = Harbor `rewards.reward`. Tests channel = fraction of tests passed **only if** the verifier exposes a vector. Rubric channel = **only if we author a rubric**. Test names are not a rubric.

---

## 8. Stump

```text
stump_pct = valid_fail / completed_trials * 100
completed_trials = solved + valid_fail
```

Timeouts and infrastructure errors do **not** count. Do not display a stump percentage until `completed_trials ≥ 1`. Hide GRPO / σ / “supports” until an 8-run group exists for that model. Never copy Caudal Opus 5 / gpt-5.6 numbers onto these slugs.

---

## 9. Failure map

When traces and tests exist, group failures from trajectory summaries + verifier output (read / write / build / test / other). Rubric tags appear **only if we author a rubric**. Until then the Failure map says the taxonomy is not yet judged.

---

## 10. Harness

| Item | Applied Work |
| --- | --- |
| Measured agent | terminus-2 |
| Oracle | Harbor `oracle` |
| Empty | Harbor `nop` (optional integrity) |
| Framework | Harbor **0.22** (not Caudal’s cited 0.5.0) |
| Keys | Private shell only (`sk-ant-…`, real OpenAI key). Never commit. Never paste into chat. |
| Jobs | gitignored `jobs/` |
| Not measured | Claude Code, Codex CLI, mini-swe-agent — do not invent estimates |

### Harbor `n_trials` vs `-k`

Confirmed against Harbor’s job model (0.22-era CLI + docs):

- There is **no separate** `n_trials` flag on `harbor run`.
- `n_trials = n_attempts × n_tasks × n_agents`.
- CLI `-k` / `--n-attempts` is **n_attempts**: it expands the cartesian product into **independent trials** (separate `TrialConfig`s). It is not “retry the same trial eight times.”
- Infra retries are `--retry` / `RetryConfig.max_retries`, and they are left at 0 for this lab.
- Concurrency is `-n` / `--n-concurrent` (use **1**, at most 2).

Protocol for 8 independent rollouts per model per task: **one job**, `-k 8`, `-n 1`. That is eight trials × one attempt each in Harbor’s sense. `scripts/run_lab_batch.ps1` prints `harbor run --help` for `-k` / `n-attempts` / `n-trials` before spending tokens, so a newer Harbor can be re-checked on the evaluation host.

Likely LiteLLM slugs (confirm on smoke; do not guess past a 401):

- `anthropic/claude-opus-5`
- `openai/gpt-5.6-sol` with fallback `openai/gpt-5.6`

---

## 11. Field map

| Lab field | Local source | Shown when |
| --- | --- | --- |
| Slug / name | `tasks/latest/<slug>/`, catalog `id` | Always |
| Domain | `task.toml` category | Always |
| Languages | `task.toml` / catalog | Always |
| UUID | catalog `uuid`, `summary.md` | Always |
| Instruction excerpt | `instruction.md` | Always |
| Oracle / tests badges | package tree | Always |
| Batch 01 selected | `docs/lab_batch_01.jsonl` | Coverage / corpus note |
| Solve n/8 | Harbor trials, classified | Only if that model has jobs |
| Stump % | `valid_fail / completed_trials` | Only if completed_trials ≥ 1 |
| Traces | `jobs/**/trajectory.json` | Only if files exist |
| Test fraction | verifier rewards/details | Only if exposed |
| Rubric | — | Not until authored |
| GRPO / σ / supports | — | Hidden until n=8 groups exist |

---

## 12. First 10 (batch 01)

Source: `docs/lab_mvp_100.jsonl`. Selector: `scripts/select_lab_batch.py` (best-per-category-language search maximizing distinct primaries, then preferred-language coverage, then catalog selection score). Recompute if oracle ≠ 1.0.

| # | Category | Primary | Slug | UUID |
| ---: | --- | --- | --- | --- |
| 1 | scientific-computing | Python | `repair-the-pendulum-motion-solver` | `bb361b7b-e01f-4068-beac-4c197355eee7` |
| 2 | scientific-computing | TypeScript | `hypersonic-fragment-cascade-epoch-atlas` | `e55547a7-d339-42b6-9aff-6b6df8f29cc0` |
| 3 | security | C | `the-dyeworks-tool-is-a-command-line-reader-at-app-environmen` | `61f6d0fd-74f9-480f-9c52-befa30a93887` |
| 4 | security | C++ | `the-root-ca-that-signed-our-east-west-mtls-credentials-is-co` | `9dc87873-29c5-4064-8182-29a6451f3d9d` |
| 5 | system-administration | Bash | `apexora-global-wave-3-campus-segmentation-is-blocked-across` | `a5317367-9c2d-4fa2-aa05-dee9bab3e7ab` |
| 6 | build-and-dependency-management | Go | `release-still-signs-edge-go-mod-q1-green-while-the-dependenc` | `3fbf9b62-caa3-44f3-82be-20107b3e97da` |
| 7 | data-processing | Haskell | `the-harborlane-replay-desk-needs-a-reusable-offline-planner` | `df101f67-b1f1-41ce-b7fa-5b65d20e1d7e` |
| 8 | machine-learning | Java | `we-re-putting-together-a-stratified-k-fold-evaluation-kit-un` | `5bd7c1a8-74f0-448f-b30f-f088169b9fe8` |
| 9 | games | JavaScript | `wildlife-counting-becomes-a-field-planning-game-when-uncerta` | `76c3437f-736a-493c-b0b3-b45679f1be23` |
| 10 | debugging | Rust | `booking-slot-merge` | `2939c523-a9c0-4197-aac6-3849160e4ac2` |

Ten distinct primaries. All eight named example languages are present. Debugging is the only debugging row in the 100. TypeScript is the only TypeScript primary in the 100.

Smoke task (1 trial × each model before the 160): `repair-the-pendulum-motion-solver`.

---

## 13. Protocol per batch of 10

Do **not** use `scripts/run_agents.ps1` as-is (it still defaults sonnet/gpt-4o over all of `tasks/latest`). Use `scripts/run_lab_batch.ps1`.

1. **Probe.** Print Harbor `-k` / n-attempts help. Require `ANTHROPIC_API_KEY` starting `sk-ant-` and a real `OPENAI_API_KEY`. Reject a `sk-proj-` value in the Anthropic slot.
2. **Oracle** the 10 (`-a oracle -k 1`). Drop reward ≠ 1.0 and rerun the selector.
3. **Smoke** one task, each model, 1 trial. Stop on auth or Docker errors.
4. **Measure** both models, 8 trials, concurrency 1 (or 2). Stop after task 2–3 if spend spikes. Do not start batch 02 automatically.
5. **Classify** with `scripts/ingest_lab_jobs.py` (same rules as `scripts/update_catalog_from_jobs.py`): solved / valid_fail / timeout / infra_error. Stump only from valid_fail.
6. **Integrity.** Optional `nop` empty=0. Drop scaffold-void trials from groups.
7. **Ingest** into `lab/` only fields we have, and **only for these 10**. The other 90 stay “not run.”

Cost ceiling this pass: 160 frontier jobs. Wall clock is sequential; hours to days on the Harbor host.

---

## 14. UI rules

- Keep the workshop ledger chrome (paper, ink, copper). Name: **Applied Work Worlds Lab**.
- Surfaces: Worlds, Coverage, Corpus, Traces, Verifier, Stump, Failure map, Harness.
- Deep link stays `lab/index.html?task=<slug>` (optional `&surface=`).
- Measured chips **only** for tasks with jobs. No fake 8 rollout chips.
- Do not title the page “51 Terminal-Bench samples” or “Post-Training Signal Lab.”

---

## 15. Out of scope this pass

Snorkel / stb, public TB2 mix-in, 100×8+8 in one shot, rubric channel unless we author rubrics, copying Caudal CSS/tabs/optimisation playground, inventing stump % or model scores.

---

## 16. Status of batch 01 runs

Live Harbor jobs belong on the evaluation host (Windows + Docker Desktop in the original stack). This spec does not treat missing cloud-agent Docker/keys as a pass. See `docs/lab_batch_01_status.json` for the last probe: keys, Harbor binary, Docker, oracle, smoke. Ingest lights Corpus/Traces/Stump only when `jobs/` contains classified trials for these slugs.
