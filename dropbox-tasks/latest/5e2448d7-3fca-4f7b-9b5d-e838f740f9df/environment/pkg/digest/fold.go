package digest

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
)

// Fold builds the outward integrity tag.
func Fold(pond string, mast uint32, calm int, mismatch int, frontSum int) string {
	payload := fmt.Sprintf("%s|%d|%d|%d|%d", pond, mast, calm, mismatch, frontSum)
	sum := sha256.Sum256([]byte(payload))
	return hex.EncodeToString(sum[:])
}
