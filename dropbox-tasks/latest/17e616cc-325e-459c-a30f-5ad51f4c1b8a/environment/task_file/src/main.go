package main

import (
	"fmt"
	"os"
)

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: closure-plan CASE_ROOT OUTDIR")
		os.Exit(2)
	}
	fmt.Fprintln(os.Stderr, "closure planner is not implemented yet")
	os.Exit(1)
}
