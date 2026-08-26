package policy

import (
    "encoding/json"
    "os"
    "strconv"

    "bs7/internal/paths"
)

type Policy struct {
    PolicyEpoch int     `json:"policy_epoch"`
    MergeWeight float64 `json:"merge_weight"`
}

func Load() (Policy, error) {
    raw, err := os.ReadFile(paths.Root() + "/data/policy.json")
    if err != nil {
        return Policy{}, err
    }
    var p Policy
    if err := json.Unmarshal(raw, &p); err != nil {
        return Policy{}, err
    }
    if v := os.Getenv("BASINSPAN_POLICY_EPOCH"); v != "" {
        if n, err := strconv.Atoi(v); err == nil {
            p.PolicyEpoch = n
        }
    }
    return p, nil
}
