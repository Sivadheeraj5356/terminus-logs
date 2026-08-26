package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"lootfair/faircore"
)

type catalog struct {
	Sessions []string `json:"sessions"`
}

func main() {
	vaultDir := "/app/dropvault"
	catalogPath := filepath.Join(vaultDir, "catalog.json")
	outPath := "/app/out/fairness_report.json"

	raw, err := os.ReadFile(catalogPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "read catalog: %v\n", err)
		os.Exit(1)
	}
	var cat catalog
	if err := json.Unmarshal(raw, &cat); err != nil {
		fmt.Fprintf(os.Stderr, "parse catalog: %v\n", err)
		os.Exit(1)
	}

	report := faircore.Report{Sessions: make([]faircore.SessionOut, 0, len(cat.Sessions))}
	for _, id := range cat.Sessions {
		path := filepath.Join(vaultDir, id+".json")
		session, err := faircore.LoadSession(path)
		if err != nil {
			fmt.Fprintf(os.Stderr, "load %s: %v\n", path, err)
			os.Exit(1)
		}
		report.Sessions = append(report.Sessions, faircore.AnalyzeSession(session))
	}

	if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
		fmt.Fprintf(os.Stderr, "mkdir: %v\n", err)
		os.Exit(1)
	}
	if err := faircore.WriteReport(outPath, report); err != nil {
		fmt.Fprintf(os.Stderr, "write: %v\n", err)
		os.Exit(1)
	}
}
