package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"balance_lab/p7_load"
	"balance_lab/p7_pipe"
)

func main() {
	scenario := flag.String("scenario", "", "scenario name")
	out := flag.String("out", "", "output archive path")
	flag.Parse()
	if *scenario == "" || *out == "" {
		fmt.Fprintln(os.Stderr, "scenario and out required")
		os.Exit(2)
	}
	envRoot := "/app/environment"
	manifest := filepath.Join(envRoot, "data", "scenarios", *scenario+".json")
	scen, err := p7_load.ReadScenario(manifest)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	drv := &p7_pipe.Driver{EnvRoot: envRoot}
	if err := drv.Run(scen, *out); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
