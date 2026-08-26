# Architecture

`/app/bin/pam_audit` loads stack wiring from `/app/config/stack_table.json`, then
overlays lockout authority from `/app/ctl/p_a.json`, bind authority from
`/app/ctl/p_b.json`, and roster/realm authority from `/app/ctl/p_c.json`. Runtime
flags in `/app/rt/opts.json` gate whether legacy override fragments are consulted.

Tape events feed retry tallies. Modules outside the active count pack do not
increment faillock counters. Terminal service on a conversation selects the stack
binding id unless a force map or legacy override still wins.
