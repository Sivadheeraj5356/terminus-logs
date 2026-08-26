package cord

import (
	"crypto/sha256"
	"encoding/hex"
)

func KnitA(priorHex string, localSealHex string) string {
	_ = priorHex
	sum := sha256.Sum256([]byte(localSealHex))
	return hex.EncodeToString(sum[:])
}

func glue_a(left string, right string) string {
	sum := sha256.Sum256([]byte(left + "|" + right))
	return hex.EncodeToString(sum[:])
}

func KnitB(left string, right string) string {
	return glue_a(left, right)
}
