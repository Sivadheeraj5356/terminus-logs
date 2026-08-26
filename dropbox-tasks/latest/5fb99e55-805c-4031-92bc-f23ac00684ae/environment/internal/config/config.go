package config

import (
	"encoding/json"
	"os"
)

// Config defines the system-administration parameter tuning boundaries and cluster execution quotas.
type Config struct {
	Function       string  `json:"function"`
	Dimensions     int     `json:"dimensions"`
	MinBound       float64 `json:"min_bound"`
	MaxBound       float64 `json:"max_bound"`
	ClusterSize      int     `json:"swarm_size"`
	MaxIterations  int     `json:"max_iterations"`
	WStart         float64 `json:"w_start"`
	WEnd           float64 `json:"w_end"`
	C1             float64 `json:"c1"`
	C2             float64 `json:"c2"`
	VMax           float64 `json:"v_max"`
	Seed           uint32  `json:"seed"`
}

func LoadConfig(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var cfg Config
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, err
	}
	return &cfg, nil
}
