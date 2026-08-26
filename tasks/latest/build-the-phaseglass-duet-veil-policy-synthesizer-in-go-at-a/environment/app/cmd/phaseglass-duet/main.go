package main

import (
	"flag"
	"fmt"
	"os"
)

func main() {
	board := flag.String("board", "", "path to a Phaseglass board JSON file")
	output := flag.String("output", "", "path for the policy JSON file")
	flag.Parse()
	if *board == "" || *output == "" {
		fmt.Fprintln(os.Stderr, "invalid board: --board and --output are required")
		os.Exit(2)
	}
	fmt.Fprintln(os.Stderr, "phaseglass veil policy synthesizer is not implemented")
	os.Exit(1)
}
