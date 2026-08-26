# Terminal-Bench environment catalog

Private inventory of authored Terminal-Bench / Harbor tasks (Dropbox `terminal-bench-tasks`), plus local Harbor tooling. This is **not** the public 89-task Terminal-Bench 2 GitHub set.

Each unique submission UUID is kept once (latest revision). Older `*_submission_*.zip` files are counted as revisions, not extra tasks.

## Catalog

| | Count |
| --- | ---: |
| Unique tasks | 448 |
| Author-labeled hard | 394 |
| Author-labeled medium | 46 |
| Harbor logs in the source zips | 0 |

- Index: [`catalog/index.md`](catalog/index.md)
- Cards: [`catalog/tasks/`](catalog/tasks/)
- JSONL: [`catalog/tasks.jsonl`](catalog/tasks.jsonl)
- Technical briefing: [`docs/AppliedWork_Environments_Technical_Briefing.docx`](docs/AppliedWork_Environments_Technical_Briefing.docx)

Stump percentage is **unknown** until Harbor agent trials exist. Difficulty labels are author metadata, not measured pass rates.

`stump_pct = valid_failures / completed_trials * 100`. Timeouts and infrastructure errors do not count.

## Rebuild (local)

The source zip and extracted worlds stay on the machine; they are gitignored.

```text
python scripts/unpack_dropbox.py          # latest zip per UUID → dropbox-tasks/latest
python scripts/build_catalog.py           # rewrite catalog from extracted tasks + jobs/
python scripts/update_catalog_from_jobs.py
```

Agent batch (private model key in the shell, never committed):

```powershell
.\scripts\run_dropbox_agents.ps1
```

## Stack

Windows + Docker Desktop, Harbor 0.22, terminus-2 / oracle. Evaluation is local. Buyer platforms are not part of the runtime.
