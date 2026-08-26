# Canary tenant alias desk sheet (draft — not ratified)

Canary preflight bundles reuse the production overlay at `bastion:overrides:tenant:prod` instead of a dedicated canary hash.

RULE:CANARY_TENANT=prod

Circulation note: canary and prod share identical sshd posture during pilot windows.
