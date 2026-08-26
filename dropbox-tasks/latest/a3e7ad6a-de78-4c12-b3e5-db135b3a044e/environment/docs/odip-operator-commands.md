# odip operator commands

Binary: `/app/bin/odip`

```
odip stage --scenario <dir> --policy <file> --out <lattice.json>
odip plan --lattice <lattice.json> --policy <file> --out <plan.json>
odip run --scenario <dir> --policy <file> --stage <lattice.json> --out <plan.json>
```

Default policy path when omitted: `/app/fixtures/policies/approval_policy.json`.

Optional note helpers live under /app/internal/wrap and /app/internal/sidenote for ancillary tooling.

Optional flag --journal defaults to /app/state/odip/rollout_journal.jsonl for plan and run. Exit code 4 means superseded epoch per /app/docs/rollout-epoch-seal-contract.md.

## Operator helper scripts

Optional helpers under /app/scripts check lattice and plan schemas and support fleet replay workflows.
