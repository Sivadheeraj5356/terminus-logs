# # Multi-arm site fabric

Submission: `f37da340-640d-49f5-9c54-0f753bcae8c8`  
Slug: `multi-arm-site-fabric`  
Latest archive: `f37da340-640d-49f5-9c54-0f753bcae8c8_submission_2026-07-15T13_09_16.166Z.zip`  
Revisions: 1

## Task summary

Bring `/etc/sitefab` up for the inventory under `/app/environment/topology/` and keep the sealed controller at `/usr/lib/sitefab` untouched. Drive everything through `/app/bin/sitefab`. File shapes live in `/app/environment/schema/`. Ops tickets are under `/app/environment/scenarios/`. Regional candidates under `/app/environment/drafts/` and `/app/environment/preseed/` are incomplete and often wrong; do not install them as-is. You need profile-scoped units for every topology arm (alpha, beta, gamma, remote), including generator/hand drop-ins so barrier settlement can commit bind-suffix reconcile for each profile's `data` arm from live drop-ins (not from topology unit rows). On beta, the settled durable opts for `data` carry the generator `bs=work` suffix. Dependents that hold across primary ro-to-rw flips need a Depends declaration and the `x-hold` Options token. Remotes that should compile early keep a nofail marker; deferred remotes do not. Seal What/Where to the topology paths, and keep LinkAfter / propagate fields coherent with compile order.

Required artifacts include: `/app/environment/topology/`, `/app/bin/sitefab`, `/app/environment/schema/`, `/app/environment/scenarios/`, `/app/environment/drafts/`, `/app/environment/preseed/`, `/app/output/sitefab_report.json`.

Author anonymous tagged this **hard** system-administration task (systemd-units, mount-policy, site-bring-up, policy-dropins, system-administration).

Time estimates: expert ~300 min, junior ~600 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `f37da340-640d-49f5-9c54-0f753bcae8c8_submission_2026-07-15T13_09_16.166Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
