package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"s9d/internal/export"
	"s9d/internal/session"
)

type suiteDoc struct {
	Graded []string `json:"graded"`
}

func loadSuite(mapsDir string) ([]string, error) {
	raw, err := os.ReadFile(filepath.Join(mapsDir, "ladder_suite.json"))
	if err != nil {
		return nil, fmt.Errorf("missing graded suite manifest: %w", err)
	}
	var doc suiteDoc
	if err := json.Unmarshal(raw, &doc); err != nil {
		return nil, fmt.Errorf("invalid graded suite manifest: %w", err)
	}
	if len(doc.Graded) == 0 {
		return nil, fmt.Errorf("graded suite manifest is empty")
	}
	out := append([]string(nil), doc.Graded...)
	sort.Strings(out)
	return out, nil
}

func main() {
	mapsDir := flag.String("maps", "", "maps directory")
	outPath := flag.String("out", "", "output report path")
	simBin := flag.String("sim", "", "h7_sim binary path")
	flag.Parse()

	if *mapsDir == "" || *outPath == "" || *simBin == "" {
		fmt.Fprintln(os.Stderr, "usage: h7d -maps DIR -out PATH -sim BIN")
		os.Exit(2)
	}

	seeds, err := loadSuite(*mapsDir)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	rows, err := session.RunLadder(*simBin, *mapsDir, seeds)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	sort.Slice(rows, func(i, j int) bool {
		return rows[i].SeedID < rows[j].SeedID
	})
	if err := export.WriteReport(*outPath, rows); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
