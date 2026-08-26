# You are building a support-queue command line tool in Go that manages a SQLite d

Submission: `bdf62428-3f1a-4029-9cea-2ae2fff7ae43`  
Slug: `you-are-building-a-support-queue-command-line-tool-in-go-tha`  
Latest archive: `bdf62428-3f1a-4029-9cea-2ae2fff7ae43_submission_2026-07-18T12_12_47.279Z.zip`  
Revisions: 6

## Task summary

You are building a support-queue command line tool in Go that manages a SQLite database of support agents, tickets, resolutions, and an HMAC-secured audit chain. The binary lives at /app/app and every command takes the database path as its first argument, followed by any command-specific arguments. Full command signatures live in /docs/API_SPEC.md, the table layout is in /docs/schema.md, exact error strings are in /docs/error-codes.md, chain rules live in /docs/chain-spec.md, statistical formulas live in /docs/statistics-spec.md, and the integrity-check rules live in /docs/lint-spec.md. Treat those files as the source of truth for anything not covered here. At a high level, init creates the four core tables and must be safe to run more than once. Add-agent and open-ticket insert rows and reject duplicates or bad tier or priority values with specific messages. List-tickets prints tickets sorted by priority urgency and age. Resolve-ticket closes a ticket, checks it against its SLA window, and appends an entry to the resolution_chain using HMAC-SHA256, with the signing key coming from the HMAC_SECRET environment variable or a documented fallback if unset. Chain-verify walks the chain looking for tampering, recomputing each row's hash from that row's own underlying field data (ticket_id, agent_id, resolution_minutes, sla_met, resolved_at, prev_hash, as stored in resolution_chain itself — chain-verify does not re-query the tickets or resolutions tables) rather than simply trusting the already-computed current_hash value that is stored alongside those fields. See...

Required artifacts include: `/app/app`.

Author anonymous tagged this **hard** data-processing task (go, sqlite, hmac, audit-chain, statistics, sla).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1800s, verifier 450s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `bdf62428-3f1a-4029-9cea-2ae2fff7ae43_submission_2026-07-18T12_12_47.279Z.zip` is a task submission, not a Harbor job. 6 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
