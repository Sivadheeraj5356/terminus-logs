# Offline rescue chroot root rebind

An offline rescue admin stack under /app/environment must rebind the active root into a staged chroot tree, keep a linker cache scoped to that tree, and materialize the minimal device node set each storage backend needs. Field rescue runs look close: interim tallies under /app/environment/fx_bins/interim/ stay plausible and single-profile smoke often passes, but full matrix grading still reports divergent digests after arena cycles and capability-mode flips.

The graded deliverable is /app/output/pack_trace.json. It must contain eight matrix rows for profiles silt, kite, rune, and dale under both capability modes cap_strict and cap_relaxed. The file must include top-level manifest_sha256 plus per-row public_id, cap_mode, prefix_digest, dev_digest, replay_digest, size_bytes, and gen_seal. Digests are 64-character lowercase hex. The size_bytes field reports total rescue packaging size for that row and must stay within the profile ceiling. The gen_seal field is the unsigned generation seal from root rebinding for that row. cap_strict requires a positive odd gen_seal with strict rescue readiness; cap_relaxed requires a positive even gen_seal with bind-only rescue. Interim file /app/environment/fx_bins/interim/q7_v9.json exposes a listing_totals object with diagnostic counts by profile; those counts must not replace graded digests.

After a successful matrix grade the staging arena at /app/output/.pack_arena is marked dirty and a second grade without recovery must fail. Corrupt arena state must also fail until restored. Arena recovery rules, digest formulas, byte ceilings, and the public grading checker are defined in /app/environment/docs/pack_trace_policy.md and /app/environment/docs/size_ceilings.md. Repeat /app/environment/migrations/mig_rst.sh only via the idempotent recovery command in pack_trace_policy.md before re-running the checker.

Repair the rescue rebinding, linker cache, and device materialization layers under /app/environment so the normal rescue pipeline regenerates the trace. Hand-written or static trace JSON is insufficient.

The platform verifier reruns /app/tests/test.sh.
