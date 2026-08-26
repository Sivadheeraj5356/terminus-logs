package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"featrecon/cargograph"
)

type manifest struct {
	Scenarios []string `json:"scenarios"`
}

func main() {
	dataDir := "/app/crate-captures"
	manifestPath := filepath.Join(dataDir, "manifest.json")
	outPath := "/app/build/feature_resolution_report.json"

	raw, err := os.ReadFile(manifestPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "read manifest: %v\n", err)
		os.Exit(1)
	}
	var man manifest
	if err := json.Unmarshal(raw, &man); err != nil {
		fmt.Fprintf(os.Stderr, "parse manifest: %v\n", err)
		os.Exit(1)
	}

	digest, err := cargograph.CaptureDigest(man.Scenarios)
	if err != nil {
		fmt.Fprintf(os.Stderr, "digest: %v\n", err)
		os.Exit(1)
	}
	chainTail, err := cargograph.CaptureChainTail(man.Scenarios, digest)
	if err != nil {
		fmt.Fprintf(os.Stderr, "chain tail: %v\n", err)
		os.Exit(1)
	}
	manifestLen, err := cargograph.ManifestPayloadLen()
	if err != nil {
		fmt.Fprintf(os.Stderr, "manifest len: %v\n", err)
		os.Exit(1)
	}
	bundledLen, err := cargograph.BundledPayloadLen(man.Scenarios)
	if err != nil {
		fmt.Fprintf(os.Stderr, "bundled len: %v\n", err)
		os.Exit(1)
	}

	report := cargograph.Report{
		FormatVersion:        3,
		CaptureDigest:        digest,
		CaptureChainTail:     chainTail,
		ManifestPayloadLen:   manifestLen,
		ManifestPayloadLenLE: cargograph.ManifestPayloadLenLE(manifestLen),
		BundledPayloadLen:    bundledLen,
		BundledPayloadLenLE:  cargograph.BundledPayloadLenLE(bundledLen),
		Scenarios:            make([]cargograph.ScenarioOut, 0, len(man.Scenarios)),
	}

	for _, sid := range man.Scenarios {
		scPath := filepath.Join(dataDir, sid+".json")
		scRaw, err := os.ReadFile(scPath)
		if err != nil {
			fmt.Fprintf(os.Stderr, "read %s: %v\n", sid, err)
			os.Exit(1)
		}
		var sc cargograph.Scenario
		if err := json.Unmarshal(scRaw, &sc); err != nil {
			fmt.Fprintf(os.Stderr, "parse %s: %v\n", sid, err)
			os.Exit(1)
		}
		sc.ScenarioID = sid
		report.Scenarios = append(report.Scenarios, cargograph.Analyze(sc))
	}

	encoded, err := json.Marshal(report)
	if err != nil {
		fmt.Fprintf(os.Stderr, "encode: %v\n", err)
		os.Exit(1)
	}
	encoded = append(encoded, '\n')
	if err := os.WriteFile(outPath, encoded, 0o644); err != nil {
		fmt.Fprintf(os.Stderr, "write: %v\n", err)
		os.Exit(1)
	}
}
