# Integrity model

The lab models a tiered file-read integrity policy in the style of kernel
measurement and appraisal. This document is the normative contract the pipeline
must satisfy. Fixtures under `data/` are written against it.

## Verbs

Each attachment carries a verb drawn from the catalog in the resolved policy
bundle:

- `log` records a digest row keyed by the exact read path issued by the workload.
- `check_hmac` appraises the path against the `hmac_hex` field in the manifest.
- `check_sig` appraises the path against the `sig_hex` field in the manifest.

A sentinel value of sixteen `f` hex digits marks an intentional appraisal failure
for the corresponding field.

## Attachments

Attachments live in tier documents referenced from the resolved policy bundle.
Each attachment carries its own numeric `tier` field; that field identifies the
attachment's band. Policy document `id` values only point at which document to
load.

Each attachment bind carries a `root` string. Only `root` is authoritative for
path matching. Other bind keys that may appear in tier documents are
non-normative and must not replace `root`.

An attachment covers a read when the read path equals the root or is a proper
descendant of the root in the path hierarchy. Sibling paths that merely share a
string prefix are not covered.

## Paths

Before coverage and manifest lookup, read paths are compared after collapsing
duplicate slash segments and dot segments. Digest rows and report events still
record the path string issued by the workload read.

## Dispatch and roll-up

Among every covering attachment, the winning band is the one with the least
numeric `tier` value. Only attachments at that winning band participate. Every
covering attachment at that band contributes its verb; the active set is the
union of those verbs.

When multiple appraisal verbs are active, every one must pass for the check
outcome to be `pass`; any failure yields `fail`. When no appraisal verb is
active, the check outcome is `skip`.

The per-read `verdict` is `ok` when observed digest logging and appraisal
outcomes match what the winning band demands. When appraisal is required and
the manifest comparison correctly fails, the check outcome is `fail` and the
per-read `verdict` is `bad`. That is still a model-correct outcome.

The reconcile pass sets `aligned` true when those invariants hold for every
audited read. See `schemas/report.schema.md`.
