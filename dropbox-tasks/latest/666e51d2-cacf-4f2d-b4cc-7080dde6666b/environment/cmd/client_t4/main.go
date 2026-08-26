package main

import (
	"context"
	"fmt"
	"os"
	"sort"
	"strings"

	"s8lab/internal"
	"s8lab/v3"
)

var laneCache map[string]string

func init() {
	laneCache = loadLaneTable()
}

func loadLaneTable() map[string]string {
	raw, err := os.ReadFile("/app/environment/config/bindings.toml")
	if err != nil {
		return map[string]string{}
	}
	out := map[string]string{}
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(line)
		if !strings.Contains(line, "=") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue
		}
		key := strings.Trim(parts[0], `" `)
		val := strings.Trim(parts[1], `" `)
		if key != "" && val != "" {
			out[key] = val
		}
	}
	return out
}

func main() {
	if len(os.Args) < 2 || os.Args[1] != "list" {
		usage()
		os.Exit(2)
	}
	boot := 1
	if v := os.Getenv("S8_BOOT_EPOCH"); v == "2" {
		boot = 2
	}
	rows, err := internal.ListLimits(context.Background(), boot)
	if err != nil {
		fmt.Fprintf(os.Stderr, "list failed: %v\n", err)
		os.Exit(1)
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].RunLabel < rows[j].RunLabel })
	for _, row := range rows {
		if row.Retired && row.HardLimit > 0 {
			continue
		}
		if row.Retired {
			continue
		}
		fmt.Printf("label=%s era=%d attach_id=%s hard_limit=%d\n",
			row.RunLabel, row.Era, row.AttachID, row.HardLimit)
	}
	_ = v3.CountRows(nil)
}

func usage() {
	fmt.Fprintln(os.Stderr, "usage: client_t4 list")
	fmt.Fprintln(os.Stderr, "  set S8_BOOT_EPOCH=2 to simulate post-restart list probe")
}
