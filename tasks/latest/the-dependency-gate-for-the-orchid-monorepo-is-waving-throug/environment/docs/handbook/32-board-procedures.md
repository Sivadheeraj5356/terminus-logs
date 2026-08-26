# Review board procedures

Chapter 01 names the Dependency Review Board; this appendix records how
it actually operates. Procedures matter to handbook readers for one
reason: every rule, clause, and quarantine status in this book is the
output of a procedure below, and knowing the procedure tells you what
kind of evidence moved it.

## Composition and quorum

Three permanent seats — Security, Legal, Build Infrastructure — each
held by a named individual with a named alternate, plus one rotating
seat filled by the requesting organization for items it brings. Quorum
is all three permanent seats (alternates count); the rotating seat
participates but does not count toward quorum. Amendments and clause
grants need a majority of seated members; quarantine ratification needs
any two permanent seats. The chair rotates annually among the permanent
seats; the chair breaks ties, which in a four-seat sitting can happen.

## Sittings

Regular sittings are monthly, minuted, and agenda'd a week ahead;
chapter 20 digests them. Emergency sittings can be called by any
permanent seat with four hours' notice and handle exactly two item
types: quarantine ratification and incident-driven amendments (the
2023-10-16 and 2024-11-05 sittings are the pattern). Anything else
raised at an emergency sitting is docketed for the next regular one —
the board learned early that emergency sessions make expansive policy
badly.

## Item types and their evidence bars

**Clause grants** (waivers, channel exceptions) follow the playbook
(chapter 23). The board expects: exact identity, the scope-exposure
argument, the rejected alternative, and a proposed condition. Grants
are effective at filing, numbered next-in-series, and land in the
registry verbatim — drafting quality matters because the text is
permanent.

**Clause amendments** (extensions, restrictions, revocations) need the
original clause, the delta, and — for extensions — re-verification of
the original conditions (the EX-131 re-review is the template).
Revocations for condition breach follow the EX-104 principle:
remediation does not cure a breach.

**Rule amendments** need the failure evidence (an incident, a churn
analysis, a counterfactual replay per chapter 21) and ship with their
replay delta attached. The board has adopted every rule amendment since
2024 with a pre-adoption replay in the packet, and the minutes record
the delta each time. Drafting practice: state boundary cases in words
(chapter 25's second standing lesson), add a worked row to chapter 27,
and name the effective date explicitly.

**Quarantine actions** are the least ceremonial: Security files,
any two permanent seats ratify, the changelog records. Lifting needs
the closing memo. The board does not debate quarantine merits at
filing time — the entry immobilizes the artifact so the investigation
can proceed; the debate, if any, happens at lifting.

**Class-table evaluations** (adding a license identifier to a class)
need a Legal memo on the identifier's terms against Orchid's
distribution model. Most evaluations close in one sitting; the memo
does the work. The bar is deliberately lower than teams assume
(chapter 23's playbook says so in as many words), because the
alternative — teams routing around unclassified rejections — is worse
than a busy Legal queue.

## Records

Everything the board does lands in exactly one of three records: the
changelog (chapter 16) for anything that changes rule or clause
standing; the registry chapters for filed clause text; the minutes
(chapter 20) for reasoning, denials, and precedent. Denials of note
are filed *in the registry* as denied-for-the-record entries (the
EX-031 pattern in the archive) when the board wants the precedent
findable by clause search rather than minute reading.

The three-record discipline is what makes the handbook's precedence
order (chapter 00) workable: an assertion about current policy is
checkable against the changelog and registry without reading years of
minutes, and the minutes stay what minutes should be — context, not
law.

## Appeals

A team disagreeing with a gate outcome has exactly two paths, and
"argue with the gate" is neither. If the outcome correctly implements
the handbook, the appeal is a policy proposal: bring the board a rule
amendment with evidence (the AM-2025-11 downgrade began as exactly
this). If the outcome misimplements the handbook, it is a defect:
file against Build Infrastructure with the row and the chapter, and
the fix ships without board action — implementations conform to the
book, not the reverse (chapter 00). The FAQ's last answer and this
paragraph are the same sentence for a reason.
