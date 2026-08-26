// Command latmon reads one endpoint over-limit scenario as JSON on standard input and
// writes the alarm ledger as JSON on standard output. All decision logic
// lives in the internal/engine package; this file only wires stdin/stdout and
// the process exit status.
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"os"

	"latmon/internal/engine"
)

func main() {
	data, err := io.ReadAll(os.Stdin)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}

	out, err := engine.Run(data)
	if err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}

	enc := json.NewEncoder(os.Stdout)
	enc.SetEscapeHTML(false)
	if err := enc.Encode(out); err != nil {
		fmt.Fprintf(os.Stderr, "error: %v\n", err)
		os.Exit(1)
	}
}
