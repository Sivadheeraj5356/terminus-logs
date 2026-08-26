# Remediation cookbook

One recipe per reason code: what the rejection means, the fastest
compliant path out, the paths that look faster and are not, and the
verification that the fix landed. Written for the engineer holding a
rejected row at admission time; the rule citations are where to argue
if you think the rejection is wrong (and chapter 32's appeals section
is how).

## `quarantined` (chapter 09)

**Means:** a board judgment matches your row — package entries by
ecosystem and name at any version, artifact entries by a pinned
digest. **Out:** for package entries, move off the package (there is
no version to upgrade to — the entry matches them all); for artifact
entries, move to a revision published under different digests, which
for remediated models is usually the retrained replacement (QR-2209's
pattern). **Not out:** waivers, exceptions, scope changes, provenance
fixes — nothing overrides active quarantine. **Verify:** the row
disappears from the reject set at the next generation; the quarantine
entry itself will not change on your account.

## `artifact-missing` / `digest-mismatch` (chapter 08)

**Means:** the snapshot does not contain a pinned file, or contains
different bytes. Treat as an incident signal first — page routing is
automatic (the runbook pages model-platform on mismatch). **Out:** if
the investigation localizes the fault to a pin typo or a stale sync,
fix the pin or re-sync and advance the generation; if upstream
rewrote (QR-2311's shape), expect a quarantine entry and follow the
`quarantined` recipe. **Not out:** re-pinning to the *computed*
digest to make the mismatch disappear — that converts an integrity
alarm into an unreviewed acceptance of unknown bytes, and the
import-review process treats it as such. **Verify:** all pinned paths
present and matching in the next audit's report.

## `license-blocked` (chapters 04, 05)

**Means:** strong-copyleft class, no active waiver covering your
exact version and scope. **Out, in preference order:** the permissive
alternative you were asked to price (chapter 23); a scope reduction
if the use genuinely narrows (runtime→build changes the exposure
argument entirely); a waiver request through the playbook; an
extension amendment if a waiver exists but your version is not
listed. **Not out:** vendoring the code past the ledger (case study
seven), or re-declaring the license (the ledger records the license
file's identifier; a wrong declaration is a data fix with review, not
an editable field). **Verify:** decision moves to annotate with
`license-exception` (waiver path) or approve (alternative path).

## `license-unclassified` (chapter 04)

**Means:** the identifier has no board evaluation — which includes
misspelled or nonstandard renderings of evaluated identifiers.
**Out:** if the identifier is wrong, fix the declaration at its
source; if it is right, request a class-table evaluation (lighter
than teams assume; one sitting historically). At dev scope this is
already only an annotation. **Not out:** a waiver request (wrong
instrument — chapter 23's checklist). **Verify:** the identifier
lands in chapter 13's table by amendment, and the row re-evaluates.

## `channel-nightly` (chapter 06)

**Means:** a dev-build pin with no applicable channel exception.
**Out:** wait for or move to the release (the default answer, and
usually days away for active upstreams); or, for a genuine
ahead-of-release need, a channel exception request with the playbook's
four elements — remembering the standing verified-provenance
condition, and that the version string must match exactly. **Not
out:** relabeling the pin's channel (the ledger derives it at pin
time; hand edits are data corruption), or pinning "one nightly back"
to a version an old clause listed — check the clause's disposition;
the registry's revoked channel exceptions outnumber its active ones.
**Verify:** annotate with `channel-exception`, or approve on a stable
pin.

## `channel-unverified-beta` (chapter 06)

**Means:** the full triple — runtime, direct, not verified. **Out:**
verify the lockfile entry; the rejection dissolves by construction
and this is nearly always the fix (chapter 07's remediation list).
Scope or origin changes also break the triple but are rarely honest
descriptions of a real change. **Not out:** requesting an exception —
no instrument covers this rejection, deliberately. **Verify:**
decision moves to annotate carrying `channel-beta` (which persists
until the pin reaches stable).

## `provenance-absent` (chapter 07)

**Means (as a rejection):** a direct dependency with no lockfile
entry. **Out:** add and verify the entry — genuinely a one-line fix
in every ecosystem (chapter 24 records what verification needs).
**Not out:** demoting the dependency to "transitive" by moving the
manifest line into a shim package; origin describes reality and the
import-review process reads diffs. **Verify:** approve, or annotate
if other findings remain.

## `npm-untrusted-scripts` (chapter 03)

**Means:** install scripts, transitive, not verified — the case study
one shape. **Out:** verify the provenance (usually: regenerate the
direct parent's lockfile so the subtree's integrity fields are
restored), or promote the package to a reviewed direct dependency if
you actually depend on it. Disabling the package's scripts at install
time also ends the condition where the build supports it — but note
the annotation `npm-install-scripts` reflects the package's declared
hooks and persists either way. **Not out:** ignoring it because "it's
just a build machine" — builder exposure is the incident this rule is
made of. **Verify:** decision moves to annotate carrying
`npm-install-scripts`.

## When two or more reasons stack

Fix them independently; they compose independently (chapter 14). The
report's full reason set is the worklist, and the diff after each fix
shows exactly what remains — W16 in the worked evaluations is the
two-reason template. The one ordering worth knowing: if `quarantined`
is in the set, start there, because its remediation (moving off the
package or revision) frequently moots the rest of the list.
