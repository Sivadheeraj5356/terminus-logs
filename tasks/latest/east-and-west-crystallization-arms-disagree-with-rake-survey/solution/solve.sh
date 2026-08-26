#!/bin/bash
set -euo pipefail

python3 - <<'PY'
from pathlib import Path

# 1) Mast floor gate: inclusive service floor.
reg = Path("/app/rosegate/src/lib.rs")
text = reg.read_text()
needle = "if epoch > floor {"
repl = "if epoch >= floor {"
if needle not in text:
    raise SystemExit("rosegate gate needle missing")
reg.write_text(text.replace(needle, repl, 1))

# 2) Profile bind: only overlay fallback when the gate rejects.
bind = Path("/app/internal/profile/bind.go")
b = bind.read_text()
old = '''// Bind overlays the service fallback pack when the mast gate rejects the plan.
func Bind(appRoot string, plan pond.Plan, gateOK bool) pond.Plan {
	_ = gateOK
	path := filepath.Join(appRoot, "profiles", "fallback.json")
'''
new = '''// Bind overlays the service fallback pack when the mast gate rejects the plan.
func Bind(appRoot string, plan pond.Plan, gateOK bool) pond.Plan {
	if gateOK {
		return plan
	}
	path := filepath.Join(appRoot, "profiles", "fallback.json")
'''
if old not in b:
    raise SystemExit("profile bind patch site missing")
bind.write_text(b.replace(old, new, 1))

# 3) Route memo: key by pond identity + sector.
memo = Path("/app/internal/engine/route_memo.go")
m = memo.read_text()
old_m = '''func memoKey(_ string, sec int) string {
	return strconv.Itoa(sec)
}'''
new_m = '''func memoKey(pondID string, sec int) string {
	return pondID + "|" + strconv.Itoa(sec)
}'''
if old_m not in m:
    raise SystemExit("route memo patch site missing")
memo.write_text(m.replace(old_m, new_m, 1))

# 4) Resume: restore last_cmd from checkpoint.
rep = Path("/app/internal/engine/replay.go")
r = rep.read_text()
old_r = (
    "\t\t// Apply resume seed before continuing the tape.\n"
    "\t\tfor k := range lastCmd {\n"
    "\t\t\tlastCmd[k] = 0\n"
    "\t\t}\n"
    "\t\tfiltered := make([]tape.Row, 0, len(rows))\n"
    "\t\tfor _, row := range rows {\n"
    "\t\t\tif afterCursor(row.Day, row.Tick, st.CursorDay, st.CursorTick) {\n"
    "\t\t\t\tfiltered = append(filtered, row)\n"
    "\t\t\t}\n"
    "\t\t}\n"
    "\t\trows = filtered\n"
    "\t\t_ = st.LastCmd"
)
new_r = (
    "\t\t// Apply resume seed before continuing the tape.\n"
    "\t\tfor k, v := range st.LastCmd {\n"
    "\t\t\tlastCmd[k] = v\n"
    "\t\t}\n"
    "\t\tfiltered := make([]tape.Row, 0, len(rows))\n"
    "\t\tfor _, row := range rows {\n"
    "\t\t\tif afterCursor(row.Day, row.Tick, st.CursorDay, st.CursorTick) {\n"
    "\t\t\t\tfiltered = append(filtered, row)\n"
    "\t\t\t}\n"
    "\t\t}\n"
    "\t\trows = filtered"
)
if old_r not in r:
    raise SystemExit("resume last_cmd patch site missing")
rep.write_text(r.replace(old_r, new_r, 1))

# 5) Bearing fold: apply offset in the forward mounting sense.
Path("/app/pkg/bearingfold/fold.go").write_text(
    '''package bearingfold

import "math"

func wrapHeading(v float64) float64 {
	out := math.Mod(v, 360.0)
	if out < 0 {
		out += 360.0
	}
	return out
}

func applyOffset(raw float64, offset float64) float64 {
	return wrapHeading(raw + offset)
}

// OpB folds a raw wind direction through the mounting-frame offset.
func OpB(raw float64, offset float64) float64 {
	return applyOffset(raw, offset)
}
'''
)

# 6) Sector fold: use the diversion table at the computed sector.
Path("/app/pkg/sectorfold/fold.go").write_text(
    '''package sectorfold

func clampSector(sec int) int {
	if sec < 0 {
		return 0
	}
	if sec > 7 {
		return 7
	}
	return sec
}

func lookupArm(sec int, table map[int]string) string {
	idx := clampSector(sec)
	if v, ok := table[idx]; ok {
		return v
	}
	return "L1"
}

// OpS maps a sector index through the diversion table.
func OpS(sec int, table map[int]string) string {
	return lookupArm(sec, table)
}
'''
)

# 7) Calm gate: hold advance while a prior command is live in the calm window.
Path("/app/pkg/calmgate/gate.go").write_text(
    '''package calmgate

func calmBlocked(last float64) bool {
	return last > 0
}

func allowAdvance(inCalm bool, last float64) bool {
	if !inCalm {
		return true
	}
	return !calmBlocked(last)
}

// OpL decides whether a calm-window row may change advance state.
func OpL(inCalm bool, last float64) bool {
	return allowAdvance(inCalm, last)
}
'''
)

# 8) Survey fold: honor the plan survey layer token.
Path("/app/pkg/surveyfold/fold.go").write_text(
    '''package surveyfold

func pickLayer(rake float64, lidar float64, layer string) float64 {
	switch layer {
	case "rake":
		return rake
	case "lidar":
		return lidar
	default:
		return rake
	}
}

// OpA picks the survey reading used for mismatch counting.
func OpA(rake float64, lidar float64, layer string) float64 {
	return pickLayer(rake, lidar, layer)
}
'''
)

# 9) Lane load order: row_id, not arm_label.
lane = Path("/app/internal/config/load.go")
lt = lane.read_text()
if "ORDER BY arm_label" not in lt:
    raise SystemExit("lane load ordering needle missing")
lane.write_text(lt.replace("ORDER BY arm_label", "ORDER BY row_id", 1))

checks = {
    "/app/rosegate/src/lib.rs": "epoch >= floor",
    "/app/internal/profile/bind.go": "if gateOK",
    "/app/internal/engine/route_memo.go": 'pondID + "|"',
    "/app/internal/engine/replay.go": "for k, v := range st.LastCmd",
    "/app/pkg/bearingfold/fold.go": "raw + offset",
    "/app/pkg/sectorfold/fold.go": "lookupArm(sec, table)",
    "/app/pkg/calmgate/gate.go": "allowAdvance",
    "/app/pkg/surveyfold/fold.go": 'case "rake"',
    "/app/internal/config/load.go": "ORDER BY row_id",
}
for path, needle in checks.items():
    text = Path(path).read_text()
    if needle not in text:
        raise SystemExit(f"patch check failed: {path} missing {needle!r}")
PY

bash /app/scripts/build.sh
export TB_POND_FIXTURE=1
/app/bin/pond_ctl
