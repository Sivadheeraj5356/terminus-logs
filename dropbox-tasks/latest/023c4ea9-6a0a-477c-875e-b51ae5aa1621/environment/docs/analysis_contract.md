# Privilege escalation analysis contract

## Tooling

Build: `make -C /app/environment all` installs the analyzer CLI to `/opt/rutile/bin/escalctl`.

Export: `escalctl analyze --profile <name> --root /app/environment/data --out /app/output/escalation_report.json`

Holdout profile labels are listed in `/app/environment/data/holdout_profiles.json`. Each profile reads bundles under `/app/environment/data/profiles/<name>/` with `iam/`, `groups/`, `roles/`, `permissions/`, `rbac/`, `cloud/`, and `catalog/` strata.

### Holdout catalog

Profiles: alpha, beta, gamma.

## Reachability channels

The combined directed graph merges four edge channels: `group`, `role`, `k8s`, and `cloud`. Final edge inventories must reflect effective reachability on each channel, not merely verbatim export rows where the channel implies chained propagation. Channel-specific policies in `/app/environment/docs/channel_policies.md` apply.

## Supporting policies

- Constraint gating: `/app/environment/docs/constraint_policy.md`
- Usage weights: `/app/environment/docs/usage_policy.md`
- Path and severity: `/app/environment/docs/path_policy.md` with `/app/environment/config/severity.toml`
- Report attestation: `/app/environment/docs/witness_policy.md`

## Report composition

Sort the final edge list by channel, then from, then to, then weight.

Analysis entry nodes are cloud identity records flagged for entry in the identity catalog. Crown targets are identity records flagged as crown.

## escalation_report.json

- `profile` string echoing the CLI flag
- `identity_count` integer count of rows in `iam/users.json`
- `edges` array of `{from, to, channel, weight}` with channel `group`, `role`, `k8s`, or `cloud`
- `chains` array of `{entry, target, hop_count, severity, path}` sorted by entry then target
- `report_digest_hex` sha256 hex of newline-joined `from:to:channel:weight` for each edge in lexicographic sorted edge-line order (64 hex characters)

Independent cross-check may use `python3 /app/environment/scripts/digest_ref.py` on export JSON.
