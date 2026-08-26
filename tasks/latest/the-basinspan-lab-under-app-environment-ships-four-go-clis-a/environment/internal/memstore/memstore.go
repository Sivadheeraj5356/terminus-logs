package memstore

import (
    "encoding/json"
    "os"

    "bs7/internal/paths"
)

type CacheEntry struct {
    PairDigestHex  string  `json:"pair_digest_hex"`
    MergeDigestHex string  `json:"merge_digest_hex"`
    EvalMSE        float64 `json:"eval_mse"`
    BarrierValue   float64 `json:"barrier_value"`
    AlignCost      float64 `json:"align_cost"`
}

type Cache struct {
    PolicyEpoch int                   `json:"policy_epoch"`
    Entries     map[string]CacheEntry `json:"entries"`
}

func CacheKey(pairDigest string) string {
    return pairDigest
}

func Load() Cache {
    raw, err := os.ReadFile(paths.VarDir() + "/align_cache.json")
    if err != nil {
        return Cache{Entries: map[string]CacheEntry{}}
    }
    var c Cache
    _ = json.Unmarshal(raw, &c)
    if c.Entries == nil {
        c.Entries = map[string]CacheEntry{}
    }
    return c
}

func Save(c Cache) error {
    b, err := json.MarshalIndent(c, "", "  ")
    if err != nil {
        return err
    }
    return os.WriteFile(paths.VarDir()+"/align_cache.json", b, 0644)
}
