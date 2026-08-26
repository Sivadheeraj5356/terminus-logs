# Provenance verification mechanics

Chapter 07 defines the three provenance states and their rules; this
appendix records how each ecosystem's `verified` determination is
actually made. It exists for two audiences: mirror operators debugging
why a row came out `unverified`, and rule authors who need to know what
the states can and cannot promise. Nothing here changes gate behavior —
the gate consumes the ledger's `provenance` column and never re-derives
it.

## npm

The lockfile of record is the workspace `package-lock.json`. An entry is
`verified` when it carries an `integrity` field (SRI form, sha512) and
the mirror has confirmed that digest against the registry tarball for
the exact resolved version. Confirmation happens at mirror ingest, not
at build time; the ledger writer trusts the mirror's attestation
database.

The common paths to `unverified`: hand-merged lockfile conflicts that
preserve the `resolved` URL but drop or mangle `integrity` (the case
study one subtree); entries whose `resolved` points outside the mirror
(git URLs, tarball URLs), which the mirror cannot attest; and legacy
lockfileVersion 1 entries carrying sha1 `integrity`, which the mirror
declines to confirm. `absent` is almost always a workspace that was
installed with lockfile writing disabled.

## PyPI

The lockfile of record is the compiled requirements set with `--hash`
entries (sha256, one per distribution file). An entry is `verified` when
every hash for the resolved version confirms against the mirror's copy
of the corresponding file. PyPI's wrinkle is multi-artifact resolution:
one version resolves to different wheels per platform, and the entry is
`verified` only when the full hash set covers every file the build
matrix can select — a partial hash set that happens to cover the
developer's platform but not the builder's is the classic path to
`unverified` appearing "only in CI."

`absent` on PyPI usually means a requirements line without hashes
(hash-checking mode disables itself for the whole resolution the moment
one line lacks hashes, so one unhashed line degrades the entire file's
rows).

## Go modules

The strongest story of the four, as chapter 03 notes. An entry is
`verified` when the module version's go.sum lines (module hash and
ziphash) confirm against the checksum database our proxy mirrors, with
the proxy's transparency-log inclusion proof checked at ingest. Because
the checksum database is global and append-only, `verified` for Go
carries a property the other ecosystems lack: the pin is confirmed
against what *everyone* sees, not just what our mirror saw.

`unverified` in Go is rare and almost always a private module whose
GONOSUMCHECK/GOPRIVATE exclusion bypasses the database; the mirror
attests those from its own first-fetch record instead, and the ledger
convention is to record them `unverified` honestly rather than launder
first-fetch trust into `verified`. `absent` is vendored code that
bypassed the module system entirely.

## Hugging Face registry

Model rows carry artifact pins in the ledger itself (chapter 08), which
makes the provenance column partially redundant for them — deliberately
so. `provenance` for a model row attests the *revision resolution*: the
lockfile of record maps the model name and revision label to a registry
revision digest, and the entry is `verified` when the mirror confirms
the label-to-digest binding at snapshot sync time. The artifact pins
then bind file content; the two checks catch different failures
(a moved label versus a rewritten file — QR-2311 is the latter).

`unverified` model rows come from revision labels resolved outside the
mirror (a direct pull during development that leaked into the ledger
writer's cache). The ledger tooling flags these loudly because the
downstream escalations that key on provenance (chapter 06's beta rule)
apply to model rows exactly as to packages.

## What `verified` does not mean

Across all four ecosystems, `verified` attests that the lockfile pins
the bytes the registry serves for that version. It does not attest that
those bytes are good (quarantine's job), that the version is wisely
chosen (channel policy's job), or that anyone reviewed the code
(nothing in this handbook claims that). The provenance ladder is
integrity-of-reference, nothing more — which is exactly why it can be
mechanically verified and why the rest of the handbook can build on it.
