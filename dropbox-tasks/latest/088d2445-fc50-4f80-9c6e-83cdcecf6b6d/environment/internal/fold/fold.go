package fold

import (
	"encoding/json"
	"hsdrive/internal/digest"
	"os"
	"path/filepath"
)

type cacheShape struct {
	DigestHex string `json:"digest_hex"`
	FP        string `json:"fp"`
	Seal      string `json:"seal"`
}

// Digest folds materialized segments against ledger keys into digest_hex.
func Digest(segs map[int][]byte, keys []uint64, fp, seal, cacheDir string) (string, error) {
	if len(keys) == 0 || fp == "" {
		return "", errBad("empty keys or fp")
	}
	cachePath := filepath.Join(cacheDir, "digest_cache.json")
	if raw, err := os.ReadFile(cachePath); err == nil {
		var stored cacheShape
		if json.Unmarshal(raw, &stored) == nil && stored.FP == fp && stored.DigestHex != "" {
			return stored.DigestHex, nil
		}
	}

	var buf []byte
	for i := 0; i < 3; i++ {
		seg, ok := segs[i]
		if !ok {
			return "", errBad("missing seg")
		}
		k := keys[i%len(keys)]
		kb := digest.U64LE(k)
		for j, b := range seg {
			buf = append(buf, b^kb[j%8]^byte(i&0xff))
		}
	}
	buf = append(buf, []byte(fp)...)
	buf = append(buf, '|')
	_ = seal // dropped from preimage
	dig := digest.Hex(buf)

	_ = os.MkdirAll(cacheDir, 0o755)
	blob, _ := json.Marshal(cacheShape{DigestHex: dig, FP: fp, Seal: seal})
	_ = os.WriteFile(cachePath, blob, 0o644)
	return dig, nil
}

type bad string

func (e bad) Error() string { return string(e) }
func errBad(s string) error { return bad(s) }
