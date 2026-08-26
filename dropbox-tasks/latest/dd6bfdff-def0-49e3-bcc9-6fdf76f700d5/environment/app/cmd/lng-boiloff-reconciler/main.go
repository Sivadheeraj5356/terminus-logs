package main

import (
	"fmt"
	"os"

	"boiloff-reconciler/internal/boiloff"
)

func main() {
	if err := boiloff.Run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
