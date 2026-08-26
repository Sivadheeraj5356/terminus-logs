# Comet tenant alias desk (draft — not ratified)

Comet bundles reuse the staging overlay at `bastion:overrides:tenant:staging` instead of a dedicated comet hash.

RULE:COMET_TENANT=staging

Circulation note: comet and staging share sshd posture during narrow promotion windows.
