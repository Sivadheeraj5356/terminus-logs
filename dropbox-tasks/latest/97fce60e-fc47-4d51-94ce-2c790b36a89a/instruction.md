The loot fairness scanner under `/app` is producing incorrect session reports after a replay refactor. Fix the implementation by editing Go code only under `/app/faircore` and `/app/rollbench`; do not modify `/app/dropvault`, `/app/go.mod`, or `/app/Makefile`.

Behavior and output requirements are defined by `/app/dropvault/fairness_rules.json` and the rule files it references. Implement all of those rules exactly.

Build with `make build` and run with `make run`. The run must produce `/app/out/lootfair` and `/app/out/fairness_report.json` written through `faircore.WriteReport`.

The report must follow the required status semantics (`FAIR` vs `BIASED`), schema, ordering, and byte format contract from the referenced rule files, and repeated `make run` on unchanged inputs must produce identical output bytes.
