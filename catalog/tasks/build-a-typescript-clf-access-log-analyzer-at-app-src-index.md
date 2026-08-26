# Build a TypeScript CLF access-log analyzer at `/app/src/index.ts`. It must read 

Submission: `5dbdf19d-5703-4186-8c92-a9febbc98244`  
Slug: `build-a-typescript-clf-access-log-analyzer-at-app-src-index`  
Latest archive: `5dbdf19d-5703-4186-8c92-a9febbc98244_submission_2026-07-13T05_49_48.976Z.zip`  
Revisions: 3

## Task summary

Build a TypeScript CLF access-log analyzer at `/app/src/index.ts`. It must read only regular `.log` files directly under `/app/logs`, ignore directories and symlinks, compile with the provided TypeScript config, and write `/app/report.json`. Parse Combined Log Format lines with an IP, ident, user, timestamp, quoted request, status, bytes, quoted referer, and quoted user agent. Ignore empty or whitespace-only lines. Treat every other bad line as malformed, including lines with leading or trailing whitespace, malformed quoting, non-real timestamps, UTC offsets whose hour is not 00 through 23 or whose minute is not 00 through 59, status values outside 100 through 599, byte values other than unsigned decimal digits or `-`, and request fields that are not exactly `METHOD URL PROTOCOL` separated by single spaces. Support LF and CRLF files by removing only a trailing carriage return before validation.

Required artifacts include: `/app/src/index.ts`, `/app/logs`, `/app/report.json`.

Author Eng maq tagged this **hard** data-processing task (typescript, log-parsing, combined-log-format, json, validation, web-logs).

Time estimates: expert ~35 min, junior ~90 min.

Harbor timeouts: agent 900s, verifier 180s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `5dbdf19d-5703-4186-8c92-a9febbc98244_submission_2026-07-13T05_49_48.976Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Agent writes a locally plausible solution that misses a hidden verifier constraint. Agent explores the environment and never produces the required /app or /output artifacts.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
