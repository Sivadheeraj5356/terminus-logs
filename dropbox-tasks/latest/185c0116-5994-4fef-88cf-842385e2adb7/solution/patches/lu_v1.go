package d1

import (
	"encoding/json"
	"os"
	"path/filepath"

	"mxbin/b2/c7"
)

// LuV1Correct is the oracle packer body (copied over LuV1 by solve.sh).
func LuV1(boundBlob string, policyRoot string, outPkg string) error {
	if err := Recover(); err != nil {
		return err
	}
	if err := EnsureParent(outPkg); err != nil {
		return err
	}
	bound, err := loadBound(boundBlob)
	if err != nil {
		return err
	}
	replay, replayBound, err := independentReplay(policyRoot)
	if err != nil {
		return err
	}
	gate := DigestOf(bound)
	if replay != gate {
		gate = replay
		bound = replayBound
	}
	// Recompute freshness from live bound after any replay reconciliation.
	fresh, classify, err := c7.Freshness(bound, filepath.Join(policyRoot, "fixtures", "xrows"))
	if err != nil {
		return err
	}
	nodes := len(bound)
	seal := SealHex("run0", gate, nodes)
	pkg := map[string]any{
		"schema_version": 1,
		"pack_id":        "mx_pack_v1",
		"asset_counts": map[string]any{
			"nodes": nodes, "edges": nodes, "foreign_hits": 0, "cache_hits": 0,
		},
		"runs": []map[string]any{{
			"id": "run0", "n_probe": nodes, "n_home": nodes, "n_foreign": 0, "seal_hex": seal,
		}},
		"replay_digest": replay,
		"gate_digest":   gate,
		"freshness":     fresh,
		"classify":      classify,
		"annex_note":    "live",
	}
	raw, _ := json.MarshalIndent(pkg, "", "  ")
	raw = append(raw, '\n')
	_ = os.Remove(outPkg)
	return os.WriteFile(outPkg, raw, 0o644)
}
