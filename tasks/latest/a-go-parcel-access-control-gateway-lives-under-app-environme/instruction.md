A Go parcel access-control gateway lives under /app/environment. It reads untrusted parcel-routing scripts and must emit exact allow or deny security decisions for each valid request record. Bring the gateway into conformance with the security contract in /app/environment/docs/ACCESS_CONTRACT.md.

The contract covers field-count validation, ignored malformed records, generated route policies, checkpoints, replay behavior, overlays, seals, leases, rates, budgets, TTL aging, sequenced request-id binding, and rollback after denials. Standard output must contain exactly one decision line for each valid REQ record and no output for state records or ignored records.

Keep the existing CLI, script format, Makefile build interface, and output schema stable. Every non-comment REQ in /app/environment/testdata/happy.script is a valid allow smoke request and must continue to emit ALLOW.

Implement the general gateway behavior for arbitrary valid scripts. The contract document, Makefile, go.mod, registry/type definitions, smoke data, and route_064.go through route_079.go are fixed reference material.
