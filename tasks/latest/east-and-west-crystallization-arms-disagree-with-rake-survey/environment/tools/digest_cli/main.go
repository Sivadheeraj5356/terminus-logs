package main

import (
	"fmt"
	"os"
	"strconv"

	"lab.local/salt_pond/pkg/digest"
)

func main() {
	if len(os.Args) != 7 {
		fmt.Fprintln(os.Stderr, "usage: digest_cli pond mast calm mismatch front_sum")
		os.Exit(2)
	}
	mast, _ := strconv.ParseUint(os.Args[2], 10, 32)
	calm, _ := strconv.Atoi(os.Args[3])
	mismatch, _ := strconv.Atoi(os.Args[4])
	front, _ := strconv.Atoi(os.Args[5])
	fmt.Println(digest.Fold(os.Args[1], uint32(mast), calm, mismatch, front))
}
