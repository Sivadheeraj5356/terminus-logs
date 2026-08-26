package main

import (
	"os"

	"zonepub/internal/cli"
)

func main() {
	os.Exit(cli.Run(os.Args[1:]))
}
