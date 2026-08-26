package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strconv"

	"fleet/go/pkg/m7"
)

func main() {
	units := flag.String("units", "", "units dir")
	scenarios := flag.String("scenarios", "", "scenarios dir")
	out := flag.String("out", "", "trace json")
	seedStr := flag.String("seed", "23", "seed")
	flag.Parse()
	seed, _ := strconv.Atoi(*seedStr)
	trace, err := m7.Simulate(*units, *scenarios, seed)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	raw, _ := json.MarshalIndent(trace, "", "  ")
	if err := os.WriteFile(*out, raw, 0o644); err != nil {
		os.Exit(1)
	}
}
