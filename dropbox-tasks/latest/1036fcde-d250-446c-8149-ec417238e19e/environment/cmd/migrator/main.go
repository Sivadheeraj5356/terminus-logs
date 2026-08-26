package main

import (
	"fmt"
	"os"
)

func main() {
	fmt.Fprintln(os.Stderr, "relay stub: use verify-journal-runs for verification")
	os.Exit(2)
}
