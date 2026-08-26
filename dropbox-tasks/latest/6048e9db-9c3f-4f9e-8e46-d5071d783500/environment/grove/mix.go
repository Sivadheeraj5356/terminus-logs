package grove

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"
)

// Stub: lane seal digest per build_obligations.md.
func SealDigest(configID string, seed int64, runMode string, boundary int, fingerprint string) string {
	payload := strings.Join([]string{
		fmt.Sprintf("%d", seed),
		configID,
		runMode,
		fmt.Sprintf("%d", boundary),
		fingerprint,
	}, "\n")
	h := sha256.Sum256([]byte(payload))
	return hex.EncodeToString(h[:])
}
