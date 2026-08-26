# Program metrics annex

The board reviews program health twice a year against the metrics
below; this annex records the definitions and the recent trajectory so
that numbers quoted in sittings mean the same thing across years.
Figures here are illustrative of the review narrative through the
2026-H1 review; the scorecard system (chapters 22, 34) is the live
source, and this annex is refreshed at each half-year review rather
than at editions.

## Definitions, so the numbers stay comparable

**Decision mix** — the approve/annotate/reject percentages across all
rows of the latest generation at review time. Computed from the
archive, not the queues. The mix is quoted per ecosystem and overall;
the overall figure is dominated by npm's row count and the per-
ecosystem view exists so that fact misleads no one.

**Reject recurrence** — of the rows rejected at review time, the
fraction also rejected (any reason) at the previous review. High
recurrence means rejections are pooling rather than being fixed, and
it is the number the board watches most closely.

**Annotation age** — per annotation type, the age distribution of open
queue items against their SLO (chapter 22). Quoted as the percentage
of items within SLO, at the org level.

**Escalation-adjacent count** — rows one attribute-change away from a
combination rejection (chapter 22's list). A leading indicator; case
study eight is what it leads to.

**Clause utilization** — per active clause, whether any current-
generation row exercises it. Unused active clauses are review-cycle
fodder; the utilization sweep is how lapse candidates surface.

**Replay conformance** — verification replays run and passed in the
half (chapter 21). The target is boring: every replay passes, and any
failure is a named incident with a postmortem.

## The 2025-H2 review, in brief

Decision mix held at roughly ninety-two percent approve, seven
annotate, one reject overall, with the familiar per-ecosystem skews:
npm carrying nearly all `npm-install-scripts` volume, PyPI carrying
the channel findings, Go essentially clean apart from provenance
annotations on vendored forks, and models small in row count but
over-represented in rejections when they occur (integrity rejections
arrive in incident-shaped bursts, not as a steady rate).

Reject recurrence fell to eleven percent from the prior review's
nineteen — the queue-builder's escalation-adjacent flagging (deployed
that spring) gets the credit in the review narrative, having converted
a class of surprise rejections into pre-empted fixes. Annotation age
was the sore spot: `provenance-unverified` within-SLO percentage
slipped below eighty for two orgs, and the review minuted the
follow-up that became case study eight's teaching material when one
aged item converted to a rejection in exactly the predicted way.

## The 2026-H1 review, in brief

The staleness boundary amendment (AM-2026-01, January) dominated the
half's annotation statistics: `provenance-stale` open items dropped by
just over half within two generations of the effective date, matching
the pre-adoption replay's ninety-four percent churn prediction (case
study nine), and the surviving items showed the age profile of
genuinely idle lockfile entries. The review recorded the amendment as
behaving as modeled — the phrase matters, because "as modeled" is the
standard every rule change since the replay discipline is held to.

Clause utilization flagged four active clauses with no exercising row
for two consecutive reviews; two entered lapse processing at their
review cycles, and the utilization sweep's output fed the archive
chapter's successor notes. Replay conformance was clean: forty-one
verification replays, forty-one byte-identical, zero incidents.

The models row deserves its half-sentence: QR-2311 (May) produced the
half's only integrity rejection burst, resolved as the postmortem
digest records, and the mirror-side revision-pinning proposal it
spawned was pending at review close.

## What the board does with these

The semiannual review is deliberately not a ceremony. Each metric has
a standing question attached, and the minutes record an answer to
each: is the mix drifting (policy calibration), is recurrence pooling
(enforcement working?), are SLOs credible (queue hygiene), are
escalation-adjacent counts building (the next incident's shape), are
clauses earning their keep (registry hygiene), and did replay stay
clean (the archive is still evidence). A metric with no decision
attached gets removed from the annex — two have been, and their
removal is minuted with the same care as their adoption, because a
dashboard nobody acts on is how annotation blindness (PM-2023-09)
started.

The annex's own meta-rule, adopted after that postmortem: every
number the board reviews must be recomputable from the archive by a
person with this handbook and a weekend. No metric may depend on
state that exists only in a dashboard's database — the archive is the
record, and the metrics are views over it, or they are not reviewed.
