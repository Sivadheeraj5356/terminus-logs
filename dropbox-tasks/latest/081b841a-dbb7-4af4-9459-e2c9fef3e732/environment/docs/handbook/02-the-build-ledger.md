# The build ledger

## What the ledger is

The build ledger is the append-only record of every external dependency the
Orchid monorepo consumes. Each build runs against a **ledger snapshot**: a
CSV of dependency rows plus a metadata document naming the snapshot's
**generation**. The generation is a monotonically increasing integer that
advances whenever the dependency set changes in any way — a version bump, a
new package, a removed package, a re-pinned model artifact. Two builds
against the same generation take exactly the same dependencies.

The gate evaluates ledger rows, not package archives. Everything the gate
needs to know about a dependency is either a column of its ledger row, an
entry in the quarantine registry, or — for model dependencies — a line in
the integrity report produced by hashing the registry snapshot.

## Ledger row semantics

A row is identified by the triple **(ecosystem, name, version)**. The same
package may appear under multiple versions in one snapshot (during a staged
migration, for example); each version is its own row and receives its own
decision.

The columns the gate consumes:

- **ecosystem** — one of `npm`, `pypi`, `go`, `huggingface`. Ecosystem
  determines which ecosystem-specific rules (chapter 03) apply.
- **license** — the declared license, as an SPDX identifier where one
  exists. Non-SPDX declarations are recorded as `LicenseRef-` strings.
  Chapter 04 defines how declarations map to license classes.
- **channel** — the release channel of the pinned version: `stable`,
  `beta`, or `nightly`. Channel policy is chapter 06.
- **provenance** and **lock_generation** — the lockfile provenance state
  and the generation at which the lockfile entry was last written. Chapter
  07 defines the three provenance states and the staleness rule.
- **scope** — where the dependency is used: `runtime` (linked or loaded by
  shipped services), `build` (used by the build itself, not shipped), or
  `dev` (developer tooling, never on the build or serving path).
- **origin** — `direct` (requested by a first-party manifest) or
  `transitive` (pulled in by another dependency's requirements).
- **install_scripts** — whether the package executes scripts at install
  time. Populated for npm rows; see chapter 03.
- **artifacts** — for model dependencies only: the pinned registry files
  as path/digest pairs. Chapter 08 defines the integrity obligations.

## Scope and origin, precisely

`scope` answers "what is exposed if this dependency is bad": `runtime` scope
exposes production services, `build` scope exposes builder infrastructure,
`dev` scope exposes only development machines. Several rules key on this
gradient — the same license or channel can be acceptable at `dev` scope and
rejectable at `runtime` scope. When one package is used at several scopes,
the ledger records the **widest** scope in use.

`origin` answers "did anyone choose this": a `direct` dependency was named
by an engineer in a manifest and code-reviewed; a `transitive` dependency
arrived because something else required it. The gate is generally *stricter*
with direct dependencies on provenance questions (an engineer who chose a
package can be asked to pin it properly) and *stricter* with transitive
dependencies on execution questions (nobody reviewed what its install script
does — see the npm rules in chapter 03).

## Generations and time

The ledger deliberately has no wall-clock component the gate depends on.
Every freshness rule in this handbook is expressed in **generations**, not
days, because generations advance with actual change to the dependency set
and are reproducible in replay. When chapter 07 says a lockfile entry is
stale, it means stale relative to the snapshot's generation number, and
re-running the gate on an old snapshot years later yields the same answer.

The metadata document also records a snapshot timestamp. It exists for
humans reading reports and plays no role in any rule in this handbook.

## What the ledger is not

The ledger is not an SBOM (it records what may enter the build, not what
shipped), not a vulnerability feed (CVE response is the incident process,
though its outcomes often become quarantine entries), and not a mirror
manifest (the registry snapshot under the models root has its own layout
document). The gate reads the ledger; it never writes it. No gate decision
mutates a row, advances a generation, or edits a quarantine entry — those
are, respectively, dependency-change, release, and review-board actions.
