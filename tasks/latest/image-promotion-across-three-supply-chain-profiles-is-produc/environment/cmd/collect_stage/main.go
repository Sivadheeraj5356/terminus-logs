package main

import (
	"flag"
	"fmt"
	"os"

	"kvlab/s2"
)

func main() {
	profile := flag.String("profile", "", "profile id")
	out := flag.String("out", "/app/output/kv_export.json", "export path")
	flag.Parse()
	if *profile == "" {
		fmt.Fprintf(os.Stderr, "usage: collect_stage --profile <id> [--out path]\n")
		os.Exit(2)
	}
	root := "/app/environment"
	if v := os.Getenv("KV_ROOT"); v != "" {
		root = v
	}
	if err := s2.Collect(root, *profile, *out); err != nil {
		fmt.Fprintf(os.Stderr, "collect_stage: %v\n", err)
		os.Exit(1)
	}
}
