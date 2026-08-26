package persist

import (
    "encoding/json"
    "os"

    "bs7/internal/paths"
)

type LedgerEntry struct {
    MergeDigestHex string `json:"merge_digest_hex"`
    StableRuns     int    `json:"stable_runs"`
    LastGeneration int    `json:"last_generation"`
}

type MergeLedger struct {
    Generation  int                    `json:"generation"`
    PolicyEpoch int                    `json:"policy_epoch"`
    Entries     map[string]LedgerEntry `json:"entries"`
}

func LoadLedger() MergeLedger {
    raw, err := os.ReadFile(paths.VarDir() + "/merge_ledger.json")
    if err != nil {
        return MergeLedger{Entries: map[string]LedgerEntry{}}
    }
    var l MergeLedger
    _ = json.Unmarshal(raw, &l)
    if l.Entries == nil {
        l.Entries = map[string]LedgerEntry{}
    }
    return l
}

func SaveLedger(l MergeLedger) error {
    b, err := json.MarshalIndent(l, "", "  ")
    if err != nil {
        return err
    }
    return os.WriteFile(paths.VarDir()+"/merge_ledger.json", b, 0644)
}

func BumpStable(prev LedgerEntry, digest string, gen int) LedgerEntry {
    if prev.MergeDigestHex == digest {
        prev.StableRuns++
    } else {
        prev.StableRuns = 1
    }
    prev.MergeDigestHex = digest
    prev.LastGeneration = gen
    return prev
}
