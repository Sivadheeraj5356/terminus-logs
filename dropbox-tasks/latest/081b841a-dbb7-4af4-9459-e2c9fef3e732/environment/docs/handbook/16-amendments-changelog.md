# Amendments and changelog

Every amendment since the Second Edition, ordered by effective date.
Amendment text is **operative**: for rule chapters it modifies the printed
rule (chapters 03–09 in this edition already incorporate every amendment
effective on or before 2026-03-02, the consolidation date); for registry
clauses it is the *only* record of extensions, restrictions, and
revocations — registry entries are never edited after filing. Quarantine
status changes are recorded here as `QR` lines for the same reason.

---

**AM-2023-10** · effective 2023-10-16 · *chapter 03*
Introduced the `npm-untrusted-scripts` rejection (install scripts +
transitive origin + provenance not `verified`) and the
`npm-install-scripts` annotation, following the builder credential
incident (case study one). QR-2101 ratified at the same sitting.

**AM-2024-03** · effective 2024-03-22 · *chapter 07*
Introduced the staleness annotation `provenance-stale` for `verified`
rows: as introduced, an entry was stale when **two or more** generations
behind the snapshot. (Revised by AM-2026-01; see below.)

**AM-2024-08** · effective 2024-08-19 · *registry EX-104*
**Revoked EX-104** (channel exception, pypi/arrow-flight-dev). A
provenance audit found the pinned dev build had been fetched outside the
mirror on two builders, breaching the sandbox condition. Revocation was
retained after remediation as the standard consequence for condition
breach.

**AM-2024-12** · effective 2024-12-09 · *chapter 04*
**Reclassified `LGPL-3.0-only` from strong-copyleft to weak-copyleft**
following the static-linking review (case study three). Rows previously
rejected `license-blocked` under the old class re-evaluate to the
weak-copyleft posture (`license-review` at runtime scope, silent
otherwise).

**AM-2025-02** · effective 2025-02-17 · *chapter 06*
Added the `channel-unverified-beta` rejection for rows where channel is
`beta`, scope is `runtime`, origin is `direct`, and provenance is not
`verified` (case study six). Beta remains annotation-only in every other
configuration. Retired the "advisory only" language from the channel
chapter.

**AM-2025-03** · effective 2025-03-30 · *registry EX-111*
**Extended EX-111** (waiver, pypi/gpl-tesseract-binding): version `0.5.2`
added to the version list after the fixture pipeline's upgrade. Scope list
unchanged.

**AM-2025-05** · effective 2025-05-12 · *chapter 07*
**Downgraded `absent` provenance on `transitive` rows from rejection to
annotation.** `provenance-absent` remains a rejection for `direct` rows;
the identifier is added to the annotation vocabulary for the transitive
case. Rationale: the fix for a transitive gap belongs to the direct
parent's lockfile, and rejecting leaf rows blocked teams on graphs they
did not author.

**AM-2025-06** · effective 2025-06-02 · *registry EX-123*
**Restricted EX-123** (waiver, npm/gpl-diagram-dsl): `dev` scope removed
from the scope list after the workstation preview tool vendored its own
renderer. The waiver continues at `build` scope only.

**AM-2025-07** · effective 2025-07-14 · *chapters 08, 13*
**Tightened the model integrity quantifier.** A model dependency verifies
only when **every** pinned artifact is present in the integrity report and
matches its pinned digest. Retired the single reason `model-integrity` in
favor of the distinct codes `artifact-missing` (pinned path absent from
the report) and `digest-mismatch` (present, different digest), which may
co-occur. Prompted by the postmortem replay of case study two.

**AM-2025-09** · effective 2025-09-08 · *registry EX-102*
**Revoked EX-102** (channel exception, npm/esbuild-canary). The upstream
fix shipped in a stable release in August 2025, ending the need the clause
was granted for; the requesting team's completion report was filed and the
board revoked at the following sitting. Nightly pins of the named package
are governed by the default channel policy from the effective date.

**AM-2025-10** · effective 2025-10-20 · *registry EX-126*
**Revoked EX-126** (channel exception, npm/turbopack-canary). The
evaluation concluded without adoption; the trial builder was
decommissioned.

**AM-2025-11** · effective 2025-11-24 · *chapter 04*
**Downgraded unclassified licenses at `dev` scope from rejection to
annotation.** `license-unclassified` remains a rejection at `runtime` and
`build` scope; the identifier is added to the annotation vocabulary for
the `dev` case. Rationale recorded: workstation tooling with unevaluated
license headers presents negligible exposure, and the rejection was
producing waiver requests the board had no instrument to grant.

**AM-2026-01** · effective 2026-01-19 · *chapter 07*
**Moved the staleness boundary.** A `verified` row is stale when the
snapshot generation exceeds its `lock_generation` by **more than two**
generations (strictly greater than two). Under the prior rule ("two or
more") an entry exactly two generations behind was stale; under this
amendment it is not. Prompted by the regeneration churn documented in
case study five.

**AM-2026-02** · effective 2026-02-23 · *registry EX-131*
**Extended EX-131** (waiver, npm/gpl-vendored-grammar): version `3.1.4`
added to the version list after the syntax-server team's grammar-bundle
upgrade; the process-isolation review was re-run against 3.1.4 and
attached to the amendment. Scope list unchanged (runtime, build, dev).

**AM-2026-04** · effective 2026-04-13 · *registry EX-136*
**Extended EX-136** (channel exception, pypi/hf-hub-dev): version
`0.27.0.dev9` added after upstream rebased the resumable-download branch.
Sunset condition unchanged.

---

## Quarantine status history

**QR-1984** · filed 2022-06-30 (package, go/legacy-yaml-shim) · **lifted
2023-02-13.** Filed on an upstream parser-differential advisory; lifted
when the advisory was withdrawn as unreproducible. Retained as the
standing example that lifted entries annotate indefinitely.

**QR-2101** · filed 2023-10-02 (package, npm/event-stream-flat) ·
**active.** Ratified with AM-2023-10. No clean-version determination;
remains active.

**QR-2209** · filed 2024-11-05 (artifact) · **active.** Training-data
licensing finding against a fine-tuned internal embedding model revision
(case study two). The retrained replacement publishes under new digests
outside the entry.

**QR-2210** · filed 2024-11-05 (artifact) · **active.** Companion filing
to QR-2209 covering a derived checkpoint of the same fine-tune that was
staged to the registry but never pinned by any ledger row. Filed to close
the door pre-emptively.

**QR-2311** · filed 2026-05-27 (artifact) · **active.** Registry
mirror-integrity finding against a third-party classifier head; the
upstream repository rewrote a published revision in place. Under
investigation.

**QR-2178** · filed 2024-07-08 (artifact) · **lifted 2025-01-27.**
Language-identification model quarantined on a false-positive tamper
signal from a mirror sync race; lifted with the sync fix.

**QR-2050** · filed 2023-05-16 (package, pypi/iniparse-shim) · **lifted
2023-09-04.** Typosquat suspicion; investigation established independent
lineage and the entry was lifted.
