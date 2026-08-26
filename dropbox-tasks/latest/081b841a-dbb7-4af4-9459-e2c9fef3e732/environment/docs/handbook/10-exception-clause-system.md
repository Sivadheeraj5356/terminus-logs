# The exception clause system

The rule chapters define defaults; exception clauses are the recorded,
bounded departures from those defaults. This chapter defines the clause
lifecycle and the reading discipline the registry requires. The registry
itself is chapters 11 and 12.

## Clause families

Two families of clause are grantable under this edition:

**License waivers** override the strong-copyleft rejection for a named
package, an enumerated version list, and an enumerated scope list
(mechanics in chapter 05).

**Channel exceptions** override the nightly rejection for a named package
and an enumerated version list, subject to the standing verified-provenance
condition (mechanics in chapter 06).

Nothing else is grantable by clause. In particular — because requests
arrive for all of these — there are no provenance exceptions, no
quarantine exceptions, no integrity ("known mismatch") exceptions, and no
unclassified-license waivers. Requests of those shapes are policy-change
requests and go through amendment, or they are incident work and go
through the quarantine program.

## Clause identity and filing

Clauses are numbered `EX-NNN` in filing order and never renumbered or
reused. The filed entry records: the family; the package identity
(ecosystem and name — exactly one of each); the enumerated version list;
for waivers, the enumerated scope list; the requesting team and the grant
rationale; the filing date; and any conditions the board attached.

Version and scope lists are always **enumerated, exact-match, and closed**.
No ranges, no globs, no "and later." This is the single most important
property of the system: a clause's blast radius is legible at a glance,
and growing it requires a new board decision.

## Dispositions: how a clause's current standing is determined

The registry preserves each clause **as filed**. Current standing is the
filed text *joined with* the clause's amendment history in the changelog
(chapter 16). Each registry entry carries a `Disposition` line maintained
by the editors:

- `active as filed` — no amendment touches the clause; the filed text is
  the current grant.
- `see AM-YYYY-MM` (one or more) — the named amendments modify the
  clause: they may **extend** it (add versions or scopes), **restrict**
  it, or **revoke** it entirely. The amendment text is operative; the
  disposition line is only a pointer, and gives no hint of the amendment's
  direction. A revoked clause grants nothing, regardless of its filed
  text.
- `expired YYYY-MM-DD` — the board attached a sunset at filing and the
  date has passed; the clause grants nothing.

The reading rule, restated from the front matter because it is the most
common mistake in gate-adjacent tooling: **a registry entry alone is never
evidence that an exception is in force.** Resolve the disposition, read
the amendments it names, and only then conclude what the clause currently
grants. The changelog is ordered by effective date; where several
amendments touch one clause, apply them in order.

## Conditions

The board may attach conditions to any grant, and two standing conditions
apply family-wide:

- Every channel exception requires the row's provenance to be `verified`
  at evaluation time (chapter 06). This condition is standing — it binds
  even where a filed clause predates it and does not mention it.
- Every waiver and exception is void while the package or artifact it
  names is under **active quarantine** — clauses modify default policy
  and never override a board judgment (chapter 09).

Clause-specific conditions appear in the filed text (isolation
requirements, review checkpoints, named owning teams). Conditions the
gate can evaluate from ledger data are enforced by the gate; conditions
it cannot (process obligations) are enforced by audit, and their breach
is grounds for revocation — several revocations in the changelog cite
exactly that.

## Requesting, extending, revoking

New grants and extensions go to the board with the use case and the exact
version/scope deltas; approvals land as amendments referencing the clause
(extensions never rewrite the registry entry). Revocations likewise land
as amendments, whether triggered by audit, by the need lapsing, or by the
periodic review cycle (waivers: two years; channel exceptions: one year —
an overdue review freezes extensions but does not auto-revoke).

The system optimizes for one reader: the person nine months from now, at
an incident bridge, asking "why is this GPL package in the build, and who
said so?" The answer must be one registry entry, its disposition chain,
and nothing else.
