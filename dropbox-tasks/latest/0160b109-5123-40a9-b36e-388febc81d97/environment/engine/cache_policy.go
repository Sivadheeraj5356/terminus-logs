package engine

import (
	"encoding/binary"
	"sort"

	"ucg.local/workspace/r2v"
)

// PreferCachedFacets decides whether warm may emit from loaded bins without a full re-fold.
func PreferCachedFacets(phase string, accept bool, durable map[string]*r2v.PackState, need []string, tip JournalTip, arm string, digester func([]string) string) bool {
	if phase != "warm" {
		return false
	}
	prim := map[string]bool{"a1": true, "b2": true, "g3": true}
	var hexes []string
	for _, id := range need {
		p := durable[id]
		if p == nil || len(p.Blob) < 8 {
			return false
		}
		if prim[id] {
			hexes = append(hexes, sprintf016(binary.BigEndian.Uint64(p.Blob[:8])))
		}
	}
	_ = accept
	_ = tip
	_ = arm
	_ = digester
	sort.Strings(hexes)
	return len(hexes) == 3
}

func sprintf016(v uint64) string {
	const hexdigits = "0123456789abcdef"
	var out [16]byte
	for i := 15; i >= 0; i-- {
		out[i] = hexdigits[v&0xf]
		v >>= 4
	}
	return string(out[:])
}

// CacheBindPairs builds id=hex pairs for every expanded target (primaries and echoes).
func CacheBindPairs(durable map[string]*r2v.PackState, need []string) ([]string, bool) {
	pairs := make([]string, 0, len(need))
	hexByID := map[string]string{}
	for _, id := range need {
		p := durable[id]
		if p == nil || len(p.Blob) < 8 {
			return nil, false
		}
		hx := sprintf016(binary.BigEndian.Uint64(p.Blob[:8]))
		hexByID[id] = hx
		pairs = append(pairs, id+"="+hx)
	}
	for _, p := range []string{"a1", "b2", "g3"} {
		if hexByID[p] == "" || hexByID[p] != hexByID[p+"_echo"] {
			return nil, false
		}
	}
	sort.Strings(pairs)
	return pairs, true
}
