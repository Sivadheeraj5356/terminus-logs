// Command plangen fits calibration families on a fit fold and plans, for each
// shift rung, a family choice that keeps the calibration gap under bound.
package main

import (
	"fmt"
	"os"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: plangen <plan|stats> --input <bundle.json> [--out <plan.json>]")
		os.Exit(2)
	}
	switch os.Args[1] {
	case "plan":
		os.Exit(runPlan(os.Args[2:]))
	case "stats":
		os.Exit(runStats(os.Args[2:]))
	default:
		fmt.Fprintf(os.Stderr, "unknown subcommand %q\n", os.Args[1])
		os.Exit(2)
	}
}
