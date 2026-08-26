package main

import (
	"fmt"
	"os"
	"path/filepath"

	"ot7/internal/driver"
	"ot7/internal/paths"
)

func main() {
	reset := false
	for _, a := range os.Args[1:] {
		if a == "--reset" {
			reset = true
		}
	}
	manifest := filepath.Join(paths.Data, "manifest.toml")
	if v := os.Getenv("MASS_MANIFEST"); v != "" {
		manifest = v
	}
	instDir := filepath.Join(paths.Data, "instances")
	if v := os.Getenv("MASS_INSTANCE_DIR"); v != "" {
		instDir = v
	}
	r := driver.Runner{InstanceDir: instDir, Reset: reset}
	if _, err := r.Execute(manifest); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
