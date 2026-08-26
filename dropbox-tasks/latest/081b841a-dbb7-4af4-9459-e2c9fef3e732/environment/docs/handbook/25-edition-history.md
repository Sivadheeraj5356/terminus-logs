# Edition history

A short institutional memory of how the handbook got its current shape.
Nothing here is normative; it exists because rules read differently when
you know what they replaced.

## First Edition (2022-09)

Twelve pages. The gate it described did three things: a license
allowlist (permissive identifiers only, everything else rejected), a
flat ban on install scripts from any origin, and a quarantine list that
was literally a text file Security edited. No channels, no provenance,
no models, no exceptions — teams that needed a GPL build tool got a
hand-maintained "known exceptions" spreadsheet that the gate did not
read.

The First Edition's lesson was that a gate without a middle tier gets
routed around: the install-script ban was so broad that builder images
grew a pre-gate "vendoring" step that laundered npm packages past the
ledger entirely. The annotation tier and the clause system both exist
because of that year.

## Second Edition (2023-06)

Introduced the three-decision model (approve/annotate/reject), the
license class table (four classes replacing the allowlist), the
exception clause registry with `EX-` numbering, and the reason-code
vocabulary as a stable contract. Retired `channel-prerelease` and
`license-copyleft` in the vocabulary reorganization (chapter 13's
retired list dates here).

The Second Edition also created the amendment process. Its own text was
still edited in place twice before the board adopted the "amendments
only, consolidation at editions" discipline late in 2023 — the two
in-place edits caused an audit-replay divergence that took a week to
diagnose, and the never-edit rule is written in that week's blood.

## Third Edition (2025-04)

The big one: channels (stable/beta/nightly with the original
advisory-only beta), lockfile provenance with the three states and the
original "two or more" staleness boundary, model dependencies with
artifact pins and the original single-artifact verification phrasing,
and the quarantine registry's two entry kinds with active/lifted
status. Most of the current gate's surface dates to this edition.

The Third Edition's consolidated text incorporated amendments through
2025-03; the beta escalation (AM-2025-02) made it in, which is why
readers who learned "beta is advisory only" learned it from Second
Edition-era material, not from any printed edition — a recurring source
of confusion the FAQ still fields.

## Fourth Edition (2026-03)

This edition. Consolidation incorporated everything through
AM-2026-02, including the three 2025 severity recalibrations
(transitive-absent, unclassified-at-dev, and the integrity quantifier)
and the 2026 staleness boundary move. Structural changes: the registry
chapters adopted the explicit `Disposition` line (previously a reader
was expected to search the changelog by clause number — two internal
tools demonstrably did not), the quarantine records chapter (19) was
added, and the operational chapters (21, 22) were promoted from team
wikis into the handbook proper so that replay and queue semantics have
one authoritative statement.

The consolidation diff was replayed before adoption (chapter 21's
pre-adoption replay) and produced zero decision changes against the
then-current snapshot — as a consolidation should, since it
incorporates only amendments already in force. The board minuted the
zero-delta replay as the acceptance criterion for all future
consolidations.

## Standing lessons

Three patterns recur across editions and are worth naming for whoever
drafts the Fifth:

1. **Severity moves down more often than up.** Every recalibration
   since the Second Edition except the beta escalation and the
   integrity quantifier has *downgraded* a rejection to an annotation.
   Rules enter strict and relax as their false-positive shape becomes
   clear; drafting a new rule at annotation severity first has never
   once been regretted.
2. **Boundaries need explicit edge-case language.** The staleness
   churn, the two-generations question, and the single-versus-every
   artifact quantifier were all ambiguities that survived review
   because the drafting read naturally in the common case. Current
   drafting practice — state the boundary case in words ("exactly two
   is not stale") — dates from these.
3. **Registries outlive their readers' assumptions.** Both major
   tooling defects in the program's history came from treating filed
   registry text as current. The disposition line is the second fix for
   the same misreading; if it proves insufficient, the Fifth Edition
   should consider machine-readable dispositions rather than more
   prose.
