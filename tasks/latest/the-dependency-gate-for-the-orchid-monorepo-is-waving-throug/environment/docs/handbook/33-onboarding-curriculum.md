# Onboarding curriculum

New gate reviewers, ledger tooling engineers, and board alternates all
work through the same curriculum; the exercises differ. Estimated time
is two working days for reviewers, a week for engineers. Nothing here
is normative — the curriculum exists so that the people applying the
handbook have all read the same handbook, in the same order, and hit
the same known misconceptions early.

## Module 1: the shape of the system (half day)

Read the front matter, charter, and ledger chapter (00–02), then the
decision procedure (14). Skip the rule chapters on the first pass —
the curriculum deliberately teaches aggregation before rules, because
the most durable misconception in the program is treating the gate as
a linear checklist that stops at the first problem. The exercise:
given a row with four findings, write the decision entry by hand,
then check against chapter 27's W16.

Common misconception to surface now: "the gate decides whether a
dependency is good." It does not; it decides whether a ledger row
complies with the handbook (chapter 01's scope paragraph). The
distinction carries the whole curriculum.

## Module 2: the rule chapters (one day)

Read 03 through 09 in order, each followed by its worked rows in
chapter 27. The reading order matters: ecosystems before licenses
(scope and origin semantics arrive in 02–03 and every later chapter
uses them), provenance before channels (the beta escalation reads
provenance), models and quarantine last (they compose with everything
before them).

Exercises, one per chapter: W4/W5 for npm scripts; W2/W3 and W7/W8
for licenses; W9–W13 for channels; W6 for staleness — reviewers must
articulate *why* gap-exactly-two is fresh, citing the boundary
language, not just recall that it is; W14/W15 for models; W16 for
quarantine composition. Engineers additionally implement each rule
against the sample ledger and diff their output against the QA golden
(the tooling reference, chapter 30, describes the loop).

## Module 3: the registries and the changelog (half day)

Read the exception system chapter (10), then — before the registries —
the changelog (16) top to bottom once. Then the registry chapters (11,
12) with the standing instruction to resolve every `Disposition`
pointer by hand, and the quarantine records (19).

The module's single teaching goal is the misreading the front matter
warns about: filed text is not current standing. The exercise is a
worksheet of six clauses (EX-102, EX-107, EX-111, EX-123, EX-131,
EX-136) where the trainee writes each clause's *current* version list,
scope list, and standing, with the changelog entry that establishes
each fact. A trainee who answers EX-102 "active, one version" or
EX-131 "one version" from the filed text alone repeats the module —
both mistakes have shipped in real tooling twice (chapter 25), which
is why the worksheet exists.

Board alternates extend the module with the procedures appendix (32)
and the minutes digest (20), tracing two amendments from proposal
through replay delta to adoption.

## Module 4: operations (half day; engineers, one day)

Read replay (21), queues (22), mirror operations (28), and the
postmortem digest (29). Reviewers do the queue triage exercise: given
a generation diff with an escalation-adjacent crossing (chapter 22's
list), explain to a hypothetical team why their unchanged row was
suddenly rejected — the answer must name the standing combination
rule and the neighboring attribute that changed. Engineers do the
replay exercise: reproduce one archived generation's report from its
retained inputs and produce a byte-identical diff, then intentionally
break determinism (iterate a map into an array) and watch verification
replay catch it.

## Module 5: the long tail (self-paced)

The case studies (15), edition history (25), archived registry (26),
risk profiles (31), and playbook (23) are assigned reading with no
exercises; they are the program's memory, and the curriculum's last
lesson is where to look things up rather than what to memorize. The
FAQ (18) is explicitly *not* assigned — trainees end up there anyway,
and the curriculum's authors prefer first contact with the FAQ to
happen while chasing a real question.

## Sign-off

Reviewers sign off with a mock triage of twenty queue items sampled
from real (anonymized) history; engineers with a green golden run of a
policy change plus a written explanation of one changelog amendment's
replay delta; alternates with a mock sitting packet. Sign-offs are
recorded by the Build Infrastructure lead. The curriculum itself is
versioned with the handbook edition and updated at consolidation —
this revision matches the Fourth Edition.
