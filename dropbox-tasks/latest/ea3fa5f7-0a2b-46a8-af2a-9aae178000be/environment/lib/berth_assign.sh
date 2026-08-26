#!/usr/bin/env bash
set -euo pipefail
# Berth assignment from ranked ledger. See /app/docs/berth-staging.md and /app/docs/priority-ledger.md.
python3 - "$1" "$2" <<'PY'
import hashlib,json,sys
ledger=json.loads(sys.argv[1]); hab=json.loads(sys.argv[2])
gap=hab["psi_gap"]; buf=hab["berth_gap_min"]; emergency=hab.get("surge_cargo_id")
by={a["cargo_id"]:a for a in ledger["ranked"]}; surge=by.pop(emergency,None) if emergency else None
order=sorted(by.values(), key=lambda e:(-e["score"], e["cargo_id"]))
state={b["berth_id"]:{"end":0.0,"psi":None,"n":0,"spec":b} for b in hab["berths"]}
assign=[]; ok=True

def place(act, surge=False):
    global ok
    opts=[]
    for b in hab["berths"]:
        bid=b["berth_id"]; spec=state[bid]["spec"]
        if not spec["psi_min"]<=act["psi"]<=spec["psi_max"]: continue
        le=state[bid]["end"]; lp=state[bid]["psi"]
        gap_used=lp is not None and abs(act["psi"]-lp)<gap
        start=act["berth_start"] if not surge else le+buf
        if gap_used and not surge: start=max(start, le+buf)
        if surge: start=max(start, le+buf); gap_used=True
        end=start+act["transfer_min"]
        opts.append((state[bid]["n"], start, bid, gap_used, end))
    if not opts: ok=False; return False
    _, start, bid, gap_used, end=min(opts, key=lambda t:(t[0],t[1],t[2]))
    row={"cargo_id":act["cargo_id"],"berth_id":bid,"seq":0,"gap_used":gap_used,"start":round(start,6),"end":round(end,6),"m3":act["m3"],"cold":act["cold"]}
    if surge: row["surge"]=True
    assign.append(row); state[bid]["end"]=end; state[bid]["psi"]=act["psi"]; state[bid]["n"]+=1
    return True
for act in order:
    if not place(act): break
if surge is not None and ok:
    if not place(surge, True): ok=False
assign.sort(key=lambda e:(e["start"],e["cargo_id"]))
for i,r in enumerate(assign,1): r["seq"]=i
body={"schema_version":1,"tide_hash":ledger["tide_hash"],"assignments":assign,"feasible":ok}
body["staging_hash"]=hashlib.sha256(json.dumps({k:body[k] for k in body if k!="staging_hash"},separators=(",",":"),sort_keys=True).encode()).hexdigest()
print(json.dumps(body))
PY
