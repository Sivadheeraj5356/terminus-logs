# Applied Work Environments Lab — build plan

**Date:** 28 August 2026  
**Brand:** Applied Work (appliedwork.ai)  
**Ship in this repo first:** `lab/`  
**MVP:** 100 unique Harbor packages, gallery only  

This plan is the working spec for the Applied Work Environments Lab. It is not a Caudal clone, not a Terminal-Bench leaderboard, and not a measured post-training signal product. Rollouts are labeled **not run**. Stump percentages and other labs’ model scores are not invented or copied.

---

## 1. What we are shipping

**Now (MVP):** a static gallery of **100 unique** authored Harbor packages, selected from the private 448-task inventory in this repo. Each row is a real world (`instruction.md`, `task.toml`, `environment/`, `solution/`, `tests/`). Deep links use `lab/index.html?task=<slug>`.

**Later:** private Harbor trials (terminus-2 / oracle) recorded in `jobs/`, then trajectory ingest into the same lab. Until those trials exist, the honest product name is a **package gallery**, not a signal lab.

**Not in scope for MVP**

- Model solve rates (Opus, GPT, or any other arm)
- Test σ, reward levels, SFT/DPO/GRPO “supports”
- Rubric-as-judge channels
- Snorkel or any buyer platform as the runtime
- Public Terminal-Bench 2/3 GitHub tasks mixed into this inventory

The public site can move to appliedwork.ai later. The source of truth stays in this repository.

---

## 2. Similar sites (what to learn, what not to copy)

Fetched 28 August 2026. Short table only; none of these brands or scoreboards are reused on the Applied Work lab page.

| Site | What it is | Useful to us | Leave it |
| --- | --- | --- | --- |
| [Caudal Post-Training Signal Lab](https://gocaudal.com/lab/51-terminal-bench-samples/) | 51 originally authored TB-style tasks with **16 recorded rollouts each**, Opus 5 / gpt-5.6 columns, optimisation arithmetic, integrity audit of 816 runs | Query-string task selection; later Harbor rollouts *if we actually run them*; honesty about variance vs difficulty | Branding, “51 Terminal-Bench samples”, copied chrome/tabs, their 4/8 · 8/8 (or any) scores, invented stump % |
| [AirDawg Labs](https://www.airdawglabs.com/) | Data-ops vendor / contributor marketplace for CLI + Docker tasks; hiring copy cites a &lt;40% pass-rate bar | Confirms the commercial unit is Docker world + oracle + tests | Their speed/cost claims, marketplace voice, pass-rate targets as if they were our measurements |
| [tbench.ai](https://www.tbench.ai/) | Public Terminal-Bench leaderboards and task examples (TB 2.1, TB 3, Challenges); Stanford × Laude | Harbor-native format; category vocabulary; reminder that **this inventory is not the public 89-task GitHub set** | Public task text, canary strings as marketing, leaderboard numbers on our packages |
| [Harbor](https://harborframework.com/docs) | Eval / optimisation framework for container tasks; local stack here is Harbor **0.22** | Runtime for later **private** trials; same package contract as TB2/TB3 | Requiring cloud sandboxes for the gallery; calling the gallery a Harbor leaderboard |
| [AfterQuery Atrium](https://atrium.afterquery.com/) | Pays companies for private codebases, CAD, financial models | Adjacent “private work as training data” market | Sourcing third-party repos; Atrium is a buy-side for code, not a Harbor gallery |

Caudal’s live lab is a **measured signal gallery**. Ours is not, until private Harbor trials exist. See `docs/Caudal_Lab_Reference_and_Similarity.md`.

---

## 3. Phases

| Phase | Name | Status |
| --- | --- | --- |
| 0 | Inventory + catalog (448 unique UUID/slug packages) | Done (`catalog/`, `tasks/latest/`) |
| **1** | **Gallery MVP — 100 unique packages in `lab/`** | **This document / this commit** |
| 2 | Private Harbor rollouts (oracle smoke, then terminus-2 groups) | Later; persist under `jobs/` (gitignored) |
| 3 | Trajectory ingest + honest reward channels (binary from Harbor reward; tests vector only if the verifier exposes one; rubric only if authored) | Later |
| 4 | Integrity pass (oracle twice, empty submission = 0, drop scaffold voids) | Later |
| 5 | Deploy static `lab/` to appliedwork.ai | Later |

Phase 1 does not pretend to be phases 2–4.

---

## 4. Selection rules (100)

Source: `catalog/tasks.jsonl` + `tasks/latest/<slug>/`.

1. **Unique** on `uuid` and `slug` (448/448 in the catalog; the 100 inherit that).
2. **Standard Harbor layout** on disk: `instruction.md`, `task.toml`, `environment/`, `solution/`, `tests/` at package root. Milestone-only trees are skipped even if the catalog flags `has_oracle`.
3. **Oracle + tests** required (catalog `has_oracle` and `has_tests`).
4. **Category mix proportional to the 448**, Hamilton / largest-remainder seats:

   | Category | Inventory (448) | MVP seats (100) |
   | --- | ---: | ---: |
   | scientific-computing | 108 | 24 |
   | security | 90 | 20 |
   | system-administration | 60 | 14 |
   | build-and-dependency-management | 51 | 11 |
   | data-processing | 51 | 11 |
   | machine-learning | 46 | 10 |
   | games | 40 | 9 |
   | debugging | 2 | 1 |
   | **Total** | **448** | **100** |

5. **Prefer hard.** Scoring: author `hard` ≫ `medium`, then `well_specified`, revision count, expert-time estimate. The shipped 100 are all **hard**.
6. **Near-duplicate pair:** `the-tool-in-app-is-a-feature-bundle-resolver-given-a-bundle` vs `the-tool-in-app-is-a-render-pipeline-plugin-resolver-given-a` (instruction Jaccard ≥ 0.72). **Keep only one in the pool** — drop the render-pipeline twin. The kept twin is eligible; it is not forced into the 100 if it does not rank in the build quota.

Rebuild:

```text
python scripts/build_lab_corpus.py --select   # docs/lab_mvp_100.jsonl + lab/corpus.json
python scripts/build_lab_corpus.py            # corpus from the frozen 100-list
python scripts/build_lab_plan_docx.py         # this plan as .docx
```

---

## 5. Lab IA (Applied Work, not a Caudal copy)

**Name:** Applied Work Environments Lab  

Public chrome is a workshop ledger (paper, ink, copper), not a dark “Post-Training Signal Lab” with Opus/gpt columns.

| Surface | Content |
| --- | --- |
| Table | Name, category, languages |
| URL | `lab/index.html?task=<slug>` |
| Panel | Title, summary, category, difficulty (author label), UUID, slug, Harbor file pointers, **Rollouts: not run**, **Stump %: —** |
| Copy | Gallery of packages; rollouts not run; no model scores |

Tabs we are **not** shipping in MVP: Trajectories, Reward signal, Optimisation, How it trains, Integrity-with-fake-816. Those become real only after phase 2+ data exists.

Assets:

- `lab/index.html`, `lab/lab.css`, `lab/lab.js`
- `lab/corpus.json` (and `lab/corpus.js` so the page works from `file://`)
- `docs/lab_mvp_100.jsonl`

Serve locally from the repo root:

```text
python -m http.server 8765
```

Then open `http://127.0.0.1:8765/lab/index.html`.

---

## 6. Harbor rollouts (later, private only)

Runtime stays **private Harbor** on the evaluation host (Harbor 0.22, terminus-2 / oracle, Docker Desktop). Buyer platforms are a commercial channel, not the runner.

When trials exist:

- `stump_pct = valid_failures / completed_trials * 100`
- Timeouts and infrastructure errors **do not count**
- Do not paste Caudal Opus 5 / gpt-5.6 numbers onto these tasks
- Do not display a stump % until the arithmetic above has a real denominator

---

## 7. Deploy later

`appliedwork.ai` exists as a domain. Do not block the repo gallery on DNS or a marketing site. When ready, publish the static `lab/` tree (and, if needed, a subset of `tasks/latest/<slug>/` for file pointers). Keep secrets, `_source/`, `jobs/`, and zips out of that deploy.

---

## 8. Out of scope / anti-copycat

- Do not title the page “51 Terminal-Bench samples” or “Post-Training Signal Lab”
- Do not ship empty rollout chips that look like 8/8
- Do not rename test names as a rubric
- Do not mix public TB canaries into Applied Work marketing copy
- Do not commit `.env`, API keys, `jobs/`, `_source/`, or the source zip
