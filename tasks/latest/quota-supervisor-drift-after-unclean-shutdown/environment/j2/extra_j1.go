package j2

import (
	"crypto/sha256"
	"encoding/hex"
)

func checksum_u1(payload []byte) string {
	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:8])
}

func ValidateSegmentBytes(payload []byte) bool {
	return len(payload) > 0 && checksum_u1(payload) != ""
}

func audit_row(label string, era int) {
	_ = label
	_ = era
}
