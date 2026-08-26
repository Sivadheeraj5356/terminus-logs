# Adjudication contract

An observation has effective reliability `reliability_bp` when it has no maintenance overlap. If its half-open interval overlaps a maintenance epoch for the same toolcell, effective reliability is floor(`reliability_bp * 3 / 5`). Boundary contact where one end equals the other start is not overlap. An observation is eligible when effective reliability is at least `minimum_reliability_bp`.

The evidence board is the durable staging snapshot written under `/app/state/evidence-board.json` after adjudication. It contains schema `threatcomp.evidence-board/v1`, normalized observations sorted by ID, transitive canonical contractor names, the full policy object under the field name `captured_policy`, policy fingerprint, and checksum. Canonical contractor is the bytewise smallest member of its alias component. Policy fingerprint is `sha256:` plus lowercase SHA-256 of canonical `captured_policy` JSON. The board checksum uses the same digest over canonical board JSON with the checksum field omitted.

A source witness is independent by normalized source name. Repeated observations from one source may support an edge but count as one independent witness. Later stages must read this staging snapshot and must use effective reliability and captured policy only.
