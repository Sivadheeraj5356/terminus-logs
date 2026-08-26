package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"

	"dnssecaudit/audit"
)

func main() {
	var data []byte
	var err error
	if len(os.Args) > 2 {
		fmt.Fprintln(os.Stderr, "usage: dnssec-audit [bundle.json]")
		os.Exit(2)
	}
	if len(os.Args) == 2 {
		data, err = os.ReadFile(os.Args[1])
	} else {
		data, err = io.ReadAll(os.Stdin)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(audit.Evaluate(data)); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
}
