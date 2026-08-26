package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"sort"

	"corp.example/modlock/internal/digest"
	"corp.example/modlock/internal/types"
)

func main() {
	if len(os.Args) < 2 || os.Args[1] != "graph-compare" {
		fmt.Println("modpolicy-inspect graph-compare --lock PATH --report PATH")
		os.Exit(2)
	}
	fs := flag.NewFlagSet("graph-compare", flag.ExitOnError)
	lockPath := fs.String("lock", "", "")
	reportPath := fs.String("report", "", "")
	_ = fs.Parse(os.Args[2:])
	lock, err := readArtifact(*lockPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	report, err := readArtifact(*reportPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if lock.ResolutionDigest != report.ResolutionDigest {
		fmt.Fprintln(os.Stderr, "digest mismatch")
		os.Exit(1)
	}
	expected := digest.Compute(lock.Modules)
	if lock.ResolutionDigest != expected {
		fmt.Fprintln(os.Stderr, "lock digest invalid")
		os.Exit(1)
	}
	lockMap := map[string]types.ModuleEntry{}
	for _, m := range lock.Modules {
		lockMap[m.Path] = m
	}
	for _, m := range report.Modules {
		lm, ok := lockMap[m.Path]
		if !ok || lm.Version != m.Version || lm.Source != m.Source || lm.PolicyDecision != m.PolicyDecision {
			fmt.Fprintln(os.Stderr, "graph mismatch:", m.Path)
			os.Exit(1)
		}
	}
	if len(lockMap) != len(report.Modules) {
		fmt.Fprintln(os.Stderr, "graph mismatch: count")
		os.Exit(1)
	}
	sort.Slice(lock.Modules, func(i, j int) bool { return lock.Modules[i].Path < lock.Modules[j].Path })
	for i, m := range lock.Modules {
		if i > 0 && lock.Modules[i-1].Path >= m.Path {
			fmt.Fprintln(os.Stderr, "modules not sorted")
			os.Exit(1)
		}
	}
	os.Exit(0)
}

func readArtifact(path string) (types.Artifact, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return types.Artifact{}, err
	}
	var artifact types.Artifact
	if err := json.Unmarshal(raw, &artifact); err != nil {
		return types.Artifact{}, err
	}
	return artifact, nil
}
