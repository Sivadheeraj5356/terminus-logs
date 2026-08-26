# Quarantine registry records

The machine-readable quarantine registry that the gate consumes is the
ledger fixture; this chapter is the human record — each entry as filed,
with its narrative and status history. Like the exception registry,
filed text is never edited; status changes are recorded in the changelog
and reflected in the machine registry. Digests are abbreviated to their
first eight characters here; the machine registry carries the full
values.

---

### QR-1962 — package — pypi/pickle5-backport

- **Filed:** 2022-03-11 by Security · **Status:** lifted 2022-08-29
- A deserialization advisory against the backport's maintainer account
  was reported upstream. The investigation concluded the account
  compromise never reached the package's release pipeline. Lifted with
  the advisory's withdrawal; the annotation history remains on every
  snapshot that still pins the backport.

### QR-1984 — package — go/legacy-yaml-shim

- **Filed:** 2022-06-30 by Security · **Status:** lifted 2023-02-13
- Filed on an upstream parser-differential advisory claiming the shim
  resolved anchors differently from the reference parser under crafted
  input. The report proved unreproducible against any released version;
  lifted at the closing memo. The registry's standing example that
  lifted entries annotate indefinitely: the shim is still pinned by two
  build tools, and both rows carry `quarantine-lifted` in every report.

### QR-2017 — package — npm/color-strings-plus

- **Filed:** 2022-11-08 by Security · **Status:** active
- The maintainer published a protestware release that corrupted output
  on machines with particular locale settings. Upstream reverted, but
  the maintainer retained publish rights; the board declined to lift
  while the trust question stands. No Orchid manifest has pinned the
  package since 2023; the entry stays as a tripwire.

### QR-2050 — package — pypi/iniparse-shim

- **Filed:** 2023-05-16 by Security · **Status:** lifted 2023-09-04
- Typosquat suspicion against a similarly named parser with an
  overlapping maintainer alias. The investigation established
  independent lineage and clean release history; lifted with the closing
  memo. Rows pinning the shim carry the lifted annotation as standard
  history.

### QR-2101 — package — npm/event-stream-flat

- **Filed:** 2023-10-02 by Security · **Status:** active
- The registry's first active filing and the incident behind the gate's
  npm rules (case study one). A maintainer handoff inserted
  credential-harvesting code into a patch release; the fork Orchid
  consumed inherited the compromised lineage. The investigation closed
  without a clean-version determination — the harvester's insertion
  point predated the earliest version our mirror retained — so the entry
  remains active at every version, as package entries do.

### QR-2133 — artifact — digest 8c44e1f0…

- **Filed:** 2024-01-26 by Model Platform · **Status:** active
- A community-published tokenizer merge file was found to disagree with
  its declared base vocabulary in a way that silently shifted token
  boundaries for CJK input. Filed by digest against the affected file;
  the model that pinned it was re-exported against the corrected
  tokenizer under new digests.

### QR-2178 — artifact — digest on file

- **Filed:** 2024-07-08 by Security · **Status:** lifted 2025-01-27
- A mirror sync race produced a tamper signal against a
  language-identification model's configuration: the sync wrote a file
  whose digest matched neither the old nor the new upstream revision.
  Quarantined pending investigation; the root cause was the mirror
  writing a partially updated file under a concurrent revision move.
  Lifted with the sync fix. Cited in mirror-operations reviews as the
  cost of in-place writes.

### QR-2209 — artifact — digest 45bcb681…

- **Filed:** 2024-11-05 by Legal · **Status:** active
- The training-data licensing finding of case study two, filed against
  the pinned configuration digest of the affected fine-tune revision.
  The retrained replacement publishes under new digests and is not
  matched by this entry. The board minuted that the entry stays active
  permanently: the judgment attaches to the artifact, and the artifact
  does not change.

### QR-2210 — artifact — digest 6f1d0c74…

- **Filed:** 2024-11-05 by Legal · **Status:** active
- Companion filing to QR-2209 covering a derived checkpoint of the same
  fine-tune, staged to the registry during the incident window but never
  pinned by any ledger row. Filed to close the door pre-emptively — a
  staged artifact is one careless pin away from a build. The entry has
  never matched a row and that is its job.

### QR-2244 — package — npm/prettier-config-orchid2

- **Filed:** 2025-03-19 by Security · **Status:** active
- Dependency-confusion filing: an external package published under a
  name one character from an internal config package, with install
  scripts. No internal manifest resolved to it (the internal scope rules
  held), but the board filed on the attempt. Active as a tripwire; the
  external package remains published.

### QR-2267 — package — pypi/requests-toolbelt-ng

- **Filed:** 2025-06-23 by Security · **Status:** lifted 2025-10-13
- An upstream release embedded an analytics beacon that fired at import
  time. Upstream removed it two releases later and published a
  postmortem; the board lifted after the removal shipped and the
  maintainer added a release-signing key. Lifted, not narrowed: package
  entries have no version scoping to narrow (chapter 09).

### QR-2311 — artifact — digest on file

- **Filed:** 2026-05-27 by Model Platform · **Status:** active
- Mirror-integrity finding against a third-party classifier head: the
  upstream repository rewrote a published revision in place, so the
  mirrored file and the pinned digest diverged for the same revision
  label. Under investigation; active pending upstream's explanation. The
  entry is recent enough that most snapshots have not yet re-pinned.

---

## Reading the registry

Three patterns worth internalizing from the records above:

**Package entries are blunt on purpose.** Every package entry matches
every version (QR-2101's missing clean-version determination is the
canonical justification). When an investigation does produce version
clarity, the resolution is lift-and-refile, never version-scoping.

**Artifact entries are surgical on purpose.** QR-2209/QR-2210 show the
pattern: judgments attach to digests, replacements publish under new
digests and are unaffected, and pre-emptive filings against staged but
unpinned artifacts are legitimate.

**Lifted is not gone.** QR-1984 and QR-2050 have annotated every
matching row for years. The annotation costs nothing and has twice
surfaced useful context in reviews when a formerly quarantined package
drifted toward trouble again.
