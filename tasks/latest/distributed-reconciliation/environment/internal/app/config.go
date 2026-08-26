package app

import (
	"encoding/json"
	"os"
)

type Flags struct {
	StrictDeps     bool `json:"strict_deps"`
	PartitionTrace bool `json:"partition_trace"`
}

type Config struct {
	ConfigID       string `json:"config_id"`
	Seed           int64  `json:"seed"`
	Profile        string `json:"profile"`
	GraphID        string `json:"graph_id"`
	TickHorizon    int    `json:"tick_horizon"`
	NodeCount      int    `json:"node_count"`
	PartitionCount int    `json:"partition_count"`
	RunMode        string `json:"run_mode"`
	BoundaryTick   int    `json:"boundary_tick"`
	BoundaryTicks  []int  `json:"boundary_ticks"`
	Flags          Flags  `json:"flags"`
}

func Load(path string) (Config, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return Config{}, err
	}
	var cfg Config
	if err := json.Unmarshal(raw, &cfg); err != nil {
		return Config{}, err
	}
	if cfg.NodeCount < 1 {
		cfg.NodeCount = 1
	}
	if cfg.PartitionCount < 1 {
		cfg.PartitionCount = 4
	}
	if cfg.TickHorizon < 1 {
		cfg.TickHorizon = 40
	}
	if cfg.RunMode == "" {
		cfg.RunMode = "steady"
	}
	if cfg.BoundaryTick < 1 {
		cfg.BoundaryTick = cfg.TickHorizon / 3
		if cfg.BoundaryTick < 1 {
			cfg.BoundaryTick = 1
		}
	}
	if len(cfg.BoundaryTicks) == 0 && cfg.RunMode == "checkpoint_chain" {
		cfg.BoundaryTicks = []int{cfg.BoundaryTick}
	}
	return cfg, nil
}
