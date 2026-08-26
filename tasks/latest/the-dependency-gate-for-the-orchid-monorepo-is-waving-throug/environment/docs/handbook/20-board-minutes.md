# Board minutes digest

Condensed minutes of Dependency Review Board sittings since 2023.
Full minutes live in the board's document store; this digest records
decisions that touched handbook content, clause grants and denials, and
quarantine ratifications. Minutes are explanatory context — where a
decision changed a rule or a clause, the operative record is the
amendment (chapter 16) or the registry entry (chapters 11, 12, 19).

## 2022

**2022-06-30.** Ratified QR-1984 (the go parser-differential filing) —
the first quarantine action under the registry structure the Second
Edition would later formalize. The minutes show the board feeling for
its own procedures: the entry was debated for merit at filing, a
practice later abandoned (file first, debate at lifting).

**2022-11-14.** First discussion of the middle tier. The First
Edition's binary gate was producing the vendoring workaround at
measurable scale (three builder images carried pre-gate vendored npm
trees), and the minutes frame the question that became the
three-decision model: "we need a way to say yes-with-a-record." No
decision; directed drafting for what became the Second Edition.

**2022-12-12.** Ratified QR-2017 (protestware). Denied the first
recorded waiver-shaped request (an AGPL admin panel, runtime scope) —
the denial reasoning was reconstructed and filed for the record as
EX-031 when the registry gained denial entries the following year.

## 2023

**2023-06-26.** Adopted the Second Edition: three-decision model,
license class table, exception registry with `EX-` numbering, stable
reason-code vocabulary. Refiled the First Edition spreadsheet's
surviving grants into the two-digit series (the archive chapter
records their fates). The minutes note the edition shipped with two
known debts — no channel policy and no provenance policy — both
deferred to "when the mirror layer can attest what a lockfile claims."

**2023-10-16.** Emergency sitting after the builder credential incident.
Ratified QR-2101. Adopted AM-2023-10 (npm install-script rules) after
debating and rejecting a broader "no transitive install scripts at all"
posture — the broad form would have rejected roughly one npm row in
seven, and the provenance-conditioned form targets the actual attack
shape. Directed the creation of a standing quarantine registry with
package and artifact entry kinds.

**2023-12-04.** Denied a waiver request for an AGPL runtime library on a
customer-facing service (the requester withdrew after the network-use
discussion). Granted no clauses. Reviewed the first quarter of
install-script annotations and set no SLO yet.

## 2024

**2024-02-19.** Granted EX-103 (GPL readline binding, build scope).
Discussed version-scoped quarantine at length following a request from
Data Infrastructure; declined — see chapter 09 for the surviving
rationale. First discussion of lockfile staleness; deferred.

**2024-03-22.** Adopted AM-2024-03, introducing `provenance-stale` at the
"two or more generations" boundary. The minutes record the board
expected the boundary to need tuning ("we are guessing at the drift
constant") — a note that aged well (see AM-2026-01).

**2024-08-19.** Adopted AM-2024-08 revoking EX-104 after the provenance
audit finding. The minutes establish the standard consequence: condition
breach yields revocation even where remediation is complete, because
clauses are grants of trust, not entitlements.

**2024-11-05.** Emergency sitting on the training-data finding. Ratified
QR-2209 and the pre-emptive QR-2210. Directed the integrity-quantifier
review that became AM-2025-07 after the postmortem replay demonstrated
the single-artifact loophole (case study two).

**2024-12-09.** Adopted AM-2024-12 reclassifying LGPL-3.0-only to
weak-copyleft on the static-linking review's findings. The minutes are
explicit that the reclassification is generic to the license and our
build configurations, not a per-package determination — the distinction
between the class table and waivers, restated.

## 2025

**2025-02-17.** Adopted AM-2025-02 (the beta escalation triple) following
case study six. The requesting postmortem had proposed rejecting all
unverified beta pins; the board narrowed to the direct/runtime/unverified
triple after Build Infrastructure demonstrated the broad form would
churn transitive rows teams cannot directly fix.

**2025-05-12.** Adopted AM-2025-05 (transitive-absent downgrade) on the
same "punish the author, not the leaf" logic. Granted EX-123 (later
restricted). Reviewed annotation burn-down; set the first SLOs for
`provenance-unverified`.

**2025-07-14.** Adopted AM-2025-07: universal quantifier for model
integrity, split reason codes (`artifact-missing`, `digest-mismatch`),
retired `model-integrity`. The minutes record the design argument that
the two failure modes have different on-call owners (mirror operations
versus model platform), which the split codes route correctly.

**2025-09-08.** Adopted AM-2025-09 revoking EX-102 — the upstream fix
had shipped stable in August, and the clause's own completion condition
triggered. Minuted as the clean-exit template: need ends, clause ends.

**2025-11-24.** Adopted AM-2025-11 (unclassified-at-dev downgrade). The
minutes acknowledge the driver honestly: the rejection was generating
waiver requests the board had no instrument to grant (waivers cover
strong-copyleft only), and the choice was between inventing a new clause
family and downgrading the dev case. The board chose the smaller system.

## 2026

**2026-01-19.** Adopted AM-2026-01 moving the staleness boundary to
"more than two" after the churn analysis (case study five). The minutes
preserve the alternative considered — exempting bulk regenerations from
staleness — and the reason it lost: exemptions require the gate to know
*why* a lockfile entry changed, which the ledger deliberately does not
record.

**2026-02-23.** Adopted AM-2026-02 extending EX-131 to version 3.1.4,
with the re-run isolation review attached. Denied a concurrent request
to convert EX-131 into a range grant ("3.1.x") — enumerated lists are
load-bearing (chapter 10), and the denial is minuted as precedent.

**2026-03-02.** Editorial sitting: approved the Fourth Edition
consolidation. Confirmed the consolidation scope — rule chapters
incorporate amendments through this date; registry chapters remain
as-filed with disposition pointers. Directed that the front matter
document the split explicitly, after two internal tools were found
treating filed clause text as current.

**2026-05-27.** Emergency ratification of QR-2311 (in-place revision
rewrite at a third-party model repository). Directed Model Platform to
propose mirror-side revision pinning so that upstream rewrites surface
as sync failures rather than integrity findings.
