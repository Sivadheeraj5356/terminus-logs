# Worked evaluations

Sixteen rows evaluated by hand against the rules in force, with the
reasoning spelled out. New gate reviewers work through these before
touching a real report; rule authors use them as drafting checks. Every
example uses hypothetical packages; the snapshot generation is 60
throughout. Findings are shown sorted, as reports present them.

---

**W1 — the boring good case.**
npm/left-align 2.1.0 · MIT · stable · verified, lock_generation 59 ·
runtime · direct · no install scripts.
Permissive license, stable channel, verified and fresh (gap 1),
no scripts, no quarantine match. Nothing fires.
→ **approve**, reasons `[]`, annotations `[]`.

**W2 — weak copyleft at runtime.**
pypi/dataframe-lite 1.8.2 · MPL-2.0 · stable · verified, 60 · runtime ·
direct.
Weak-copyleft class at runtime scope draws the review annotation;
nothing else fires.
→ **annotate**, `[]`, `[license-review]`.

**W3 — the same package at build scope.**
Identical row, scope build.
Weak copyleft outside runtime scope has no finding — the obligations
attach at distribution.
→ **approve**, `[]`, `[]`.

**W4 — untrusted transitive scripts.**
npm/native-imageproc 3.0.1 · MIT · stable · unverified, 58 ·
runtime · transitive · install scripts true.
Scripts give `npm-install-scripts`. Unverified gives
`provenance-unverified` (staleness does not apply to non-verified
rows). Scripts + transitive + not verified is the rejection triple.
→ **reject**, `[npm-untrusted-scripts]`,
`[npm-install-scripts, provenance-unverified]`.

**W5 — the same row, verified.**
As W4 with provenance verified, lock_generation 58.
The rejection triple loses its provenance leg. Gap 2 is exactly at the
boundary — not stale.
→ **annotate**, `[]`, `[npm-install-scripts]`.

**W6 — staleness, both sides of the boundary.**
go/fastcsv v2.2.0 · MIT · stable · verified, lock_generation 57 ·
runtime · direct.
Gap 3 exceeds two: stale.
→ **annotate**, `[]`, `[provenance-stale]`.
The same row at lock_generation 58 (gap exactly 2) has no finding:
→ **approve**, `[]`, `[]`.

**W7 — strong copyleft, no waiver, dev scope.**
pypi/qcheck-gpl 4.0.0 · GPL-3.0-only · stable · verified, 60 · dev ·
direct.
Strong copyleft rejects at every scope absent a waiver — there is no
dev carve-out in the strong class (the dev carve-out belongs to
*unclassified*).
→ **reject**, `[license-blocked]`, `[]`.

**W8 — the same row under an active waiver.**
As W7, with an active waiver covering (pypi, qcheck-gpl), version
4.0.0, scope dev.
Exact match on all three lists replaces the rejection.
→ **annotate**, `[]`, `[license-exception]`.

**W9 — beta, verified.**
npm/style-tokens 5.0.0-beta.3 · MIT · beta · verified, 60 · runtime ·
direct.
Beta always annotates. The escalation triple requires non-verified
provenance; verified breaks it.
→ **annotate**, `[]`, `[channel-beta]`.

**W10 — beta, the escalation triple.**
As W9 with provenance unverified.
Runtime + direct + not verified: the triple fires, and the two
annotations record the full picture alongside.
→ **reject**, `[channel-unverified-beta]`,
`[channel-beta, provenance-unverified]`.

**W11 — beta, transitive, unverified.**
As W10 with origin transitive.
The triple requires direct origin; transitive beta never escalates.
→ **annotate**, `[]`, `[channel-beta, provenance-unverified]`.

**W12 — nightly, no clause.**
pypi/proto-tools 6.0.0.dev2 · Apache-2.0 · nightly · verified, 60 ·
build · direct.
Nightly rejects at every scope; no registry clause names the package.
Verified provenance is necessary for an exception but grants nothing
by itself.
→ **reject**, `[channel-nightly]`, `[]`.

**W13 — nightly, clause present, provenance failing.**
As W12 with an active channel exception listing 6.0.0.dev2, but
provenance unverified.
The standing verified-provenance condition makes the clause
inapplicable; there is no partial honor.
→ **reject**, `[channel-nightly]`, `[provenance-unverified]`.

**W14 — model integrity, mixed failure.**
huggingface/orion-labs/reranker-xs r2026.01 · Apache-2.0 · stable ·
verified, 60 · build · direct · three pinned artifacts: one matches the
integrity report, one is absent from it, one is present with a
different digest.
The quantifier is *every*; the two failing artifacts produce their
distinct codes, and the one matching artifact vouches for nothing.
→ **reject**, `[artifact-missing, digest-mismatch]`, `[]`.

**W15 — lifted quarantine on a clean model.**
huggingface/orion-labs/lang-detect r2025.11 · Apache-2.0 · stable ·
verified, 60 · build · direct · one pinned artifact, matching; a
*lifted* artifact entry matches that pinned digest.
Integrity passes; the lifted entry annotates, forever.
→ **annotate**, `[]`, `[quarantine-lifted]`.

**W16 — stacked rejections.**
npm/metrics-agent-classic 0.9.1 · LicenseRef-Vendor-EULA · stable ·
verified, 60 · runtime · direct · an *active* package quarantine entry
matches (npm, metrics-agent-classic).
Unclassified license at runtime scope rejects; the quarantine rejects
independently. Reasons are a set — both are recorded, sorted.
→ **reject**, `[license-unclassified, quarantined]`, `[]`.

---

## Drafting notes

Three of these examples exist because a draft rule once got them wrong
in review. W5's boundary case (gap exactly two) is stated in chapter 07
in words for that reason. W14's "one matching artifact vouches for
nothing" is the quantifier amendment restated as a row. W13 is the
standing-condition case reviewers most often miss: a clause can be
active, exact on version, and still inapplicable. When drafting a new
rule, add its W-row here first — if the row's outcome cannot be derived
from chapter text alone, the chapter text is not done.
