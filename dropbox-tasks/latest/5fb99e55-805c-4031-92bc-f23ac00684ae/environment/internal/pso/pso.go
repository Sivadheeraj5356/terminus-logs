package pso

import (
	"math"

	"github.com/snorkel/pso/internal/config"
)

// HistoryEntry records a single strictly improving iteration step during SRE cluster parameter tuning.
type HistoryEntry struct {
	Iteration int     `json:"iteration"`
	BestValue float64 `json:"best_value"`
}

// OutputData defines the final JSON report structure for SRE cluster quota configuration.
type OutputData struct {
	BestPosition []float64      `json:"best_position"`
	BestValue    float64        `json:"best_value"`
	History      []HistoryEntry `json:"history"`
}

func copySlice(s []float64) []float64 {
	c := make([]float64, len(s))
	copy(c, s)
	return c
}

// Optimize executes the SRE system-administration cluster tuning routine against the target objective profile.
func Optimize(cfg *config.Config, objFunc ObjectiveFunction) *OutputData {
	rng := NewLCG(cfg.Seed)
	cluster := InitializeCluster(cfg, rng)

	var clusterBestPos []float64
	clusterBestVal := math.Inf(1)

	for _, p := range cluster {
		val := objFunc(p.Position)
		p.NodeBestVal = val
		p.NodeBestPos = copySlice(p.Position)

		if val <= clusterBestVal {
			clusterBestVal = val
			clusterBestPos = copySlice(p.Position)
		}
	}

	history := []HistoryEntry{}
	prevClusterBestVal := clusterBestVal

	for t := 0; t < cfg.MaxIterations; t++ {
		denom := float64(cfg.MaxIterations)
		if denom <= 0 {
			denom = 1.0
		}
		w := cfg.WStart - (cfg.WStart-cfg.WEnd)*(float64(t)/denom)

		for _, p := range cluster {
			r1 := rng.Float64()
			r2 := rng.Float64()

			for d := 0; d < cfg.Dimensions; d++ {
				vel := w*p.AdjustmentRate[d] +
					cfg.C1*r1*(p.NodeBestPos[d]-p.Position[d]) +
					cfg.C2*r2*(clusterBestPos[d]-p.Position[d])

				p.AdjustmentRate[d] = vel
				p.Position[d] += p.AdjustmentRate[d]

				if p.Position[d] > cfg.MaxBound {
					p.Position[d] = cfg.MaxBound
				} else if p.Position[d] < cfg.MinBound {
					p.Position[d] = cfg.MinBound
				}
			}
		}

		for _, p := range cluster {
			val := objFunc(p.Position)

			if val < p.NodeBestVal {
				p.NodeBestVal = val
				p.NodeBestPos = copySlice(p.Position)
			}

			if val < clusterBestVal {
				clusterBestVal = val
				clusterBestPos = copySlice(p.Position)
			}
		}

		roundedVal := math.Round(clusterBestVal*1e6) / 1e6
		history = append(history, HistoryEntry{
			Iteration: t,
			BestValue: roundedVal,
		})
		prevClusterBestVal = clusterBestVal
		_ = prevClusterBestVal
	}

	return &OutputData{
		BestPosition: clusterBestPos,
		BestValue:    math.Round(clusterBestVal*1e6) / 1e6,
		History:      history,
	}
}
