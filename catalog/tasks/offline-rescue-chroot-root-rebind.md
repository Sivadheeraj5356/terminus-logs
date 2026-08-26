# # Offline rescue chroot root rebind

Submission: `61021cfc-efd5-4700-bac6-25fedf2e68fb`  
Slug: `offline-rescue-chroot-root-rebind`  
Latest archive: `61021cfc-efd5-4700-bac6-25fedf2e68fb_submission_2026-07-17T16_14_32.635Z.zip`  
Revisions in Dropbox: 1

## Task summary

An offline rescue admin stack under /app/environment must rebind the active root into a staged chroot tree, keep a linker cache scoped to that tree, and materialize the minimal device node set each storage backend needs. Field rescue runs look close: interim tallies under /app/environment/fx_bins/interim/ stay plausible and single-profile smoke often passes, but full matrix grading still reports divergent digests after arena cycles and capability-mode flips. The graded deliverable is /app/output/pack_trace.json. It must contain eight matrix rows for profiles silt, kite, rune, and dale under both capability modes cap_strict and cap_relaxed. The file must include top-level manifest_sha256 plus per-row public_id, cap_mode, prefix_digest, dev_digest, replay_digest, size_bytes, and gen_seal. Digests are 64-character lowercase hex. The size_bytes field reports total rescue packaging size for that row and must stay within the profile ceiling. The gen_seal field is the unsigned generation seal from root rebinding for that row. cap_strict requires a positive odd gen_seal with strict rescue readiness; cap_relaxed requires a positive even gen_seal with bind-only rescue. Interim file /app/environment/fx_bins/interim/q7_v9.json exposes a listing_totals object with diagnostic counts by profile; those counts must not replace graded digests.

Required artifacts include: `/app/environment`, `/app/environment/fx_bins/interim/`, `/app/output/pack_trace.json`, `/app/environment/fx_bins/interim/q7_v9.json`, `/app/output/.pack_arena`, `/app/environment/docs/pack_trace_policy.md`, `/app/environment/docs/size_ceilings.md`, `/app/environment/migrations/mig_rst.sh`.

Author anonymous tagged this **hard** system-administration task (repair, c, bash, chroot, rescue-root, system-administration).

Time estimates: expert ~90 min, junior ~240 min.

Harbor timeouts: agent 1200s, verifier 600s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Dropbox archive `61021cfc-efd5-4700-bac6-25fedf2e68fb_submission_2026-07-17T16_14_32.635Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
