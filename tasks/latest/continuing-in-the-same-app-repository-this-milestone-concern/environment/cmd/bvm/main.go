package main

import (
	"fmt"
	"os"

	"example.com/bvm/internal/bvm"
)

func main() {
	out, code, err := bvm.Run(os.Args[1:])
	if err != nil {
		fmt.Fprintln(os.Stderr, err.Error())
		os.Exit(2)
	}
	if out != "" {
		fmt.Println(out)
	}
	os.Exit(code)
}
