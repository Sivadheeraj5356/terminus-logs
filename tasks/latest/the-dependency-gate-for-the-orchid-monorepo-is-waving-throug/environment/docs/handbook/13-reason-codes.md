# Reason codes and annotations

This chapter is the exhaustive vocabulary of gate findings. A finding
identifier not listed here is invalid gate output; a rule elsewhere in the
handbook that appears to require a new identifier requires an amendment to
this chapter first. Identifiers are lowercase, hyphen-separated, and
stable across editions — dashboards, review queues, and burn-down tooling
key on them.

Two identifiers (`license-unclassified` and `provenance-absent`) appear in
**both** vocabularies: the same underlying condition is a rejection in one
configuration and an annotation in another, and the defining chapters
specify which applies. For any single ledger row, a given identifier
appears at most once, in exactly one of the two lists — the conditions
that produce the reason and the annotation are mutually exclusive by
construction (they branch on `scope` or `origin`).

## Reason codes (rejections)

| Code | Produced by | Condition |
|---|---|---|
| `quarantined` | ch. 09 | The row matches a quarantine entry with `active` status (package entries by ecosystem + name; artifact entries by any pinned digest). |
| `artifact-missing` | ch. 08 | A model row pins an artifact path absent from the integrity report. |
| `digest-mismatch` | ch. 08 | A model row pins an artifact whose computed digest differs from the pin. |
| `license-blocked` | ch. 04, 05 | Strong-copyleft class with no active waiver covering ecosystem, name, version, and scope. |
| `license-unclassified` | ch. 04 | Unclassified license class at `runtime` or `build` scope. |
| `channel-nightly` | ch. 06 | `nightly` channel with no applicable active channel exception (exact version match plus `verified` provenance). |
| `channel-unverified-beta` | ch. 06 | `beta` channel and `runtime` scope and `direct` origin and provenance not `verified`. |
| `provenance-absent` | ch. 07 | `absent` provenance on a `direct`-origin row. |
| `npm-untrusted-scripts` | ch. 03 | npm row with install scripts, `transitive` origin, and provenance not `verified`. |

## Annotations

| Code | Produced by | Condition |
|---|---|---|
| `quarantine-lifted` | ch. 09 | The row matches a quarantine entry with `lifted` status. |
| `license-exception` | ch. 04, 05 | Strong-copyleft class covered by an active waiver (replaces `license-blocked`). |
| `license-review` | ch. 04 | Weak-copyleft class at `runtime` scope. |
| `license-unclassified` | ch. 04 | Unclassified license class at `dev` scope. |
| `channel-beta` | ch. 06 | `beta` channel, unconditionally. |
| `channel-exception` | ch. 06 | `nightly` channel covered by an applicable active channel exception (replaces `channel-nightly`). |
| `provenance-unverified` | ch. 07 | `unverified` provenance. |
| `provenance-stale` | ch. 07 | `verified` provenance with the snapshot generation exceeding `lock_generation` by more than two. |
| `provenance-absent` | ch. 07 | `absent` provenance on a `transitive`-origin row. |
| `npm-install-scripts` | ch. 03 | npm row with install scripts, unconditionally. |

## Composition rules

Findings accumulate independently across chapters; no finding suppresses
another except where a chapter explicitly defines a replacement pair
(`license-blocked` ↔ `license-exception`; `channel-nightly` ↔
`channel-exception`). A replacement pair is exclusive by definition: the
row carries exactly one of the two, decided by whether the exception
applies. Both members of a replacement pair never co-occur.

Within one row, each list is a **set**: an identifier appears once even
if several inputs independently produce it (two active quarantine entries
matching one row still yield a single `quarantined`). Reports present both
lists sorted lexicographically (see the decisions-format contract outside
this handbook).

## Retired identifiers

Third-Edition tooling emitted `model-integrity` as a single reason for any
artifact discrepancy; the split into `artifact-missing` and
`digest-mismatch` came with the quantifier amendment (chapter 16). The
retired identifier must not be emitted; dashboards translate historical
records on read. Similarly retired: `channel-prerelease` (folded into
`channel-beta` in the Second Edition) and `license-copyleft` (split into
the class-specific codes when the class table was introduced).
