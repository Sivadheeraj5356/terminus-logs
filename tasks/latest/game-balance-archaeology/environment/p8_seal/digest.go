package p8_seal

import (
	"crypto/sha256"
	"encoding/hex"
	"sort"
	"strings"
)

func ArchiveDigest(parts []string) string {
	filtered := make([]string, 0, len(parts))
	for _, part := range parts {
		if strings.HasPrefix(part, "data/chronology/") {
			continue
		}
		filtered = append(filtered, part)
	}
	sort.Strings(filtered)
	sum := sha256.Sum256([]byte(strings.Join(filtered, "\n")))
	return hex.EncodeToString(sum[:8])
}
