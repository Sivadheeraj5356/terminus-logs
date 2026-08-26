package main

import (
	"fmt"
	"os"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: app <command> [args]")
		os.Exit(1)
	}
	if err := run(os.Args[1:]); err != nil {
		msg := err.Error()
		if msg != "" {
			fmt.Fprintln(os.Stderr, msg)
		}
		os.Exit(1)
	}
}
