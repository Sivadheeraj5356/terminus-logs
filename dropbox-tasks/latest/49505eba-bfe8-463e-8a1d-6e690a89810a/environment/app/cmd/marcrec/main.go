package main

import (
	"flag"
	"fmt"
	"os"
)

func main() {
	flag.Parse()
	fmt.Fprintln(os.Stderr, "marcrec: not implemented")
	os.Exit(2)
}
