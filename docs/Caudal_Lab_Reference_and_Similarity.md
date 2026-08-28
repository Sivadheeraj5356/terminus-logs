# Caudal lab reference and similarity

**Date:** 28 August 2026  
**Workspace:** terminus-logs (Harbor / Terminal-Bench package inventory)  
**Caudal pages fetched live:** [https://gocaudal.com/lab/51-terminal-bench-samples/](https://gocaudal.com/lab/51-terminal-bench-samples/) and [https://gocaudal.com/lab/51-terminal-bench-samples/?sortA=1&task=authority-rotation-rollback-window](https://gocaudal.com/lab/51-terminal-bench-samples/?sortA=1&task=authority-rotation-rollback-window)  
**Corpus asset:** `corpus.json.gz` (server delivered already-inflated JSON) plus `rows.js`

This note compares Caudal AI Labs’ public Post-Training Signal Lab (51 originally authored Terminal-Bench 2.1-style tasks with recorded rollouts) to the local inventory of 448 unique Harbor packages. It does not copy Caudal’s Opus 5 or gpt-5.6 solve rates onto local tasks, and it does not invent stump percentages.

---

## 1. Can we ship a Caudal-style lab?

**Yes — as a gallery of authored Terminal-Bench / Harbor packages.**  
**Not yet — as a rollout / signal lab.**

The local `tasks/latest/<slug>/` trees are the same *kind of object* Caudal starts from: Harbor-format worlds with `instruction.md`, `task.toml`, `environment/`, oracle `solution/`, and `tests/`. Catalog metadata records **448** unique submission UUIDs, every latest package tagged `has_oracle: true` and `has_tests: true`.

What Caudal’s public lab actually *is*, however, is a **measured signal gallery**: 16 terminus-2 rollouts per task (8 × Opus 5, 8 × gpt-5.6), three reward channels (Binary / Tests / Rubric), step-level trajectories, integrity audit of all 816 runs, and a UI that drives optimisation arithmetic from those vectors.

On this inventory:

- `has_oracle` and `has_tests` are **true** for all 448 rows.
- `has_logs` is **true on 1 row** (`the-shipped-go-equivalence-service-audits-twenty-cross-compi`): the zip contains `result.json` / `reward.txt` from an oracle/job artifact inside the package. The catalog card still says **no agent trajectories**, `stump_pct` is null, and `band` is `no_logs`. That is **not** a Caudal-style rollout.
- `stump_pct` is **null** on every row.
- `band` is **`no_logs`** on every row.
- `caudal_lab_readiness` is **`oracle_verified`** for all 448 unique tasks, and **`has_rollout` for 0**.

A package gallery can be shipped now (index, cards, instruction, world, oracle, tests). A Post-Training Signal Lab cannot be shipped until private Harbor trials exist and trajectories are ingested. Do not paste Caudal’s 4/8 · 8/8 (or any other model score from that page) onto these tasks.

---

## 2. Caudal schema (live fetch, 28 August 2026)

HTML-only fetch of the lab URL returns a ~19 KB SPA shell titled **Post-Training Signal Lab**. The shell can render “Could not load the corpus” if `corpus.json.gz` is not inflated. The live page loads:

| Asset | Role |
| --- | --- |
| `lab.css` / `lab.js` | UI |
| `rows.js` | Compact 51-row table (slug, domain, language, Opus/8, gpt/8, supports, 8+8 rollout vectors) |
| `corpus.json.gz` | Per-task instruction, rubric, 16 trajectories |
| `fair.json.gz` | Companion fairness / audit payload |

**Intro copy (live):** 51 originally authored Terminal-Bench 2.1 style tasks; **8 domains**, **10 languages**, **Harbor 0.5.0** format, **terminus-2** agent, **offline, digest-pinned**. Claim: every task written from scratch, not a rewrite/translation/parameter-swap of a public benchmark task. Thesis: difficulty is a proxy; **variance is the quantity that survives into a gradient**.

**Rollouts:** 8 per model on two frontier models → **816** recorded runs. Reward channels in the Optimisation tab: **Binary**, **Tests**, **Rubric**. Arms labeled **Opus 5** and **gpt-5.6** (trajectory chips also say gpt-5.6-sol). Objectives: SFT, SDFT, RFT, DPO, GRPO, PPO.

**Navigation tabs (live):** Introduction, Corpus, Trajectories, Reward signal, Optimisation, How it trains, Integrity, Harness.

**Corpus table columns (live):** Task, Domain, Lang, Opus, gpt, Test σ, Levels, Supports.  
Test σ = standard deviation of fraction-of-tests-passed across all 16 runs; Levels = how many distinct reward values that channel takes.

**Domains in `rows.js` (8):** machine-learning (9), security (8), system-administration (8), games (6), scientific-computing (6), build-and-dependency-management (5), data-processing (5), debugging (4).  
**Languages in `rows.js` (10):** cpp (10), go (8), rust (8), typescript (5), python (5), c (4), ruby (3), bash (3), java (3), javascript (2).

**Integrity (live copy):** 816 rollouts audited; 0 verifier inconsistencies; 0 environment faults shipped; 0 false failures shipped. Oracle must pass twice in separate processes and on ARM64 as well as x86-64; empty submission scores zero; no network at grade time. Five tasks were **removed** (not annotated) after Opus-only scaffold voids, including a `gromacs` example.

**Harness (live):** Measured = terminus-2 in Harbor. Estimated (not measured on this corpus) = mini-swe-agent, Claude Code, Codex CLI.

These Opus / gpt numbers belong to **Caudal’s** 51-task lab. They are not measurements of the local 448.

### Selected-task card: `authority-rotation-rollback-window`

Live URL: https://gocaudal.com/lab/51-terminal-bench-samples/?sortA=1&task=authority-rotation-rollback-window

From `rows.js` + `corpus.json`:

| Field | Live value |
| --- | --- |
| Slug / Task | `authority-rotation-rollback-window` |
| Domain | security |
| Language | typescript |
| Opus 5 | **4/8** (Caudal’s lab, not ours) |
| gpt-5.6 | **8/8** (Caudal’s lab, not ours) |
| Supports | SFT/RFT+DPO+GRPO/PPO |
| Test σ (16-run tests channel) | 0.072 |
| Test levels | 2 |
| Instruction retained | 184 words |
| Rubric criteria | 10 |
| Rollouts in corpus object | 16 |
| Corpus object keys | deep, domain, ins, lang, rolls, rubric |

**Context bar (live, when this task is selected):** security · typescript · Opus 4/8 · gpt 8/8 · test σ · levels · “n of 51”.

**Trajectory card body (live UI):** the prompt (verbatim instruction, identical for all 16 runs; “No hints, no test names, no solution path”); 16 rollout chips (pass/fail, tests passed, step count); replay of the selected run; per-step reasoning / command / terminal output / fault tags (read, write, build, test, other, went wrong, corrected); rubric as judged for that rollout; tests vector; failure modes across judged rollouts.

**Instruction (verbatim from `corpus.json`, excerpt):**

```
The local signing service completes a trust-root change during its normal matrix run, but mixed upgrade histories can later admit newly submitted work under retired material. A warm worker can also disagree with a restarted worker, while the quick status file still looks healthy. Fix the TypeScript sources under `/app/environment` so completed changeovers remain monotonic across restored relay state, new work is refused under retired material, work captured before the cutoff can finish in its captured context, and equivalent warm and restarted workers converge. Reset, restoration, and repeated runs must preserve the highest committed generation.

Run `bash /app/environment/scripts/run-lab.sh /app/output/run-ledger.json` to exercise the matrix. The command deletes and regenerates `/app/output/run-ledger.json`; the local check is `bash /tests/test.sh`. The report is an evidence ledger of observations and transitions, not a table of precomputed verdicts. Its complete schema, ordering, canonical encoding, and digest contract are in `/app/environment/docs/record-shape.md`; principal behavior, cutoff and recovery semantics are in `/app/environment/docs/behavior.md`.

Make the normal pipeline produce the result by repairing the sources. A hand-written ledger, fixture or test changes, wrapper-only changes, and edits that only make the quick status path green are insufficient.
```

**Rubric (from `corpus.json`):**

1. (3) Agent traces publication, warm-worker carry, ticket enforcement, relay restoration, and durable-state paths before repairing them
2. (5) Agent preserves the highest committed generation across publication, stale restoration, reset, and repeated execution
3. (5) Agent permits captured pre-cutoff completion while denying new admission under retired authority material
4. (3) Agent makes equivalent warm and restarted workers use the same active authority and generation
5. (3) Agent merges restored retirement history without allowing older relay bytes to become current
6. (2) Agent regenerates and inspects ledger transitions, observations, and digest-bound evidence after source changes
7. (-5) Agent hand-writes the ledger or changes fixtures or verifier files to manufacture expected evidence
8. (-3) Agent applies blanket retired-authority rejection that also blocks valid captured completion
9. (-3) Agent permits stale restoration to lower the committed floor or reactivate retired authority material
10. (-2) Agent changes only wrappers or quick-status artifacts without repairing the authoritative TypeScript state paths

---

## 3. Unique-task filter

**Method.** One catalog row per latest submission UUID (`sid` / `uuid`). Older `*_submission_*.zip` files are revisions, not extra tasks. Uniqueness is counted again here from `catalog/tasks.jsonl` and `catalog/uuid_map.json`. Near-duplicates are **listed, not dropped**: two tasks that share a template sentence but solve different worlds stay in the unique set.

| Count | Value |
| --- | ---: |
| Catalog rows | 448 |
| Unique UUIDs | 448 |
| Unique slugs (`id`) | 448 |
| UUID collisions | 0 |
| Slug collisions (same slug, >1 UUID) | 0 |
| Exact slugs `problem` / `task` / `goal` | 0 |
| Slugs whose first token is problem/task/goal | 3 |
| Near-duplicate pairs (instruction_summary Jaccard ≥ 0.72) | 1 |
| Pairs dropped from the unique set | 0 |
| `has_oracle` true | 448 |
| `has_tests` true | 448 |
| `has_logs` true | 1 |
| `stump_pct` non-null | 0 |
| Band `no_logs` | 448 |
| `caudal_lab_readiness` = oracle_verified | 448 |
| `caudal_lab_readiness` = has_rollout | 0 |
| `caudal_lab_readiness` = package_only | 0 |

**Slug collisions:** none.

One row has `has_logs: true` (`the-shipped-go-equivalence-service-audits-twenty-cross-compi`): the zip contains `result.json` / `reward.txt`. The catalog card still reports **no agent trajectories**, `stump_pct` null, `band` `no_logs`. Readiness is therefore `oracle_verified`, not `has_rollout`.

**Generic-prefix slugs (kept; they are real tasks whose titles start with those words):**

- `goal-harden-the-flask-media-metadata-service-in-app-without-changing-the-reposit`
- `problem-offline-workspace-builds-against-the-air-gapped-crate-mirror-fail-cargo`
- `task-catalog-beta-ndj-ndjson-one-json-object-per-line-with-a-leader-string-and-a`

**Near-duplicate instruction pairs (Jaccard ≥ 0.72). Distinct tasks; not collapsed:**

- `the-tool-in-app-is-a-feature-bundle-resolver-given-a-bundle` ↔ `the-tool-in-app-is-a-render-pipeline-plugin-resolver-given-a` (Jaccard 0.879)

---

## 4. Field map: Caudal UI → local files

| Caudal UI field | Local source today | Gap |
| --- | --- | --- |
| Task slug | Folder name `tasks/latest/<slug>/`; catalog `id` | None for identity |
| Domain | `task.toml` `[metadata].category`; catalog `category` | Category taxonomies are the same eight TB families |
| Language | `task.toml` `languages`; catalog `languages` | Caudal table shows one primary lang; we may list several |
| Instruction / prompt | `instruction.md`; catalog `instruction_summary`; `summary.md` | We have the prompt; Caudal also stores it inside each rollout record |
| Oracle / reference solution | `solution/` (typically `solve.sh`) | Caudal additionally requires double-run + ARM64 evidence we have not published |
| Tests / verifier | `tests/test.sh` (Harbor reward) | We have tests; we do not have 16-run test vectors |
| Opus / gpt /8 | — | **No local agent trials.** Do not copy Caudal’s numbers |
| Test σ, levels | — | Requires a tests-channel vector per run |
| Supports (SFT/RFT/DPO/…) | — | Derived from reward variance across rollouts |
| Trajectory inspector | Harbor `result.json` / agent logs when present | `band` `no_logs` on all 448; one zip has oracle `result.json`, not agent trajectories |
| Rubric criteria + judge | — | Not in these packages |
| Reward channels Binary / Tests / Rubric | Binary ≈ Harbor reward 0/1 once trials exist; Tests ≈ test fraction; Rubric absent | Rubric channel cannot be faked from tests alone |
| Integrity audit (816, false-failure removal) | — | Needs a rollout set |
| Harness label (terminus-2 / Harbor) | README: Harbor + terminus-2 / oracle locally | Version differs (Caudal cites Harbor 0.5.0; local stack is Harbor 0.22 in README) |
| `sortA`, selected `task=` query | Static site not built | Gallery can add query-string task selection without rollouts |
| Stump % | Catalog `stump_pct` | **null** until valid-fail / completed-trial arithmetic exists |

---

## 5. Similarity to `authority-rotation-rollback-window`

The local 448 are the same *kind* of object (Harbor TB packages). Thematic overlap with Caudal’s example task is scored from title + slug + `instruction_summary` against the **live** Caudal instruction (TypeScript signing-service trust-root changeover / retired authority material — the live prompt does **not** mention macaroons) plus a keyword list requested for this comparison (authority, rotation, rollback, window, macaroon, gateway, PKI, cert). **This is not evidence that any local task was copied from Caudal.** Shared vocabulary is common in security and systems tasks. No local slug is `authority-rotation-rollback-window`.

1. `this-internal-mtls-pki-bridge-under-app-environment-left-a-p` (security) — Jaccard vs Caudal instruction 0.092; keyword hits: authority, pki, certificate, tls, mtls, trust, revocation, keystore. PKI / certificate / TLS material; authority / rotation / window tokens
2. `pki-migration-trust-attestation-publisher` (security) — Jaccard vs Caudal instruction 0.021; keyword hits: authority, pki, certificate, trust, revocation, ca. PKI / certificate / TLS material; authority / rotation / window tokens
3. `the-root-ca-that-signed-our-east-west-mtls-credentials-is-co` (security) — Jaccard vs Caudal instruction 0.045; keyword hits: authority, rotation, certificate, mtls, ca. PKI / certificate / TLS material; authority / rotation / window tokens
4. `cipherwave-has-paused-an-hls-content-key-rotation-because-it` (security) — Jaccard vs Caudal instruction 0.098; keyword hits: authority, rotation, certificate, trust. PKI / certificate / TLS material; authority / rotation / window tokens
5. `jwt-jwks-signing-key-admission` (security) — Jaccard vs Caudal instruction 0.130; keyword hits: rotation, trust, revocation. authority / rotation / window tokens
6. `security-review-flagged-privilege-leaks-in-the-auth-session` (security) — Jaccard vs Caudal instruction 0.117; keyword hits: authority, rotation, window. authority / rotation / window tokens
7. `build-a-node-js-certificate-worker-app-src-worker-js-that-ma` (system-administration) — Jaccard vs Caudal instruction 0.030; keyword hits: pki, certificate, certificates, ca. PKI / certificate / TLS material
8. `the-signed-request-proxy-in-app-enforces-an-authorization-bo` (security) — Jaccard vs Caudal instruction 0.106; keyword hits: authority, rotation, revocation. authority / rotation / window tokens
9. `the-gateway-snapshot-in-app-contains-an-inert-go-main-packag` (security) — Jaccard vs Caudal instruction 0.027; keyword hits: macaroons, gateway. macaroon authorization vocabulary; gateway in title or instruction
10. `apexora-global-wave-3-campus-segmentation-is-blocked-across` (system-administration) — Jaccard vs Caudal instruction 0.072; keyword hits: authority, rollback, gateway. gateway in title or instruction; rollback semantics; authority / rotation / window tokens
11. `specification-archaeology` (security) — Jaccard vs Caudal instruction 0.099; keyword hits: authority, pki, trust. PKI / certificate / TLS material; authority / rotation / window tokens
12. `our-token-service-under-app-auth-rejects-jwts-signed-with-th` (security) — Jaccard vs Caudal instruction 0.069; keyword hits: rotation, window, revocation. authority / rotation / window tokens

Keyword overlap is strongest on PKI / certificate / rotation / rollback tasks. Macaroon and gateway hits are included when present; they are not implied by Caudal’s live instruction.

---

## 6. Appendix: per-task index

A 448-row Word table is omitted. Every unique task is in:

`docs/caudal_lab_task_index.jsonl`

Fields: `slug`, `uuid`, `category`, `difficulty`, `summary`, `caudal_lab_readiness`.

Category summary (readiness = `oracle_verified` for every unique task). One `has_logs` flag in build-and-dependency-management is an oracle job artifact, not agent rollouts:

| Category | Unique tasks | oracle_verified | has_logs |
| --- | ---: | ---: | ---: |
| scientific-computing | 108 | 108 | 0 |
| security | 90 | 90 | 0 |
| system-administration | 60 | 60 | 0 |
| build-and-dependency-management | 51 | 51 | 1 |
| data-processing | 51 | 51 | 0 |
| machine-learning | 46 | 46 | 0 |
| games | 40 | 40 | 0 |
| debugging | 2 | 2 | 0 |

---

## 7. What to build for parity

Private Harbor only. No buyer-platform runtime.

1. **Package gallery (can ship now).** Static site over `catalog/tasks.jsonl`: slug, domain, language, difficulty, instruction excerpt, links into `tasks/latest/<slug>/`. Query-string task selection in the Caudal style. No model scores.
2. **Private Harbor trials.** terminus-2 (and/or oracle smoke) with `-k` (or equivalent) so each task gets a group of independent attempts. Persist `result.json`, `reward.txt`, trajectories.
3. **Trajectory ingest.** Map Harbor logs into step records (command, stdout/stderr, pass/fail). That is the inspector tab.
4. **Reward channels, honestly.** Binary = Harbor reward. Tests = fraction of tests passed when the verifier exposes a vector. Rubric = only if a rubric is actually authored and judged — do not rename test names as a rubric.
5. **Integrity pass.** Oracle twice; empty submission scores zero; drop scaffold voids rather than leaving them in a GRPO group.
6. **Do not invent stump %.** `stump_pct = valid_failures / completed_trials * 100`. Timeouts and infrastructure errors do not count.

Until step 2 exists, the honest label is **oracle-verified Harbor packages**, not a signal lab.
