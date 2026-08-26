# An on-call reliability engineer is deciding whether a degraded stateful service 

Submission: `403fcd7c-b947-492d-a268-d2992e87485f`  
Slug: `an-on-call-reliability-engineer-is-deciding-whether-a-degrad`  
Latest archive: `403fcd7c-b947-492d-a268-d2992e87485f_submission_2026-07-16T03_44_46.566Z.zip`  
Revisions in Dropbox: 1

## Task summary

An on-call reliability engineer is deciding whether a degraded stateful service group may move to a standby host without split-brain writes, exposed held services, or a lost rollback path. The incident evidence is under `/app/records`, the authoritative operating rules are in `/app/README.md`, and the completed failover readiness dossier must live under `/app/dossier`. The dossier has exactly sixteen artifacts across `/app/dossier/decision`, `/app/dossier/evidence`, `/app/dossier/attestations`, and `/app/dossier/index`; each artifact must describe the same incident epoch, service group, selected host, evidence basis, and safety conclusion. Place an executable operational assessment entrypoint at `/app/solve.sh`. It must read the current `/app/records` at runtime and issue the dossier from that incident evidence, because the checker may replace the estate with another same-contract failover situation before invoking it. The public rules cover incident-epoch currency, health precedence, quorum counting, lease fencing, storage mount exclusivity, dependency ordering, route exposure, credential validity, rollback blockers, exact status strings, canonical ordering, artifact integrity, and the earliest-blocker semantics for an unsafe cutover.

Required artifacts include: `/app/records`, `/app/README.md`, `/app/dossier`, `/app/dossier/decision`, `/app/dossier/evidence`, `/app/dossier/attestations`, `/app/dossier/index`, `/app/solve.sh`.

Author anonymous tagged this **hard** system-administration task (failover, quorum, fencing, rollback, service-dependencies, artifact-integrity).

Time estimates: expert ~210 min, junior ~720 min.

Harbor timeouts: agent 1200s, verifier 300s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `403fcd7c-b947-492d-a268-d2992e87485f_submission_2026-07-16T03_44_46.566Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
