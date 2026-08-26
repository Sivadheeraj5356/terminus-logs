# Auth-tape lockout operations

Night cutover left three live authority planes under `/app/ctl/` and runtime
defaults under `/app/rt/`. `/app/scripts/stack_probe.sh` only exercises the unix
path and will report CLEAN even when faillock, stack binding, or principal
expiry disagree with desk notes.

Signed desk packets under `/app/data/corp/` supersede draft cutover material
under `/app/ops/cutover/` and non-authoritative fragments under `/app/config/`
once tips are in force. Retire stale override material that still hijacks stack
binding or roster precedence.

Durable ledgers under `/app/var/tally/` persist across shifts. Hygiene requires
that active desk carry rows agree on disk with the signed carry tip, not only in
the published carryover map: for each active carry slug, rewrite
`/app/var/tally/<slug>.tally` so its `failures` field equals the desk carry
value. Phantom bridge tallies for non-active slugs must be zeroed or removed
before pack replay, or clean conversations inherit orphaned failures.

Runtime defaults under `/app/rt/` must match desk polarity — soft probe posture
and legacy override honor paths disagree with the signed tip even when the unix
stack probe reports CLEAN.

Rebuild with `/app/scripts/build.sh`, then replay the pack via
`/app/tools/auth_tape_replay` so `/app/output/pam_lockout_report.json` is
generated from live state.
