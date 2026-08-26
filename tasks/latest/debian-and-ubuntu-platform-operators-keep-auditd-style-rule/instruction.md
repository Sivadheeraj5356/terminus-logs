Debian and Ubuntu platform operators keep auditd-style rule stacks and
augenrules-style tier merges next to host audit policy. Host audit flavor is in
/app/environment/etc/audit/auditd.conf, with rule-include flavor under
/app/environment/etc/audit/rules.d/. After ordinary rule reloads, a second
reload cycle, or a syscall-class revoke, a bundled local readiness check can
still report convergence while regenerated lineage under /app/output shows
missing syscall classes, conflicting generation markers, or dropped rows that
were previously accepted in the enforced view.

Bring the host audit rule-reload and lineage path under /app/environment into
line so /app/bin/arctl reload --profile <name> and
/app/bin/arctl inspect --profile <name> regenerate
/app/output/rule_lineage.json through the normal operator pipeline. Hand-written
output, static JSON drops, test edits, and wrapper-only bypasses are rejected.
The verifier may delete that artifact, disturb durable state, and rerun the
operator commands.

Profiles: relay, depot, and yard. The report names the profile, reloads
with scope_digest values, surviving rules, and provenance notes. Seeded starter
rows for yard are in /app/environment/store/ledger.json. Schema and digest
formulas live in /app/environment/docs/overview.md and
/app/environment/emit/schema.json.

Inspect notes must name the input_tree, durable_state, and emission surfaces
required by the overview schema. A short local readiness probe is advisory only
and does not replace reload+inspect.
