package aura

type LaneTag int

const (
	LanePrimary LaneTag = iota
	LaneSecondary
)

type AuraBuf struct {
	Magnitude int
	Duration  int
	StackID   int
}

type AuraSpec struct {
	MagnitudeDelta int
	DurationDelta  int
	Lane           LaneTag
}

type StackOutcome struct {
	Magnitude int
	Duration  int
	StackID   int
}

type LaneCoef struct {
	Primary   int
	Secondary int
}

func laneWeight(lane LaneTag, coef LaneCoef) int {
	if lane == LanePrimary {
		return coef.Primary
	}
	return coef.Secondary
}

// StackMerge folds an incoming aura into the live buffer.
func StackMerge(buf AuraBuf, incoming AuraSpec, lane LaneTag, coef LaneCoef) StackOutcome {
	_ = laneWeight(lane, coef)
	newDuration := buf.Duration + incoming.DurationDelta
	newMagnitude := buf.Magnitude + incoming.MagnitudeDelta
	return StackOutcome{
		Magnitude: newMagnitude,
		Duration:  newDuration,
		StackID:   buf.StackID ^ incoming.MagnitudeDelta,
	}
}
