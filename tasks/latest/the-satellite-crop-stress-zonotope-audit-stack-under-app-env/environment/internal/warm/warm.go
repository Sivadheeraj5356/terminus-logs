package warm

import (
	"encoding/json"
	"os"
)

type stageShape struct {
	Status string `json:"status"`
}

type cacheShape struct {
	DigestHex string `json:"digest_hex"`
	FP        string `json:"fp"`
	Seal      string `json:"seal"`
}

// StageLooksGreen reports whether stage summary claims coherence.
func StageLooksGreen(path string) bool {
	raw, err := os.ReadFile(path)
	if err != nil {
		return false
	}
	var s stageShape
	if json.Unmarshal(raw, &s) != nil {
		return false
	}
	return s.Status == "coherent"
}

// ReadCachedDigest loads a previously staged digest_hex when present.
func ReadCachedDigest(cachePath, _fp, _seal string) (string, bool) {
	raw, err := os.ReadFile(cachePath)
	if err != nil {
		return "", false
	}
	var c cacheShape
	if json.Unmarshal(raw, &c) != nil || c.DigestHex == "" {
		return "", false
	}
	return c.DigestHex, true
}
