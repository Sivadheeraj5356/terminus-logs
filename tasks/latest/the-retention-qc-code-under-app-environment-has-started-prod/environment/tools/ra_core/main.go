package main

import (
	"errors"
	"flag"
	"fmt"
	"math"
	"os"

	"ra.local/field/internal/report"
)

func main() {
	var output string
	var root string
	var holdout string
	var coverage float64
	flag.StringVar(&output, "emit-attestation", "", "write a JSON attestation")
	flag.StringVar(&root, "input-root", "/app/environment/data/cell_bin", "read CELL/3 files recursively")
	flag.StringVar(&holdout, "holdout", "", "emit only the named held-out run")
	flag.Float64Var(&coverage, "coverage", 0.9, "finite-sample coverage target")
	flag.Parse()
	if output == "" || flag.NArg() != 0 || math.IsNaN(coverage) ||
		math.IsInf(coverage, 0) || coverage <= 0 || coverage >= 1 {
		fail(errors.New(
			"usage: ra_run --emit-attestation OUTPUT [--input-root ROOT] [--holdout RUN] [--coverage TARGET]",
		))
	}
	doc, err := report.Build(root, holdout, coverage)
	if err != nil {
		fail(err)
	}
	if err := report.Write(output, doc); err != nil {
		fail(err)
	}
}

func fail(err error) {
	fmt.Fprintln(os.Stderr, "ra_run:", err)
	os.Exit(2)
}
