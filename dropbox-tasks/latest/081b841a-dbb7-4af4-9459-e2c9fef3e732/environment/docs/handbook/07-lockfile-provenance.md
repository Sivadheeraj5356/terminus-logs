# Lockfile provenance

Provenance answers one question: **does the lockfile pin the bytes this
row will actually resolve to?** The ledger records one of three states per
row, plus the generation at which the lockfile entry was written. The
rules in this chapter are stated as in force. Two of them were revised
since the Third Edition — the transitive-absent downgrade and the
staleness boundary — and the revision history is in chapter 16; quoted
thresholds in older case studies do not reflect it.

## The three states

**verified** — the lockfile entry exists and carries an integrity value
our mirror has confirmed against the upstream registry (npm integrity
hashes, PyPI file digests, the go.sum database, or registry revision
digests for model rows). This is the healthy state and the majority of
every snapshot.

**unverified** — the lockfile entry exists but its integrity value could
not be confirmed: the upstream fetch was bypassed, the mirror lacked the
artifact at verification time, or the entry was hand-edited. The bytes are
pinned, but the pin's authority is the lockfile author rather than the
registry.

**absent** — there is no lockfile entry for this row at all. Whatever the
build fetches is whatever the resolver picks on the day. `lock_generation`
is recorded as `0` for absent rows.

## Rules in force

**Absent provenance.** An `absent` row that is **direct** in origin is
rejected with reason `provenance-absent`: the engineer who added the
dependency owns its pin, and an unpinned direct dependency is a one-line
fix away from compliance. An `absent` row that is **transitive** receives
the `provenance-absent` **annotation** instead. The downgrade for
transitive rows is deliberate (and post-dates the Third Edition — see
chapter 16): a transitive gap is a defect in the direct dependency's
lockfile discipline, the fix belongs there, and rejecting the leaf row
punished teams for graphs they did not author. The same identifier serves
as reason and annotation; chapter 13 lists it in both vocabularies.

**Unverified provenance.** Every `unverified` row receives the
`provenance-unverified` annotation, at every scope and origin. It does not
reject on its own, but it feeds two escalations owned by other chapters:
the npm untrusted-scripts rejection (chapter 03) and the unverified-beta
rejection (chapter 06). It also disqualifies the row from any channel
exception (chapter 06).

**Staleness.** A `verified` row is additionally annotated
`provenance-stale` when its lockfile entry is old relative to the
snapshot: the rule in force is that an entry is stale when the snapshot
generation exceeds the row's `lock_generation` by **more than two
generations**. An entry written at the current or previous generation is
fresh; one written two generations ago is at the boundary and is **not**
stale; three or more generations of lag is stale. (The boundary was the
subject of an amendment — the original rule read "two or more"; the
current rule is strictly "more than two." Chapter 16 records the change
and its rationale: generation churn from unrelated dependency changes was
re-flagging rows that had not themselves moved.)

Staleness applies only to `verified` rows. An `unverified` or `absent`
row already carries a stronger provenance finding, and stacking staleness
on top of those produced double-counted review queues in the Third
Edition era.

## What provenance is not

Provenance is about the *pin*, not the *package*. A malicious package with
a perfect lockfile entry is `verified`; a hand-vendored copy of a fine
package is `absent`. Provenance findings therefore never substitute for
quarantine (chapter 09) or integrity (chapter 08) findings, and vice
versa.

`lock_generation` records when the lockfile *entry* was last written, not
when the package was released or last upgraded. Re-pinning the same
version (for example, after a lockfile regeneration) refreshes the entry
and clears staleness without any version change — this is intended, since
the annotation exists to flag entries no tooling has revisited, not old
software as such.

## Remediation quick reference

- `provenance-absent` (reject, direct): add the lockfile entry; verify it.
- `provenance-absent` (annotation, transitive): regenerate the direct
  parent's lockfile so the resolver writes the missing entries.
- `provenance-unverified`: re-fetch through the mirror so integrity is
  confirmed, or re-resolve the entry from the registry.
- `provenance-stale`: regenerate the lockfile entry at the current
  generation; no version change is required.
