// Command formula-order reports the relative age of two formula versions.
//
// A package manager keeps every formula's published releases in order so it can
// decide which of two versions is the newer one when it resolves an upgrade or
// pins a dependency. This command exposes that single ordering decision:
//
//	formula-order <version-a> <version-b>
//
// It prints -1 when version-a sorts before (is older than) version-b, 1 when it
// sorts after (is newer), and 0 when the two versions are considered equal.
package main

import (
	"fmt"
	"os"

	"formulacatalog/internal/version"
)

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: formula-order <version-a> <version-b>")
		os.Exit(2)
	}
	fmt.Println(version.Compare(os.Args[1], os.Args[2]))
}
