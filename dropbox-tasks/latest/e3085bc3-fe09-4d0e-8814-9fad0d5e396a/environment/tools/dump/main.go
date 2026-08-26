package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"imlab/internal/model"
)

func main() {
	path := flag.String("program", "output/program.json", "program path")
	flag.Parse()
	var p model.Program
	if err := model.ReadJSON(*path, &p); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(p)
}
