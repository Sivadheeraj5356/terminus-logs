package engine

import (
	"crypto/sha256"
	"encoding/hex"
)

func DigestHex(parts []string) string {
	h := sha256.New()
	for i, p := range parts {
		if i > 0 {
			h.Write([]byte{','})
		}
		h.Write([]byte(p))
	}
	return hex.EncodeToString(h.Sum(nil))
}
