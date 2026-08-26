package engine

import (
	"math"

	"lab.local/salt_pond/pkg/bearingfold"
	"lab.local/salt_pond/pkg/pond"
	"lab.local/salt_pond/pkg/sectorfold"
	"lab.local/salt_pond/pkg/tape"
)

type windOutcome struct {
	armKey string
	delta  float64
}

func sectorIndex(dir float64) int {
	d := math.Mod(dir, 360.0)
	if d < 0 {
		d += 360
	}
	return int(d/45.0) % 8
}

func mapWindArm(plan pond.Plan, row tape.Row) (string, float64) {
	adj := bearingfold.OpB(row.DirDeg, plan.MastBearingOffset)
	sec := sectorIndex(adj)
	if cached, ok := memoGet(plan.PondID, sec); ok {
		return cached, row.SpeedKn * 0.5
	}
	armKey := sectorfold.OpS(sec, plan.SectorTable)
	memoPut(plan.PondID, sec, armKey)
	return armKey, row.SpeedKn * 0.5
}

func applyWindRow(
	plan pond.Plan,
	row tape.Row,
	lastCmd map[string]float64,
	state map[string]*ArmRow,
) (windOutcome, bool) {
	armKey, delta := mapWindArm(plan, row)
	out := windOutcome{armKey: armKey, delta: delta}
	if _, ok := state[armKey]; !ok {
		return out, false
	}
	calmLo, calmHi := plan.CalmWindow[0], plan.CalmWindow[1]
	inCalm := row.Tick >= calmLo && row.Tick <= calmHi && row.SpeedKn < plan.CalmThresholdKn
	if holdCalm(inCalm, lastCmd[armKey]) {
		return out, true
	}
	if delta > 0 {
		lastCmd[armKey] = delta
	}
	st := state[armKey]
	if delta > 0 {
		st.AdvanceCmd = delta
	}
	st.FrontM += delta
	st.TelemetryOK = row.TelemetryOK
	return out, false
}
