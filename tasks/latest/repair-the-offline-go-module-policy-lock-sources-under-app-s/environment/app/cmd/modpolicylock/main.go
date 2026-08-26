package main

import (
	"os"

	"corp.example/modlock/internal/cli"
)

func main() {
	os.Exit(cli.Main(os.Args[1:]))
}
