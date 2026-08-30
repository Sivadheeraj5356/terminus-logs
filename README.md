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
- Applied Work Worlds Lab (100 unique packages; measured chips only after Harbor ingest): [`lab/index.html`](lab/index.html)
- Worlds Lab spec (100 gallery, measured set 10→50 in tens, cheap k=5): [`docs/AppliedWork_Worlds_Lab_Spec.md`](docs/AppliedWork_Worlds_Lab_Spec.md)
- Founder share (PR / zip / how to watch Harbor): [`docs/Founder_Share.md`](docs/Founder_Share.md)
- Lab build plan: [`docs/AppliedWork_Lab_Build_Plan.md`](docs/AppliedWork_Lab_Build_Plan.md)
- MVP 100-list: [`docs/lab_mvp_100.jsonl`](docs/lab_mvp_100.jsonl)
- Frozen tens: [`docs/lab_batch_01.jsonl`](docs/lab_batch_01.jsonl) … [`docs/lab_batch_05.jsonl`](docs/lab_batch_05.jsonl)
- Batch 01 loss analysis (agent trials, not invented scores): [`docs/lab_batch_01_loss_analysis.md`](docs/lab_batch_01_loss_analysis.md)

Stump percentage is **unknown** until Harbor agent trials exist. Difficulty labels are author metadata, not measured pass rates.

`stump_pct = valid_fail / (solved + valid_fail) * 100`. Timeouts and infrastructure errors (auth, Docker, credit-too-low, 429 quota) do not count.

The Worlds Lab is a static gallery over 100 unique packages. Twelve surfaces: Worlds, Coverage, Catalog, Runs, Traces, Stump, Failures, Verifier, Harness, Spend, Batches, Agents. Measured chips appear only for frozen batch slugs that have ingested Harbor jobs. Chips use **solved / recorded trials** (a 1-trial haiku probe is `0/1`, not `0/5`). Going-forward measure is **5 independent trials × two cheap arms** (Haiku + gpt-4o-mini; if mini 429, probe gpt-4o then other cheap OpenAI slugs; Sonnet fallback if every OpenAI slug 429s). Stop after five batches (50 packages).

## Local website

Serve the gallery from the **repo root** (so `/lab/index.html` and `../tasks/latest/...` file links resolve):

```bash
python3 -m http.server 8765 --bind 0.0.0.0
```

Then open:

- Batch 01 table (10 of 100): http://127.0.0.1:8765/lab/index.html?filter=batch
- Catalog / Tasks alias: http://127.0.0.1:8765/lab/index.html?surface=tasks
- Both: http://127.0.0.1:8765/lab/index.html?surface=tasks&filter=batch
- All frozen tens (50): http://127.0.0.1:8765/lab/index.html?surface=catalog&filter=frozen
- Batch 02: http://127.0.0.1:8765/lab/index.html?surface=catalog&filter=b02
- One package: http://127.0.0.1:8765/lab/index.html?task=repair-the-pendulum-motion-solver
- `surface=tasks` still aliases Catalog

Cloudflare quick tunnels (`*.trycloudflare.com`) are **ephemeral**. They die when the VM sleeps or `cloudflared` exits. Do not treat an old hostname as a stable URL. Never commit `.env` or API keys.

Identity is **Applied Work Worlds Lab**. This is not Senior SWE-Bench, Snorkel, or Caudal branding.

Founder share notes (PR / zip / tunnel restart): [`docs/Founder_Share.md`](docs/Founder_Share.md).

## Rebuild (local)

The source zip stays local and is gitignored. Extracted latest packages live in `tasks/latest/` under catalog slugs (not UUID folder names). Each folder keeps the original UUID in `summary.md`.

```text
python scripts/unpack_tasks.py            # latest zip per UUID → tasks/latest/<slug>
python scripts/build_catalog.py           # rewrite catalog from extracted tasks + jobs/
python scripts/update_catalog_from_jobs.py
python scripts/build_lab_corpus.py --select   # 100-list + lab/corpus.json
python scripts/build_lab_corpus.py            # corpus from the frozen 100-list
python scripts/select_lab_batch.py            # freeze docs/lab_batch_01.jsonl
python scripts/select_lab_batch.py --write-later  # freeze batches 02–05 from remaining 90
python scripts/ingest_lab_jobs.py             # merge jobs/ into frozen tens only
python scripts/build_lab_plan_docx.py         # docs/AppliedWork_Lab_Build_Plan.docx
python scripts/build_worlds_lab_spec_docx.py  # docs/AppliedWork_Worlds_Lab_Spec.docx
python scripts/probe_lab_runtime.py           # keys / Harbor / Docker probe
python scripts/test_lab_batch.py
```

Lab batch (private keys in the Harbor shell, never committed). Do **not** use `run_agents.ps1` for this — it still defaults sonnet/gpt-4o over all of `tasks/latest`. Going-forward protocol is **cheap k=5** (Haiku + gpt-4o-mini; probe gpt-4o and other cheap OpenAI slugs on mini 429; Sonnet fallback if all OpenAI slugs 429). If one provider is blocked, the other arm still runs. Do not start a second `harbor run` while one is already running.

```bash
python3 scripts/run_lab_batch.py --phase probe --batch 1
python3 scripts/run_lab_batch.py --phase oracle --batch 1
python3 scripts/run_lab_batch.py --phase smoke --batch 1
python3 scripts/run_lab_batch.py --phase measure --batch 1 --yes-measure
python3 scripts/run_lab_batch.py --phase classify
```

Windows:

```powershell
.\scripts\run_lab_batch.ps1 -Phase probe -Batch 1
.\scripts\run_lab_batch.ps1 -Phase oracle -Batch 1
.\scripts\run_lab_batch.ps1 -Phase smoke -Batch 1
.\scripts\run_lab_batch.ps1 -Phase measure -Batch 1 -YesMeasure
.\scripts\run_lab_batch.ps1 -Phase classify
```

## Stack

Windows + Docker Desktop, Harbor 0.22, terminus-2 / oracle. Evaluation is local. Buyer platforms are not part of the runtime.
