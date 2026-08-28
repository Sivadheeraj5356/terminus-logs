# Terminal-Bench environment catalog

Private inventory of authored Terminal-Bench / Harbor tasks from a private `terminal-bench-tasks` archive, plus local Harbor tooling. This is **not** the public 89-task Terminal-Bench 2 GitHub set.

Each unique submission UUID is kept once (latest revision). Older `*_submission_*.zip` files are counted as revisions, not extra tasks.

## Catalog

| | Count |
| --- | ---: |
| Unique tasks | 448 |
| Author-labeled hard | 394 |
| Author-labeled medium | 46 |
| Harbor logs in the source zips | 0 |

- Task packages (instruction, `task.toml`, Docker world, oracle, tests, `summary.md`): [`tasks/latest/`](tasks/latest/)
- Index: [`catalog/index.md`](catalog/index.md)
- Cards: [`catalog/tasks/`](catalog/tasks/)
- JSONL: [`catalog/tasks.jsonl`](catalog/tasks.jsonl)
- UUID ↔ slug map: [`catalog/uuid_map.json`](catalog/uuid_map.json)
- Caudal lab comparison (package gallery vs rollout/signal lab): [`docs/Caudal_Lab_Reference_and_Similarity.md`](docs/Caudal_Lab_Reference_and_Similarity.md)
- Applied Work Environments Lab (100 unique packages, rollouts **not run**): [`lab/index.html`](lab/index.html)
- Lab build plan: [`docs/AppliedWork_Lab_Build_Plan.md`](docs/AppliedWork_Lab_Build_Plan.md)
- MVP 100-list: [`docs/lab_mvp_100.jsonl`](docs/lab_mvp_100.jsonl)

Stump percentage is **unknown** until Harbor agent trials exist. Difficulty labels are author metadata, not measured pass rates.

`stump_pct = valid_failures / completed_trials * 100`. Timeouts and infrastructure errors do not count.

The Environments Lab is a static gallery over 100 unique packages. It does not display model scores. Serve from the repo root (`python -m http.server 8765`) and open `/lab/index.html?task=<slug>`.

## Rebuild (local)

The source zip stays local and is gitignored. Extracted latest packages live in `tasks/latest/` under catalog slugs (not UUID folder names). Each folder keeps the original UUID in `summary.md`.

```text
python scripts/unpack_tasks.py            # latest zip per UUID → tasks/latest/<slug>
python scripts/build_catalog.py           # rewrite catalog from extracted tasks + jobs/
python scripts/update_catalog_from_jobs.py
python scripts/build_lab_corpus.py --select   # 100-list + lab/corpus.json
python scripts/build_lab_corpus.py            # corpus from the frozen 100-list
python scripts/build_lab_plan_docx.py         # docs/AppliedWork_Lab_Build_Plan.docx
```

Agent batch (private model key in the shell, never committed):

```powershell
.\scripts\run_agents.ps1
```

## Stack

Windows + Docker Desktop, Harbor 0.22, terminus-2 / oracle. Evaluation is local. Buyer platforms are not part of the runtime.
