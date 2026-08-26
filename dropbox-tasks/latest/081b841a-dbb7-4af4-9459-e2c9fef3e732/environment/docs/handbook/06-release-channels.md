# Release channels

The `channel` column records which release line the pinned version comes
from: `stable`, `beta`, or `nightly`. Channel policy exists because a
version's release line is a statement by its maintainers about how much
scrutiny it has had, and the gate treats that statement as an input to
risk. The rules in this chapter are stated as in force; the beta rule in
particular was strengthened by amendment after the Third Edition (chapter
16), and older material describing beta as "advisory only" is out of date.

## Channel classification

The ledger derives the channel from the pinned version string and the
upstream release metadata at pin time: `stable` for ordinary releases,
`beta` for pre-releases on a maintained line (`-beta.N`, `-rc.N`, `bN`
suffixes and equivalents), `nightly` for dev builds cut from an unreleased
line (`-nightly.*`, `.devN`, snapshot dates). The gate trusts the column;
it does not re-parse version strings.

## stable

No channel finding. This is the default posture the other two channels are
measured against.

## beta

Every `beta` row receives the `channel-beta` annotation. The annotation is
permanent for as long as the pin stays on a pre-release — it is the
standing signal that a production surface is running ahead of an upstream
release.

In addition, one combination escalates to rejection. A beta row is
rejected with reason `channel-unverified-beta` when **all three** of the
following hold:

- `scope` is `runtime`, and
- `origin` is `direct`, and
- `provenance` is not `verified`.

The logic of the triple: a runtime-scope pin exposes shipped services; a
direct dependency means an engineer chose the pre-release deliberately;
and non-verified provenance means the lockfile does not pin the actual
bytes. Any one or two of these is tolerable and merely annotated (the
provenance rules add their own findings), but the combination — a chosen,
shipped pre-release with no integrity chain — is the profile of every
"we were running a beta we couldn't reproduce" incident in the program's
history. Verifying the lockfile entry clears the rejection while keeping
the `channel-beta` annotation; so does dropping to `build`/`dev` scope.

Transitive beta pins are *not* escalated by this rule regardless of scope
or provenance: the remediation for a transitive pre-release is to fix the
direct dependency that demands it, and that path is kept annotation-only
so the fix lands through normal dependency review.

## nightly

Nightly builds are rejected with reason `channel-nightly` by default, at
every scope and origin. There is no scope carve-out (a nightly compiler on
builders was the subject of case study four) and no provenance mitigation:
a verified pin of a nightly build is a reproducible pin of code its own
maintainers have not cut a release from.

The only override is an **active channel exception clause** (chapter 10;
registry in chapters 11–12) naming the package's ecosystem and name, whose
version list contains the row's version exactly, and — a standing
condition on every channel exception, imposed by the board rather than
per-clause — the row's provenance must be `verified`. When such a clause
applies, the rejection is replaced by the `channel-exception` annotation.
A channel exception whose row is not `verified` simply does not apply, and
the default rejection stands; the clause is not "partially" honored.

Channel exceptions are the rarest clause type in the registry and are
granted almost exclusively for toolchain-adjacent packages where the team
tracks an upstream development line by necessity. Several have been
revoked after the need passed — a filed clause in the registry proves
nothing about current standing (chapter 10; dispositions in chapter 16).

## Composition

Channel findings compose with all other chapters: a nightly row under an
active exception can still be quarantined, license-blocked, or
provenance-annotated, and the `channel-exception` annotation never
suppresses those. Channel policy reads `channel`, `scope`, `origin`, and
`provenance`; it never reads license or artifact data.
