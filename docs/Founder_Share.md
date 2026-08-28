# Share Worlds Lab with the founder

**Audience:** CB (Siva) → Raja (`rajaadil07`, GitHub collaborator)  
**Deadline context:** UI can go out tonight. Frontier 160 (10 × 8 Opus + 8 gpt-5.6-sol) still needs Docker/Harbor on an eval host and is **not** done.  
**Do not paste API keys.** Keys already leaked in chat — **rotate** Anthropic and OpenAI keys. Never reprint them.

---

## 1. Send in the next five minutes

### A. Open the PR (preferred if they can clone)

Draft PR: https://github.com/Sivadheeraj5356/terminus-logs/pull/1  
Branch: `cursor/applied-work-lab-batch-01-826a`

Ask them to open `lab/index.html` after clone:

```bash
git clone git@github.com:Sivadheeraj5356/terminus-logs.git
cd terminus-logs
git checkout cursor/applied-work-lab-batch-01-826a
python -m http.server 8765
```

Then: http://127.0.0.1:8765/lab/index.html

Deep links:

- Overview (default): `/lab/index.html`
- Tasks table: `/lab/index.html?surface=tasks`
- Batch 01: `/lab/index.html?surface=tasks&filter=batch`
- One package: `/lab/index.html?task=repair-the-pendulum-motion-solver`
- Agents (honest ingest, no fake curves): `/lab/index.html?surface=agents`

### B. Zip if they cannot clone the private repo

From the repo root:

```bash
bash scripts/pack_lab_share.sh
```

That writes `docs/worlds-lab-founder-share.zip` (`lab/` + this note + two sample Harbor packages so file links are not all 404). Send the zip. They unzip and run:

```bash
python -m http.server 8765
```

and open `/lab/index.html`. The other 98 package file links 404 unless they have the full repo.

### C. Public tunnel from this VM

This cloud-agent VM did **not** get a stable public tunnel (`cloudflared` / `ngrok` not available here). **Clone or PR is the share path.** Do not wait on a URL from this pod.

---

## 2. What to tell them they are looking at

| Surface | What is real tonight |
| --- | --- |
| Overview | Applied Work Worlds Lab intro, 100 / 448 / batch-01 = 10, charts from **our** `instruction.md` + category mix |
| Tasks | All 100 rows. **01** mark on the frozen ten. Measured column: `oracle` for ingested oracle jobs; `Opus n/8` / `GPT n/8` only for agent trials |
| Agents | Only Harbor ingest. Smoke + oracle exist. **No effort curves.** **No 8/8.** Incomplete Opus 8-trial on pendulum may still be running in `jobs/` (gitignored) until classify+ingest |

Identity is **Applied Work Worlds Lab**. Layout follows a research-lab chrome (top nav, cream page, lavender accent, airy tables). It is not Senior SWE-Bench and not Snorkel.

---

## 3. Watch Harbor in the background (do not sit in the agent)

Leave the Harbor worker alone: https://cursor.com/agents/bc-25b86760-bb95-570b-bbdc-811f434c0215

This UI restyle: https://cursor.com/agents/bc-c8335263-e81e-541d-9718-c4891cbcadeb

Parent Worlds Lab chat: https://cursor.com/agents/bc-6d1b9c8d-8492-40cb-aa39-d597e427826a

While jobs run:

| Watch | Where |
| --- | --- |
| Probe + smoke + measure flags | `docs/lab_batch_01_status.json` |
| Last classified ingest | `docs/lab_batch_01_results.json` |
| Live Harbor output | `jobs/` (**gitignored** — do not commit; do not commit `.env`) |

After a batch of trials finishes:

```bash
python scripts/ingest_lab_jobs.py
```

Then refresh `/lab/index.html`. Measured chips and Agents n/8 update **only then**. Timeout and infra still do not count as stump.

Honest snapshot when this note was written:

- Harbor 0.22 + Docker probe: green
- Pendulum smoke: Opus reward 1.0, GPT-5.6-sol valid fail (0.0, not infra)
- Frozen 10: oracle 1.0 (Go oracle-fail package was dropped and replaced)
- Frontier: Opus `k=8` on pendulum **started** (`jobs/lab01-opus-repair-the-pendulum-motion-solver`). Target remains **160** jobs. Not complete.

---

## 4. Deadline realism

- **Tonight:** gallery + SSB-like chrome is shareable (PR, zip, or local `http.server`).
- **Not tonight unless the eval host finishes:** 10 × (8+8) frontier. Nested Docker on a cloud agent is the wrong place to claim 160 done.
- After ingest, if a chip says `1/8`, that is **one recorded attempt of eight planned**, not a fake full group.
