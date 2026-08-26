package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"kvlab/internal/pullgate"
)

func main() {
	profile := flag.String("profile", "", "profile id")
	step := flag.Int("step", 0, "timeline step index")
	flag.Parse()
	if *profile == "" {
		fmt.Fprintf(os.Stderr, "usage: pull_gate --profile <id> [--step N]\n")
		os.Exit(2)
	}
	root := "/app/environment"
	if v := os.Getenv("KV_ROOT"); v != "" {
		root = v
	}
	res, err := pullgate.Run(root, *profile, *step)
	if err != nil {
		fmt.Fprintf(os.Stderr, "pull_gate: %v\n", err)
		os.Exit(1)
	}
	_ = json.NewEncoder(os.Stdout).Encode(res)
}
