# Requesting exceptions: a playbook

Chapter 10 defines the clause system; this chapter is the practical
guide for teams writing requests. It is descriptive of board practice,
not normative — but requests that follow it get decided in one sitting,
and requests that do not usually come back with questions that cost a
month.

## Before you write anything

**Confirm you need a clause at all.** Half of the requests the board
bounces are asking for instruments that do not exist or outcomes the
rules already permit. The checklist:

- Strong-copyleft rejection → license waiver. This is grantable.
- Nightly rejection → channel exception. Grantable, rarely.
- `license-unclassified` rejection → *not a waiver.* Ask the board to
  evaluate the identifier into the class table (a much lighter process
  than teams assume — most evaluations close in one sitting).
- Any provenance rejection → not grantable. Fix the lockfile; the
  remediation quick-reference in chapter 07 is genuinely short.
- `npm-untrusted-scripts` → not grantable. Verify the provenance or
  promote the dependency to direct ownership.
- Anything quarantined → not grantable, at all, by anyone. Work the
  incident; quarantine outcomes change by investigation, not request.
- Beta escalation (`channel-unverified-beta`) → not grantable, and you
  do not need it: verifying the lockfile entry dissolves the rejection
  by construction.

**Check the registry for prior art.** A revoked or expired clause for
the same package is not a precedent against you, but the revocation
reason will be the board's first question. An active clause for the
same package may already cover you — after you resolve its disposition
(chapter 10; do not trust filed text).

## Writing a waiver request

The board decides waivers on four facts. State them in order:

1. **Exact identity.** Ecosystem, name, and the enumerated versions you
   need — the versions you will actually pin, not a range you would
   like. Range requests are denied as filed (the EX-131 range denial is
   minuted precedent).
2. **Scope, argued from exposure.** Say which scopes you need and why
   the copyleft obligations do not attach there. Build-scope arguments
   are well-trodden (generators, fixture pipelines, notice tooling —
   see the registry for a dozen templates). Runtime-scope requests need
   an isolation story the board can review; EX-131 is the only runtime
   grant in the current registry and it came with a process-boundary
   review attached.
3. **The alternative you rejected.** Every strong-copyleft package has
   permissive competitors; the request should say why they lose
   (capability, correctness, migration cost — all acceptable answers
   when quantified).
4. **The condition you propose.** Offer the confinement condition
   yourself (builder-only, workstation-only, no-network). Requests that
   arrive pre-conditioned signal that the team understands what it is
   asking to be trusted with.

## Writing a channel exception request

Channel exceptions are the registry's rarest family because the default
answer is "wait for the release." The requests that succeed share a
shape: a specific upstream fix, verified against Orchid's own corpus,
needed ahead of a release train with a known-ish date, confined to
named builders, with a sunset. State the fix, the verification you ran,
the confinement, and the sunset. Remember the standing conditions: the
pinned row must have `verified` provenance or the clause simply will
not apply (chapter 06), and the version list is exact — nightly version
strings are long and easy to mistype, and a typo means the clause
covers nothing.

If you cannot name the version because you plan to track the nightly
line continuously: stop. That request has been denied every time it has
been made, and the case-study-four scar tissue is why.

## After the grant

Extensions (new versions, new scopes) are amendments — file the delta,
not a new request, and expect the original conditions to be re-checked
(EX-131's re-run isolation review is the template). Keep your review
cycle current: an overdue review freezes extensions (chapter 10), and
the freeze is enforced mechanically at filing.

Above all, treat the clause's conditions as live obligations. The
registry's revocation history is short and every entry on it is a
condition breach or a lapsed need; the board has never revoked a clause
whose conditions were being met and whose need persisted.
