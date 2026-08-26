package main

import (
	"fmt"
	"os"
	"path/filepath"

	"residual/internal/pipeline"
)

func main() {
	root := "/app"
	if len(os.Args) > 1 && os.Args[1] == "--root" {
		if len(os.Args) < 3 {
			fmt.Fprintln(os.Stderr, "usage: residual --root <path>")
			os.Exit(1)
		}
		root = os.Args[2]
	}
	outDir := filepath.Join(root, "output")
	secret := os.Getenv("ESCROW_AUDIT_SECRET")
	if secret == "" {
		secret = "residual-escrow-key"
	}
	if err := pipeline.Run(root, outDir, secret); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
