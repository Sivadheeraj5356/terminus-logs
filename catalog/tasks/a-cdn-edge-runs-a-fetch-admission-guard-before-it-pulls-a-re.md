# A CDN edge runs a fetch-admission guard: before it pulls a resource from an upst

Submission: `512da6e5-bd97-4ca4-87aa-8576ac4a731d`  
Slug: `a-cdn-edge-runs-a-fetch-admission-guard-before-it-pulls-a-re`  
Latest archive: `512da6e5-bd97-4ca4-87aa-8576ac4a731d_submission_2026-07-19T20_30_54.351Z.zip`  
Revisions: 1

## Task summary

A CDN edge runs a fetch-admission guard: before it pulls a resource from an upstream, it checks the request against the route's allowlist and either admits the fetch or blocks it. Leave the check too loose and an attacker slips an injected `data:` script or a look-alike host such as `evil.example.com.attacker.com` past the allowlist, and the smuggled content runs; make it too strict and the guard drops assets the site legitimately serves. The guard in the Go sources at `/app` makes exactly this allow-or-block decision. It is handed the allowlist attached to a route (the raw value of a Content-Security-Policy directive such as `script-src`), the candidate resource URL, and the page's own origin, and answers whether that fetch is admitted. What is there now leans on loose substring and prefix checks that both wave through fetches it should refuse and turn away legitimate ones; the job is to enforce the allowlist precisely so the bypasses close without breaking real traffic. The guard enforces the allowlist with the Content-Security-Policy Level 3 rules for matching a URL against a source list, which govern every case here: `'self'` against the origin scheme, host, and port, where the only scheme relaxations allowed are `http`-to-`https` and `ws`-to-`wss` (matched against the URL scheme's own default port), so an `https` origin does not admit a `wss` URL and a `wss`/`https` URL is never admitted by a `ws`/`http`-only match; a `*.example.com` host wildcard that admits subdomains but not the bare domain or a different domain; a scheme source such as `https:` matching by...

Required artifacts include: `/app/fetch_gate`.

Author anonymous tagged this **hard** security task (content-security-policy, source-list, url-matching, cdn-edge, web-security).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `512da6e5-bd97-4ca4-87aa-8576ac4a731d_submission_2026-07-19T20_30_54.351Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
