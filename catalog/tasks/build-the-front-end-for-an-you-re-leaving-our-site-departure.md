# Build the front-end for an "you're leaving our site" departure page at `/app` (s

Submission: `19dab18f-8fd8-42a2-8070-c41889e662e6`  
Slug: `build-the-front-end-for-an-you-re-leaving-our-site-departure`  
Latest archive: `19dab18f-8fd8-42a2-8070-c41889e662e6_submission_2026-07-10T12_51_53.766Z.zip`  
Revisions in Dropbox: 1

## Task summary

Build the front-end for an "you're leaving our site" departure page at `/app` (served at `/` in the sandbox). It reads a destination URL and a partner name out of the page's own query string and shows a "Continue to X" link out to that destination; there's no backend, everything is static HTML/CSS/JS. The catch: the destination and partner name both come straight from the URL, which means a visitor can be sent here with anything in those fields, including values crafted to look like one of the real partner links without actually being one, or to hijack the tab the link opens. `/app/LINKOUT_POLICY.md` is the binding spec - it names the actual allowed partner destinations, the exact element contract the verifier drives the page through, and the safety properties the departure link and the surrounding page have to satisfy. Nothing outside that file is part of the task.

Required artifacts include: `/app/LINKOUT_POLICY.md`.

Author aisha tagged this **hard** security task (browser-security, open-redirect, tabnabbing, csp).

Time estimates: expert ~55 min, junior ~120 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `19dab18f-8fd8-42a2-8070-c41889e662e6_submission_2026-07-10T12_51_53.766Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
