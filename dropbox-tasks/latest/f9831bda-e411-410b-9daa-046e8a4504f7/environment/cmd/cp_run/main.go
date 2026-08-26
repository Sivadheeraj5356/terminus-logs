package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"conformal-coverage-witness-pack/pkg/h2"
)

func main() {
	out := flag.String("out", "/app/output/cp_witness.json", "output path")
	flag.Parse()
	root := "/app/environment"
	wit, err := h2.BuildWitness(root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "build: %v\n", err)
		os.Exit(2)
	}
	if err := os.MkdirAll(filepath.Dir(*out), 0755); err != nil {
		fmt.Fprintf(os.Stderr, "mkdir: %v\n", err)
		os.Exit(2)
	}
	raw, _ := json.MarshalIndent(wit, "", "  ")
	if err := os.WriteFile(*out, raw, 0644); err != nil {
		fmt.Fprintf(os.Stderr, "write: %v\n", err)
		os.Exit(2)
	}
	traceDir := "/app/output/mode_traces"
	_ = os.MkdirAll(traceDir, 0755)
	for _, cycle := range wit.Cycles {
		tpath := filepath.Join(traceDir, cycle.ProfileID+"_"+cycle.PassMode+".json")
		tr, _ := json.MarshalIndent(cycle, "", "  ")
		_ = os.WriteFile(tpath, tr, 0644)
	}
}
