package main

import (
	"fmt"
	"os"
	"path/filepath"

	"desk/desk"
)

func main() {
	root := os.Getenv("DESK_ROOT")
	if root == "" {
		root = "/app"
	}
	index := filepath.Join(root, "shared", "pack_index.json")
	curves := filepath.Join(root, "curves")
	legacy := filepath.Join(root, "legacy")
	_ = os.MkdirAll(legacy, 0o755)

	order, err := desk.LoadOrder(index)
	if err != nil {
		panic(err)
	}
	var body string
	for _, name := range order {
		spec, err := desk.LoadSpec(filepath.Join(curves, name+".json"))
		if err != nil {
			panic(err)
		}
		d := desk.FreshDepthOnly(spec)
		body += fmt.Sprintf("%s fresh_depth=%d\n", name, d)
	}
	path := filepath.Join(legacy, "fresh_lane.txt")
	if err := os.WriteFile(path, []byte(body), 0o644); err != nil {
		panic(err)
	}
	fmt.Print(body)
}
