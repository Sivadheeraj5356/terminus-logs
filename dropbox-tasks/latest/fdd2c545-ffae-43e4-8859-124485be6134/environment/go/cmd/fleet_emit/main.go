package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"fleet/go/pkg/m2"
	"fleet/go/pkg/q3"
)

func main() {
	resolved := flag.String("resolved", "", "resolved json")
	unitsDir := flag.String("units", "", "units dir")
	manifestOut := flag.String("manifest", "", "manifest json path")
	flag.Parse()
	if err := q3.EmitUnits(*resolved, *unitsDir); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	man, err := m2.BuildManifest(*unitsDir)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	// sort entries for tarball listing only
	man.Entries = m2.SortedEntries(man.Entries)
	raw, _ := json.MarshalIndent(man, "", "  ")
	if err := os.WriteFile(*manifestOut, raw, 0o644); err != nil {
		os.Exit(1)
	}
}
