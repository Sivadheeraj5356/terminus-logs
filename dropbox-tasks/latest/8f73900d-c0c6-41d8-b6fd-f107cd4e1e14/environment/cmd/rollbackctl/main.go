package main

import (
	"fmt"
	"os"
)

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	switch os.Args[1] {
	case "inspect":
		if err := runInspect(); err != nil {
			fmt.Fprintf(os.Stderr, "inspect: %v\n", err)
			os.Exit(1)
		}
	case "validate":
		if err := runValidate(os.Args[2:]); err != nil {
			fmt.Fprintf(os.Stderr, "validate: %v\n", err)
			os.Exit(1)
		}
	case "plan", "emit":
		if err := runPlan(os.Args[2:]); err != nil {
			fmt.Fprintf(os.Stderr, "plan: %v\n", err)
			os.Exit(1)
		}
	default:
		usage()
		os.Exit(2)
	}
}

func usage() {
	fmt.Fprintf(os.Stderr, "usage: rollbackctl inspect|validate [--graph <path>]|plan|emit [--out <path>]\n")
}
