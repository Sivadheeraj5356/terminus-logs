# Front matter

## Edition and scope

This is the **Fourth Edition** of the Orchid Dependency Governance Handbook,
consolidated 2026-03-02. It supersedes the Third Edition (2025-04) and every
interim memo issued between editions. The handbook governs all four dependency
ecosystems the Orchid monorepo consumes — npm, PyPI, Go modules, and the
Hugging Face model registry — and applies to every build that runs against a
ledger snapshot, whether on a developer workstation, in presubmit, or in the
release pipeline.

The handbook is a *policy* document, not a tooling manual. It says what the
gate must decide, not how any particular implementation arrives at the
decision. Implementations come and go; the obligations described here persist.
Where an implementation and this handbook disagree, the handbook is
authoritative, and the discrepancy is a defect in the implementation.

## How to read this edition

The Fourth Edition made one structural change that trips up returning readers:
the **rule chapters were consolidated, the registry chapters were not.**

Chapters 03 through 09 — ecosystems, license classes, waiver mechanics,
release channels, lockfile provenance, model registry integrity, and the
quarantine program — were rewritten during consolidation so that the text on
the page is the rule **as currently in force**. Historical values that were
revised between editions appear only as explicitly marked historical notes,
and the full revision trail lives in the changelog (chapter 16).

Chapters 11 and 12 — the exception clause registry — deliberately preserve
each clause **as originally filed**, because clause text is a legal-style
record: the filed wording is what the requesting team agreed to and what the
review board approved. A filed clause is *not* a statement that the clause is
currently in force. Every registry entry carries a `Disposition` line; when
that line points at an amendment identifier, the amendment in chapter 16 is
part of the clause's current meaning. Revocations, extensions, and scope
changes are recorded **only** in the changelog. Reading a registry entry
without resolving its disposition gives you the clause as it stood on its
filing date, which may be years out of date.

This split is intentional. Rule chapters answer "what is the rule today?"
directly. Registry chapters answer "what exactly was granted?" and require a
join against chapter 16 to answer "is it still granted, and in what form?"

## Precedence

When two provisions appear to conflict, resolve in this order:

1. An amendment in chapter 16, by its effective date (latest wins).
2. The rule chapters (03–09) as printed in this edition.
3. A filed exception clause (11–12), as modified by its disposition.
4. Case studies (15), the FAQ (18), and the glossary (17), which are
   explanatory and never controlling.

A case study that quotes a threshold, a class table, or a clause is quoting
the rule **as it stood at the time of the incident**. Several case studies
predate amendments that changed the quoted values. They were kept in their
original form because the narrative only makes sense against the rules of the
day; they are not a source of current values.

## Terminology conventions

Field names from the ledger (`scope`, `origin`, `provenance`, `channel`,
`lock_generation`) are used in their exact ledger spelling throughout. Reason
codes and annotation identifiers appear in fixed-width type (for example,
`quarantined`, `provenance-stale`) and are enumerated exhaustively in chapter
13; no other identifier is valid gate output. "Reject", "annotate", and
"approve" are the only decisions; chapter 14 defines how findings aggregate
into a decision.

## Change control

Handbook changes are made by amendment only. An amendment carries an
identifier (`AM-<year>-<month>`), an effective date, the chapters it touches,
and its operative text. Amendments are cumulative and are never rebased into
registry entries retroactively; consolidation into rule-chapter text happens
only at edition boundaries. Chapter 16 lists every amendment since the Second
Edition. If a rule matters to a decision you are making, and the rule's
chapter admits any doubt, check the changelog before acting — an amendment
effective after this edition's consolidation date modifies the printed text
of chapters 03–09 as well.
