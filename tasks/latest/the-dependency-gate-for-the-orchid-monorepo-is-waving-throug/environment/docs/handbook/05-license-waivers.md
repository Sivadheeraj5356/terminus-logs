# License review and waivers

Strong-copyleft dependencies are rejected by default (chapter 04). This
chapter describes the only mechanism that overrides that default: the
**license waiver**, a species of exception clause (chapter 10) granted by
the review board for a named package, an explicit version list, and an
explicit scope list.

## What a waiver is

A waiver is a determination by the board — with Legal sitting — that a
specific use of a specific strong-copyleft package, at specific versions
and scopes, does not create obligations the company is unwilling to carry.
The classic grants: a GPL build tool that never ships (compilers,
generators, shims around GNU readline), or a GPL library isolated behind a
process boundary the board has reviewed.

A waiver is *never* a class re-evaluation. If the board concludes a license
was simply mis-classed, the class table changes by amendment; a waiver
records that the class is right and this particular use is nonetheless
acceptable.

## Waiver anatomy

Every waiver is filed in the exception registry with:

- **Package identity** — one ecosystem and one name. A waiver never spans
  packages; forks and renames require new filings.
- **Version list** — explicit, enumerated versions. Waivers never use
  ranges. When a team upgrades a waived package, the new version must be
  added by amendment before the ledger can pin it — this is deliberate
  friction, since a new version can add new components under different
  terms.
- **Scope list** — the ledger scopes the waiver covers. A waiver granted
  for `build` scope says nothing about `runtime` use of the same package
  and version; the rejection stands for any scope outside the list. Scope
  restrictions are the board's main tool for granting narrow waivers, and
  most filed waivers do not cover `runtime`.
- **Disposition** — the standing of the clause after any amendments; see
  chapter 10.

## How a waiver applies

For a ledger row with a strong-copyleft license, the gate checks the
registry for an **active** waiver whose ecosystem and name equal the row's,
whose version list contains the row's version exactly, and whose scope list
contains the row's scope. If — and only if — all three match on an active
clause, the `license-blocked` rejection is replaced by the
`license-exception` annotation.

There is no partial credit anywhere in this check. Version `6.2.3` is not
covered by a waiver listing `6.2.1` and `6.2.2`; `runtime` scope is not
covered by a waiver listing `build`; and a revoked waiver covers nothing at
all regardless of what its filed text says. String comparison is exact,
including version suffixes — `3.1.0` and `3.1.0-patched` are different
versions to the gate as they are to the package manager.

Waivers apply only to the strong-copyleft rejection. They do not touch
`license-unclassified` (an unclassified license needs a board evaluation,
not a waiver), quarantine findings, channel findings, or provenance
findings. A row can simultaneously carry `license-exception` and be
rejected for entirely unrelated reasons.

## Requesting and maintaining waivers

Requests go to the board with the use case, the isolation story, and the
version list the team actually needs. Grants are recorded as `EX-` clauses
in the registry chapters; extensions (new versions, added scopes) and
revocations are recorded as amendments in chapter 16 that reference the
clause. The registry entry itself is never edited after filing — a reader
of chapter 11 or 12 sees the original grant, and must resolve the
disposition against the changelog to know its current form. Chapter 10
describes this lifecycle in full.

Waivers are reviewed on a two-year cycle. A lapsed review does not
auto-revoke (revocation is always an explicit amendment), but it does
freeze extensions: the board will not add versions to a waiver whose
review is overdue, which in practice pushes teams off the waived package
or through a fresh review.

## A note on "shim" packages

A recurring request pattern is the GPL *shim*: a thin wrapper around a GPL
library, published under the library's license, used only at build time.
The board has granted several of these (the readline case in the registry
is representative) and consistently restricts them to `build` scope. Teams
occasionally read such a grant as covering the shim "wherever it ends up."
It does not. If a shim migrates into a shipped binary, its ledger row
becomes `runtime`-scoped, the scope check fails, and the default rejection
returns — precisely the situation the scope list exists to catch.
