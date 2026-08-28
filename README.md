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
- Worlds Lab spec (10×8+8 then next 10): [`docs/AppliedWork_Worlds_Lab_Spec.md`](docs/AppliedWork_Worlds_Lab_Spec.md)
- Founder share (PR / zip / how to watch Harbor): [`docs/Founder_Share.md`](docs/Founder_Share.md)
- Lab build plan: [`docs/AppliedWork_Lab_Build_Plan.md`](docs/AppliedWork_Lab_Build_Plan.md)
- MVP 100-list: [`docs/lab_mvp_100.jsonl`](docs/lab_mvp_100.jsonl)
- First measured ten: [`docs/lab_batch_01.jsonl`](docs/lab_batch_01.jsonl)
- Batch 01 loss analysis (agent trials, not invented scores): [`docs/lab_batch_01_loss_analysis.md`](docs/lab_batch_01_loss_analysis.md)

Stump percentage is **unknown** until Harbor agent trials exist. Difficulty labels are author metadata, not measured pass rates.

`stump_pct = valid_failures / completed_trials * 100`. Timeouts and infrastructure errors do not count.

The Worlds Lab is a static gallery over 100 unique packages (Overview / Tasks / Agents). Measured chips appear only for batch-01 slugs that have ingested Harbor jobs. Serve from the repo root (`python -m http.server 8765`) and open `/lab/index.html?task=<slug>`. To send the gallery tonight, see [`docs/Founder_Share.md`](docs/Founder_Share.md).

## Rebuild (local)

The source zip stays local and is gitignored. Extracted latest packages live in `tasks/latest/` under catalog slugs (not UUID folder names). Each folder keeps the original UUID in `summary.md`.

```text
python scripts/unpack_tasks.py            # latest zip per UUID → tasks/latest/<slug>
python scripts/build_catalog.py           # rewrite catalog from extracted tasks + jobs/
python scripts/update_catalog_from_jobs.py
python scripts/build_lab_corpus.py --select   # 100-list + lab/corpus.json
python scripts/build_lab_corpus.py            # corpus from the frozen 100-list
python scripts/select_lab_batch.py            # freeze docs/lab_batch_01.jsonl
python scripts/ingest_lab_jobs.py             # merge jobs/ into the 10 only
python scripts/build_lab_plan_docx.py         # docs/AppliedWork_Lab_Build_Plan.docx
python scripts/build_worlds_lab_spec_docx.py  # docs/AppliedWork_Worlds_Lab_Spec.docx
python scripts/probe_lab_runtime.py           # keys / Harbor / Docker probe
python scripts/test_lab_batch.py
```

Lab batch (private keys in the Harbor shell, never committed). Do **not** use `run_agents.ps1` for this — it still defaults sonnet/gpt-4o over all of `tasks/latest`.

```powershell
.\scripts\run_lab_batch.ps1 -Phase probe
.\scripts\run_lab_batch.ps1 -Phase oracle
.\scripts\run_lab_batch.ps1 -Phase smoke
.\scripts\run_lab_batch.ps1 -Phase measure -YesMeasure
.\scripts\run_lab_batch.ps1 -Phase classify
```

## Stack

Windows + Docker Desktop, Harbor 0.22, terminus-2 / oracle. Evaluation is local. Buyer platforms are not part of the runtime.
