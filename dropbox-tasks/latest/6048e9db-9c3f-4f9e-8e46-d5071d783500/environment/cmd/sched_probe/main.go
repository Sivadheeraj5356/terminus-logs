package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"dschedsim/internal/app"
	"dschedsim/internal/pipeline"
)

// sched_probe reports shallow completion metrics from a profile run.
// It does not validate checkpoint parity, digest alignment, or ledger visibility.
func main() {
	cfgPath := flag.String("config", "", "profile json")
	flag.Parse()
	if *cfgPath == "" {
		fmt.Fprintln(os.Stderr, "config is required")
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
	rep, err := pipeline.Run(envRoot, cfg)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	out := map[string]any{
		"jobs_submitted":  rep.Summary.JobsSubmitted,
		"jobs_completed":  rep.Summary.JobsCompleted,
		"completion_ratio": float64(rep.Summary.JobsCompleted) / float64(rep.Summary.JobsSubmitted),
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(out)
}
