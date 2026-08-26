# Ecosystem risk profiles

The rule chapters treat the four ecosystems uniformly except where
chapter 03 says otherwise. This appendix records the *risk reasoning*
behind that near-uniformity: what each ecosystem's supply chain
actually looks like from Orchid's side, what has gone wrong where, and
why the board has (mostly) resisted ecosystem-specific rules. Rule
authors proposing an ecosystem carve-out start here; most proposals die
against the histories below.

## npm: scale and execution

The npm graph is the largest and the only one with routine install-time
code execution — the two facts that dominate its profile. Orchid's npm
surface at the current generation is roughly five direct manifests per
product team fanning out to thousands of transitive rows; no human has
read the transitive set, and the gate's design accepts that honestly
(chapter 03's origin asymmetry).

What has actually gone wrong: the 2023 credential harvester (case study
one, QR-2101), the 2022 protestware release (QR-2017), and the 2025
dependency-confusion attempt (QR-2244). All three were execution or
identity attacks; none was a licensing event — npm's license hygiene is
mediocre but its licenses are overwhelmingly permissive. The profile
justifies exactly the two rules chapter 03 carries: script visibility
everywhere, and the untrusted-transitive-scripts rejection. Proposals
to go further (block all install scripts; require direct review of the
transitive set) have failed against the First Edition's lesson — the
vendoring workaround was worse than the risk (chapter 25).

## PyPI: metadata noise and pre-release culture

PyPI's profile is dominated by two habits: unreliable license metadata
(one in twelve sampled packages disagrees with its own license file)
and a strong pre-release culture — the ecosystem's dev-build versioning
is why most nightly rows are PyPI rows. What has gone wrong at Orchid:
the analytics-beacon release (QR-2267) and the typosquat scare
(QR-2050, lifted). Neither produced a PyPI-specific rule; the beacon
was handled by quarantine and the typosquat by investigation.

The metadata noise does shape practice: the ledger convention of
recording the license-file identifier over the classifier (chapter 04)
exists for PyPI's sake, and the unclassified-license rules do most of
their work on PyPI rows. The retired source-distribution requirement
(chapter 03) was this ecosystem's one carve-out, and its failure — the
mirror could not enforce it uniformly — is the standing argument
against enforcement rules the infrastructure cannot see.

## Go: strong rails, boring profile

The checksum database gives Go the strongest integrity rails of the
four, and its profile is correspondingly quiet: no Go package has ever
been the subject of an active Orchid quarantine (QR-1984 was lifted as
unreproducible). The interesting Go rows are the exceptions to the
rails — vendored forks with `absent` provenance and private modules
with `unverified` — and chapter 24 records why those states are
reported honestly rather than laundered.

The board's one Go debate (chapter 03): making non-verified provenance
auto-reject ecosystem-wide. The proposal returns roughly annually and
loses the same way each time — the gradient argument. The rails make
`verified` cheap in Go, so the rows that lack it are precisely the
unusual ones where a rejection would block real work: bootstrap forks,
incident patches, private modules mid-migration. The provenance
annotations plus origin escalations already price those correctly.

## Hugging Face: identity is the whole game

The model registry's profile is unlike the other three because there is
no install-time code execution and almost no license variance (the
overwhelming majority of pinned models are Apache-2.0 or
`LicenseRef-`-recorded dataset terms — the latter kept the unclassified
rules honest on model rows). The entire risk concentrates in artifact
identity: what exactly are these bytes, and are they the bytes we
evaluated? Every model incident in program history — the training-data
finding (QR-2209/2210, case study two), the tokenizer disagreement
(QR-2133), the sync race (QR-2178, lifted), the upstream rewrite
(QR-2311) — is an identity story.

That concentration explains the design: digest pins in the ledger, the
universal quantifier (chapter 08), artifact-kind quarantine entries
(chapter 09), and the mirror's never-rewrite-locally discipline
(chapter 28). It also explains what the gate deliberately does not do
for models: no semantic validation of artifact content (PM-2024-06
records the boundary), no size or architecture policy, no evaluation
gating — those belong to the model platform's own review, which runs
before artifacts reach the registry at all.

## The uniformity default

Reading the four profiles together: the risks differ, but the
*instruments* the gate needs are the same everywhere — identity pins,
provenance states, channel discipline, quarantine, and exceptions with
enumerated blast radii. The board's standing preference for uniform
rules with narrow, evidence-backed carve-outs (two for npm, one for
models' artifact machinery) has survived every annual review since the
Second Edition, and each ecosystem's headline incident was handled
within the uniform toolkit. The bar for a new carve-out is a failure
the uniform rules *cannot* express — not merely an ecosystem where one
rule fires more often.
