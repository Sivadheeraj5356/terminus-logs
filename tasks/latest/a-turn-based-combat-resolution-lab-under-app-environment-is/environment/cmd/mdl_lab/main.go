package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"mdllab/internal/fold"
	"mdllab/internal/pulse"
	"mdllab/internal/replay"
)

var manifests = []string{"sc_m1", "sc_m2", "sc_m3", "sc_m4", "sc_m5"}

func main() {
	full := flag.Bool("full-matrix", false, "run graded matrix")
	depth := flag.Int("depth", 5, "combo depth")
	out := flag.String("out", "", "output path")
	flag.Parse()
	if !*full || *out == "" {
		fmt.Fprintln(os.Stderr, "usage: mdl_lab --full-matrix --depth 5 --out /app/output/cmb_out.json")
		os.Exit(2)
	}
	code := runFullMatrix(*out, *depth)
	os.Exit(code)
}

func runFullMatrix(outPath string, depth int) int {
	coef, err := replay.LoadCoef()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	sweep, err := replay.LoadScenario(filepath.Join(replay.EnvRoot, "scenarios", "sweep_m0.json"))
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}

	runs := make([]fold.RunRow, 0, len(manifests)*2)
	profiles := []pulse.TickProfile{pulse.ProfileStrict, pulse.ProfileLoose}
	for _, codename := range manifests {
		spec, err := replay.LoadScenario(filepath.Join(replay.EnvRoot, "scenarios", codename+".json"))
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			return 2
		}
		depthLimit := depth
		if !(spec.Combo || sweep.Combo) && depthLimit > 3 {
			depthLimit = 3
		}
		for _, profile := range profiles {
			row, err := replay.RunManifest(spec, profile, depthLimit, coef)
			if err != nil {
				fmt.Fprintln(os.Stderr, err)
				return 2
			}
			row["depth_limit"] = depthLimit
			runs = append(runs, fold.RunRow(row))
		}
	}

	matrix, err := fold.FoldMatrix(runs)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	if err := fold.CheckBands(matrix); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	payload, err := json.MarshalIndent(matrix, "", "  ")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	payload = append(payload, '\n')
	if err := os.WriteFile(outPath, payload, 0o644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	if !fold.MatrixClean(matrix) {
		return 2
	}
	return 0
}
