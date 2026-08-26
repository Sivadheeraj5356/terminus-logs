package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"

	"svis/contracts"
	"svis/propagation/simulate"
)

func main() {
	bundleDir := "/app/release-graphs"
	manifestPath := bundleDir + "/workspace_manifest.json"
	outPath := "/app/build/impact_report.json"

	manifestBytes, err := os.ReadFile(manifestPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "read manifest: %v\n", err)
		os.Exit(1)
	}
	var manifest contracts.WorkspaceManifest
	if err := json.Unmarshal(manifestBytes, &manifest); err != nil {
		fmt.Fprintf(os.Stderr, "parse manifest: %v\n", err)
		os.Exit(1)
	}

	report := contracts.ImpactReport{Projects: make([]contracts.ProjectReport, 0, len(manifest.Projects))}
	for _, pid := range manifest.Projects {
		cfgPath := bundleDir + "/" + pid + ".json"
		cfgBytes, err := os.ReadFile(cfgPath)
		if err != nil {
			fmt.Fprintf(os.Stderr, "read %s: %v\n", cfgPath, err)
			os.Exit(1)
		}
		var cfg contracts.ProjectConfig
		if err := json.Unmarshal(cfgBytes, &cfg); err != nil {
			fmt.Fprintf(os.Stderr, "parse %s: %v\n", cfgPath, err)
			os.Exit(1)
		}
		if cfg.ProjectID == "" {
			cfg.ProjectID = pid
		}
		report.Projects = append(report.Projects, simulate.Simulate(cfg))
	}

	if err := os.MkdirAll("/app/build", 0o755); err != nil {
		fmt.Fprintf(os.Stderr, "mkdir: %v\n", err)
		os.Exit(1)
	}
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	enc.SetIndent("", "  ")
	if err := enc.Encode(report); err != nil {
		fmt.Fprintf(os.Stderr, "marshal: %v\n", err)
		os.Exit(1)
	}
	if err := os.WriteFile(outPath, buf.Bytes(), 0o644); err != nil {
		fmt.Fprintf(os.Stderr, "write: %v\n", err)
		os.Exit(1)
	}
}
