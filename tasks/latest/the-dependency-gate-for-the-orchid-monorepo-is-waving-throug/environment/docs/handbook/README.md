# Orchid Dependency Governance Handbook — Fourth Edition

This handbook is the governing document for the Orchid monorepo build gate. It
defines what may enter a build, under which conditions, and with which recorded
findings. When any tool, dashboard, or policy bundle disagrees with this
handbook, the handbook wins.

Reading order for newcomers: front matter, charter, and the build-ledger
chapter first; then the five rule chapters (ecosystems, licenses, channels,
provenance, model registry); then the quarantine and exception machinery.
Veterans mostly live in the two exception registry chapters and the changelog.

| Chapter | File |
|---|---|
| Front matter | `00-front-matter.md` |
| Program charter | `01-program-charter.md` |
| The build ledger | `02-the-build-ledger.md` |
| Package ecosystems | `03-package-ecosystems.md` |
| License classes | `04-license-classes.md` |
| License review and waivers | `05-license-waivers.md` |
| Release channels | `06-release-channels.md` |
| Lockfile provenance | `07-lockfile-provenance.md` |
| Model registry integrity | `08-model-registry-integrity.md` |
| The quarantine program | `09-quarantine-program.md` |
| The exception clause system | `10-exception-clause-system.md` |
| Exception registry, EX-100 series | `11-exception-registry-100.md` |
| Exception registry, EX-120 series | `12-exception-registry-120.md` |
| Reason codes and annotations | `13-reason-codes.md` |
| The decision procedure | `14-decision-procedure.md` |
| Case studies | `15-case-studies.md` |
| Amendments and changelog | `16-amendments-changelog.md` |
| Glossary | `17-glossary.md` |
| Frequently asked questions | `18-faq.md` |
| Quarantine registry records | `19-quarantine-registry.md` |
| Board minutes digest | `20-board-minutes.md` |
| Audit replay and the compliance record | `21-audit-replay.md` |
| Review queues and burn-down operations | `22-review-queues.md` |
| Requesting exceptions: a playbook | `23-clause-request-playbook.md` |
| Provenance verification mechanics | `24-provenance-mechanics.md` |
| Edition history | `25-edition-history.md` |
| Archived clause registry (pre-EX-100) | `26-archived-clause-registry.md` |
| Worked evaluations | `27-worked-evaluations.md` |
| Mirror operations | `28-mirror-operations.md` |
| Incident postmortem digest | `29-postmortem-digest.md` |
| Ledger tooling reference | `30-ledger-tooling-reference.md` |
| Ecosystem risk profiles | `31-ecosystem-risk-profiles.md` |
| Review board procedures | `32-board-procedures.md` |
| Onboarding curriculum | `33-onboarding-curriculum.md` |
| Report consumers and integrations | `34-report-integrations.md` |
| Clause and registry FAQ | `35-clause-faq.md` |
| Drafting style guide | `36-drafting-style-guide.md` |
| Program metrics annex | `37-program-metrics-annex.md` |
| Remediation cookbook | `38-remediation-cookbook.md` |

A note on currency: the rule chapters (03 through 09) were consolidated for
this edition and state the rules **as currently in force**. The exception
registry chapters (11 and 12) reproduce each clause **as originally filed**;
a clause's current standing is determined by its filed text *together with*
any amendment recorded in the changelog (chapter 16). Do not treat a registry
entry as in force without checking its disposition.
