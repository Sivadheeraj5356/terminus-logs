package main

// Archival demo driver — outside the ReelSeal sealing path.
import (
	"fmt"
	"os"
)

func main() {
	fmt.Fprintln(os.Stderr, "legacy seal driver is non-authoritative")
	os.Exit(1)
}
