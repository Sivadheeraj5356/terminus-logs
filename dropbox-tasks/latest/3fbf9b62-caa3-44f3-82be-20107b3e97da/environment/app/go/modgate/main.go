package main

import (
	"fmt"
	"os"

	"modgate/internal/pipeline"
)

func main() {
	manifest := ""
	out := ""
	args := os.Args[1:]
	for i := 0; i < len(args); i++ {
		switch args[i] {
		case "--manifest":
			if i+1 >= len(args) {
				fatal("missing --manifest value")
			}
			manifest = args[i+1]
			i++
		case "--out":
			if i+1 >= len(args) {
				fatal("missing --out value")
			}
			out = args[i+1]
			i++
		}
	}
	if manifest == "" || out == "" {
		fatal("usage: modgate --manifest <path> --out <dir>")
	}
	if err := pipeline.Run(manifest, out); err != nil {
		fatal(err.Error())
	}
	fmt.Println("MODGATE_OK")
}

func fatal(msg string) {
	fmt.Fprintln(os.Stderr, msg)
	os.Exit(1)
}
