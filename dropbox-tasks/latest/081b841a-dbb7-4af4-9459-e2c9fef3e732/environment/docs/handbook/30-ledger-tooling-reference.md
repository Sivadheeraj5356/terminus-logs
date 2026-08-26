# Ledger tooling reference

The gate is one consumer of the ledger; this appendix documents the
tooling ecosystem around it, for orientation. Commands and paths here
describe the audit workspace layout; the data contracts live in the
documents outside this handbook (ledger format, input format, decisions
format, registry snapshot).

## The audit pipeline

An audit run has four mechanical stages:

1. **Hash** — every artifact path pinned by any ledger row is hashed
   from the registry snapshot with OpenSSL (SHA-256), producing the
   integrity report. Pinned paths with no file on disk are omitted, not
   errored: absence is a policy question (chapter 08), not a tooling
   failure.
2. **Convert** — the ledger CSV, quarantine CSV, and generation
   metadata are joined with the integrity report into the single policy
   input document. Conversion is mechanical and total: every row
   converts, malformed rows abort the run rather than skip.
3. **Evaluate** — the policy bundle produces the decisions report from
   the input document. Evaluation is pure (chapter 21's determinism
   obligations); the engine is pinned in the workspace and takes no
   network.
4. **Record** — the report lands in the output directory, and in
   production, the archive.

The stages are deliberately separable: an investigation can re-run
evaluation against a historical input document without re-hashing
(verification replay), or re-hash without re-evaluating (mirror
monitoring's weekly pass, chapter 28).

## Workspace conventions

The audit workspace keeps fixtures, policy, and outputs apart:

- ledger fixtures under the ledger directory — the CSVs and metadata,
  read-only to the audit;
- the policy bundle under the policy directory — the only component a
  policy change touches;
- the registry snapshot under the models directory — read-only, synced
  by the mirror;
- generated documents under the output directory — the hash report,
  the input document, and the decisions report, all regenerated on
  every run and never hand-edited;
- QA fixtures under the qa directory — the golden decisions for the
  checked-in sample ledger, used by the conformance smoke check
  (chapter 21's "golden evaluation").

A hand-edited output document is the workspace's cardinal sin: every
downstream consumer assumes outputs are derivable from inputs, and the
audit regenerates them unconditionally, so an edit both lies and
disappears.

## The QA golden

The golden decisions file pins the expected report for the sample
ledger that ships with the workspace. Its role is the smoke check: a
policy change that alters the sample's decisions shows up as a golden
diff immediately, locally, before any review. Two properties keep the
golden honest. First, it is *derived* — regenerated from a known-good
policy against the sample fixtures, never written by hand; a golden
update in a change is a claim that the decision change is intended,
and reviewers treat it exactly like a behavior-change diff. Second, it
is *not the specification* — the handbook is (chapter 21). A policy
that matches the golden has passed a smoke test over the sample's
shapes; the sample is small, and plenty of documented semantics have
no sample row exercising them. Conformance beyond the smoke check is
the archive's verification replay, which evaluates corpora far larger
and stranger than the sample.

## Failure conventions

Tooling failures and policy findings are kept rigorously apart. A
missing fixture file, an unreadable CSV, a policy bundle that fails to
parse — these abort the audit with a nonzero exit and produce no
report at all. The gate never encodes "the tooling broke" as a
decision; a report exists only when every stage completed, and every
decision in it is a policy outcome. Investigations rely on this: a
generation with no archived report is a pipeline incident, a
generation with rejections is a policy story, and the two never
masquerade as each other.

## Local iteration

Policy work iterates locally: run the audit, read the report or the
golden diff, adjust the bundle, re-run. The evaluation engine accepts
the policy directory and an input document directly, so a focused
loop can skip hashing and conversion once the input document exists.
Two habits keep local work honest: regenerate rather than edit the
input document when fixtures change, and treat the golden diff as the
review artifact it is — a clean diff plus an unread handbook chapter
is how the archive's replay finds you later.
