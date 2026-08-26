# Incident postmortem digest

One-page digests of program-relevant postmortems, in chronological
order. The case studies chapter narrates the six incidents that shaped
major rules; this digest covers the longer tail — smaller incidents
whose lessons landed as conditions, tooling changes, or minuted
practice rather than headline amendments. Digests preserve the
original findings' framing; rules quoted are as-of-incident.

## PM-2023-04: the lockfile merge that wasn't

A release was cut from a lockfile that had been resolved twice and
merged by hand; the merged file was internally consistent but pinned a
dependency subtree neither parent branch had tested. No gate rule
fired — every entry was verified, every license permissive. The
postmortem's finding: the gate correctly had no opinion, and the gap
belonged to the merge tooling. Outcome: lockfile files became
merge=binary in the monorepo's attributes, forcing regeneration over
manual merges. Cited here because "the gate should have caught it" was
the initial framing, and the correction — the gate gates *rows*, not
*resolutions* — is worth keeping findable.

## PM-2023-09: annotation blindness

A team shipped three quarters with `provenance-unverified` on a
payment-path dependency; the annotation was in every report and read
by no one. The postmortem produced the queue builder (chapter 22) —
annotations became work items with owners rather than lines in a
report. The SLO regime followed at the next board sitting. The
incident is the origin of the chapter 01 principle that findings are
cheap and silence is expensive: the annotation had been correct and
useless for nine months.

## PM-2024-02: the generator in the artifact

The EX-019 revocation's other half. A GPL code generator's runtime
support file was found inside a shipped binary — the waiver's premise
("generated code carries no copyleft") had failed for one generator
family. Remediation rebuilt affected releases; the registry outcome
was the generated-output condition on every generator waiver since.
The postmortem also produced the notice-pipeline cross-check: shipped
binaries are scanned against the license inventory, catching class
mismatches the ledger's declared-license column cannot see.

## PM-2024-06: quarantine that arrived late

QR-2133's tokenizer merge file had been pinned for eleven days before
the community disclosure that triggered the filing. The postmortem
asked whether the gate could have caught the disagreement between the
merge file and its declared base vocabulary — answer: no, and it
should not try; semantic validation of artifact content is
model-platform territory (the chapter 01 boundary). Outcome: the
model-platform ingest suite grew a tokenizer-consistency check that
runs before artifacts reach the registry, and the handbook gained
nothing — recorded here as the deliberate non-amendment it was.

## PM-2025-01: the setuptools sprawl

EX-097's revocation story. A single-builder channel exception was
found active on four builders; each copy had been made in good faith
during builder-image refreshes. The postmortem traced the mechanism —
the pin lived in a shared base-image layer rather than the
builder-specific overlay the clause assumed — and the remediations
were structural: clause-conditioned pins moved to per-builder
overlays, and builder-image CI began diffing pinned versions against
the exception registry's confinement conditions. The board's "a
clause that is easy to copy will be copied" line entered the playbook
chapter from this postmortem.

## PM-2025-08: the wave that wasn't an incident

A legal takedown tombstoned attestations for one package family
(chapter 28), and forty-one rows went `provenance-unverified` in a
single generation. On-call treated the wave as a compromise signal
and escalated; three hours were spent establishing that the gate was
doing exactly what it should. Outcomes: the mirror layer's takedown
runbook now pre-announces expected annotation waves to the on-call
channel, and the queue builder batches same-cause items under one
banner. Recorded here so the next wave reads as a checklist item, not
a mystery.

## PM-2026-05: the rewrite upstream

QR-2311's companion digest. A third-party model repository rewrote a
published revision in place; the mirror preserved both observations,
the pinned digest diverged from the served file, and the gate's
`digest-mismatch` rejection was the first alarm anyone saw. The
postmortem is notable for what worked: the atomic-sync and
never-rewrite-locally properties (chapter 28) meant the divergence
was evidence rather than confusion, and quarantine-by-digest
immobilized the artifact without blocking the model's other, clean
revisions. Open item at time of writing: mirror-side revision pinning
so upstream rewrites surface as sync failures — the board directed a
proposal at the 2026-05-27 sitting.

---

Reading the digest end to end, the pattern the board keeps citing:
the gate's job is to make facts undeniable, not to have opinions
about everything. Half the postmortems above end with a change
*outside* the gate, and the handbook counts those as successes — the
report said something true, someone read it, and the fix landed where
the fault was.
