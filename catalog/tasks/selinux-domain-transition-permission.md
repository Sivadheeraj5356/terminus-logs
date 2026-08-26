# # SELinux Domain Transition Permission

Submission: `4c297dcc-2133-4ba9-97bd-82e19c299258`  
Slug: `selinux-domain-transition-permission`  
Latest archive: `4c297dcc-2133-4ba9-97bd-82e19c299258_submission_2026-07-10T11_44_14.248Z.zip`  
Revisions in Dropbox: 2

## Task summary

The domain-transition lab replays three case batches through a hop-check CLI. After a clean rebuild and pipeline run, the emitted security report shows accepted transitions where policy traps should deny, disagreement between configured, sampled, and live grant masks on the same row, and incorrect accept tags when an identical role label appears under a different pivot key in a later batch. Replay batches listed in `/app/docs/d8_run_notes.md`, then run `/app/tools/h2_runner` and `/app/tools/q1_emit`. The hop runner writes `/app/var/d8_raw.jsonl` and `/app/var/d8_pivot.jnl`; the emitter writes `/app/output/d8_observations.json` and `/app/var/d8_stamp.txt`. Tests delete generated artifacts, run `make -C /app/environment clean`, rebuild with `make -C /app/environment all -j2`, and rerun both tools. Row and gate digests recompute through `python3 /app/environment/lib/digest_check.py`.

Required artifacts include: `/app/docs/d8_run_notes.md`, `/app/tools/h2_runner`, `/app/tools/q1_emit`, `/app/var/d8_raw.jsonl`, `/app/var/d8_pivot.jnl`, `/app/output/d8_observations.json`, `/app/var/d8_stamp.txt`, `/app/environment`.

Author anonymous tagged this **hard** system-administration task (selinux, mac, sandbox, capability, security, domain).

Time estimates: expert ~45 min, junior ~150 min.

Harbor timeouts: agent 1800s, verifier 1500s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `4c297dcc-2133-4ba9-97bd-82e19c299258_submission_2026-07-10T11_44_14.248Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Identity, ACL, or permission mapping is close but fails the restore/authority contract. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
