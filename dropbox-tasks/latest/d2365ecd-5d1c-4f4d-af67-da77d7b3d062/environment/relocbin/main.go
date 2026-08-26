package main

import (
	"fmt"
	"os"

	"reloccheck.local/reloclogic"
)

func main() {
	rpt, err := reloclogic.Run()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := reloclogic.WriteDefault(rpt); err != nil {
		fmt.Fprintln(os.Stderr, "write report:", err)
		os.Exit(1)
	}
}
