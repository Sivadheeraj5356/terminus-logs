package main

import (
	"fmt"
	"os"
)

// logError writes an error message to stderr.
func logError(msg string) {
	fmt.Fprintln(os.Stderr, "[error]", msg)
}
