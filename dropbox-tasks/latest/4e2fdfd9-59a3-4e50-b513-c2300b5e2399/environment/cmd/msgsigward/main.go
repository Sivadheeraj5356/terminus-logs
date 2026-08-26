// Command msgsigward reads one immutable RFC 9421 HTTP message-signature bundle
// (input.json) and prints the security decision line:
//
//	<verdict> <reason> <covered>
//
// It exits non-zero (with a message on stderr) when the input cannot be parsed
// or evaluated, rather than panicking.
package main

import (
	"encoding/json"
	"fmt"
	"os"

	"msgsigward/internal/msgsig"
)

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "usage: msgsigward <input.json>")
		os.Exit(2)
	}
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		fmt.Fprintln(os.Stderr, "read input:", err)
		os.Exit(1)
	}
	var in msgsig.Input
	if err := json.Unmarshal(data, &in); err != nil {
		fmt.Fprintln(os.Stderr, "parse input:", err)
		os.Exit(1)
	}
	verdict, reason, covered, err := msgsig.Verify(in)
	if err != nil {
		fmt.Fprintln(os.Stderr, "verify:", err)
		os.Exit(1)
	}
	fmt.Printf("%s %s %s\n", verdict, reason, covered)
}
