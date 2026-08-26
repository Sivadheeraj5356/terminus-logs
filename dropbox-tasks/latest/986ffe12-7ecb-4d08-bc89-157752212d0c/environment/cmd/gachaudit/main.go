package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"gachaudit/pkg/audit"
	"gachaudit/pkg/config"
	"gachaudit/pkg/draw"
	"gachaudit/pkg/ingest"
	"gachaudit/pkg/ledger"
)

func main() {
	input := flag.String("input", "/app/data/sessions.json", "session bundle")
	cfgPath := flag.String("config", "/app/config/gacha.json", "gacha config")
	override := flag.String("override", "/app/config/live_overrides.toml", "live overrides")
	output := flag.String("output", "/app/output/report.json", "report path")
	ledgerPath := flag.String("ledger", "/app/output/pity_ledger.json", "pity ledger")
	fallback := flag.String("fallback", "/app/config/desk_fallback.json", "desk fallback when overlay missing")
	flag.Parse()

	cfg, err := config.LoadBase(*cfgPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "config: %v\n", err)
		os.Exit(2)
	}
	if _, err := os.Stat(*override); err == nil {
		if err := config.ApplyOverride(cfg, *override); err != nil {
			fmt.Fprintf(os.Stderr, "override: %v\n", err)
			os.Exit(2)
		}
	} else {
		if err := config.ApplyDeskFallback(cfg, *fallback); err != nil {
			fmt.Fprintf(os.Stderr, "fallback: %v\n", err)
			os.Exit(2)
		}
	}

	bundle, err := ingest.Load(*input)
	if err != nil {
		fmt.Fprintf(os.Stderr, "input: %v\n", err)
		os.Exit(2)
	}

	tracker := draw.NewTracker()
	entries, err := ledger.Load(*ledgerPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "ledger: %v\n", err)
		os.Exit(2)
	}
	tracker.Load(entries)

	rep := audit.Run(bundle, cfg, tracker)
	if err := os.MkdirAll("/app/output", 0o755); err != nil {
		fmt.Fprintf(os.Stderr, "mkdir: %v\n", err)
		os.Exit(2)
	}
	if err := ledger.Save(*ledgerPath, tracker.Snapshot()); err != nil {
		fmt.Fprintf(os.Stderr, "ledger save: %v\n", err)
		os.Exit(2)
	}
	raw, err := json.MarshalIndent(rep, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "marshal: %v\n", err)
		os.Exit(2)
	}
	if err := os.WriteFile(*output, append(raw, '\n'), 0o644); err != nil {
		fmt.Fprintf(os.Stderr, "write: %v\n", err)
		os.Exit(2)
	}
}
