# Share Worlds Lab with the founder

**Audience:** CB (Siva) → Raja (`rajaadil07`, GitHub collaborator)  
**Deadline context:** Gallery + 12 Worlds Lab surfaces are shareable. Cheap k=5 fill **stopped** on Anthropic credit-too-low (Batch 01 partial). Batches 02–05 are frozen, not measured. Not 50/50. Not 160/160.  
**Do not paste API keys.** Keys already leaked in chat — **rotate** Anthropic and OpenAI keys. Never reprint them.

---

## 1. Send in the next five minutes

### A. Open the PR (preferred if they can clone)

Draft PR: https://github.com/Sivadheeraj5356/terminus-logs/pull/1  
Branch: `cursor/applied-work-lab-batch-01-826a`

Ask them to open `lab/index.html` after clone. Serve from the **repo root**:

```bash
git clone git@github.com:Sivadheeraj5356/terminus-logs.git
cd terminus-logs
git checkout cursor/applied-work-lab-batch-01-826a
python3 -m http.server 8765 --bind 0.0.0.0
```

Then: http://127.0.0.1:8765/lab/index.html

Batch filter (all frozen tens): http://127.0.0.1:8765/lab/index.html?surface=catalog&filter=batch  
Batch 01 only: http://127.0.0.1:8765/lab/index.html?surface=catalog&filter=b01  
`surface=tasks` still aliases Catalog.

Deep links:

- Worlds (default): `/lab/index.html` or `?surface=worlds`
- Catalog: `/lab/index.html?surface=catalog`
- Frozen batches: `/lab/index.html?surface=catalog&filter=batch`
- One package: `/lab/index.html?task=repair-the-pendulum-motion-solver`
- Pendulum Runs / Traces / Failures: `?surface=runs&task=repair-the-pendulum-motion-solver` (same for `traces`, `failures`)
- Spend / Batches (credit stop): `?surface=spend` · `?surface=batches`
- Agents (honest ingest, no fake curves): `/lab/index.html?surface=agents`

### B. Zip if they cannot clone the private repo

From the repo root:

```bash
bash scripts/pack_lab_share.sh
```

That writes `docs/worlds-lab-founder-share.zip` (`lab/` + this note + two sample Harbor packages so file links are not all 404). Send the zip. They unzip and run:

```bash
python3 -m http.server 8765 --bind 0.0.0.0
```

and open http://127.0.0.1:8765/lab/index.html?filter=batch (or `?surface=tasks`). The other 98 package file links 404 unless they have the full repo. Never commit `.env`.

### C. Public tunnel (ephemeral only)

Cloudflare quick tunnels (`*.trycloudflare.com`) are **not stable**. They die when the VM sleeps or `cloudflared` exits. Do not bookmark an old hostname from a previous agent run.

To start a new one on this pod (repo root, Harbor jobs left alone):

```bash
python3 -m http.server 8765 --bind 0.0.0.0
cloudflared tunnel --url http://127.0.0.1:8765
```

`cloudflared` prints a new `https://*.trycloudflare.com` each time. Serve from the repo root so `/lab/index.html` and `../tasks/latest/...` file links resolve. Bind `0.0.0.0` (not `127.0.0.1` only). Prefer the clone path in A if you need a durable share.

If the tunnel is down, fall back to the PR/clone path in A. GitHub Pages is a weaker fallback because `tasks/latest` is huge.

---

## 2. What to tell them they are looking at

| Surface | What is real |
| --- | --- |
| Worlds | Applied Work Worlds Lab intro, 100 gallery / 50 measured target, charts from **our** `instruction.md` |
| Coverage | Domain × language matrix; batch 01–05 marks; teal = ingested jobs |
| Catalog | All 100 rows. Batch chips 01–05. Measured column is **solved / recorded** (haiku 1-trial is `0/1`, not `0/5`) |
| Runs / Traces / Failures / Stump | One dot per recorded trial; trajectory summaries; named verifier holes |
| Verifier / Harness / Spend / Batches | Oracle rules, terminus-2 + Harbor 0.22 only, Harbor `cost_usd`, ledger 01–05 |
| Agents | Only Harbor ingest. **No effort curves.** **No padded 8/8.** |

Identity is **Applied Work Worlds Lab**. Layout follows a research-lab chrome (top nav, cream page, ink-teal accent). It is not Senior SWE-Bench and not Snorkel.

---

## 3. Harbor is idle (credit / quota stop)

Do **not** start a second `harbor run`. Anthropic returned **credit-balance-too-low**; OpenAI `gpt-4o-mini` is still **429 insufficient_quota**. Stop file: [`lab_batch_01_stop.json`](lab_batch_01_stop.json). The Sonnet second arm was never started.

| Watch | Where |
| --- | --- |
| Credit / quota stop | `docs/lab_batch_01_stop.json` |
| Last classified ingest | `docs/lab_measured_results.json` (legacy `docs/lab_batch_01_results.json`) |
| Live Harbor output | `jobs/` (**gitignored** — do not commit; do not commit `.env`) |

After jobs finish (they have, for this share):

```bash
python3 scripts/ingest_lab_jobs.py
python3 scripts/write_loss_notes.py
```

Then refresh `/lab/index.html`. Measured chips update **only then**. Denominator is recorded trials — never padded to 5 or 8. Timeout, Docker, credit-too-low, and 429 are **infra**, not stump.

Honest snapshot (ingest `2026-08-29T02:02:18Z`):

- Harbor 0.22 + Docker probe: green
- Gallery 100; measured target 50; **10** Batch 01 rows have Harbor jobs
- Batch 01 oracles: 10/10 at 1.0
- Cheap arm `anthropic/claude-haiku-4-5`: pendulum **0/5** valid_fail; hypersonic **0/5** (1 valid_fail + 4 infra); dyeworks **0/3** infra (aborted); seven other Batch 01 slugs **0/1** (wildlife timeout, not stump)
- Second arm: not started (`gpt-4o-mini` 429; Sonnet never launched)
- Frontier history still on pendulum/hypersonic (Opus 5 + `openai/gpt-5.6-sol` k=8) and partial dyeworks — extra history, not the going-forward protocol
- Batches 02–05: frozen jsonl only, **not oracled, not measured**
- Loss notes: [`lab_batch_01_loss_analysis.md`](lab_batch_01_loss_analysis.md). **Not 50/50. Not 160/160.**

Parent Worlds Lab chat: https://cursor.com/agents/bc-6d1b9c8d-8492-40cb-aa39-d597e427826a

---

## 4. Deadline realism

- **Share now:** gallery + 12 surfaces (PR, zip, or local `http.server`).
- **Not now:** remaining Batch 01 Haiku fills, Sonnet k=5, or batches 02–05 — blocked until credits/quota return.
- A chip like `claude-haiku-4-5 0/5` means **0 solves out of 5 recorded trials**. A 1-trial probe is `0/1`, never padded to `/5` or `/8`. See the loss note.
