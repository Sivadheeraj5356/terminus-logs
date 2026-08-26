package main

import (
	"flag"
	"fmt"
	"os"

	"plangen/arrange"
	"plangen/internal/io"
	"plangen/trail"
)

// runPlan reads a bundle, seals the fit fold, settles on a family per rung, and
// hands the result to the emitter.
func runPlan(args []string) int {
	fs := flag.NewFlagSet("plan", flag.ContinueOnError)
	input := fs.String("input", "", "path to the bundle document")
	out := fs.String("out", "", "path to write the plan document")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	if *input == "" || *out == "" {
		fmt.Fprintln(os.Stderr, "plan requires --input and --out")
		return 2
	}
	b, err := io.Load(*input)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	bk, digest, floor, err := prepare(b, *out)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	picks, ok := arrange.Route(bk, b.Rungs, b.Unit, b.Bins, digest, floor, b.Rim)
	if !ok {
		_ = trail.Abort(*out)
		if derr := emit(*out, bk, b.Rungs, nil, b.Unit, b.Bins, digest, b.Hold); derr != nil {
			fmt.Fprintln(os.Stderr, derr)
		}
		return 1
	}
	for i, p := range picks {
		if err := trail.Mark(*out, digest, b.Rungs[i].Severity, p); err != nil {
			fmt.Fprintln(os.Stderr, err)
			return 1
		}
	}
	if err := emit(*out, bk, b.Rungs, picks, b.Unit, b.Bins, digest, b.Hold); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	_ = trail.Close(*out)
	return 0
}
