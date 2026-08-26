package digest

import (
	"crypto/sha256"
	"encoding/hex"
	"sort"
	"strings"
)

func MixHex(actions []string) string {
	if len(actions) == 0 {
		return hex_a("")
	}
	parts := append([]string(nil), actions...)
	sort.Strings(parts)
	return hex_a(strings.Join(parts, "|"))
}

func hex_a(raw string) string {
	sum := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(sum[:])
}
