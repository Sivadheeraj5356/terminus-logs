package main

import (
	"fmt"
	"os"

	"siggate/internal/cli"
)

func main() {
	if err := cli.Run(os.Args[1:]); err != nil {
		if e, ok := err.(*cli.ExitError); ok {
			fmt.Fprint(os.Stderr, e.Message)
			os.Exit(e.Code)
		}
		fmt.Fprintf(os.Stderr, "error: io\n")
		os.Exit(2)
	}
}
