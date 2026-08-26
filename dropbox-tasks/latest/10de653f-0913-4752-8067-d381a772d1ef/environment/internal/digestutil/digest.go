package digestutil

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
)

func HexFile(path string) (string, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return HexBytes(b), nil
}

func HexBytes(b []byte) string {
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

func CanonicalJSON(v any) ([]byte, error) {
	return json.Marshal(v)
}
