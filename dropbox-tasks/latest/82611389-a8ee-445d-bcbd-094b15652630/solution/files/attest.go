package attest

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"strings"
)

// PlanDigest hashes module IDs in plan order, each followed by a newline.
func PlanDigest(modules []string) string {
	sum := sha256.New()
	for _, id := range modules {
		sum.Write([]byte(id))
		sum.Write([]byte{'\n'})
	}
	return hex.EncodeToString(sum.Sum(nil))
}

// PlanSeal binds plan_digest to the release pin with domain byte 0x46.
func PlanSeal(planDigestHex string, releasePin string, moduleCount uint32) (string, error) {
	raw, err := hex.DecodeString(planDigestHex)
	if err != nil || len(raw) != 32 {
		return "", err
	}
	sum := sha256.New()
	sum.Write([]byte{0x46})
	sum.Write(raw)
	sum.Write([]byte(strings.TrimSpace(releasePin)))
	buf := make([]byte, 4)
	binary.BigEndian.PutUint32(buf, moduleCount)
	sum.Write(buf)
	return hex.EncodeToString(sum.Sum(nil)), nil
}
