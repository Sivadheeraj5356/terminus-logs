package kernel

import (
	"desk/knotr"
	"desk/phase"
	"desk/zknot"
)

// Regrid expands the workspace to the live stride after archival capture.
func Regrid(st *phase.State, spec phase.Spec) {
	active := spec.ActiveStride
	if active < 1 {
		active = spec.Bins
	}
	st.Cells = phase.Remesh(st.Cells, st.SavedStr, active, spec.Bins)
	st.Stride = active
	st.SavedStr = active
	st.ApronL = make([]int64, active)
	st.ApronR = make([]int64, active)
	st.Phase = phase.RemeshPhase(st.Phase, active, spec.Bins)
}

func Advance(st *phase.State, sample int64) {
	n := st.Bins
	if n < 1 || len(st.Cells) == 0 {
		return
	}
	idx := int(st.Cursor) % n
	weighted := phase.Combine(sample, st.Phase)
	if idx < len(st.ApronL) {
		weighted = phase.Combine(weighted, st.ApronL[idx])
	}
	if idx < len(st.ApronR) {
		weighted = phase.Combine(weighted, st.ApronR[idx])
	}
	if idx < len(st.Cells) {
		st.Cells[idx] = phase.Combine(st.Cells[idx], weighted)
	}
	st.Phase = phase.Combine(st.Phase, int64(st.Cursor)+1)
	st.Cursor++
}

func PrepareApron(st *phase.State, spec phase.Spec) {
	knotr.RimW(st, spec, st.WidthB)
}

// DepthBits extracts the transit depth product. laneMark is 0 on the
// uninterrupted path and non-zero on the checkpoint path for burst packs.
func DepthBits(st *phase.State, spec phase.Spec, laneMark uint8) int64 {
	terms := make([]int64, 0, st.Bins)
	half := spec.HalfW
	if half < 1 {
		half = 1
	}
	mid := st.Bins / 2
	n := st.Bins
	if n > len(st.Cells) {
		n = len(st.Cells)
	}
	for i := 0; i < n; i++ {
		d := i - mid
		if d < 0 {
			d = -d
		}
		v := st.Cells[i]
		al := int64(0)
		ar := int64(0)
		if i < len(st.ApronL) {
			al = st.ApronL[i]
		}
		if i < len(st.ApronR) {
			ar = st.ApronR[i]
		}
		if d <= half {
			v = phase.Combine(v, al)
		} else {
			v = phase.Combine(v, ar)
		}
		terms = append(terms, phase.Combine(v, st.Phase))
	}
	return zknot.MeldQ(terms, len(terms), laneMark)
}

func ResidualScore(st *phase.State) int64 {
	var acc int64
	for _, v := range st.Cells {
		if v < 0 {
			v = -v
		}
		acc ^= v & 0xffff
	}
	if acc < 0 {
		acc = -acc
	}
	return acc % 97
}
