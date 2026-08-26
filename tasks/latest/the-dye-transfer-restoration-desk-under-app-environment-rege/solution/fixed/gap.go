package matchmesh

import (
	"encoding/json"
	"math"
	"os"
)

const Eps = 1e-9

type Channels struct {
	Cyan    float64 `json:"cyan"`
	Magenta float64 `json:"magenta"`
	Yellow  float64 `json:"yellow"`
	Silver  float64 `json:"silver"`
}

func LoadThreshold(path string, fallback float64) float64 {
	if path == "" {
		return fallback
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return fallback
	}
	var v struct {
		Threshold float64 `json:"threshold"`
	}
	if err := json.Unmarshal(raw, &v); err != nil || v.Threshold <= 0 {
		return fallback
	}
	return v.Threshold
}

func sanitize(v float64) float64 {
	if math.IsNaN(v) || math.IsInf(v, 0) {
		return Eps
	}
	if v < Eps {
		return Eps
	}
	return v
}

func gapLog(dEnd, dMidEnd, dStart, dMidStart float64) float64 {
	numEnd := sanitize(dEnd)
	denEnd := sanitize(dMidEnd)
	numStart := sanitize(dStart)
	denStart := sanitize(dMidStart)
	return math.Log10(numEnd/denEnd) - math.Log10(numStart/denStart)
}

func ScoreSplice(endA, midA, startB, midB Channels, thr float64) (Channels, bool) {
	ends := []float64{endA.Cyan, endA.Magenta, endA.Yellow, endA.Silver}
	midsA := []float64{midA.Cyan, midA.Magenta, midA.Yellow, midA.Silver}
	starts := []float64{startB.Cyan, startB.Magenta, startB.Yellow, startB.Silver}
	midsB := []float64{midB.Cyan, midB.Magenta, midB.Yellow, midB.Silver}
	out := make([]float64, 4)
	ok := true
	for i := 0; i < 4; i++ {
		out[i] = gapLog(ends[i], midsA[i], starts[i], midsB[i])
		if math.Abs(out[i]) > thr {
			ok = false
		}
	}
	g := Channels{Cyan: out[0], Magenta: out[1], Yellow: out[2], Silver: out[3]}
	return g, ok
}
