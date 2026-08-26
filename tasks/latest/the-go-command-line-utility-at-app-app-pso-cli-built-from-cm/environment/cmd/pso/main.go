package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"github.com/snorkel/pso/internal/config"
	"github.com/snorkel/pso/internal/pso"
)

func main() {
	configPath := flag.String("config", "", "Path to the configuration JSON file")
	outputPath := flag.String("output", "", "Path to the output JSON file")
	flag.Parse()

	if *configPath == "" || *outputPath == "" {
		fmt.Fprintf(os.Stderr, "Usage: %s -config <path> -output <path>\n", os.Args[0])
		os.Exit(1)
	}

	cfg, err := config.LoadConfig(*configPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to load config: %v\n", err)
		os.Exit(1)
	}

	objFunc := pso.GetFunction(cfg.Function)
	result := pso.Optimize(cfg, objFunc)

	outData, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to marshal output: %v\n", err)
		os.Exit(1)
	}

	if err := os.WriteFile(*outputPath, outData, 0644); err != nil {
		fmt.Fprintf(os.Stderr, "Failed to write output file: %v\n", err)
		os.Exit(1)
	}
}
