package pso

import (
	"github.com/snorkel/pso/internal/config"
)

// Node represents an individual server node configuration state vector in the SRE parameter tuning cluster.
type Node struct {
	Position  []float64 // Current parameter coordinate values
	AdjustmentRate  []float64 // Current parameter adjustment step vector
	NodeBestPos  []float64 // Node local best parameter configuration found so far
	NodeBestVal  float64   // Node local best profile evaluation score
}

// InitializeCluster initializes the cluster state nodes across the parameter boundary range [-bound, bound].
func InitializeCluster(cfg *config.Config, rng *LCG) []*Node {
	cluster := make([]*Node, cfg.ClusterSize)
	for i := 0; i < cfg.ClusterSize; i++ {
		p := &Node{
			Position: make([]float64, cfg.Dimensions),
			AdjustmentRate: make([]float64, cfg.Dimensions),
			NodeBestPos: make([]float64, cfg.Dimensions),
			NodeBestVal: 0.0,
		}
		for d := 0; d < cfg.Dimensions; d++ {
			p.Position[d] = cfg.MinBound + (cfg.MaxBound-cfg.MinBound)*rng.Float64()
			p.AdjustmentRate[d] = (rng.Float64()*2.0 - 1.0) * (cfg.MaxBound - cfg.MinBound)
			p.NodeBestPos[d] = p.Position[d]
		}
		cluster[i] = p
	}
	return cluster
}
