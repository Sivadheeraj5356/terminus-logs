# License classes

Every ledger row declares a license, and the gate maps the declaration to
one of four **classes**. All license policy downstream — review
annotations, waiver eligibility, rejection — operates on the class, never
on the raw identifier. The class table in this chapter is the table in
force. (The table has been revised once since the Second Edition; the
history is in chapter 16 and matters only for reading older case studies.)

## The class table

| Class | SPDX identifiers |
|---|---|
| **permissive** | `MIT`, `BSD-2-Clause`, `BSD-3-Clause`, `Apache-2.0`, `ISC` |
| **weak-copyleft** | `MPL-2.0`, `LGPL-3.0-only`, `EPL-2.0` |
| **strong-copyleft** | `GPL-3.0-only`, `AGPL-3.0-only`, `SSPL-1.0` |
| **unclassified** | every identifier not listed above |

The table is deliberately short. It is not an opinion about every license
that exists; it is the list of identifiers the review board has actually
evaluated against Orchid's distribution model. An identifier the board has
not evaluated is `unclassified` even if it is obviously permissive in
spirit — `Unlicense`, `0BSD`, and `Zlib` have all sat in `unclassified`
until someone brought them to the board, and only identifiers with a
current in-force evaluation appear above.

Note that `LGPL-3.0-only` sits in **weak-copyleft**. Its placement was
re-evaluated after the 2024 static-linking review concluded that our build
configurations for LGPL dependencies uniformly satisfy the relinking
requirement; the reclassification is recorded as an amendment in chapter
16. Case study three predates that re-evaluation and describes an LGPL
rejection under the older table — read it as history, not as the rule.

## Class obligations

**permissive** — no gate finding. Attribution obligations are handled by
the notice-generation pipeline, which is out of the gate's scope.

**weak-copyleft** — acceptable at every scope. At `runtime` scope the row
receives the `license-review` annotation, which routes it into the
quarterly legal review of shipped copyleft surface. At `build` and `dev`
scope there is no finding: the copyleft obligations of these licenses
attach to distribution of the covered work, and build/dev usage does not
distribute.

**strong-copyleft** — rejected with reason `license-blocked`, at every
scope, unless an **active license waiver** covers the row (see chapter 05
for waiver mechanics and chapters 11–12 for the registry). When a waiver
applies, the rejection is replaced by the `license-exception` annotation,
which keeps the row visible in every report the legal team reads. The
default-reject posture is not a statement that these licenses are
unusable; it is a statement that using one is a legal decision, made by
the board per package and version, never by an engineer's lockfile.

**unclassified** — rejected with reason `license-unclassified`, except at
`dev` scope, where the row receives the `license-unclassified`
**annotation** instead. The dev-scope carve-out is deliberate and recent
(see chapter 16): developer tooling with an exotic license header exposes
the company to essentially nothing, and the annotation keeps the row on
the review queue without blocking a workstation tool. The same identifier
appears as both a reason code and an annotation; chapter 13 lists both
vocabularies and the decision procedure in chapter 14 explains how the two
usages never collide.

## Declaration hygiene

The class is computed from the ledger's `license` column verbatim. The
gate does not fuzzy-match identifiers: `Apache 2.0`, `apache-2.0`, and
`Apache-2.0+` are all `unclassified` because none of them is the evaluated
identifier `Apache-2.0`. This is intentional. A mis-declared license is a
data-quality problem in the ledger, and the correct fix is to fix the
declaration, not to teach the gate to guess. When a package's registry
metadata and its license file disagree, the ledger convention is to record
the identifier from the license file; the `LicenseRef-` form is used for
genuinely bespoke terms (internal tools, purchased components, dataset
licenses on model rows).

## Interaction with other rules

License findings compose with everything else. A quarantined GPL package
under an active waiver is still quarantined (`quarantined` rejects even as
`license-exception` annotates); a nightly-channel MPL runtime dependency
collects `license-review` alongside whatever chapter 06 has to say about
its channel. No license outcome ever suppresses another chapter's finding,
and nothing in this chapter reads `origin`, `provenance`, or `channel` —
scope is the only other column license policy touches.
