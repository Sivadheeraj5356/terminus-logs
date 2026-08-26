# Under /app is an offline ACL policy tool the network team runs before pushing a 

Submission: `4392a04d-f53b-4a81-aa36-76e5c25519e0`  
Slug: `under-app-is-an-offline-acl-policy-tool-the-network-team-run`  
Latest archive: `4392a04d-f53b-4a81-aa36-76e5c25519e0_submission_2026-07-06T12_55_30.762Z.zip`  
Revisions: 1

## Task summary

Under /app is an offline ACL policy tool the network team runs before pushing a firewall change. It's a Go module for an `acl` binary with two JSON-printing subcommands, and neither is finished. `acl evaluate --rules <path> --flows <path>` walks the observed flows and decides allow or deny for each, recording every log rule crossed before the terminal rule, plus a summary. `acl lint --rules <path> [--flows <path>]` audits the ruleset itself. Sample rulesets and flows live in `/app/testdata`. Rules are consulted by priority, not file order, and both subcommands must agree on that order. evaluate reports each decision with a `matched` id (the sentinel `default-deny` when nothing matches) and a `logged` list. lint has to surface the load-time problems (`bad_cidr`, `bad_port`, `bad_action`, `bad_proto`, `bad_direction`, `bad_id`, `dup_id`, `bad_priority`, and the informational `normalized`) with a `by_reason` tally, plus the analysis findings `shadowed`, `redundant`, `unreachable`, and a summary that partitions the loaded rules.

Required artifacts include: `/app/testdata`, `/app/docs`.

Author anonymous tagged this **hard** security task (go, firewall, acl, cidr, security-policy, packet-filtering).

Time estimates: expert ~90 min, junior ~180 min.

Harbor timeouts: agent 900.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Archive `4392a04d-f53b-4a81-aa36-76e5c25519e0_submission_2026-07-06T12_55_30.762Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Identity, ACL, or permission mapping is close but fails the restore/authority contract. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
