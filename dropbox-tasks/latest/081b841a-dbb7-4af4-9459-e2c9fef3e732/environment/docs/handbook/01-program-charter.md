# Program charter

## Why the gate exists

The Orchid monorepo builds ship to every product surface the company runs.
A dependency that enters the build enters all of them, and it enters with the
privileges of the build itself: install scripts run on builder machines,
model artifacts are loaded into services that handle customer content, and
licenses attach obligations to the shipped binaries. The dependency gate
exists so that these consequences are decided deliberately, once, in a place
that can be audited — rather than implicitly, per-team, in ten thousand
lockfile diffs.

The gate's mandate comes from two incidents, both described at length in the
case studies chapter. The first was a compromised npm package whose install
script exfiltrated builder credentials; the package arrived transitively, was
never reviewed by any human, and ran on 340 builder hosts before it was
caught. The second was a fine-tuned internal model whose training set was
later found to include data the company had no right to use; the artifact had
already been baked into two service images by the time legal flagged it. In
both cases the post-incident review found the same root cause: there was no
single point at which the organization *decided* to take the dependency.

## What the gate decides

For every row of the build ledger, the gate produces exactly one of three
decisions:

- **approve** — the dependency enters the build with no recorded findings.
- **annotate** — the dependency enters the build, but with findings recorded
  against it that downstream tooling and reviewers can see and act on.
- **reject** — the dependency may not enter the build. Builds referencing it
  fail at ledger admission.

The gate does not patch, substitute, or vendor dependencies, and it does not
distinguish between "reject and page someone" versus "reject quietly" — those
are pipeline concerns. The gate's entire output is the decisions report; its
entire input is the ledger snapshot, the quarantine registry, and the
integrity report for pinned model artifacts.

## Principles

**Decisions are rule-derived, not discretionary.** Every finding the gate
records traces to a rule in this handbook. A human can grant an exception,
but the exception itself becomes a filed clause with an identifier, a scope,
and a disposition history — the discretion is exercised once and recorded,
not re-exercised at every build.

**The ledger is the unit of account.** The gate evaluates what the ledger
says the build will take, not what happens to be on disk or in a cache.
If the ledger and reality disagree, that is an integrity failure (chapter
08) or a provenance failure (chapter 07), and the gate's job is to say so.

**Findings are cheap; silence is expensive.** Annotations exist so that the
gate can record concerns without blocking work. Teams are expected to burn
down their annotation counts, and several annotation types escalate to
rejections under conditions the rule chapters define. A gate that only said
yes or no would be routed around; the middle tier is what makes the strict
tier enforceable.

**History is preserved, not rewritten.** Quarantine entries are lifted, never
deleted. Exception clauses are revoked or amended by changelog entry, never
edited in place. The decisions report for a ledger generation is
reproducible years later from the same inputs and the handbook text then in
force.

## Ownership

The Build Infrastructure group owns the gate implementation and this
handbook's editorial process. The Dependency Review Board — three permanent
members from Security, Legal, and Build Infrastructure, plus a rotating seat
from the requesting org — owns rule content, quarantine entries, and
exception clause approval. Amendments require a board majority; emergency
quarantine entries may be filed unilaterally by Security and ratified at the
next board sitting, and every entry in the current quarantine registry was
ratified.

## Relationship to other controls

The gate is one of four dependency controls and deliberately does not
duplicate the other three: registry-side malware scanning (owned by
Security), runtime SBOM attestation (owned by Release Engineering), and the
supply-chain incident process (owned by Security). In particular, the gate
does not scan artifact *content* — it verifies artifact *identity* against
pins and quarantine records. A clean gate decision is a statement that the
ledger row complies with this handbook, not that the dependency is free of
defects.
