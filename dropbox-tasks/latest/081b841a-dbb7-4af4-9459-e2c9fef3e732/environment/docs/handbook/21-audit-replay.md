# Audit replay and the compliance record

Every gate evaluation produces a decisions report, and every report is
archived against its ledger generation. This chapter describes what the
archive is for, what replay means, and the determinism obligations that
make both possible. Nothing here adds rules to the gate; it explains why
several rules elsewhere are shaped the way they are.

## The compliance record

The archived report for generation N is the answer to "what did the
organization decide to build with, and what did it know at the time?" It
is consulted in three situations:

**Incident scoping.** When a dependency turns out to be bad, the first
question is which generations carried it and with what findings. The
archive answers by grep: the reason and annotation vocabularies are
stable identifiers (chapter 13), so "every generation where this row was
annotated `provenance-unverified`" is a mechanical query. This is the
reason identifier stability is a hard rule — renaming a code orphans the
history behind it.

**License audits.** Legal's quarterly copyleft review starts from the
set of rows carrying `license-review` and `license-exception` in the
current generation's report, cross-referenced against the waiver
registry. The annotation-forever behavior of `license-exception` (a
waived row is annotated in every report, indefinitely) exists precisely
so this query never misses a waived dependency.

**Change review.** The report diff between consecutive generations is a
review artifact: a dependency upgrade PR gets the diff of decisions its
ledger change produces. Reason *sets* (not first-reason-wins) matter
here — a diff that shows `quarantined` disappearing but
`license-blocked` remaining tells a reviewer the upgrade is still not
landable, in one glance.

## Replay

Replay is re-running the gate against a historical snapshot — the same
ledger CSV, quarantine registry state, and integrity report — to
reproduce its archived decisions. The program runs replay in three
modes:

- **Verification replay** re-evaluates with the rules in force *at the
  time* and must reproduce the archived report byte for byte. A
  divergence means either the archive was produced by a defective
  implementation (it happens; case study two's postmortem replay is the
  famous instance) or nondeterminism has crept into the current one.
- **Counterfactual replay** evaluates a historical snapshot under
  *current* rules, answering "which of today's findings were present
  but invisible then?" Counterfactuals informed both the integrity
  quantifier amendment and the beta escalation — in each case the board
  asked for the count of historical rows the proposed rule would have
  flagged.
- **Pre-adoption replay** evaluates the current snapshot under
  *proposed* rules. Every amendment proposal since the Third Edition has
  shipped with its replay delta attached; the minutes reference them
  routinely.

Replay is why the gate reads no wall clock, no environment, and no
network (chapter 14's determinism contract). A rule keyed to calendar
days would make verification replay depend on when the replay runs; a
generation-keyed rule replays exactly.

## Determinism obligations on implementations

The contract restated operationally, since implementations are replaced
more often than rules:

1. **Total, stable ordering everywhere output has an order.** Report
   entries by (ecosystem, name, version) with plain string comparison;
   finding arrays sorted lexicographically. No map-iteration order may
   reach the output.
2. **No environmental inputs.** Hostname, locale, timezone, filesystem
   iteration order, and clock are all forbidden inputs. The integrity
   report is an *input document*, not something the policy computes —
   hashing happens in tooling, outside the decision function.
3. **Closed-world evaluation.** The decision for a row is a function of
   the row, the snapshot generation, the quarantine registry, the
   exception registry as amended, and the integrity report. If an
   implementation wants any other input, the rule it is implementing
   does not exist in this handbook.
4. **Set semantics for findings.** Duplicate production of an
   identifier is legal internally and invisible externally.

Conformance is checked by golden evaluation in the gate's own CI: a
pinned sample snapshot with its expected report, evaluated on every
change to the implementation. The sample is deliberately small and
covers the common shapes; it is a smoke test, not the specification —
the specification is this handbook, and verification replay against the
archive is the real conformance suite.

## Retention

Reports are retained for the life of the monorepo plus the longest
license obligation horizon Legal tracks. Ledger snapshots and quarantine
registry states are retained on the same schedule, because a report
without its inputs cannot be replayed, and an unreplayable report is
testimony rather than evidence.
