package main

import (
	"fmt"
	"os"
	"path/filepath"

	"thermalcal/internal/api"
)

func main() {
	projectRoot, err := os.Getwd()
	if err != nil {
		fmt.Fprintf(os.Stderr, "cwd: %v\n", err)
		os.Exit(1)
	}
	inputDir := filepath.Join(projectRoot, "input_data")
	outputDir := filepath.Join(projectRoot, "output_data")
	if len(os.Args) == 3 {
		inputDir = os.Args[1]
		outputDir = os.Args[2]
	} else if len(os.Args) != 1 {
		fmt.Fprintf(os.Stderr, "usage: thermalcal [<input_dir> <output_dir>]\n")
		os.Exit(2)
	}
	if err := api.Run(api.Options{
		ProjectRoot: projectRoot,
		InputDir:    inputDir,
		OutputDir:   outputDir,
	}); err != nil {
		fmt.Fprintf(os.Stderr, "run: %v\n", err)
		os.Exit(1)
	}
}
