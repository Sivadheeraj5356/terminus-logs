package grove

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"
)

// SealDigest binds lane checkpoint metadata to the schedule fingerprint.
func SealDigest(configID string, seed int64, runMode string, boundary int, fingerprint string) string {
	payload := strings.Join([]string{
		configID,
		fmt.Sprintf("%d", seed),
		runMode,
		fmt.Sprintf("%d", boundary),
		fingerprint,
	}, "\n")
	h := sha256.Sum256([]byte(payload))
	return hex.EncodeToString(h[:])
}
