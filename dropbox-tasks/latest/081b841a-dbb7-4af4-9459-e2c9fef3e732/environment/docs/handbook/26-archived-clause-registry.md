# Archived clause registry — First and Second Edition era

When the Second Edition introduced the `EX-` numbering, existing grants
from the First Edition's "known exceptions" spreadsheet were refiled
with numbers below 100, and the Second Edition era filled most of the
two-digit range. At the Fourth Edition consolidation the board archived
every clause below EX-100: **nothing in this chapter is in force.**
Grants that were still needed at archive time were refiled in the
current series (their entries note the successor). The archive is kept
because clause history is precedent — denial and revocation reasoning
in this range is still cited in sittings.

Entries below are reproduced as refiled in the Second Edition format,
which lacked the `Disposition` line; the archive header of each entry
states its terminal status instead.

---

### EX-011 — license waiver — pypi/gpl-readline-legacy · superseded 2024-05-09

The First Edition spreadsheet's oldest surviving grant: GNU readline
bindings for the original release conductor, build scope, versions
5.x era. Superseded by EX-107 when the conductor was rewritten and the
shim replaced the direct binding. Cited as the template for every
readline-family grant since.

### EX-014 — license waiver — npm/gpl-minifier-classic · lapsed 2023-06-30

GPL-3.0-only minifier used by the pre-monorepo web build, build scope.
Lapsed at the Second Edition adoption when the web build moved to a
permissive toolchain; never refiled.

### EX-019 — license waiver — go/gpl-protoc-plugin · revoked 2023-04-17

Code generator waiver, build scope. Revoked when an audit found the
plugin's generated stubs embedded a nontrivial runtime support file
under the same GPL license — the "generated code carries no copyleft"
premise did not hold for this generator. The incident is why every
generator waiver since (EX-108, EX-124, EX-140) carries a
generated-output condition.

### EX-023 — channel exception — pypi/numpy-nightly · lapsed 2023-01-31

The program's first channel exception, granted before channel policy
had standing conditions. The clause as filed had no provenance
requirement and no sunset; it lapsed by its own terms when the pinned
nightly line released. The gaps in this filing shaped the family-wide
conditions chapter 10 now lists.

### EX-027 — license waiver — pypi/gpl-doc-extractor · lapsed 2023-06-30

Docstring extraction tool for the original docs pipeline, build scope.
Lapsed unused at the Second Edition adoption.

### EX-031 — license waiver — npm/agpl-admin-panel · denied, filed for the record 2023-02-20

The board's first recorded denial-with-prejudice: an AGPL admin UI
requested at runtime scope for a customer-adjacent service. Filed in
the registry as denied so the reasoning would be findable: AGPL
network-use terms plus customer exposure exceeded any isolation story
available. Cited in every subsequent AGPL runtime discussion.

### EX-034 — license waiver — go/gpl-asn1-compiler · superseded 2024-06-30

ASN.1 struct generator, build scope. Superseded by EX-108 (the MIBs
compiler grant) when the two generators merged upstream.

### EX-038 — channel exception — npm/webpack-canary · revoked 2023-08-14

Canary bundler pin for a performance investigation. Revoked when the
investigation ended, in the era before sunset conditions were standard;
the three-month gap between the need ending and the revocation is cited
as the argument for mandatory sunsets on channel exceptions.

### EX-042 — license waiver — pypi/gpl-latex-renderer · lapsed 2024-02-29

LaTeX rendering bindings for the research-notes pipeline, build scope.
The pipeline was decommissioned; the clause lapsed at its first review
cycle with no consumer.

### EX-047 — license waiver — npm/gpl-svg-optimizer · superseded 2023-09-19

SVG optimizer for the docs build, build scope, versions 1.x. Superseded
by EX-101 when the docs build consolidated its rendering toolchain and
the optimizer was replaced by the plotting wrapper's built-in pass.

### EX-051 — license waiver — pypi/sspl-metrics-client · denied, filed for the record 2023-11-06

SSPL metrics client requested at runtime scope. Denied on the same
posture later applied in EX-125's dev-scope grant: SSPL is treated
under strong-copyleft rules, and runtime scope requires an isolation
review the requesting service could not satisfy (the client was to be
linked directly into the serving binary).

### EX-055 — license waiver — go/gpl-ebpf-tracer · lapsed 2024-08-31

Kernel tracing library for builder profiling, dev scope. Lapsed when
the profiling tooling moved to the permissive successor library; the
review cycle closed it automatically — the first clause retired by the
overdue-review freeze rather than by explicit action.

### EX-058 — channel exception — pypi/cython-dev · lapsed 2023-05-31

Dev-build compiler pin used to validate a code-generation fix ahead of
release. Lapsed at its sunset. Notable as the first filing to include
a builder-confinement condition, now standard in the family.

### EX-063 — license waiver — npm/gpl-i18n-extractor · superseded 2025-03-24

Message-extraction tool for the translation pipeline, build scope.
Superseded by EX-120 when the extraction and collation toolchains
merged.

### EX-066 — license waiver — pypi/agpl-notebook-diff · lapsed 2024-11-30

Notebook diffing tool, dev scope. Lapsed unused at review; the
requesting team had moved to the permissive fork within a quarter of
the grant. Cited in the playbook chapter's "alternative you rejected"
guidance — the alternative arrived six months after the request.

### EX-071 — license waiver — go/gpl-disasm · revoked 2024-10-21

Disassembly library inside a release-artifact inspection tool, build
scope. Revoked for condition breach: the tool was found installed on
two bastion hosts, outside its builder confinement. The remediation
was complete before the sitting; the revocation stood anyway (the
EX-104 principle, applied in the same quarter).

### EX-075 — channel exception — npm/vite-beta · lapsed 2024-04-30

Filed when beta-channel policy was stricter in draft than it shipped;
by the time the clause was granted, the annotation-only beta posture
made it unnecessary for its purpose. Lapsed at sunset unused. The
minutes note the lesson: clause requests racing policy drafts should
wait for the policy.

### EX-082 — license waiver — pypi/gpl-fixture-faker · superseded 2024-09-02

Test-data generation library, build scope. Superseded by EX-111 when
the fixture pipeline consolidated its generators.

### EX-088 — license waiver — npm/gpl-audio-transcode · lapsed 2025-05-31

Audio transcoding wrapper for the media test corpus, build scope.
Lapsed when the corpus moved to pre-transcoded fixtures; the clause's
final review notes the fixture approach removed the last GPL tool from
the media pipeline.

### EX-093 — license waiver — go/agpl-graph-store · denied, filed for the record 2024-12-16

AGPL graph database client, dev scope requested, denied. Unusually, a
*dev*-scope denial: the "local development database" turned out to be
a shared staging cluster reachable from the office network, and the
isolation premise failed at review. Cited as the reason dev-scope AGPL
grants (EX-106, EX-112, EX-128) all carry explicit loopback or
no-shared-deployment conditions.

### EX-097 — channel exception — pypi/setuptools-nightly · revoked 2025-01-27

The archive's cautionary tale: a nightly build-backend pin granted for
one builder to validate a packaging fix, found eight months later to
be pinned on four builders by copy-paste. Revoked for scope creep; the
packaging team's remediation and the resulting builder-image audit are
covered in the postmortem digest. The board's minuted takeaway — "a
clause that is easy to copy is a clause that will be copied" — is
quoted in the playbook chapter's confinement guidance.

---

## Reading the archive

The two-digit era's terminal statuses tell the program's story in
miniature: early grants lapsed or were superseded as toolchains
consolidated; the denials-for-the-record established the AGPL and SSPL
postures the current registry inherits; and the revocations — every
one a condition breach or scope creep — built the conditions discipline
chapter 10 codifies. Nothing here grants anything; everything here
explains why the current registry looks the way it does.
