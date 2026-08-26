# ## Goal

Submission: `be063bdd-bdaa-4b0b-86dc-11f74f61b7b2`  
Slug: `goal-harden-the-flask-media-metadata-service-in-app-without-changing-the-reposit`  
Latest archive: `be063bdd-bdaa-4b0b-86dc-11f74f61b7b2_submission_2026-07-05T23_51_17.597Z.zip`  
Revisions: 2

## Task summary

Harden the Flask media metadata service in `/app` without changing the repository root layout. The finished project is an offline build-and-report pipeline: it must not download anything, it must not trust a system `yq`, and `make report PORT=<port>` must generate `build/hardened-report.json` from the current fixtures, manifest, and live local API responses rather than from hard-coded values. Run Flask only on localhost with debug disabled. Allow CORS only for `https://media.example.test`, return `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`, and never expose absolute fixture paths. `/health` stays public and returns `status: ok` and `debug: false`. `/media` must require `X-API-Key: media-local-build-token`; missing or wrong keys return HTTP 401. Authorized `/media` returns only policy-accepted media as `{count, items}`, where every item has exactly `name`, `format`, `width`, `height`, and `mode`, sorted by filename. Update `openapi.yaml` to describe the hardened API, use a server URL starting with `http://127.0.0.1`, bump the old `0.1.0` version, and define/apply an API-key security scheme named exactly `ApiKeyAuth`.

Required artifacts include: not named as `/app` paths.

Author anonymous tagged this **hard** security task (perl, flask, cli-tools, supply-chain, manifest, api).

Time estimates: expert ~130 min, junior ~270 min.

Harbor timeouts: agent 900.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=weak, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `be063bdd-bdaa-4b0b-86dc-11f74f61b7b2_submission_2026-07-05T23_51_17.597Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
