package main

import (
	"encoding/json"
	"fmt"
	"os"
)

// The league rules are published in arena_rules.md. Implement adjudication
// here without changing the public position or the rules document.
func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: conclave INPUT OUTPUT")
		os.Exit(2)
	}
	var raw any
	b, err := os.ReadFile(os.Args[1])
	if err != nil || json.Unmarshal(b, &raw) != nil {
		fmt.Fprintln(os.Stderr, "invalid position")
		os.Exit(2)
	}
	fmt.Fprintln(os.Stderr, "adjudicator not implemented")
	os.Exit(1)
}
