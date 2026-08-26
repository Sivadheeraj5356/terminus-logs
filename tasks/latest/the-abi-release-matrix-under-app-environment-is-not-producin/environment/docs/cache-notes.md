# Configure cache notes

Reconfiguring a lane (a full `cmake -S … -B …`) is the expensive step, so each
lane build tree is reused when it is provably still valid. Two independent
guards must both agree before a warm tree is reused without reconfigure:

1. **Profile stamp** — `cache_stamp.sh` records a stamp keyed on the *content*
   of the resolved lane profile. If the profile file's bytes change (even
   in place, with the same path), the stamp no longer matches and the lane
   reconfigures.

2. **Journal freshness** — the lane journal must be current per
   `journal-contract.md`: both the IDL fingerprint and the tool fingerprint must
   match the present inputs.

If either guard fails, the lane reconfigures and its `configure_epoch` advances.

The IDL fingerprint (`idl_fingerprint.sh`) covers the raw file bytes of
`pack.order` itself — not merely the fragment names it resolves — then every
fragment that file lists (in order), then the legacy compat table and the
provenance manifest. A comment-only or whitespace-only edit to `pack.order`
that leaves the fragment list unchanged still changes the fingerprint and
invalidates every warm lane that consumes the pack.

A reused tree still rebuilds through the build system, so an unchanged lane
reproduces its artifacts exactly while paying nothing for reconfigure.

Warm-hold markers under a lane build tree (for example `.warm-hold`) are
operator-owned and must survive an output-only wipe of the release directory.
