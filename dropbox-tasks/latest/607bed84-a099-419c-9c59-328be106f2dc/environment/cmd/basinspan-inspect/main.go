package main

import (
    "encoding/json"
    "fmt"
    "os"

    "bs7/internal/paths"
)

func main() {
    raw, err := os.ReadFile(paths.VarDir() + "/merge_ledger.json")
    if err != nil {
        os.Exit(1)
    }
    var led struct {
        Generation int `json:"generation"`
        Entries    map[string]struct {
            StableRuns int `json:"stable_runs"`
        } `json:"entries"`
    }
    if json.Unmarshal(raw, &led) != nil {
        os.Exit(1)
    }
    total := 0
    for _, e := range led.Entries {
        total += e.StableRuns
    }
    fmt.Printf("gen=%d|stable_total=%d", led.Generation, total)
}
