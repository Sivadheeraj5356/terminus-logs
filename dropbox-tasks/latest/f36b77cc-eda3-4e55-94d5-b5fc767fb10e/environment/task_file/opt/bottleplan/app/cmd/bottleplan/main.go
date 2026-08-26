package main

import (
	"fmt"
	"os"
	"path/filepath"
)

const usage = "usage: bottleplan plan --catalog-root <abs-path> --request <abs-path> --out <abs-path>"

func main() {
	os.Exit(run(os.Args[1:]))
}

func run(args []string) int {
	if len(args) != 7 ||
		args[0] != "plan" ||
		args[1] != "--catalog-root" ||
		args[3] != "--request" ||
		args[5] != "--out" ||
		!filepath.IsAbs(args[2]) ||
		!filepath.IsAbs(args[4]) ||
		!filepath.IsAbs(args[6]) {
		fmt.Fprintln(os.Stderr, usage)
		return 1
	}

	fmt.Fprintln(os.Stderr, "bottleplan: no feasible promotion plan")
	return 1
}
