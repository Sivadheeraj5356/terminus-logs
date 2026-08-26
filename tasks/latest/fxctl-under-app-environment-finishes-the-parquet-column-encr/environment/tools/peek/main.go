package main

import (
	"flag"
	"fmt"
	"os"

	"fxdesk/chunkxor"
	"fxdesk/internal/io"
	parsefooter "fxdesk/internal/footer"
)

func main() {
	caseID := flag.String("case", "", "case id")
	flag.Parse()
	if *caseID == "" {
		fmt.Fprintln(os.Stderr, "usage: peek --case <id>")
		os.Exit(1)
	}
	spec, err := io.LoadCase(*caseID)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	raw, err := io.ReadRel(spec.Blob)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	view, err := parsefooter.ParseFooter(raw)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if len(view.Chunks) == 0 {
		fmt.Println("empty")
		return
	}
	ch := view.Chunks[0]
	start := int(ch.Offset)
	end := start + int(ch.Length)
	if end > len(raw) {
		end = len(raw)
	}
	part, err := chunkxor.DecryptChunk(raw[start:end], nil, int64(start))
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Printf("%q\n", string(part))
}
