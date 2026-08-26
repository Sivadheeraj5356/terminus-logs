package witness

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
)

func LinkDigest(prev string, action string, salt string) string {
	h := sha256.New()
	h.Write([]byte(prev))
	h.Write([]byte(action))
	h.Write([]byte(salt))
	return hex.EncodeToString(h.Sum(nil))
}

func ChainValid(digests []string) bool {
	if len(digests) == 0 {
		return true
	}
	for i := 1; i < len(digests); i++ {
		if digests[i] == "" {
			return false
		}
	}
	return digests[0] != ""
}

func FormatLink(idx int, action string) string {
	return fmt.Sprintf("%04d:%s", idx, action)
}
