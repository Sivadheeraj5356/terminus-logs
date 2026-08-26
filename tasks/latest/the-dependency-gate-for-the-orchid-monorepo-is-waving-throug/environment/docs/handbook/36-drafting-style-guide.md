# Drafting style guide

For amendment authors, registry clerks, and whoever drafts the Fifth
Edition. The handbook's authority depends on its text behaving like an
interface: precise where machines consume it, plain where humans do,
and boring everywhere. These conventions are extracted from the
editorial decisions the program has actually litigated.

## Rules

**State the rule in the indicative, once.** "A model dependency
verifies when every pinned artifact…" — not "should verify," not
"must be considered to verify," and not restated three ways in three
paragraphs. Rule chapters may explain, motivate, and give history, but
exactly one sentence per rule carries the normative load, and it reads
like a definition.

**State boundary cases in words, in the same breath.** The staleness
rule names the exactly-two case; the integrity rule says four matching
artifacts do not vouch for a fifth. This convention is written in
incident blood (chapter 25's second lesson): a boundary that is only
implied by an inequality will eventually be implemented off by one.
When a rule contains a comparison, the sentence after it says which
side of the line the equal case falls on.

**Quantifiers are explicit.** *Every*, *any*, *at least one*, *exactly
one* — never a bare plural. "Pinned artifacts must match" was the
Third Edition's costliest sentence (case study two); the Fourth
Edition's rewrite exists because a plural noun quietly reads as
"any" to an implementer having a bad week.

**Name the fields.** Rules reference ledger columns by their exact
spelling (`lock_generation`, not "the lockfile generation") on first
use in every rule statement. Prose may relax afterward; the normative
sentence does not.

**One rule, one home.** Every rule lives in exactly one chapter, and
other chapters point rather than paraphrase. The escalations that
*read* another chapter's state (the beta triple reading provenance)
are stated where they fire, with a cross-reference from where they
read. Paraphrases drift; the Second Edition's twin descriptions of
the install-script rule disagreed within a year.

## Identifiers and vocabulary

New reason codes and annotations are lowercase, hyphen-separated,
noun-phrased, and specific enough to be greppable in an archive query
(`digest-mismatch`, not `bad-artifact`). The identifier is permanent
(chapter 34's append-only obligation), so drafting one is a naming
decision with a decade's horizon: no abbreviations that only this
year's team expands correctly, no severity words baked into the name
(severity is the reason/annotation split's job — `provenance-absent`
serves as both, which works precisely because the name carries the
condition, not the verdict).

Chapter 13 is amended in the same change that introduces the
identifier, with its producing chapter and condition row. An
identifier that appears anywhere before it appears in chapter 13 is a
drafting failure the decorator's translation table will catch in CI
(chapter 34) — but catching it in review is cheaper.

## Amendments

An amendment's operative paragraph does four things in order: names
the rule or clause it touches, states the new text or delta
completely, states the old behavior it replaces, and names the
rationale in one sentence with a pointer to the fuller record (case
study, postmortem, replay delta). AM-2026-01 is the template. The
replaced behavior is stated *in the amendment* — future readers of
the changelog must be able to reconstruct both sides of the change
without hunting archived editions.

Effective dates are explicit calendar dates, never "on adoption."
Registry-touching amendments name the clause number in the header
line, because dispositions are resolved by scanning headers.

## Registry entries

Filed clause text is permanent, so the clerk's checklist at filing:
identity exact (one ecosystem, one name, spelled as the ledger spells
it); versions enumerated with no ranges; scopes enumerated for
waivers; conditions phrased so that breach is observable (a condition
nobody can audit is decoration); requesting team named; grant
rationale one paragraph, self-contained. The entry will be read in
five years by someone with no context — it either carries its own, or
it sends them to the minutes, and the minutes are long.

Denials filed for the record use the same shape with the denial
reasoning where the grant rationale would be. Successor notes at
archival name the replacing clause number and nothing else.

## Prose register

The handbook's voice is institutional but not bureaucratic: short
declaratives, concrete nouns, and the occasional recorded joke where
the minutes had one (EX-114's irony survives because the sitting
noted it). Hedging is banned from normative text — "generally,"
"typically," and "as appropriate" are review-blockers in a rule
sentence, tolerated in explanatory prose only where the variation is
real and named. Historical notes are marked as history; the Fourth
Edition's consolidation discipline (current text in rule chapters,
history in the changelog) is a drafting rule as much as a structural
one.

Finally, the test every draft faces before the board sees it: hand
the text and a synthetic ledger row to someone outside the drafting
group and ask for the row's findings. If they need the author in the
room, the draft is not done. Chapter 27 exists because this test
kept producing keepable artifacts.
