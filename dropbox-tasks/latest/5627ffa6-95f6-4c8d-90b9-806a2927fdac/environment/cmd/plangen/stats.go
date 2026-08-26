package main

import (
	"flag"
	"fmt"
	"os"

	"plangen/arrange"
	"plangen/internal/io"
	"plangen/spread"
	"plangen/tabulate"
)

// runStats writes a descriptive trace of a bundle to standard error. Nothing it
// reports takes part in fitting, measuring, or choosing.
func runStats(args []string) int {
	fs := flag.NewFlagSet("stats", flag.ContinueOnError)
	input := fs.String("input", "", "path to the bundle document")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	if *input == "" {
		fmt.Fprintln(os.Stderr, "stats requires --input")
		return 2
	}
	b, err := io.Load(*input)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	cov := tabulate.Coverage(b.Fit, b.Unit, b.Cells)
	lo, hi, mean := spread.Window(b.Fit)
	counts := arrange.Summarize(b.Rungs)
	fmt.Fprintf(os.Stderr, "cells populated: %d\n", cov)
	fmt.Fprintf(os.Stderr, "fit raw window: min=%d max=%d mean=%d\n", lo, hi, mean)
	fmt.Fprintf(os.Stderr, "rung row counts: %v\n", counts)
	return 0
}
