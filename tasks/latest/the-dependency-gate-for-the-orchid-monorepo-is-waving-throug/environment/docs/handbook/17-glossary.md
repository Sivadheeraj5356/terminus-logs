# Glossary

Definitions are normative only where the defining chapter says so; this
glossary exists so terms are used one way throughout the handbook.

**active (quarantine)** — Entry status meaning the board's judgment is in
force; matched rows are rejected with reason `quarantined`. See chapter 09.

**active (clause)** — A filed exception clause whose disposition chain
leaves it granting something: `active as filed`, or amended without
revocation or expiry. See chapter 10.

**amendment** — The only instrument that changes handbook content between
editions. Identified `AM-<year>-<month>`, effective-dated, recorded in
chapter 16.

**annotation** — A finding that records a concern without blocking ledger
admission. Vocabulary in chapter 13.

**artifact** — A file in the model registry snapshot, pinned by a
`huggingface` ledger row as a path/digest pair. See chapter 08.

**artifact entry** — A quarantine entry pinning a SHA-256 digest; matches
rows whose pinned artifact list contains that digest. See chapter 09.

**build (scope)** — The dependency is used by the build itself and is not
part of shipped artifacts. Compare *runtime*, *dev*.

**channel** — The release line of a pinned version: `stable`, `beta`, or
`nightly`. Policy in chapter 06.

**channel exception** — Clause family overriding the nightly rejection for
enumerated versions of one package, conditional on `verified` provenance.
Chapters 06 and 10.

**class (license)** — One of `permissive`, `weak-copyleft`,
`strong-copyleft`, `unclassified`, assigned to a license identifier by the
table in chapter 04.

**decision** — The gate's per-row output: `approve`, `annotate`, or
`reject`. Aggregation in chapter 14.

**dev (scope)** — Developer tooling; never on the build or serving path.

**direct (origin)** — Named in a first-party manifest; chosen by an
engineer and code-reviewed.

**disposition** — A registry entry's pointer to its amendment history;
resolving it against chapter 16 yields the clause's current standing.

**ecosystem** — The dependency's source: `npm`, `pypi`, `go`, or
`huggingface`.

**edition** — A consolidation of the handbook. Rule chapters are rewritten
to incorporate amendments at edition boundaries; registry chapters never
are.

**exception clause** — A filed, numbered departure from default policy:
a license waiver or a channel exception. Chapter 10.

**finding** — A reason or annotation recorded against a ledger row.

**generation** — The ledger snapshot's monotonically increasing integer;
advances with any dependency-set change. Freshness rules are expressed in
generations. Chapter 02.

**integrity report** — The path-to-digest map produced by hashing the
registry snapshot's pinned files; the gate compares it against ledger
pins. Chapter 08.

**ledger** — The append-only record of dependencies the monorepo consumes;
the gate's primary input. Chapter 02.

**lifted** — Quarantine status meaning the judgment was withdrawn; matched
rows are annotated `quarantine-lifted`, indefinitely. Chapter 09.

**lock_generation** — The generation at which a row's lockfile entry was
last written; `0` when provenance is `absent`. Chapter 07.

**model dependency** — A `huggingface`-ecosystem row: pinned artifacts
rather than a package archive. Chapters 03 and 08.

**origin** — How the row entered the graph: `direct` or `transitive`.

**package entry** — A quarantine entry pinning (ecosystem, name); matches
every version of that package. Chapter 09.

**provenance** — Whether the lockfile pins the bytes the row resolves to:
`verified`, `unverified`, or `absent`. Chapter 07.

**reason** — A finding that makes the row's decision `reject`. Vocabulary
in chapter 13.

**replacement pair** — Two identifiers of which exactly one applies to a
qualifying row: `license-blocked`/`license-exception`,
`channel-nightly`/`channel-exception`. Chapter 13.

**runtime (scope)** — Linked or loaded by shipped services; the widest
exposure scope.

**scope** — Where the dependency is used: `runtime`, `build`, or `dev`;
the ledger records the widest scope in use. Chapter 02.

**snapshot (ledger)** — The CSV-plus-metadata fixture a build runs
against; identified by its generation.

**snapshot (registry)** — The content-addressed tree of model artifacts
under the models root. See the registry snapshot document.

**stale** — A `verified` lockfile entry more than two generations behind
the snapshot. Chapter 07.

**transitive (origin)** — Pulled in by another dependency's requirements;
chosen by no one.

**waiver (license)** — Clause family overriding the strong-copyleft
rejection for enumerated versions and scopes of one package. Chapter 05.

## Terms of art from the operational chapters

**burn-down** — The expected reduction of open queue items for an
annotation type against its SLO. Chapter 22.

**counterfactual replay** — Evaluating a historical snapshot under
current rules, to size what a rule change would have caught. Chapter 21.

**escalation-adjacent** — A row one attribute-change away from a
combination rejection; flagged in queue tooling. Chapter 22.

**filed for the record** — A denial entered in the registry so its
precedent is findable by clause search. Chapters 26, 32.

**golden evaluation** — The CI smoke check comparing a policy change's
output on the sample ledger against the pinned expected report.
Chapters 21, 30.

**pre-adoption replay** — Evaluating the current snapshot under
proposed rules; attached to every amendment packet. Chapters 21, 32.

**successor note** — The archive annotation naming the clause that
refiled an archived grant. Chapter 26.

**tombstone (attestation)** — The record state after a retention
exception; tombstoned attestations verify as `unverified`. Chapter 28.

**verification replay** — Re-running a historical evaluation with the
rules of its day; must reproduce the archived report byte for byte.
Chapter 21.

**zero-delta consolidation** — The acceptance criterion for edition
consolidations: replaying the current snapshot under the consolidated
text must change no decision. Chapter 25.
