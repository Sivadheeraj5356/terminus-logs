# Frequently asked questions

Answers here are explanatory, not controlling (front matter precedence).
Where an answer states a rule, the defining chapter is cited; read it.

## Ledger and decisions

**My package appears twice in the report. Bug?**
No — rows are keyed by (ecosystem, name, version), and staged migrations
legitimately pin two versions of one package at once. Each version gets
its own decision. (Chapter 02.)

**Why was my dependency rejected for three reasons at once? One would
have been enough to fail the build.**
Reasons are a set, not a verdict-plus-details: burn-down tooling diffs
full reason sets across generations, and reviewers triage from the
complete picture. Implementations that short-circuit fail audit replay.
(Chapter 14.)

**A rejected row also shows annotations. Why bother recording those?**
Because remediation planning reads them. A row rejected only for
`provenance-absent` that also carries `channel-beta` tells its owner two
things to fix, not one. Annotations are never cleared by a rejection.
(Chapter 14.)

**Does the gate ever look at the calendar?**
No rule in force reads wall-clock time. Freshness is measured in
generations; the snapshot timestamp exists for humans. Clause sunsets are
dates, but they are resolved by the board when recording dispositions,
not evaluated by the gate. (Chapters 02, 07, 10.)

## Licenses

**My license is obviously permissive but got `license-unclassified`.**
The class table lists evaluated identifiers, not vibes. Bring the
identifier to the board; until it lands in the table by amendment, it is
unclassified — rejected at runtime and build scope, annotated at dev
scope. (Chapter 04.)

**We have a waiver, so why did the gate reject the upgrade?**
Waiver version lists are enumerated and closed. The new version must be
added by amendment before the ledger pins it. Check the clause's
disposition too — an extension you remember requesting may have landed,
or the waiver may have been restricted since filing. (Chapters 05, 10,
16.)

**The registry says our clause covers us. The gate disagrees.**
Registry entries are reproduced as filed; the changelog is where
revocations and restrictions live. Resolve the `Disposition` line before
trusting filed text. This is the single most common misreading of the
handbook. (Chapters 00, 10.)

**Can we get a waiver for an unclassified license?**
No such instrument exists. Waivers apply to the strong-copyleft rejection
only; unclassified identifiers need a board evaluation into the class
table. (Chapters 04, 05, 10.)

## Channels and provenance

**Beta was always just an annotation. When did that change?**
The annotation-only posture ended for one configuration — runtime scope,
direct origin, provenance not verified — by amendment in early 2025.
Everything else about beta is still annotation-only. If you learned the
rules from the Third Edition, re-read the channel chapter. (Chapters 06,
16.)

**Our nightly pin has a filed exception and verified provenance but was
still rejected.**
Check the version list (exact match, including suffixes), then the
disposition (channel exceptions get revoked more than any other clause
family), then quarantine (an active entry voids every clause). (Chapters
06, 09, 10.)

**Why is exactly-two-generations-behind fresh? It used to be stale.**
The boundary moved by amendment in 2026 after regeneration churn kept
re-flagging unchanged rows. "More than two" is the rule in force; the
case study explains the churn mechanics. (Chapters 07, 15, 16.)

**Transitive dependency, no lockfile entry — reject or annotate?**
Annotate, since the 2025 amendment. Direct rows with absent provenance
still reject. Same identifier, different severity, branching on origin.
(Chapter 07.)

## Models and quarantine

**Four of our five pinned artifacts verify. Surely that's fine?**
No. The quantifier is *every*; four matches do not vouch for a fifth.
Missing and mismatched files are distinct reasons and can co-occur.
(Chapter 08.)

**Our model was quarantined but the digests all match. How can both be
true?**
Integrity says the snapshot contains the bytes you pinned; quarantine
says you may not use those bytes. Matching digests make the quarantine
match *more* certain, not less. (Chapters 08, 09.)

**The quarantined revision was retrained and republished. Are we
covered?**
If the retrained revision publishes under new digests and your ledger
pins those, artifact entries against the old digests do not match you.
Package entries would — but package entries are not filed for model
rows. (Chapter 09.)

**Can a lifted quarantine ever stop annotating?**
No. Lifted entries are history, and history annotates indefinitely. The
annotation is informational and blocks nothing. (Chapter 09.)

## Process

**Who can change these rules?**
The review board, by amendment, majority vote. Emergency quarantine may
be filed unilaterally by Security and ratified after the fact. (Chapters
01, 16.)

**The handbook and the gate implementation disagree. Which do I trust?**
The handbook, always. A disagreement is an implementation defect; file it
against Build Infrastructure with the row and the chapter. (Chapter 00.)

## Reading and reports

**Why do the registry chapters print out-of-date information on
purpose?**
Because filed clause text is a record of what was agreed, and records
that get edited stop being records — the program learned this from an
audit-replay divergence caused by in-place edits (chapter 25). The
cost is a reading discipline: filed text plus disposition plus
changelog. The front matter explains the split; the onboarding
worksheet drills it. (Chapters 00, 10, 33.)

**Is there a single page that lists every rule currently in force?**
Deliberately not. Rules live in their defining chapters with their
context and boundary language; a consolidated cheat sheet would be the
most-cited and least-maintained page in the book, and cheat sheets are
how superseded thresholds survive in the wild. The nearest safe
approximations are the reason-code tables (which enumerate conditions,
with pointers) and the worked evaluations. (Chapters 13, 27.)

**A report entry's `annotations` array is empty but the row obviously
has issues. Is the gate blind?**
The gate records what the rules produce, nothing more. "Obviously has
issues" usually means a concern no rule expresses — which is either a
policy proposal (chapter 32's appeals path) or one of the concerns the
gate deliberately leaves to other controls (chapter 01's boundary
list). Check the worked evaluations before assuming a defect: several
"obviously wrong" rows are boundary cases behaving as documented.
(Chapters 01, 14, 27.)

**Do decisions ever consider who owns the dependency, how widely it's
used, or how critical the service is?**
No. The gate's inputs are the row, the registries, and the integrity
report — closed-world by design (chapter 21). Criticality weighting
was proposed and declined twice: it makes decisions unreproducible
(ownership and criticality change without ledger changes) and it
belongs in queue prioritization, which is where it lives. (Chapters
14, 21, 22.)

**How fast does a quarantine filing take effect?**
Next gate run — quarantine is evaluated at decision time, not baked
into snapshots, so no generation change is needed. This is the fastest
control in the program and the reason emergency filings are
worthwhile. (Chapter 09.)

**Two versions of the same package got different decisions in one
report. Which one is "the" decision for the package?**
Both. Decisions attach to rows, rows are (ecosystem, name, version)
triples, and a staged migration legitimately has one version approved
and the other rejected — that split is often the migration's whole
status report in two lines. Tooling that wants a per-package rollup is
free to compute one, but the gate does not define it. (Chapters 02, 14.)

**Where do I find why a rule is the way it is, rather than what it
is?**
In order of usefulness: the rule chapter's own prose, the changelog
entry that last touched it, the case study or postmortem the changelog
cites, and the minutes of the adopting sitting. The curriculum's last
module is essentially this list. (Chapters 15, 16, 20, 29, 33.)
