package digest

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"hash"
	"io"
	"sort"
)

func SHA256(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func SHA256Reader(r io.Reader) (string, error) {
	h := sha256.New()
	if _, err := io.Copy(h, r); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

func StableJSON(v any) ([]byte, error) {
	return json.Marshal(v)
}

func StableJSONDigest(v any) (string, error) {
	b, err := StableJSON(v)
	if err != nil {
		return "", err
	}
	return SHA256(b), nil
}

func SortedKeys(m map[string]string) []string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return keys
}

func NewHasher() hash.Hash {
	return sha256.New()
}
