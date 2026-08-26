# The `/app` project is `channelgate`, the subscription authorization check on a s

Submission: `9594f9fa-bc95-4cb2-9f36-26883c019240`  
Slug: `the-app-project-is-channelgate-the-subscription-authorizatio`  
Latest archive: `9594f9fa-bc95-4cb2-9f36-26883c019240_submission_2026-07-19T14_56_39.070Z.zip`  
Revisions in Dropbox: 2

## Task summary

The `/app` project is `channelgate`, the subscription authorization check on a sensor telemetry bus. It reads a JSON batch on standard input, where each request pairs a channel rule a tenant has configured with the channel a subscriber is asking to read, and it writes one JSON result object on standard output. Keep the input schema exactly `{"requests":[{"rule":"...","channel":"..."}]}` and the output schema exactly `{"admitted":[true,false]}`. Each result says whether the rule admits the entire requested channel; rules that cannot be parsed must report `false`.

Required artifacts include: `/app/src`.

Author anonymous tagged this **hard** security task (security, authorization, admission, denial-of-service, search).

Time estimates: expert ~120 min, junior ~300 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `9594f9fa-bc95-4cb2-9f36-26883c019240_submission_2026-07-19T14_56_39.070Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
