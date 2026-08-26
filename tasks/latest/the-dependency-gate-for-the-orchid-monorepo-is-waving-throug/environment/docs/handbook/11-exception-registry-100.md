# Exception clause registry — EX-100 series

Entries are reproduced **as filed** (chapter 10). The `Disposition` line is
a pointer, not a summary: where it names an amendment, the amendment text
in chapter 16 is operative and may extend, restrict, or revoke the filed
grant. Nothing in this chapter, read alone, establishes that a clause is
in force.

---

### EX-100 — license waiver — pypi/gnu-getopt-port

- **Filed:** 2023-08-04 · **Requested by:** Developer Platform
- **Versions:** 1.4.0
- **Scopes:** dev
- **Grant:** GPL-3.0-only argument-parsing port used by an internal CLI
  scaffolding tool that runs exclusively on developer workstations. The
  tool is not distributed outside the company and produces no shipped
  artifacts.
- **Conditions:** The requesting team confirms annually that the tool
  remains workstation-only.
- **Disposition:** active as filed

### EX-101 — license waiver — npm/gplot-render

- **Filed:** 2023-09-19 · **Requested by:** Observability
- **Versions:** 5.2.1, 5.2.3
- **Scopes:** build
- **Grant:** GPL-3.0-only plotting wrapper invoked by the docs build to
  render latency diagrams. Output images ship; the renderer does not.
- **Conditions:** Rendering runs in the docs builder only; no service
  image may install the package.
- **Disposition:** active as filed

### EX-102 — channel exception — npm/esbuild-canary

- **Filed:** 2024-01-22 · **Requested by:** Web Toolchain
- **Versions:** 0.21.0-nightly.88
- **Grant:** The bundler team tracked an upstream nightly to pick up a
  code-splitting fix ahead of its release, after the fix was verified
  against the monorepo's bundle corpus in a sandboxed builder.
- **Conditions:** The team upgrades to the first stable release carrying
  the fix and reports completion to the board.
- **Disposition:** see AM-2025-09

### EX-103 — license waiver — go/readline-gnu

- **Filed:** 2024-02-10 · **Requested by:** Database Tools
- **Versions:** v1.1.2
- **Scopes:** build
- **Grant:** GPL-3.0-only readline binding linked into an internal schema
  REPL used during migrations. The REPL binary is builder-resident and is
  not part of any release artifact.
- **Conditions:** Binary distribution outside builder images voids the
  waiver.
- **Disposition:** active as filed

### EX-104 — channel exception — pypi/arrow-flight-dev

- **Filed:** 2024-03-05 · **Requested by:** Data Infrastructure
- **Versions:** 16.0.0.dev122
- **Grant:** Dev build of the Flight RPC bindings needed for a wire-format
  fix during the columnar-store migration.
- **Conditions:** Sunset at the upstream 16.0.0 release; sandboxed builder
  verification before each pin.
- **Disposition:** see AM-2024-08

### EX-105 — license waiver — pypi/sphinx-gpl-domains

- **Filed:** 2024-03-28 · **Requested by:** Documentation
- **Versions:** 0.9.4
- **Scopes:** build
- **Grant:** GPL-3.0-only Sphinx extension providing custom directives for
  the operations handbook build. Generated HTML ships; the extension does
  not.
- **Conditions:** None beyond family-standing conditions.
- **Disposition:** active as filed

### EX-106 — license waiver — npm/agpl-graph-layout

- **Filed:** 2024-04-16 · **Requested by:** Network Tooling
- **Versions:** 2.3.0
- **Scopes:** dev
- **Grant:** AGPL-3.0-only force-directed layout library used by a
  topology debugging page served only on engineer loopback. The board
  accepted the dev-scope isolation argument specifically because the page
  binds to localhost by design.
- **Conditions:** Any network exposure of the page voids the waiver.
- **Disposition:** active as filed

### EX-107 — license waiver — pypi/readline-gpl-shim

- **Filed:** 2024-05-09 · **Requested by:** Release Engineering
- **Versions:** 6.2.1, 6.2.2
- **Scopes:** build
- **Grant:** GPL-3.0-only shim exposing GNU readline to the release
  conductor's interactive approval prompts. The conductor runs on release
  builders; its binaries are not shipped. The two listed versions differ
  only in a terminfo lookup fix.
- **Conditions:** The shim must remain confined to the conductor; any
  appearance in a service image is a scope breach.
- **Disposition:** active as filed

### EX-108 — license waiver — go/gpl-mibs-compiler

- **Filed:** 2024-06-30 · **Requested by:** Network Tooling
- **Versions:** v0.8.1
- **Scopes:** build
- **Grant:** GPL-3.0-only SNMP MIB compiler generating Go structs checked
  into the monorepo. Generated code carries no copyleft; the compiler runs
  at build time only.
- **Conditions:** Generated-file headers must name the generator and
  version.
- **Disposition:** active as filed

### EX-109 — channel exception — pypi/grpcio-nightly

- **Filed:** 2024-07-21 · **Requested by:** Service Mesh
- **Versions:** 1.66.0.dev41, 1.66.0.dev47
- **Grant:** Nightly gRPC bindings carrying the fork-safety fix the mesh
  sidecar needed ahead of upstream's release train.
- **Conditions:** Sunset at upstream 1.66.0; the sidecar soak suite runs
  against every pinned nightly before ledger admission.
- **Disposition:** expired 2024-11-30

### EX-110 — license waiver — npm/gpl-sourcemap-explorer

- **Filed:** 2024-08-13 · **Requested by:** Web Performance
- **Versions:** 3.0.2
- **Scopes:** dev
- **Grant:** GPL-3.0-only bundle-size analysis tool run manually by
  engineers investigating regressions.
- **Conditions:** None beyond family-standing conditions.
- **Disposition:** active as filed

### EX-111 — license waiver — pypi/gpl-tesseract-binding

- **Filed:** 2024-09-02 · **Requested by:** Document Processing
- **Versions:** 0.5.0
- **Scopes:** build
- **Grant:** GPL-3.0-only OCR binding used by the fixture-generation
  pipeline that produces test corpora for the ingestion service. Fixtures
  ship to the test tree only.
- **Conditions:** Fixture outputs are reviewed for embedded source
  fragments before commit.
- **Disposition:** see AM-2025-03

### EX-112 — license waiver — go/agpl-object-differ

- **Filed:** 2024-09-25 · **Requested by:** Storage
- **Versions:** v1.0.4
- **Scopes:** dev
- **Grant:** AGPL-3.0-only structural diff library inside a bucket-state
  debugging CLI. Workstation use only.
- **Conditions:** The CLI may not be installed on bastion or production
  hosts.
- **Disposition:** active as filed

### EX-113 — channel exception — npm/rollup-wasm-nightly

- **Filed:** 2024-10-08 · **Requested by:** Web Toolchain
- **Versions:** 4.22.0-nightly.19
- **Grant:** Nightly of the WASM-backed bundler core, needed to reproduce
  and confirm an upstream memory-corruption fix against our largest
  bundles.
- **Conditions:** Sunset at the next stable minor; single-builder
  confinement.
- **Disposition:** expired 2025-01-31

### EX-114 — license waiver — pypi/gpl-license-scanner

- **Filed:** 2024-10-29 · **Requested by:** Compliance Engineering
- **Versions:** 2.1.0, 2.1.1
- **Scopes:** build
- **Grant:** The irony was noted at the sitting: a GPL-3.0-only scanner
  that inventories license texts across the monorepo for the notice
  pipeline. Runs at build time; its output notices ship, it does not.
- **Conditions:** None beyond family-standing conditions.
- **Disposition:** active as filed

### EX-115 — license waiver — npm/gpl-terminal-kit

- **Filed:** 2024-11-19 · **Requested by:** Developer Platform
- **Versions:** 1.9.0
- **Scopes:** dev
- **Grant:** GPL-3.0-only terminal UI toolkit inside the local dev-server
  dashboard.
- **Conditions:** None beyond family-standing conditions.
- **Disposition:** active as filed

### EX-116 — channel exception — pypi/protobuf-dev

- **Filed:** 2024-12-04 · **Requested by:** API Platform
- **Versions:** 5.29.0.dev0
- **Grant:** Dev build of the protobuf runtime pinned to validate the
  editions-syntax migration before committing schema changes fleet-wide.
- **Conditions:** Sunset at upstream 5.29.0; schema-conformance suite runs
  against the pin nightly.
- **Disposition:** expired 2025-03-15

### EX-117 — license waiver — pypi/agpl-pdf-toolkit

- **Filed:** 2025-01-13 · **Requested by:** Document Processing
- **Versions:** 4.2.0
- **Scopes:** build
- **Grant:** AGPL-3.0-only PDF manipulation toolkit used by the invoice
  fixture generator. The board weighed AGPL network-use terms and accepted
  the build-scope isolation: the generator has no network surface.
- **Conditions:** The generator must remain network-isolated; a socket
  listener anywhere in its process voids the waiver.
- **Disposition:** active as filed

### EX-118 — channel exception — pypi/opa-wasm-runtime

- **Filed:** 2025-02-06 · **Requested by:** Build Infrastructure
- **Versions:** 0.9.0.dev4, 0.9.0.dev6
- **Grant:** Dev builds of the WASM policy evaluator used by the gate's
  own presubmit shadow-evaluation, tracking upstream's unreleased bundle
  API. The two pins bracket the API change the team is validating.
- **Conditions:** Shadow evaluation only; the production gate must not
  load the WASM runtime. Standing verified-provenance condition noted at
  filing.
- **Disposition:** active as filed

### EX-119 — license waiver — go/gpl-flamegraph

- **Filed:** 2025-03-11 · **Requested by:** Performance
- **Versions:** v0.11.3
- **Scopes:** dev
- **Grant:** GPL-3.0-only flamegraph renderer used by the profiling CLI on
  workstations.
- **Conditions:** None beyond family-standing conditions.
- **Disposition:** active as filed
