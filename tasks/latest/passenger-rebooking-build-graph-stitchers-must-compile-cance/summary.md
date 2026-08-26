# Passenger rebooking build graph stitchers must compile cancellation-to-replaceme

- **UUID:** `3b4836cb-00ab-4b87-9066-191d521b2c1e`
- **Slug:** `passenger-rebooking-build-graph-stitchers-must-compile-cance`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

Passenger rebooking build graph stitchers must compile cancellation-to-replacement depends_on edges and seat-inventory closures into staged layer manifests, then publish digest-sealed build ledgers that operations can trust without rebuilding the dependency graph from live inputs. Shipped compile and publish stages do not match the dependency graph, manifest digest, and export contracts below.

Inputs live under /app/data/ (passengers.json, flight-cancellations.json, seat-inventory.json, alliance-agreements.json, airline-policies.json). Compile writes /app/state/rebooking-snapshot.json and /app/state/rebooking-ledger.json.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
