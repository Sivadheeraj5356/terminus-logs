# labyrinth-oracle

Go HTTP playtest oracle for labyrinth text-adventure sessions. It tracks
world, room, inventory, consumed targets, and failed attempts, and serves
hints through a probe/assemble snapshot pipeline with route seals and abort
tickets under /app/hint-scratch/.

Contracts: /app/docs/oracle-contract.md, /app/docs/world-schema.md,
/app/docs/probe-assemble-pipeline.md, /app/docs/snapshot-attestation.md,
/app/docs/route-abort-contract.md, and /app/docs/rules-format.md.
