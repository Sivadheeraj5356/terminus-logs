# Package ecosystems

The gate consumes dependencies from four ecosystems, and most rules in this
handbook apply uniformly across them. This chapter records where the
ecosystems genuinely differ and the ecosystem-specific rules currently in
force. (Rules in this chapter are stated as in force; historical revisions
are in chapter 16.)

## npm

npm is the largest ecosystem in the ledger by row count and the only one
where package installation can execute arbitrary code on builder machines as
a matter of routine packaging practice. The `install_scripts` ledger column
records whether the pinned package declares `preinstall`, `install`, or
`postinstall` hooks.

Two rules are in force:

**Install-script visibility.** Every npm dependency with `install_scripts`
true receives the `npm-install-scripts` annotation, at every scope and
origin. The annotation is informational on its own — plenty of legitimate
packages compile native code at install time — but it is the input to
builder-hardening reviews and to the escalation below.

**Untrusted transitive scripts.** An npm dependency with `install_scripts`
true that is **transitive** in origin and whose lockfile provenance is not
`verified` is rejected with reason `npm-untrusted-scripts`. The combination
is the exact shape of the 2023 credential-exfiltration incident (case study
one): code nobody chose, running at install time, with no integrity chain on
what will actually be fetched. Making the provenance `verified`, or lifting
the package to a reviewed direct dependency, both clear the rejection.

Note the asymmetry against direct dependencies: a *direct* dependency with
install scripts and weak provenance is handled by the provenance rules
(chapter 07) alone; the `npm-untrusted-scripts` rejection is specifically
about the transitive case. This was debated at length — the board's position
is that a direct dependency has a named owner who passed code review, and
the provenance chapter already gives that owner obligations.

## PyPI

PyPI rows carry no ecosystem-specific gate rule in this edition. Two
properties of the ecosystem still matter operationally. First, PyPI is where
most `nightly`-channel pins occur (dev-build version strings such as
`X.Y.Z.devN`), so the channel rules of chapter 06 do most of their work
here. Second, PyPI license declarations are the least reliable of the four
ecosystems — the classifier metadata and the license file disagree in
roughly one package in twelve we sample — which is why the license-class
tie-break rule in chapter 04 exists.

Historical note: between the Second and Third Editions this chapter carried
a PyPI-specific rule requiring source distributions for `runtime`-scope
packages. It was retired as unenforceable at our mirror layer; do not apply
it.

## Go modules

Go's module system provides the strongest provenance story of the four
ecosystems: the go.sum database gives content addresses for every module
version, and our mirror verifies them at fetch time. Consequently nearly
every `go` row in a healthy snapshot has `verified` provenance, and a `go`
row with `absent` provenance is almost always a vendored fork that bypassed
the module proxy — worth attention during review beyond what the provenance
rules already record.

There is no `go`-specific gate rule in force. The board considered making
non-`verified` provenance an automatic rejection for `go` rows (it is
technically achievable ecosystem-wide) but declined: the provenance rules in
chapter 07 already escalate on origin, and special-casing one ecosystem's
*capability* as another's *obligation* produced perverse review incentives
in trial runs.

## Hugging Face (model registry)

Model dependencies differ from package dependencies in kind, not just in
source: the artifact is data, the "version" is a registry revision, and the
supply-chain risk lives in the artifact bytes rather than in install-time
code execution. The ledger therefore pins model dependencies to explicit
artifact digests, and the integrity obligations — presence and exact match
of **every** pinned artifact — are substantial enough to have their own
chapter (08), as does the registry snapshot layout (see the registry
snapshot document outside this handbook).

For the purposes of every generic rule in this handbook, model dependencies
are ordinary ledger rows: they have licenses (chapter 04 applies unchanged),
channels (a model pinned from a registry pre-release line is `beta` or
`nightly` like anything else), provenance, scope, and origin. The
`huggingface` ecosystem adds obligations; it never relaxes any.
