# Keelmark drydock packaging notes (draft)

These ops notes predate the canonical pack ledger. Prefer the normative ledger under
/app/keelmark-ledger when values disagree. Historical threshold sheet used warn=700
and critical=900 with fully zero-padded timestamps — that sheet is retired.

## GHC 9.0 migration addendum

The 8.10-to-9.0 migration replaced the tide-era stream handling with the gate-v2
stream profile. Shipped consoles must compile the internal libraries with the CPP
define named by `packaging_build.stream_profile_cpp_define` in the normative ledger,
on every package listed under `packaging_build.stream_profile_required_on`. A build
without that profile on either library silently regresses to the retired tide-era
stream handling and its reports will not reconcile against the normative ledger.

The compat trees under each package are retained solely as the 8.10 audit trail.
They compile cleanly, but they implement the retired tide sheet — banker's rounding,
strict threshold trips, fully zero-padded timestamps, ascending peer ties, quoted
coverage_pct, swapped block-row keys, and a single-newline gate seal. Nothing under
a compat tree may be wired into a shipped binary.

The migration never finished copying Keelmark.Scan, Keelmark.Classify, and
Keelmark.Emit into the maintained src trees. Those modules must be restored under
`packages/keelmark-core/src/Keelmark/Scan.hs`,
`packages/keelmark-core/src/Keelmark/Classify.hs`, and
`packages/keelmark-report/src/Keelmark/Emit.hs` so they implement the normative
ledger (overlay retraction during parse, type-strict kN, inclusive audit window,
max-keeping dedup, half-up tenths, inclusive thresholds, hour/second-only padding,
Z-A peer ties, bare coverage_pct, ledger key order, double-newline seal) rather
than the tide sheet. Only Types and Main already live under the maintained trees.

See `packaging_build.compat_trees`, `packaging_build.restored_modules`, and
`packaging_build.project_local_overrides` in the normative ledger — bookworm hosts
sometimes leave a cabal.project.local that strips the gate profile even after the
.cabal files look correct.
