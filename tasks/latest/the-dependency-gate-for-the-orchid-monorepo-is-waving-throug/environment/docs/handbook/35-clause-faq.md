# Clause and registry FAQ

A second FAQ, scoped to the exception machinery — the questions the
board's clerk actually fields, week over week. Like chapter 18,
answers are explanatory, not controlling; the defining chapters are
10 (system), 11–12 (registry), 16 (changelog), 23 (playbook), 26
(archive).

**How do I cite a clause in a design doc?**
By number and current standing, resolved as of a date: "EX-131
(active, as amended through AM-2026-02)." Citing filed text without
the disposition resolution is the misreading this handbook warns
about most; a doc that says "EX-131 covers 3.1.0" is already stale
and was arguably wrong the day it was written.

**Our clause number is in the archive chapter. Does that mean it's
dead?**
If it is below EX-100, yes — the Fourth Edition archived the entire
two-digit range, and anything still needed was refiled in the current
series with a successor note. Nothing below EX-100 grants anything.

**Can two clauses cover the same package?**
Yes, and it happens (a waiver and a channel exception can name the
same package; two waivers can cover disjoint version sets after a
messy migration). Each clause is evaluated independently against its
own family's rule. What cannot happen is one clause covering two
packages — identity is one ecosystem and one name, always.

**We renamed our package upstream. Does the waiver follow?**
No. Identity is exact; a rename is a new package and requires a new
filing. The board fast-tracks rename refilings when the terms and use
are unchanged (one sitting, historically), but it does not skip them —
renames are exactly when vendored surprises arrive.

**What does an `expired` disposition actually check?**
Nothing, mechanically, at gate time. Sunsets are resolved by the
clerk when recording dispositions: when a filed sunset date passes,
the disposition line is updated to `expired`, and the machine registry
the gate consumes is regenerated without the clause. The gate never
reads calendars (chapter 18's determinism answer); expiry is a
registry-maintenance action that happens to be triggered by a date.

**Who notices when a clause should expire but the disposition wasn't
updated?**
The registry regeneration job diffs filed sunsets against dispositions
weekly and files a clerk task on divergence. It has fired three times
in program history; none reached a gate decision, which is the point
of checking weekly.

**Can a clause be amended twice?**
Yes — dispositions chain. EX-111 carries one extension; nothing caps
the count. Apply amendments in effective-date order (chapter 10). A
clause with a long chain is usually a hint that the underlying need
has outgrown the clause and the board may consolidate at the next
review — a consolidation *refiles* (new number, current terms) rather
than rewriting the old entry.

**Is there any way to get a temporary waiver while the board
considers the real one?**
No. There is no provisional grant instrument, deliberately: a
provisional that unblocks work removes the requester's urgency while
leaving the board's, and the incentive gradient runs the wrong way.
The board's actual concession to urgency is scheduling — emergency
sittings exist for quarantine, but a genuinely release-blocking
clause request has historically been heard within a week at a regular
or specially convened sitting.

**Our request was denied. Where does that leave the rejected rows?**
Where they were: rejected, with the denial minuted and — for
precedent-setting denials — filed for the record in the registry
(the EX-031 pattern). The productive paths after a denial are the
ones the playbook lists: a different isolation story, a different
scope, a permissive alternative, or a rule-amendment proposal if you
think the default itself is wrong.

**Why are version lists closed? Upstream patches constantly.**
Because the alternative was tried by every requester's first draft
and fails review every time: a range grant delegates the board's
judgment to upstream's release discipline. The friction is the
feature — each version added is a moment where someone confirms the
terms and the use haven't shifted. Teams that patch-chase file
extension amendments in batches; the clerk's records show the median
extension turnaround is one sitting.

**Does a waiver survive an ecosystem migration (the package moved
from npm to our internal registry)?**
No — ecosystem is half the identity. And note that the migration
usually moots the waiver anyway: a package republished through an
internal registry has its license terms re-reviewed at import, which
is the class-table path, not the waiver path.

**What happens to clauses at the next edition?**
Registry entries persist as filed, dispositions and all; editions
never rebase them (chapter 00). The one edition-boundary action in
registry history is the Fourth's archival of the pre-EX-100 range,
and the bar for repeating that (a numbering-era boundary, every
affected clause individually dispositioned) is recorded in the
consolidation minutes.
