An offline HAProxy edge load-balancer under `/app/environment` composes ACL and backend route plans, commits them as immutable generations behind a plan/commit token workflow, and records every commit in an append-only hash-chained ledger. The pipeline has drifted out of the contract documented under `/app/environment/docs`, so the regenerated audits and the durable state around them are no longer correct or consistent. Bring the module behavior under `/app/environment` back onto the documented contract so the normal build-and-reload path produces conformant results: every matrix cell routed to its published backend target within the published row and group ceilings, refusal-marked cells left unrouted, byte-identical paired run digests, and the ledger, generations, registry, and the `status` and `verify` reports all consistent with one another. No outbound network access is available.

Build the module and run each arm:

```bash
bash /app/environment/scripts/build_all.sh
/app/environment/bin/lb_drive --arm dense --out /app/output/haproxy_route_audit.json
/app/environment/bin/lb_drive --arm sparse --out /app/output/haproxy_route_audit.json
/app/environment/bin/lb_drive --arm weave --out /app/output/haproxy_route_audit.json
/app/environment/bin/lb_drive --arm starve --out /app/output/haproxy_route_audit.json
/app/environment/bin/lb_drive --arm held_out --out /app/output/haproxy_route_audit.json
/app/environment/bin/lb_drive --arm side_cut --out /app/output/haproxy_route_audit.json
/app/environment/bin/lb_drive --arm side_rcv --out /app/output/haproxy_route_audit.json
/app/environment/bin/lb_drive --arm side_prt --out /app/output/haproxy_route_audit.json
/app/environment/bin/lb_drive --arm side_stl --out /app/output/haproxy_route_audit.json
```

The regenerated /app/output/haproxy_route_audit.json carries arm, rule_rows, route_count, group_count, cell_outcomes, group_keys, hop_records, pane_digest, twin_digest, expected_row_cap, expected_group_cap, session_floor, session_gen, interrupt, run_stamp, generation, manifest_seal, ledger_head, plan_token, and status. The same binary also exposes plan, commit, status, verify, replay, and recover workflows. The command forms, the audit fields, the plan-token and transaction-id formulas, the ledger entry schema and chain formula, and the generation manifest seal are documented in /app/environment/docs/inv_fields.md; route ordering, packing, and matcher semantics are in /app/environment/docs/rx_board.md. Matrix cell packs live under `/app/environment/fixtures/qv/` and carry inputs, not expected answers. Durable state — the session registry, the commit ledger, immutable generation directories with their seals, the current pointer, recorded transaction ids, the quarantine area, and the cut journal — lives under `/app/environment/state/`; plan documents land under `/app/var/qxhub/plans/` and the scratch shadow surface is `/app/var/qxhub/lane.shadow`. The verifier rebuilds with the normal pipeline and checks the regenerated audit together with the durable state, so hand-written outputs will not pass and `/app/environment/bin/lb_drive` must stay the Go binary rebuilt from the module sources; `build_all.sh` uses the Go toolchain at `/usr/local/go/bin/go` even when `go` is not on the shell PATH.
