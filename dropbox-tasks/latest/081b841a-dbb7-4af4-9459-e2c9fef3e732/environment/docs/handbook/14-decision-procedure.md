# The decision procedure

This chapter defines how per-row findings become the row's decision, and
how the rows become the decisions report. It is short because the
procedure is mechanical by design — every judgment call lives in the rule
chapters, and this chapter only aggregates.

## Per-row aggregation

For each ledger row, evaluate every rule chapter independently and collect
two sets: the **reasons** (rejection findings) and the **annotations**.
Then:

1. If the reason set is non-empty, the decision is **reject**. All
   collected annotations are still recorded — a rejected row's annotation
   list is not cleared, because reviewers triaging a rejection want the
   full picture (a rejected beta row still shows its `channel-beta`).
2. Otherwise, if the annotation set is non-empty, the decision is
   **annotate**.
3. Otherwise, the decision is **approve**.

There is no severity ordering among reasons, no "primary" reason, and no
short-circuiting: a row that is quarantined *and* license-blocked *and*
unpinned reports all three reasons. Implementations that stop at the first
rejection produce incomplete reports and fail audit replay, because
burn-down tooling diffs full reason sets across generations.

The two replacement pairs (chapter 13) are resolved *inside* their rule
chapters, before aggregation: the license rules emit exactly one of
`license-blocked` or `license-exception` for a strong-copyleft row, and
the channel rules emit exactly one of `channel-nightly` or
`channel-exception` for a nightly row. Aggregation never revisits them.

## Evaluation order does not matter

Rule chapters read only ledger columns, the quarantine registry, the
integrity report, and the exception registry. No chapter reads another
chapter's findings. Consequently the chapters may be evaluated in any
order — the sets are unions of independent contributions. Two findings
about the same underlying fact (an `unverified` row that is also caught by
the npm script rule) are two findings, by design; deduplication happens
only at the identifier level within each set.

## Report assembly

The report carries the snapshot's generation and one decision entry per
ledger row. Entries are ordered by **ecosystem, then name, then version**,
ascending, using plain string comparison at each key — no version-aware
comparison, no locale collation. Within each entry, `reasons` and
`annotations` are emitted as lexicographically sorted arrays (they are
sets; the sort is presentational). Both arrays are always present, empty
where there are no findings.

Determinism is a contract: the same ledger snapshot, quarantine registry,
integrity report, and handbook rules must produce a byte-identical report
on every evaluation, on any machine, in any year. This is what makes
audit replay possible (re-running old generations against the rules then
in force) and what makes report diffs meaningful review artifacts. Any
nondeterminism — map iteration order leaking into arrays, wall-clock
reads, environment-dependent tie-breaks — is a defect.

## What the decision does

Downstream consumption, for context (none of this is the gate's job):
**reject** fails ledger admission, so the offending generation never
becomes buildable; **annotate** admits the row and files the annotations
into the owning team's review queue, where several annotation types carry
burn-down SLOs set outside this handbook; **approve** admits silently.
The report is also archived per generation as the compliance record the
audit replay reads.

## Worked example

A hypothetical row: npm package, `beta` channel, `runtime` scope,
`transitive` origin, `unverified` provenance, MIT license, install scripts
true.

- Channel: `channel-beta` annotation. The escalation does not fire —
  origin is `transitive`, and the triple requires `direct`.
- Provenance: `provenance-unverified` annotation. Staleness does not
  apply to non-`verified` rows.
- npm: `npm-install-scripts` annotation, and — install scripts,
  transitive, not verified — the `npm-untrusted-scripts` **reason**.
- License: permissive, nothing.

Reason set `{npm-untrusted-scripts}` is non-empty: **reject**, with
annotations `[channel-beta, npm-install-scripts, provenance-unverified]`
recorded alongside. Verifying the lockfile entry would clear the reason
and leave an annotate decision with the same three annotations minus
`provenance-unverified` — the row's remediation path is legible straight
from the report.
