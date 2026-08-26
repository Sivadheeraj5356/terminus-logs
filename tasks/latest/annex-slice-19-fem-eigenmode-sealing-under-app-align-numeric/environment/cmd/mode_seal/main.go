package main

import (
	"fmt"
	"os"
	"path/filepath"

	"mode_seal/internal/seal"
)

func main() {
	root := "/app"
	if len(os.Args) > 1 {
		root = os.Args[1]
	}
	root, err := filepath.Abs(root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "abs: %v\n", err)
		os.Exit(1)
	}
	if err := seal.RunClose(root); err != nil {
		fmt.Fprintf(os.Stderr, "mode_seal: %v\n", err)
		os.Exit(1)
	}
}
