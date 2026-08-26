package main

import (
	"flag"
	"fmt"
	"os"

	"h6env/compaction/internal/drive_h6"
)

func main() {
	dual := flag.Bool("dual", false, "run dual cred chain")
	warm := flag.Bool("warm", false, "run warm cred only using prior output")
	reset := flag.Bool("reset", false, "clear var state")
	flag.Parse()
	if *reset {
		drive_h6.ResetState()
	}
	if *warm {
		if err := drive_h6.RunWarmOnly(); err != nil {
			fmt.Fprintf(os.Stderr, "warm run failed: %v\n", err)
			os.Exit(1)
		}
		return
	}
	if *dual {
		if err := drive_h6.RunDual(); err != nil {
			fmt.Fprintf(os.Stderr, "dual run failed: %v\n", err)
			os.Exit(1)
		}
		return
	}
	fmt.Fprintln(os.Stderr, "usage: cmd_h6 --dual")
	os.Exit(2)
}
