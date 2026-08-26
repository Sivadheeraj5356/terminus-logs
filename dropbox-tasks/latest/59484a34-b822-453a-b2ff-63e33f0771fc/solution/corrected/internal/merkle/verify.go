package merkle

import (
	"crypto/sha256"
	"encoding/hex"
)

func LeafHash(serial string, leafIndex int, leafPayload string) string {
	h := sha256.New()
	h.Write([]byte(serial))
	h.Write([]byte("|"))
	h.Write([]byte(leafPayload))
	return hex.EncodeToString(h.Sum(nil))
}

func decodeHex32(s string) ([]byte, error) {
	return hex.DecodeString(s)
}

func parentHash(left, right []byte) string {
	h := sha256.New()
	h.Write(left)
	h.Write(right)
	return hex.EncodeToString(h.Sum(nil))
}

func VerifyPath(leafHash string, leafIndex int, path []string, rootHash string, treeSize int) bool {
	if treeSize <= 0 || leafIndex < 0 || leafIndex >= treeSize {
		return false
	}
	curBytes, err := decodeHex32(leafHash)
	if err != nil {
		return false
	}
	cur := leafHash
	idx := leafIndex
	for _, sibling := range path {
		sibBytes, err := decodeHex32(sibling)
		if err != nil {
			return false
		}
		if idx%2 == 0 {
			cur = parentHash(curBytes, sibBytes)
		} else {
			cur = parentHash(sibBytes, curBytes)
		}
		curBytes, err = decodeHex32(cur)
		if err != nil {
			return false
		}
		idx = idx / 2
	}
	return cur == rootHash
}
