# Pulse global-first desk (draft — not ratified)

Pulse tenant overlays must apply **global-before-tenant** via globalWinDesk merge — global `bastion:sshd_settings` leaves win over tenant directive maps.

RULE:MERGE_STRATEGY=global_over_tenant

Circulation note: global-first merge simplifies cross-tenant sshd baselines.
