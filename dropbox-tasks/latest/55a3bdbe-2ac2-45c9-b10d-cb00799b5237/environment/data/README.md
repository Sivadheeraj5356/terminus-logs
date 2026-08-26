# keeper-framing data dictionary

These files describe forty subjects (`subject_id` su-01..su-40) on a wildlife photographer's
shoot list, along with the recent record of how the long lens has fared on each. A single frame
fired at a subject either lands a keeper (the bird sharp, the eye lit, nothing clipped) or it
does not, and whether any one frame keeps is a per-frame chance `p` set by that subject. Frames
are independent, so firing `n` frames at a subject banks a keeper with probability
`1 - (1 - p)^n`; one keeper is all it takes.

`subjects.csv` carries one row per subject. `showiness` is a field score for how boldly the
subject sits to the lens, read off the first scouting pass, and the per-frame keeper chance
climbs with it. `hide_cost` and `guide_cost` are the subject's per-frame prices on the two
routes described below.

`frame_log.csv` is the record of recent frames, one row per frame fired. `keeper` is 1 when that
frame was a keeper and 0 when it was not. Coverage is uneven from one subject to the next: some
carry a long run of frames and others only a few, and a handful were worked hard without a single
frame ever keeping.

`shoot_policy.json` holds `reference_showiness` (a baseline showiness reading), `keeper_prob_min`
and `keeper_prob_max` (the range any inferred keeper rate must lie within), `keeper_floor` (the
level every subject has to reach), `hide_frame_budget`, and `cost_ceiling` (the hard cap on
committed cost; a plan whose total crosses it is rejected).

Frames for a subject come from two routes. A shared public-hide session fires frames cheaply at
`hide_cost` but draws on one shared ration of `hide_frame_budget` frames spread across all forty
subjects; a private guided sit lays down any number of frames at the higher `guide_cost`. A
plan's committed cost is the sum, over all subjects, of its hide frames at `hide_cost` plus its
guided frames at `guide_cost`, and it may not cross `cost_ceiling`.
