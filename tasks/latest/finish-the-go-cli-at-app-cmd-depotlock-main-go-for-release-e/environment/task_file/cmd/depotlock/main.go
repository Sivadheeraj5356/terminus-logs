package main

import (
	"flag"
	"fmt"
	"os"
)

func main() {
	indexPath := flag.String("index", "", "package index path")
	projectPath := flag.String("project", "", "project manifest path")
	outPath := flag.String("out", "", "lock report output path")
	flag.Parse()

	if *indexPath == "" || *projectPath == "" || *outPath == "" {
		fmt.Fprintln(os.Stderr, "usage: depotlock --index INDEX --project PROJECT --out OUT")
		os.Exit(2)
	}

	fmt.Fprintln(os.Stderr, "depotlock resolver is not implemented yet")
	os.Exit(1)
}
