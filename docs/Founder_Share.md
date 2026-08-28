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
- Pendulum + Games chip (task wins for the panel; filter stays): `/lab/index.html?surface=tasks&task=repair-the-pendulum-motion-solver&filter=games`
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

### C. Public tunnel (send this)

Live while this cloud-agent VM is awake:

**https://pierre-direct-healthy-correct.trycloudflare.com/lab/index.html?surface=tasks&task=repair-the-pendulum-motion-solver&filter=games**

Base: https://pierre-direct-healthy-correct.trycloudflare.com

That trycloudflare hostname is a **quick tunnel**. It dies when the VM sleeps or `cloudflared` exits. It is not a stable custom domain.

To restart on this pod (repo root, Harbor jobs left alone):

```bash
python3 -m http.server 8765 --bind 0.0.0.0
cloudflared tunnel --url http://127.0.0.1:8765
```

`cloudflared` prints a new `https://*.trycloudflare.com` each time. Serve from the repo root so `/lab/index.html` and `../tasks/latest/...` file links resolve. Bind `0.0.0.0` (not `127.0.0.1` only).

If the tunnel is down, fall back to the PR/clone path in A. GitHub Pages is a weaker fallback because `tasks/latest` is huge.

---

## 2. What to tell them they are looking at

| Surface | What is real tonight |
| --- | --- |
| Overview | Applied Work Worlds Lab intro, 100 / 448 / batch-01 = 10, charts from **our** `instruction.md` + category mix |
| Tasks | All 100 rows. **01** mark on the frozen ten. Measured column: `oracle` for ingested oracle jobs; `Opus n/8` / `GPT n/8` only for agent trials |
| Agents | Only Harbor ingest. **No effort curves.** **No 8/8.** Loss notes: [`lab_batch_01_loss_analysis.md`](lab_batch_01_loss_analysis.md) |

Identity is **Applied Work Worlds Lab**. Layout follows a research-lab chrome (top nav, cream page, ink-teal accent). It is not Senior SWE-Bench and not Snorkel.

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

Honest snapshot (re-ingest after jobs finish):

- Harbor 0.22 + Docker probe: green
- Frozen 10: oracle 1.0 (Go oracle-fail package dropped and replaced)
- Frontier recorded: **32/160** (pendulum + hypersonic, 8×2 each). Dyeworks Opus k=8 is the live job.
- Loss analysis: [`lab_batch_01_loss_analysis.md`](lab_batch_01_loss_analysis.md). Timeout/infra are not stumps. Target remains **160**. Not complete.

---

## 4. Deadline realism

- **Tonight:** gallery + SSB-like chrome is shareable (PR, zip, or local `http.server`).
- **Not tonight unless the eval host finishes:** 10 × (8+8) frontier. Nested Docker on a cloud agent is the wrong place to claim 160 done.
- After ingest, a chip like `GPT-5.6-sol 1/8` is **solves out of 8 planned**, not a fake full group. Pendulum Opus can read `7/8` because smoke + k=8 are unioned; k=8-only is 6/8. See the loss note.
