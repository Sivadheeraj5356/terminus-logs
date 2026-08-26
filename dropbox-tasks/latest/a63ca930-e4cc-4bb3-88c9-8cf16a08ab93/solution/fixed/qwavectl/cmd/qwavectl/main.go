package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"qstatebench/circexec/engine"
)

type roster struct {
	Circuits []string `json:"circuits"`
}

// pruneBuildStaging removes stale build artifacts but keeps the qwavectl binary.
func pruneBuildStaging(dir string) error {
	entries, err := os.ReadDir(dir)
	if err != nil {
		if os.IsNotExist(err) {
			return os.MkdirAll(dir, 0o755)
		}
		return err
	}
	for _, ent := range entries {
		name := ent.Name()
		if name == "qwavectl" {
			continue
		}
		if err := os.RemoveAll(filepath.Join(dir, name)); err != nil {
			return err
		}
	}
	return nil
}

func main() {
	corpusDir := "/app/wavefn_corpus"
	rosterPath := "/app/wavefn_corpus/roster.json"
	outPath := "/app/build/statevec_benchmark_report.json"

	raw, err := os.ReadFile(rosterPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "read roster: %v\n", err)
		os.Exit(1)
	}
	var ros roster
	if err := json.Unmarshal(raw, &ros); err != nil {
		fmt.Fprintf(os.Stderr, "parse roster: %v\n", err)
		os.Exit(1)
	}

	report := engine.Report{Circuits: make([]engine.CircuitOut, 0, len(ros.Circuits))}
	for _, id := range ros.Circuits {
		path := corpusDir + "/" + id + ".json"
		sc, err := engine.LoadCircuit(path)
		if err != nil {
			fmt.Fprintf(os.Stderr, "load %s: %v\n", path, err)
			os.Exit(1)
		}
		report.Circuits = append(report.Circuits, engine.Simulate(sc))
	}

	if err := os.MkdirAll("/app/build", 0o755); err != nil {
		fmt.Fprintf(os.Stderr, "mkdir: %v\n", err)
		os.Exit(1)
	}
	if err := pruneBuildStaging("/app/build"); err != nil {
		fmt.Fprintf(os.Stderr, "prune: %v\n", err)
		os.Exit(1)
	}
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(report); err != nil {
		fmt.Fprintf(os.Stderr, "marshal: %v\n", err)
		os.Exit(1)
	}
	if err := os.WriteFile(outPath, buf.Bytes(), 0o644); err != nil {
		fmt.Fprintf(os.Stderr, "write: %v\n", err)
		os.Exit(1)
	}
}
