package engine

import (
	"math"

	"lab.local/salt_pond/pkg/pond"
	"lab.local/salt_pond/pkg/surveyfold"
)

func finalizeSurvey(
	arms []pond.Arm,
	state map[string]*ArmRow,
	surveys map[string]map[int][2]float64,
	layer string,
) (int, int) {
	mismatch := 0
	frontSum := 0
	for _, a := range arms {
		st := state[a.ArmKey]
		var rake, lidar float64
		if m, ok := surveys[a.ArmKey]; ok && len(m) > 0 {
			maxDay := 0
			for d := range m {
				if d > maxDay {
					maxDay = d
				}
			}
			rake, lidar = m[maxDay][0], m[maxDay][1]
		} else {
			rake, lidar = st.FrontM, st.FrontM
		}
		surveyM := surveyfold.OpA(rake, lidar, layer)
		st.SurveyM = surveyM
		if math.Abs(st.FrontM-surveyM) > 0.25 {
			mismatch++
		}
		frontSum += int(math.Round(st.FrontM * 10))
	}
	return mismatch, frontSum
}
