# System administration workflow — fleet daemon start-race desk

This task is a system-administration fleet rollout on systemd hosts. The graded work is operational: publish a daemon lifecycle desk-trace that seals socket-activation start-race phases across the fleet topology. It is not a single-script debug exercise and not an application bug hunt.

## Terminology

| Term | Plain meaning |
|------|----------------|
| desk | Operations console that coordinates per-scenario daemon starts and persists host state under /app/desk-state |
| k9 tools | Fleet operator binaries: k9_invoke (run one scenario), k9_recover (rebuild checkpoint validity), k9_emit (seal the operational report) |
| socket-activation | systemd starts a daemon when its listener socket accepts work, then may pass file descriptors to the service |
| desk-trace | Operational JSON report at /app/output/k9_trace.json with phase rows and a chain_fingerprint seal |
| xr4 depth | Sampling depth listing for the xr4 rollout phase; sector markers are listed per scenario in k9_contract.md |
| WAL barrier order | Write-ahead log ordering that must match checkpoint seals before emit accepts the fleet run |
| chain_fingerprint | Digest over sorted phase rows that must stay stable across a second emit |

## Fleet rollout stages

1. Load scenario fixtures from /app/cases/seq into the desk state root /app/desk-state.
2. Invoke daemon lifecycle for each scenario index through k9_invoke.
3. Persist epoch caches, signal slots, and WAL append lines for the host topology.
4. Recover checkpoint validity through k9_recover when the append log is consistent.
5. Emit the operational seal /app/output/k9_trace.json through k9_emit.

## Operational envelopes

- Daemon lifecycle rows must bind sequences to on-disk ledger snapshots at invoke time.
- Topology drift is detected when ledger bytes change between invokes for the same scenario index.
- Config drift across hosts is represented by scenario-isolated signal slots; slots must not cross scenario indices.
- The operational seal is accepted only when WAL CRC lines match payloads and checkpoint state is valid.

Detailed field math and per-scenario tables live in /app/docs/k9_contract.md. Operator command lines live in /app/docs/fleet-operator-commands.md.
