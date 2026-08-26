package main

import (
	"fmt"
	"os"

	"backuptrust/orchestrate"
)

func main() {
	if err := orchestrate.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "ebta: %v\n", err)
		os.Exit(1)
	}
}
