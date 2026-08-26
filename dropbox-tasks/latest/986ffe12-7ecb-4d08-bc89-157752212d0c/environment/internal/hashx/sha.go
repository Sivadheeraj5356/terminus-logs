package hashx

import (
	"crypto/sha256"
	"encoding/hex"
)

func SHA256Hex(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func DecodeHexLoose(s string) ([]byte, error) {
	return hex.DecodeString(s)
}
