# Overview

Passenger rebooking build graph stitch compiles cancellation-to-replacement depends_on edges and seat-inventory closures into staged layer manifests, then publishes digest-sealed build ledgers. The compile stage collapses duplicate cancellation revisions, closes eligible replacement edges by passenger priority under alliance and connection constraints, and writes snapshot plus ledger state with a manifest digest and stage sequence. The publish stage renders plan and summary JSON from staged artifacts only so consumers never rebuild the dependency graph from live inputs.

Read input-spec.md for dataset schemas, staging-contract.md for snapshot fields and fingerprint rules, alliance-rules.md and connection-rules.md for eligibility constraints, export-spec.md for publish shapes, and ledger-contract.md for ledger persistence and manifest digest stability.
