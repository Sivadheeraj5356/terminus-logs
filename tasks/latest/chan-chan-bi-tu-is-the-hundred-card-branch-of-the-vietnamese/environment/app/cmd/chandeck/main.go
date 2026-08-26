package main

import (
	"bufio"
	"fmt"
	"io"
	"os"

	"chandeck/internal/chandeck"
)

func main() {
	raw, err := io.ReadAll(os.Stdin)
	if err != nil {
		fmt.Fprintln(os.Stderr, "chandeck: read error")
		os.Exit(1)
	}
	out := chandeck.Trace(raw)
	w := bufio.NewWriter(os.Stdout)
	_, _ = io.WriteString(w, out)
	_ = w.Flush()
}
