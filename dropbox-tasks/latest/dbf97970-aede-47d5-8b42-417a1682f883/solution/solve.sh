#!/usr/bin/env bash
set -euo pipefail
# Artifact-cache read delegation under a deferred demand charge. Each cache must ride the runner-group
# tier it COMES TO REST in after the deferred settle, not the first tier in its escalation order. A cache
# may only ride a tier whose seeded roster covers its required jobs and holds none of its forbidden jobs
# (the escalation column lists exactly those legal tiers, tightest first). A cache's weight charges its
# tier settle_delay placements later, not on the spot (rgW_budget 5, rgX_budget 3, rgY_budget 4, rgZ
# unbounded, settle_delay 2, all from /app/tier.conf).
#
# Deferred settle over placement_order lint,api,web,infra,data,mobile,ml,docs: while an earlier
# placement's charge is still pending, later caches read rgX as emptier than it settles and take it; once
# every charge lands rgX is over budget 3 and sheds its latest occupants down their escalation chains
# until every bounded tier is within budget. The fixed point is
#     lint->rgW  api->rgY  web->rgX  infra->rgZ  data->rgW  mobile->rgX  ml->rgX  docs->rgZ
#   with rgX at exactly budget 3. An instant charge instead settles web on rgW, infra on rgX, data on
#   rgX, mobile on rgZ, ml on rgZ and docs on rgW, delegating six caches through the wrong roster.

D=/srv/ci-cache

declare -A WRITER=(
    [lint]=runA [web]=runA [api]=runB [infra]=runB
    [data]=runC [mobile]=runC [ml]=runD [docs]=runD
)
declare -A TIER=(
    [lint]=rgW [api]=rgY [web]=rgX [infra]=rgZ
    [data]=rgW [mobile]=rgX [ml]=rgX [docs]=rgZ
)

for s in lint api web infra data mobile ml docs; do
    d="$D/$s"
    w="${WRITER[$s]}"
    g="${TIER[$s]}"
    # ownership: root owner, writer's private group, setgid so drops carry the writer group
    chown root:"$w" "$d"
    chmod 2770 "$d"
    # traverse for the settled tier roster on the directory itself
    setfacl -m "u:$w:rwx"  "$d"
    setfacl -m "g:$g:r-x"  "$d"
    # inheritance for later artifact files: writer keeps write, tier roster read only, mask open
    setfacl -d -m "u:$w:rwx" "$d"
    setfacl -d -m "g:$w:rwx" "$d"
    setfacl -d -m "g:$g:r-x" "$d"
    setfacl -d -m "m::rwx"   "$d"
done
