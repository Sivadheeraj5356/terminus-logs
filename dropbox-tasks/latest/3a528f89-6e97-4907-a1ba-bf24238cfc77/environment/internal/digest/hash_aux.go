package digest

import (
	"crypto/sha256"
	"encoding/hex"
)

func AuxMix(a, b string) string {
	sum := sha256.Sum256([]byte(a + ":" + b))
	return hex.EncodeToString(sum[:4])
}
