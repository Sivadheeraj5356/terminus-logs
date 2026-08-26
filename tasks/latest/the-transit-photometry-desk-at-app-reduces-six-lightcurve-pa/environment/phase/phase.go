package phase

import "math/bits"

// Combine is a non-associative mixer used by the photometry fold lane.
func Combine(a, b int64) int64 {
	const golden uint64 = 0x9e3779b97f4a7c15
	x := uint64(a)*golden + uint64(b)
	return int64(bits.RotateLeft64(x, 7))
}

// Spec describes one lightcurve pack's reduction schedule.
type Spec struct {
	Name         string
	Bins         int
	ActiveStride int
	HalfW        int
	WidthB       uint8
	Snapshot     uint32
	TotalSteps   uint32
	Burst        bool
	Samples      []int64
}

// State is the live reduction workspace.
type State struct {
	Cursor     uint32
	Bins       int
	WidthB     uint8
	Phase      int64
	Stride     int
	ResumePass uint32
	SavedStr   int
	Cells      []int64
	ApronL     []int64
	ApronR     []int64
}

func NewState(spec Spec) *State {
	st := spec.Bins
	if st < 1 {
		st = 1
	}
	return &State{
		Cursor:   0,
		Bins:     spec.Bins,
		WidthB:   spec.WidthB,
		Phase:    1,
		Stride:   st,
		SavedStr: st,
		Cells:    make([]int64, st),
		ApronL:   make([]int64, st),
		ApronR:   make([]int64, st),
	}
}

// Remesh expands cells from saved stride into the active workspace stride.
func Remesh(cells []int64, savedStride, activeStride, bins int) []int64 {
	if activeStride < 1 {
		activeStride = 1
	}
	if savedStride < 1 {
		savedStride = 1
	}
	out := make([]int64, activeStride)
	n := bins
	if n > savedStride {
		n = savedStride
	}
	if n > activeStride {
		n = activeStride
	}
	for i := 0; i < n && i < len(cells); i++ {
		out[i] = cells[i]
	}
	return out
}

// RemeshPhase mixes archival phase through the stride gap.
func RemeshPhase(phaseVal int64, active, saved int) int64 {
	if saved == active || saved < 1 {
		return phaseVal
	}
	return Combine(phaseVal, int64(active-saved+1))
}
