package main

import (
	"flag"
	"fmt"
	"os"

	"sigproxy/internal/backend"
)

func main() {
	fs := flag.NewFlagSet("backend-capture", flag.ExitOnError)
	listen := fs.String("listen-unix", "/tmp/backend.sock", "")
	output := fs.String("output", "/tmp/backend-capture.json", "")
	_ = fs.Parse(os.Args[1:])

	if err := backend.ServeCapture(*listen, *output); err != nil {
		fmt.Fprintf(os.Stderr, "backend-capture: %v\n", err)
		os.Exit(1)
	}
}
