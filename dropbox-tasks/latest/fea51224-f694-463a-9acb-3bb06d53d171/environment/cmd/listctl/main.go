package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strconv"

	"slotmgr/internal/catalog"
	"slotmgr/internal/store"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: listctl show <cycle>")
		os.Exit(2)
	}
	root := os.Getenv("REPLAY_ROOT")
	if root == "" {
		root = "/app/environment"
	}
	if os.Args[1] != "show" {
		fmt.Fprintln(os.Stderr, "usage: listctl show <cycle>")
		os.Exit(2)
	}
	cycle := 1
	if len(os.Args) >= 3 {
		if n, err := strconv.Atoi(os.Args[2]); err == nil {
			cycle = n
		}
	}
	suffix := string(rune('a' + cycle - 1))
	path := filepath.Join(root, "fixtures", "array_slots_"+suffix+".json")
	b, err := os.ReadFile(path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "listctl: %v\n", err)
		os.Exit(1)
	}
	var snap store.SlotSnap
	if err := json.Unmarshal(b, &snap); err != nil {
		fmt.Fprintf(os.Stderr, "listctl: %v\n", err)
		os.Exit(1)
	}
	merged := catalog.FoldRows(snap.Rows)
	for _, row := range merged {
		fmt.Printf("peer=%s slots_free=%d cleared_units=%d\n", row.PeerTag, row.SlotsFree, row.ClearedUnits)
	}
}
