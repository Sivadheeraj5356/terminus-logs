package main

// spoold service supervisor entry point (build r3)

import (
	"fmt"
	"os"

	"spoold/internal/sp"
)

func main() {
	if err := sp.Run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
