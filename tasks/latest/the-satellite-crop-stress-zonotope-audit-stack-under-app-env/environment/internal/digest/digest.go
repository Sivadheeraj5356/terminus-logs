package digest

import (
	"crypto/sha256"
	"encoding/hex"
)

func Hex(data []byte) string {
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])
}

func HexStr(s string) string {
	return Hex([]byte(s))
}

func U64LE(k uint64) []byte {
	out := make([]byte, 8)
	for i := 0; i < 8; i++ {
		out[i] = byte((k >> (8 * i)) & 0xff)
	}
	return out
}
