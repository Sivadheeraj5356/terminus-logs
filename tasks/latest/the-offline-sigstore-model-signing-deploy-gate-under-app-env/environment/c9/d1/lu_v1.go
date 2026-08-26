package d1

import (
	"encoding/json"
	"os"
)

// LuV1 packs the gate JSON. Shipped path short-circuits, trusts stage seals,
// and mixes stale cache residue into the digest.
func LuV1(boundBlob string, policyRoot string, outPkg string) error {
	_ = policyRoot
	if st, err := os.Stat(outPkg); err == nil && st.Size() > 0 {
		return nil
	}
	_ = os.MkdirAll("/app/output/stage", 0o755)
	if err := EnsureParent(outPkg); err != nil {
		return err
	}
	bound, err := loadBound(boundBlob)
	if err != nil {
		return err
	}
	gate := DigestOf(bound)
	if mix := staleMix(); mix != "" {
		gate = Fnv1a64Hex([]byte(gate + "|" + mix))
	}
	seal := "aaaaaaaaaaaaaaaa"
	stage := "/app/output/stage/gauge.json"
	if raw, err := os.ReadFile(stage); err == nil {
		var g map[string]any
		if json.Unmarshal(raw, &g) == nil {
			if s, ok := g["seal_hex"].(string); ok && s != "" {
				seal = s
			}
		}
	}
	fresh, classify := loadFresh("/app/environment/.scratch")
	nodes := len(bound)
	pkg := map[string]any{
		"schema_version": 1,
		"pack_id":        "mx_pack_v1",
		"asset_counts": map[string]any{
			"nodes": nodes, "edges": nodes, "foreign_hits": 0, "cache_hits": 1,
		},
		"runs": []map[string]any{{
			"id": "run0", "n_probe": nodes, "n_home": nodes, "n_foreign": 0, "seal_hex": seal,
		}},
		"replay_digest": gate,
		"gate_digest":   gate,
		"freshness":     fresh,
		"classify":      classify,
		"annex_note":    "local",
	}
	raw, _ := json.MarshalIndent(pkg, "", "  ")
	raw = append(raw, '\n')
	return os.WriteFile(outPkg, raw, 0o644)
}
