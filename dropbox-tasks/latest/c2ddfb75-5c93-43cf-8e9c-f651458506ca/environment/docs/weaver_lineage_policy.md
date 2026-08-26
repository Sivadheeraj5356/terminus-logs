# Succession policy

Lineage weight starts at `1.0`. Walk maker `mentor_of` links from the panel weaver toward the root weaver, multiplying each hop's `thread_trust`.

Each weaver entry in `master_weavers/succession_epochs` carries `active_from_year`. Only take a hop when the panel `completion_year` is greater than or equal to that hop's `active_from_year`. If a hop is inactive, stop the walk without traversing it.

Compile the active successor map from the panel `completion_year` at walk time. The walk inputs are:

1. starting `weaver_id`
2. the raw `mentor_of` map from `/app/data/master_weavers/`
3. the full master-weavers registry (for `thread_trust` and succession epochs)
4. the panel `completion_year`

Do not pass a precompiled successor map that drops `completion_year` filtering. Publish `weaver_lineage` rounded to six decimal places.
