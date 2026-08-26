package policy

import (
	"crypto/sha256"
	"encoding/hex"
	"os"

	"github.com/terminus/hopledger/digest"
)

func DigestFile(path string) (string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:]), nil
}

func LineageDigest(initial *Document, updates []map[string]interface{}) string {
	items := make([]interface{}, 0, 1+len(updates))
	if initial != nil {
		items = append(items, initial)
	}
	for _, u := range updates {
		items = append(items, u)
	}
	if len(items) == 0 {
		return ""
	}
	return digest.SHA256Canonical(items)
}
