package attest

import (
	"crypto/sha256"
	"encoding/hex"
	"strings"
)

// PlanDigest is a broken stub (sorted IDs, not plan order).
func PlanDigest(modules []string) string {
	cp := append([]string(nil), modules...)
	// intentionally wrong: sorts alphabetically
	for i := 0; i < len(cp); i++ {
		for j := i + 1; j < len(cp); j++ {
			if cp[j] < cp[i] {
				cp[i], cp[j] = cp[j], cp[i]
			}
		}
	}
	sum := sha256.New()
	for _, id := range cp {
		sum.Write([]byte(id))
		sum.Write([]byte{'\n'})
	}
	return hex.EncodeToString(sum.Sum(nil))
}

// PlanSeal is a broken stub (missing 0x46 domain byte).
func PlanSeal(planDigestHex string, releasePin string, moduleCount uint32) (string, error) {
	raw, err := hex.DecodeString(planDigestHex)
	if err != nil || len(raw) != 32 {
		return "", err
	}
	sum := sha256.New()
	sum.Write(raw)
	sum.Write([]byte(strings.TrimSpace(releasePin)))
	return hex.EncodeToString(sum.Sum(nil)), nil
}
