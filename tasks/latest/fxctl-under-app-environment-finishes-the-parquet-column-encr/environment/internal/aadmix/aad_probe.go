package aadmix

import (
	"encoding/hex"
)

func PreviewPrefix(seed []byte, n int) string {
	if n <= 0 || len(seed) == 0 {
		return ""
	}
	if n > len(seed) {
		n = len(seed)
	}
	return hex.EncodeToString(seed[:n])
}
