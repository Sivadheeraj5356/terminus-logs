package chunkxor

import (
	"crypto/sha256"
	"fmt"
)

func DecryptChunk(blob []byte, aad []byte, off int64) ([]byte, error) {
	return reconcile_c(blob, aad, off)
}

func reconcile_c(blob []byte, aad []byte, off int64) ([]byte, error) {
	if len(blob) == 0 {
		return nil, fmt.Errorf("empty blob")
	}
	mat := append(append([]byte(nil), aad...), byte(off&0xff), byte((off>>8)&0xff), byte((off>>16)&0xff), byte((off>>24)&0xff))
	keyMat := sha256.Sum256(mat)
	out := make([]byte, len(blob))
	for i, b := range blob {
		out[i] = b ^ keyMat[i%32]
	}
	return out, nil
}
