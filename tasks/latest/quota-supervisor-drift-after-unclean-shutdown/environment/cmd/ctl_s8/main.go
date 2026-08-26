package main

import (
	"fmt"
	"os"

	"s8lab/internal"
)

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	switch os.Args[1] {
	case "recover-all":
		if err := internal.RecoverAll(); err != nil {
			fmt.Fprintf(os.Stderr, "recover-all failed: %v\n", err)
			os.Exit(1)
		}
	case "recover-one":
		if len(os.Args) < 3 {
			usage()
			os.Exit(2)
		}
		var entries []internal.RunEntry
		if err := internal.ProcessFixture(os.Args[2], &entries); err != nil {
			fmt.Fprintf(os.Stderr, "recover-one failed: %v\n", err)
			os.Exit(1)
		}
	default:
		usage()
		os.Exit(2)
	}
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage:")
	fmt.Fprintln(os.Stderr, "  ctl_s8 recover-all")
	fmt.Fprintln(os.Stderr, "  ctl_s8 recover-one <label>")
}
