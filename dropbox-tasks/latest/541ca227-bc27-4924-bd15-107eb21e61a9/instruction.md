# Routing ownership under in-place profile reload

`/app/bin/linkctl` is the offline link-policy control plane for topology
profiles under `/app/data/topology_w3/` and grant/withdraw events in
`/app/var/grant_feed.jsonl`. Operators drive cold boot, in-place profile
reload, and WAL-backed state reconstruction with
`bash /app/scripts/run_link_ops.sh <profile>` and
`linkctl recover --root /app/var/state --out /app/output`.

Each run must leave `/app/output/effective_fib.json`,
`/app/output/link_status.json`, and `/app/output/reconfigure_journal.jsonl`
aligned with `/app/environment/docs/operator_contract.md`:

- After cold boot on a profile, the effective FIB fingerprint matches that
  contract (rows carry `key`, `prefix`, `via`, and `class`).
- After in-place reload onto another profile, the effective FIB matches the
  restarted reachability set for the target profile even when link probes
  still report `carrier_up` (each probe also carries `slot_id` and
  `mirror_gen`).
- Journal lines record `phase` with `gen_planned` / `gen_committed`; status
  probe `mirror_gen` tracks sealed committed generations, not open planned
  generations.
- Recover rebuilds from the last sealed WAL frame only; unsealed frames are
  not tips. Deferred quarantine rows whose admit fence is unreachable stay
  out of the FIB while admitted shim rows remain.

The control plane lives under `/app/environment`. The verifier deletes
`/app/output/*` and regenerates through those disclosed commands, so static
output writes do not satisfy the contract.
