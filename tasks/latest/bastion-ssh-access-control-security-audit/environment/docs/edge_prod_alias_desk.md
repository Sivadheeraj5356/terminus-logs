# Edge tenant alias desk (draft — not ratified)

Edge bundles reuse the prod overlay at `bastion:overrides:tenant:prod` instead of a dedicated edge hash.

RULE:EDGE_TENANT=prod

Circulation note: edge and prod share identical sshd posture during narrow promotion windows.
