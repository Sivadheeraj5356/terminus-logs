package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	h2 "conformal-coverage-witness-pack/pkg/h2"
)

func main() {
	out := flag.String("out", "/app/output/cp_witness.json", "output path")
	fullCycle := flag.Bool("coverage-audit", false, "full cycle check")
	health := flag.Bool("health", false, "health probe")
	flag.Parse()

	if *health {
		fmt.Println("health: interim rows available")
		os.Exit(0)
	}

	root := "/app/environment"
	if *fullCycle {
		raw, err := os.ReadFile(*out)
		if err != nil {
			fmt.Fprintf(os.Stderr, "read witness: %v\n", err)
			os.Exit(2)
		}
		var wit h2.Witness
		if err := json.Unmarshal(raw, &wit); err != nil {
			fmt.Fprintf(os.Stderr, "parse witness: %v\n", err)
			os.Exit(2)
		}
		if len(wit.Cycles) < 16 {
			fmt.Fprintf(os.Stderr, "cycles too small\n")
			os.Exit(1)
		}
		if wit.Summary.MatrixStatus != "settled" || wit.Summary.CarrySpan != 0 {
			fmt.Fprintf(os.Stderr, "summary not settled\n")
			os.Exit(1)
		}
		for _, cycle := range wit.Cycles {
			if cycle.ProfileID == "" || len(cycle.Rows) == 0 {
				fmt.Fprintf(os.Stderr, "incomplete cycle\n")
				os.Exit(1)
			}
			if cycle.CarrySpan != 0 {
				os.Exit(1)
			}
		}
		os.Exit(0)
	}

	built, err := h2.BuildWitness(root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "build: %v\n", err)
		os.Exit(2)
	}
	if err := h2.WriteWitness(*out, built); err != nil {
		fmt.Fprintf(os.Stderr, "write: %v\n", err)
		os.Exit(2)
	}
}
