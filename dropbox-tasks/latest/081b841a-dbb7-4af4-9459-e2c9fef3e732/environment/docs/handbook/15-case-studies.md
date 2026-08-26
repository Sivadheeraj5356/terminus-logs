# Case studies

Case studies are preserved in their original form and quote the rules **as
they stood at the time of each incident**. Several quoted thresholds and
classifications have since been amended; nothing in this chapter is a
source of current rule values (see the front matter's precedence order and
the changelog).

## Case study one: the install script that chose itself (2023)

The incident that created the gate's npm rules. A stream-processing
utility deep in the web toolchain's transitive graph changed maintainers;
the new maintainer published a patch release whose `postinstall` script
decoded and ran a credential harvester. No first-party manifest named the
package — it arrived through two levels of transitive resolution — and
the lockfile entries for the affected subtree had been hand-merged during
a conflict, leaving them unverifiable against the registry.

The harvester ran on 340 builder hosts over nine days. Containment was
straightforward (builder credentials are short-lived), but the review
found the structural problem: code nobody chose, executing at install
time, with no integrity chain. Every element of what is now the
`npm-untrusted-scripts` rejection traces to this incident, as does the
quarantine registry itself — the package's entry, QR-2101, was the
registry's first active filing and remains active because the
investigation never produced a clean-version determination.

## Case study two: the model that had already shipped (2024)

An internally fine-tuned embedding model was published to the registry
and pinned by two services. Months later, a licensing review of training
corpora concluded that one dataset in the fine-tune had been used outside
its terms. The artifact was quarantined by digest (QR-2209), and the
model team published a retrained revision under new digests.

The uncomfortable finding was how close the gate of the day came to
missing it. Third-Edition integrity language said a model dependency
"verifies when a pinned artifact matches the integrity report" — drafted
when models were pinned as single archives — and the two services' pins
had by then grown to multi-file sets. During the postmortem replay, a
snapshot was found in which one pinned file had been rewritten upstream
while another still matched; under the old wording the row verified. The
quantifier was tightened by amendment shortly after (every pinned
artifact, with distinct codes for missing versus mismatched files), and
the incident is the reason chapter 08 reads the way it does.

## Case study three: the LGPL rejection that wasn't wrong, then was (2024)

A platform team pinned an LGPL-3.0-only structured-logging helper at
runtime scope and was rejected — correctly, under the class table of the
day, which placed `LGPL-3.0-only` in strong-copyleft alongside GPL and
AGPL. The team requested a waiver; the board instead commissioned the
static-linking review it had been deferring, concluded that Orchid's
build configurations uniformly satisfy the relinking requirement, and
reclassified the license into weak-copyleft by amendment.

The episode is preserved because it illustrates the boundary between the
two instruments: a waiver records "the class is right, this use is
acceptable anyway"; a reclassification records "the class was wrong."
The team's rejection predated the amendment and was never retroactively
reversed — the row simply re-evaluated to `license-review` at the next
generation after the amendment took effect.

## Case study four: the nightly compiler (2025)

A toolchain team pinned a nightly compiler build on builders, at `build`
scope, reasoning that scope isolation made it safe. The compiler nightly
miscompiled a checksum routine in a way that surfaced only in one
service's release artifacts; three weeks of binaries had to be rebuilt
and re-attested. The board's response was to remove the scope carve-out
that channel policy then contained — nightly is now rejected at every
scope absent a filed exception, and the incident is cited in every
channel-exception denial since. The clause the toolchain team eventually
received was scoped to a single builder, a single version, and a sunset,
which is the template channel exceptions follow to this day.

## Case study five: staleness churn and the boundary fix (2025–2026)

When staleness was introduced, the rule read "an entry is stale when it
is two or more generations behind the snapshot." In practice, generation
numbers advance with *any* ledger change, so an entry could drift to
exactly two-behind purely because unrelated teams landed dependency
changes — and mass lockfile regenerations to clear the annotation caused
generation churn that pushed *other* rows to two-behind, re-flagging
them in turn. One memorable week saw the same three hundred rows flagged,
cleared, and re-flagged twice with no underlying change.

The board considered exempting bulk regenerations from staleness
entirely, then chose the smaller fix: move the boundary so that exactly
two generations of lag is fresh and staleness begins strictly beyond
two. The amendment's effect was immediate — the churn pattern requires
the boundary to sit at the typical drift distance, and one generation of
headroom broke the cycle. The episode is why the staleness rule's
boundary language in chapter 07 is unusually explicit about the
two-behind case.

## Case study six: the beta that could not be reproduced (2024)

A payments-adjacent service pinned a beta release of its HTTP framework
directly, at runtime, to pick up a connection-pooling fix. The lockfile
entry was hand-edited during an urgent deploy and never re-verified.
When the team later tried to reproduce a production incident, the bytes
the resolver fetched no longer matched what production ran — upstream
had republished the beta tag, as pre-release channels are free to do.

Channel policy of the day treated beta as "advisory only" — an
annotation, nothing more. The postmortem argued, and the board accepted,
that one specific combination deserved rejection: chosen deliberately
(direct), exposed in production (runtime scope), and unpinned in the
integrity sense (provenance not verified). That triple became the
`channel-unverified-beta` escalation by amendment; the annotation-only
posture survives for every other beta configuration.

## Case study seven: the waiver that moved scopes (2025)

A diagram-DSL compiler held a waiver at both build and dev scope
(EX-123 as filed). During a toolchain cleanup, the workstation preview
tool vendored its own permissive renderer, and the dev-scope half of
the grant became dead weight — until an audit found the *vendored*
renderer had quietly re-introduced the GPL grammar files the waiver
existed to cover, outside any waiver at all, because vendored code
bypasses the ledger entirely.

The board's response was two-sided. The waiver was restricted to build
scope (the amendment is in the changelog), closing the grant to match
reality. And the vendoring gap — code entering the repo without a
ledger row — was referred to the monorepo's import-review process,
which grew a license scan on vendored directories. The case is cited
when teams propose vendoring as a way around a gate finding: the gate's
jurisdiction ends at the ledger, and the import-review process exists
precisely so that boundary is not an escape hatch.

## Case study eight: the annotation that predicted the incident (2025)

A transitive npm dependency carried `npm-install-scripts` and
`provenance-unverified` annotations for five months. Neither blocks;
the queue items aged past their SLO with routine deferrals. When the
direct parent finally regenerated its lockfile, the resolution moved
the transitive row to a version whose install script had been
compromised in the interim — and the gate rejected the new row with
`npm-untrusted-scripts` at ledger admission, before any builder ran it.

The case is taught in both directions. The rejection worked exactly as
designed: the escalation-adjacent combination (chapter 22) crossed its
threshold and the gate caught it cold. And the five months of ignored
annotations were the near-miss the SLO regime exists to prevent — the
row's owning team had every signal needed to verify the provenance in
month one, which would have made the eventual upgrade a non-event. The
postmortem's one-line summary entered the review-queue chapter
verbatim: annotations are the gate telling you where the next rejection
will come from.

## Case study nine: the replay that changed a vote (2026)

When the staleness boundary amendment (case study five) reached the
board, the packet included the standard pre-adoption replay. One board
member, skeptical that the churn was as mechanical as claimed, asked
for a second counterfactual: replay the previous six months under the
*proposed* boundary and count how many of the flagged-then-cleared
rows would simply never have been flagged. The answer — ninety-four
percent — moved the vote from contested to unanimous, and the six
percent residue identified two rows that were genuinely stale and had
been hiding in the churn noise. Both were regenerated within the week.

The case earns its place here as the program's cleanest demonstration
of the replay discipline (chapter 21): the archive answered a policy
question with arithmetic, the arithmetic changed a decision, and the
side effect surfaced real work. It is cited in every subsequent debate
about whether maintaining replay infrastructure is worth the cost.
