package knotr

import "desk/phase"

const archivalW uint8 = 1

// RimW fills neighbor correction rings before the in-transit reduction.
func RimW(st *phase.State, spec phase.Spec, widthB uint8) {
	w := widthB
	if st.ResumePass > 0 {
		w = archivalW
	}
	bins := spec.Bins
	n := bins
	if n > len(st.Cells) {
		n = len(st.Cells)
	}
	if n < 1 {
		return
	}
	for i := 0; i < n; i++ {
		baseL := st.Cells[(i+n-1)%n]
		baseR := st.Cells[(i+1)%n]
		if w >= 2 && n >= 2 {
			baseL = phase.Combine(baseL, st.Cells[(i+n-2)%n])
			baseR = phase.Combine(baseR, st.Cells[(i+2)%n])
		}
		if i < len(st.ApronL) {
			st.ApronL[i] = baseL
		}
		if i < len(st.ApronR) {
			st.ApronR[i] = baseR
		}
	}
}
