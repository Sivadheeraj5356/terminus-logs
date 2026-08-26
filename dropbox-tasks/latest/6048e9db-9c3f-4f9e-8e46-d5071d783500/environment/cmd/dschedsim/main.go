package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"dschedsim/internal/app"
	"dschedsim/internal/io"
	"dschedsim/internal/lanes"
	"dschedsim/internal/pipeline"
)

func main() {
	cfgPath := flag.String("config", "", "profile json")
	outPath := flag.String("out", "", "audit json path")
	lanePath := flag.String("lane-out", "/app/output/scheduler_lane_state.json", "lane state json path")
	flag.Parse()
	if *cfgPath == "" || *outPath == "" {
		fmt.Fprintln(os.Stderr, "config and out are required")
		os.Exit(2)
	}
	cfg, err := app.Load(*cfgPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	envRoot := "/app/environment"
	if v := os.Getenv("DSCHEDSIM_ENV_ROOT"); v != "" {
		envRoot = v
	}
	_ = filepath.Clean(envRoot)
	rep, err := pipeline.Run(envRoot, cfg)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := (io.Writer{}).Emit(*outPath, rep); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if cfg.RunMode == "checkpoint_resume" || cfg.RunMode == "checkpoint_chain" {
		st := lanes.State{
			ConfigID:            rep.ConfigID,
			Seed:                rep.Seed,
			RunMode:             rep.RunMode,
			BoundaryTick:        rep.BoundaryTick,
			ScheduleFingerprint: rep.Summary.ScheduleFingerprint,
			PoisonAccepted:      false,
		}
		if err := lanes.WriteLaneState(*lanePath, st); err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
	}
}
