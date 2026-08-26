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

func gapLog(dEnd, dStart float64) float64 {
	return math.Abs(dEnd - dStart)
}

func ScoreSplice(endA, midA, startB, midB Channels, thr float64) (Channels, bool) {
	g := Channels{
		Cyan:    gapLog(endA.Cyan, startB.Cyan),
		Magenta: gapLog(endA.Magenta, startB.Magenta),
		Yellow:  gapLog(endA.Yellow, startB.Yellow),
		Silver:  gapLog(endA.Silver, startB.Silver),
	}
	ok := math.Abs(g.Cyan) <= thr &&
		math.Abs(g.Magenta) <= thr &&
		math.Abs(g.Yellow) <= thr &&
		math.Abs(g.Silver) <= thr
	return g, ok
}
