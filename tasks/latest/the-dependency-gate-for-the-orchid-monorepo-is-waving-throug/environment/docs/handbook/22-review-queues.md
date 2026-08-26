# Review queues and burn-down operations

Annotations only work if someone reads them. This chapter describes the
operational machinery downstream of the `annotate` decision: how
findings become queue items, who owns them, and the burn-down
expectations attached to each annotation type. None of this changes what
the gate emits; it is why the middle tier exists (chapter 01's "findings
are cheap; silence is expensive").

## From report to queue

After each generation's report is archived, the queue builder diffs it
against the previous generation and files one queue item per (row,
annotation) pair that is new, into the queue of the row's owning team.
Ownership is resolved from the manifest that pins the dependency for
direct rows, and from the nearest direct ancestor's manifest for
transitive rows — the same "punish the author" logic the provenance
rules use (chapter 07).

Items close automatically when the annotation disappears from a later
generation's report; nothing closes by hand. This is deliberate: the
only way to clear a finding is to change the input that produces it,
so queue state and ledger state cannot drift apart.

## Burn-down expectations by annotation

SLOs are set by the board and reviewed twice a year. Current values:

- **`provenance-unverified`** — 30 days. The oldest SLO and the most
  commonly breached; it feeds two rejection escalations (chapters 03,
  06), so an aging unverified row is one dependency change away from a
  blocked build. Breach pages nobody but appears in the org-level
  scorecard.
- **`provenance-stale`** — 90 days. Deliberately lax: staleness is a
  hygiene signal, and the fix (lockfile regeneration) is routinely
  batched. The churn history behind the current boundary (case study
  five) is why this SLO is not tighter.
- **`provenance-absent`** (transitive) — 60 days, owned by the direct
  ancestor's team. The queue item text names the ancestor manifest, not
  the leaf row, matching where the fix lands.
- **`channel-beta`** — no SLO. The annotation is a standing posture
  signal, not a defect; it closes when the pin reaches a stable
  release. The scorecard tracks *count* of beta rows per org instead.
- **`license-review`** — quarterly, aligned to Legal's copyleft review
  cycle rather than a per-item clock. Items batch into the review; the
  review's output occasionally becomes waiver requests or class-table
  proposals.
- **`license-exception`** — no burn-down (the annotation is permanent
  by design), but every item links the granting clause, and clause
  review cycles (chapter 10) consume the queue as their worklist.
- **`license-unclassified`** (dev) — 120 days, the gentlest SLO,
  matching the negligible exposure that justified the downgrade
  (AM-2025-11). The expected close is a board evaluation adding the
  identifier to the class table — or the tool ceasing to be used.
- **`quarantine-lifted`** — no SLO, no expected close. The item exists
  so reviewers see the history; teams may suppress it in their queue
  *views* but the item persists.
- **`npm-install-scripts`** — no per-item SLO; feeds the builder
  hardening review, which samples the queue rather than draining it.
- **`channel-exception`** — no burn-down; items link the clause and
  close at the clause's sunset or revocation.

## Escalation dynamics

Three annotation types sit one condition away from a rejection, and the
queue tooling flags these "escalation-adjacent" items prominently:

- an `unverified` direct runtime row that later pins a beta version
  crosses into `channel-unverified-beta` (chapter 06);
- an `unverified` transitive npm row that later enables install scripts
  crosses into `npm-untrusted-scripts` (chapter 03);
- a `channel-exception` row whose provenance regresses from `verified`
  loses the exception entirely and reverts to `channel-nightly`
  (chapter 06).

The flag exists because each crossing looks, from the diff, like the
gate "suddenly" rejecting a row nobody touched — when in fact a
neighboring attribute changed under a standing combination rule. Review
tooling that explains the triple prevented most of the escalation
surprise tickets after AM-2025-02 landed.

## Scorecards

The org-level scorecard aggregates queue age percentiles per annotation
type, beta-row counts, and escalation-adjacent counts. Two design
choices keep it honest. First, the scorecard reads the *archive*, not
the queues — a queue item deleted by tooling error resurrects at the
next scorecard build because the annotation is still in the report.
Second, rejected rows do not vanish from hygiene metrics: a rejection
whose row also carried annotations contributes them to the counts,
since the annotations describe work that survives whatever unblocks the
rejection (chapter 14 records annotations on rejected rows for exactly
this reason).
