# The quarantine program

Quarantine is the gate's emergency brake: a registry of dependencies and
artifacts that must not enter builds, maintained by the review board and
consumed by the gate on every evaluation. Where the rest of this handbook
encodes standing policy, quarantine encodes *specific judgments about
specific things* — usually the output of a security incident, a legal
finding, or an upstream compromise disclosure.

## Entry kinds

The registry holds two kinds of entry, and the matching semantics differ:

**Package entries** pin an (ecosystem, name) pair. A package entry matches
every ledger row with that ecosystem and name, at **every version**.
Version-scoped quarantine was considered and rejected by the board: in
every incident that has actually occurred, by the time an entry was filed
the team did not yet know which versions were affected, and a
version-scoped entry would have raced the investigation. When an
investigation concludes that specific versions are clean, the entry is
lifted and, if warranted, refiled — history is preserved either way.

**Artifact entries** pin a SHA-256 digest. An artifact entry matches every
ledger row whose **pinned artifact list** contains that digest — the match
runs against the digests the ledger declares, not against the computed
integrity report. The distinction is deliberate. A quarantine is a
judgment about bytes the organization decided to take (the pin); whether
the snapshot currently *contains* those bytes is a separate, integrity
question (chapter 08). If a quarantined pin's snapshot file has drifted,
the row collects both findings independently.

Artifact entries exist because model dependencies are not meaningfully
identified by name and version: the same revision label can be republished
with different weights, and the same weights can appear under several
names (mirrors, forks, re-uploads). The digest is the only identity worth
a judgment. Package entries are never filed for `huggingface` rows — the
board quarantines model *artifacts*, not model *names*.

## Entry status

Every entry carries a status, and exactly two statuses exist:

**active** — the judgment is in force. Every row the entry matches is
rejected with reason `quarantined`. There are no scope, origin, channel,
or provenance carve-outs, no waiver mechanism, and no exception clause
that overrides an active quarantine — this is the one finding in the
handbook with no override of any kind. (Exception clauses modify default
*policy*; they do not overrule a specific board judgment. See chapter 10.)

**lifted** — the judgment has been withdrawn, but the entry is retained as
history. Every row a lifted entry matches receives the
`quarantine-lifted` **annotation**. The annotation is informational: it
tells reviewers this dependency was once the subject of an incident, which
is exactly the context a reviewer wants when the same package drifts
toward trouble again. Lifted entries never reject and never expire.

Entries are matched independently: a row matched by one active and one
lifted entry is rejected for the first and annotated for the second, and
both findings appear. Statuses change only by board action recorded in the
changelog; the registry file reflects current status, and the changelog
carries the history of every status change.

## Current entries of note

Two entries in the current registry come up in reviews often enough to
summarize here (the registry file is the authoritative list):

- **QR-2101** (package, npm/event-stream-flat, active) — filed after the
  upstream maintainer handoff that inserted credential-harvesting code
  into a widely-used stream utility; the fork we consumed inherited the
  compromised lineage. The investigation closed without a clean version
  determination, so the entry remains active.
- **QR-2209** (artifact, active) — the fine-tuned internal embedding
  model whose training set was found to include improperly licensed data
  (the incident behind case study two). The pinned digest of the affected
  revision's configuration is quarantined; the model team's remediation
  publishes a retrained revision under new digests, which the entry does
  not match.

QR-1984 (package, go/legacy-yaml-shim, lifted) is the registry's oldest
entry and survives as the standard example that lifted entries annotate
forever: every snapshot that still pins that shim carries the annotation,
and will until the last consumer migrates.

## Filing and lifting

Security may file an entry unilaterally in an emergency; the board
ratifies, amends, or lifts at its next sitting. Lifting requires the
incident's closing memo. Neither filing nor lifting edits the ledger —
quarantine is a judgment *about* dependencies, applied at evaluation time,
and takes effect on the next gate run without a generation change.
