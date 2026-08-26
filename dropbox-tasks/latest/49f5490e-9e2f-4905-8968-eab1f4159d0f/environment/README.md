# Break-glass authentication lab

This repository is a deterministic reduction of a PAM-style authentication service. It contains a source policy compiler, a runtime stack evaluator, authentication modules, a transaction-like effect pipeline, an append-only event journal, and materialized state projections.

Use `/app/scripts/build.sh` to compile, `/app/scripts/regenerate-policy.sh` to rebuild runtime policy, and `/app/scripts/verify-public.sh` for the public end-to-end contract. Operator-facing formats and state guarantees are described under `/app/docs`.
