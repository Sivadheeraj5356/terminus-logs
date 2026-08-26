# Exception clause registry — EX-120 series

Entries are reproduced **as filed** (chapter 10). Resolve every
`Disposition` line against the changelog (chapter 16) before treating a
clause as in force; amendments may extend, restrict, or revoke the filed
grant, and the pointer does not indicate which.

---

### EX-120 — license waiver — npm/gpl-icu-tables

- **Filed:** 2025-03-24 · **Requested by:** Internationalization
- **Versions:** 74.1.0
- **Scopes:** build
- **Grant:** GPL-3.0-only packaging of collation table generators used to
  produce the trimmed ICU data bundles services load. Generated bundles
  are data, not covered code.
- **Conditions:** Generator runs confined to the i18n builder.
- **Disposition:** active as filed

### EX-121 — channel exception — pypi/uvicorn-nightly

- **Filed:** 2025-04-02 · **Requested by:** API Platform
- **Versions:** 0.31.0.dev12
- **Grant:** Nightly ASGI server build pinned to validate the
  lifespan-protocol fix against the platform's shutdown-drain harness.
- **Conditions:** Sunset at upstream 0.31.0; harness runs before each
  deploy of the pin.
- **Disposition:** expired 2025-07-01

### EX-122 — license waiver — pypi/gpl-radius-client

- **Filed:** 2025-04-18 · **Requested by:** Corporate Infrastructure
- **Versions:** 3.3.1
- **Scopes:** build
- **Grant:** GPL-3.0-only RADIUS client library used by the builder-image
  provisioning step that enrolls builders with the corporate NAC.
- **Conditions:** Provisioning step only; the library must not persist
  into published builder images.
- **Disposition:** active as filed

### EX-123 — license waiver — npm/gpl-diagram-dsl

- **Filed:** 2025-05-06 · **Requested by:** Architecture Guild
- **Versions:** 2.7.0, 2.7.2
- **Scopes:** build, dev
- **Grant:** GPL-3.0-only diagram DSL compiler rendering the architecture
  decision records. Filed for both builder rendering and workstation
  preview.
- **Conditions:** Rendered SVGs are reviewed for embedded fonts under
  separate terms.
- **Disposition:** see AM-2025-06

### EX-124 — license waiver — go/gpl-tzdata-compiler

- **Filed:** 2025-05-27 · **Requested by:** Platform Libraries
- **Versions:** v2.2024.1
- **Scopes:** build
- **Grant:** GPL-3.0-only timezone data compiler producing the trimmed
  tzdata blobs embedded in service binaries. The blobs are facts; the
  compiler is covered code and never ships.
- **Conditions:** None beyond family-standing conditions.
- **Disposition:** active as filed

### EX-125 — license waiver — pypi/sspl-search-connector

- **Filed:** 2025-06-10 · **Requested by:** Search
- **Versions:** 8.14.0
- **Scopes:** dev
- **Grant:** SSPL-1.0 client connector used by a local index-inspection
  notebook. The board treated SSPL under the strong-copyleft posture and
  accepted workstation-only use.
- **Conditions:** The connector may not be imported by any deployed
  service or scheduled job.
- **Disposition:** active as filed

### EX-126 — channel exception — npm/turbopack-canary

- **Filed:** 2025-06-25 · **Requested by:** Web Toolchain
- **Versions:** 2.0.0-canary.44
- **Grant:** Canary of the incremental bundler evaluated as a potential
  replacement for the current pipeline, pinned for the evaluation builder
  only.
- **Conditions:** Evaluation builder confinement; weekly report to the
  board during the trial.
- **Disposition:** see AM-2025-10

### EX-127 — license waiver — pypi/gpl-fontforge-bindings

- **Filed:** 2025-07-08 · **Requested by:** Design Systems
- **Versions:** 2.0.20240101
- **Scopes:** build
- **Grant:** GPL-3.0-only font manipulation bindings used to subset icon
  fonts during the asset build. Subset fonts ship under their own license;
  the bindings do not ship.
- **Conditions:** None beyond family-standing conditions.
- **Disposition:** active as filed

### EX-128 — license waiver — npm/agpl-query-console

- **Filed:** 2025-07-29 · **Requested by:** Data Platform
- **Versions:** 1.12.0
- **Scopes:** dev
- **Grant:** AGPL-3.0-only interactive query console used against local
  development databases only.
- **Conditions:** Console builds must not be reachable from shared
  environments; binding to non-loopback interfaces voids the waiver.
- **Disposition:** active as filed

### EX-129 — channel exception — go/delve-nightly

- **Filed:** 2025-08-14 · **Requested by:** Developer Platform
- **Versions:** v1.24.0-dev.3
- **Grant:** Nightly debugger build carrying goroutine-label support the
  workstation tooling needed ahead of release.
- **Conditions:** Workstation images only; sunset at upstream v1.24.0.
- **Disposition:** expired 2025-12-01

### EX-130 — license waiver — pypi/gpl-imagemagick-shim

- **Filed:** 2025-09-03 · **Requested by:** Media Pipeline
- **Versions:** 1.1.0
- **Scopes:** build
- **Grant:** GPL-3.0-only shim over the image toolkit used by the
  thumbnail fixture generator in the media test corpus build.
- **Conditions:** Fixture generation only.
- **Disposition:** active as filed

### EX-131 — license waiver — npm/gpl-vendored-grammar

- **Filed:** 2025-09-22 · **Requested by:** Editor Experience
- **Versions:** 3.1.0
- **Scopes:** runtime, build, dev
- **Grant:** GPL-3.0-only grammar bundle vendored by the code-highlighting
  service. Unusually, granted at all three scopes: the highlighting
  service isolates the grammar behind the syntax-server process boundary
  the board reviewed, and the same bundle drives the build-time
  documentation renderer and workstation preview. The process-isolation
  review is attached to the filing.
- **Conditions:** The syntax-server boundary must persist; merging the
  grammar into a consuming process voids the waiver.
- **Disposition:** see AM-2026-02

### EX-132 — license waiver — go/gpl-elf-notes

- **Filed:** 2025-10-09 · **Requested by:** Release Engineering
- **Versions:** v0.4.0
- **Scopes:** build
- **Grant:** GPL-3.0-only ELF note reader used by the provenance stamper
  that annotates release binaries. The stamper reads and writes notes at
  build time and is not distributed.
- **Conditions:** None beyond family-standing conditions.
- **Disposition:** active as filed

### EX-133 — channel exception — pypi/ruff-nightly

- **Filed:** 2025-10-28 · **Requested by:** Developer Platform
- **Versions:** 0.8.0.dev22
- **Grant:** Nightly linter build pinned to validate a rule-stability fix
  against the monorepo before the team enabled the rule fleet-wide.
- **Conditions:** Presubmit shadow-lint only; sunset at upstream 0.8.0.
- **Disposition:** expired 2026-01-15

### EX-134 — license waiver — pypi/gpl-numeric-bench

- **Filed:** 2025-11-12 · **Requested by:** Scientific Computing
- **Versions:** 5.0.2
- **Scopes:** dev
- **Grant:** GPL-3.0-only numerical benchmark harness used to
  characterize kernel regressions on workstations and lab machines.
- **Conditions:** Lab confinement; results published internally only.
- **Disposition:** active as filed

### EX-135 — license waiver — npm/gpl-license-header-tool

- **Filed:** 2025-12-01 · **Requested by:** Compliance Engineering
- **Versions:** 4.4.0
- **Scopes:** build
- **Grant:** GPL-3.0-only header insertion tool run by the notice pipeline
  over generated sources.
- **Conditions:** None beyond family-standing conditions.
- **Disposition:** active as filed

### EX-136 — channel exception — pypi/hf-hub-dev

- **Filed:** 2025-12-16 · **Requested by:** Model Platform
- **Versions:** 0.27.0.dev5
- **Grant:** Dev build of the registry client library, pinned to validate
  resumable snapshot downloads against the internal mirror before the
  mirror's cutover.
- **Conditions:** Mirror-validation builder only; sunset at upstream
  0.27.0.
- **Disposition:** see AM-2026-04

### EX-137 — license waiver — go/gpl-sqlparse-port

- **Filed:** 2026-01-20 · **Requested by:** Database Tools
- **Versions:** v1.6.1
- **Scopes:** build
- **Grant:** GPL-3.0-only SQL grammar port used by the migration linter
  that runs in presubmit. Lint findings ship to review comments; the
  linter does not ship.
- **Conditions:** None beyond family-standing conditions.
- **Disposition:** active as filed

### EX-138 — license waiver — pypi/agpl-vector-store

- **Filed:** 2026-02-11 · **Requested by:** Retrieval
- **Versions:** 0.19.0
- **Scopes:** dev
- **Grant:** AGPL-3.0-only vector store used in local retrieval-quality
  notebooks. The board declined runtime scope at the same sitting and
  minuted the refusal.
- **Conditions:** Notebooks only; no shared deployments.
- **Disposition:** active as filed

### EX-139 — channel exception — npm/swc-nightly

- **Filed:** 2026-03-18 · **Requested by:** Web Toolchain
- **Versions:** 1.7.0-nightly.31
- **Grant:** Nightly transform-core build pinned to confirm an upstream
  fix for a minification miscompile our bundle corpus reproduces.
- **Conditions:** Reproduction builder only; sunset at the fix's stable
  release.
- **Disposition:** active as filed

### EX-140 — license waiver — pypi/gpl-avro-tools

- **Filed:** 2026-04-07 · **Requested by:** Data Infrastructure
- **Versions:** 1.11.3
- **Scopes:** build
- **Grant:** GPL-3.0-only schema tooling used by the pipeline that
  compiles Avro schemas into generated readers. Generated code ships;
  the tool does not.
- **Conditions:** Generated-file headers must name the generator.
- **Disposition:** active as filed
