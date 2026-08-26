# SSHD merge desk sheet (draft — not ratified)

Deep-merge tenant sshd overlays with **global directives winning** over tenant leaves on conflict.

RULE:MERGE_STRATEGY=global_over_tenant
RULE:SSHD_MERGE_ORDER=global_first

Circulation note: global bastion posture must not be weakened by tenant overlays.
