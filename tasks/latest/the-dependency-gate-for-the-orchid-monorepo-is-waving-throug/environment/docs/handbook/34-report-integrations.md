# Report consumers and integrations

The decisions report is a contract (the decisions-format document
outside this handbook), and a contract is only as stable as its
consumers are numerous. This appendix inventories the systems that
read the report today, what each one keys on, and the compatibility
obligations that inventory implies. Anyone proposing a report shape
change or a vocabulary change reads this first — chapter 13's
identifier-stability rule has a blast radius, and this is the map of
it.

## Ledger admission

The most privileged consumer: admission reads only the `decision`
field per row, fails the generation on any `reject`, and admits
otherwise. Admission deliberately ignores reasons and annotations —
the decision field is the whole interface, which is why the
aggregation rules (chapter 14) are part of the contract rather than an
implementation nicety. Admission runs synchronously in the
generation-advance path; its latency budget is why the report is one
document rather than a query API.

## The queue builder

Reads (row identity, annotations) pairs and diffs consecutive
generations (chapter 22). Keys on annotation identifiers verbatim —
the reason renames in chapter 13's retired list each cost a queue
builder migration, which is where the identifier-stability rule earned
its teeth. The queue builder is also the consumer that cares most
about the both-lists-always-present rule: an absent `annotations`
array (as opposed to an empty one) once crashed item generation for an
entire org's rows, and the contract has said "always present" since.

## Scorecards and dashboards

The org scorecard reads the archive, not live reports (chapter 22's
resurrection property depends on this). Grafana boards for builder
health read reject-rate and annotation-count timeseries derived from
the same archive. Both consumers key on identifiers *and* on the
report's ordering contract — the diff panels assume (ecosystem, name,
version) ordering to align rows across generations without a join.
Ordering is therefore not presentational: chapter 14 calls it a
contract, and this is the consumer that would notice.

## PR decoration

Dependency-change PRs get a comment with the decision diff their
ledger change would produce (pre-adoption evaluation against the
candidate ledger). The decorator renders reason and annotation
identifiers as human strings from a translation table keyed on chapter
13's vocabulary — an identifier missing from the table renders as the
raw code with a lint warning in the decorator's own CI. Twice the
table has caught a policy change that emitted an undeclared
identifier; the decorator is accidentally the vocabulary's second
enforcement point.

## Legal's copyleft review

Quarterly export of rows carrying `license-review` or
`license-exception`, joined against the waiver registry by clause
reference. The join is why `license-exception` annotations alone are
not enough — the reviewers need *which* waiver, and the queue item
carries the clause link (chapter 22). The export reads the archive at
quarter boundaries; it is the consumer with the longest memory and the
reason report retention is phrased in license-horizon terms (chapter
21).

## The compliance archive itself

The archive is both store and consumer: verification replay reads
archived reports byte-for-byte (chapter 21), which makes *every*
serialization detail part of the contract — key order within entries,
array formatting, the generation field's type. The determinism
obligations exist substantially for this consumer's sake. Nothing that
merely "renders the same" is compatible; the archive compares bytes.

## Compatibility obligations, derived

From the inventory, the standing rules for anyone changing report
shape or vocabulary:

1. **Identifiers are append-only.** New codes may be added (with
   chapter 13 amended first); existing codes never rename or change
   meaning. Retirement means the code stops being *emitted*, never
   that its archived occurrences are rewritten.
2. **Both arrays, always, sorted.** Consumers are entitled to `reasons`
   and `annotations` as present, sorted, duplicate-free arrays on
   every entry.
3. **Ordering is load-bearing.** Entry order is (ecosystem, name,
   version), plain string comparison. Consumers align on it.
4. **Additive fields only, and rarely.** A new entry field requires a
   survey of this inventory and a board-adopted contract amendment;
   the last one (the generation echo) predates the Third Edition.
5. **The archive outranks convenience.** Any change that would make a
   replayed historical report compare unequal to its archived bytes is
   not a change to the format — it is a new format, versioned as such,
   with the archive keeping both.

The inventory above is reviewed at each edition consolidation; systems
reading the report without appearing here have no compatibility claim,
which is stated bluntly because it has come up.
