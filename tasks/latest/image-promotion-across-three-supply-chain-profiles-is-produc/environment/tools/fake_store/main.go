package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
)

func main() {
	catalog := flag.String("catalog", "", "catalog path")
	flag.Parse()
	if *catalog == "" {
		fmt.Fprintf(os.Stderr, "usage: fake_store --catalog <path>\n")
		os.Exit(2)
	}
	raw, err := os.ReadFile(*catalog)
	if err != nil {
		fmt.Fprintf(os.Stderr, "fake_store: %v\n", err)
		os.Exit(1)
	}
	var doc any
	_ = json.Unmarshal(raw, &doc)
	_ = json.NewEncoder(os.Stdout).Encode(doc)
}
