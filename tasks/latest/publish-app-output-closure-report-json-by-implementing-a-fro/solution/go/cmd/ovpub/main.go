package main

import (
	"fmt"
	"os"

	"github.com/tbench/clmerge/internal/kvfold"
)

func main() {
	if err := kvfold.WriteReport(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
