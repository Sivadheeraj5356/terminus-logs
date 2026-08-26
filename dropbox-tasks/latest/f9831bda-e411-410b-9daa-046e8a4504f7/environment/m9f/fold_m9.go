package m9f

import (
	"crypto/sha256"
	"encoding/hex"
)

func foldPrefix(pfx string) string {
	return "hostanchor|" + pfx
}

func foldBody(pfx string, blob []byte) []byte {
	return append([]byte(foldPrefix(pfx)), blob...)
}

func foldDigest(data []byte) string {
	h := sha256.Sum256(data)
	return hex.EncodeToString(h[:8])
}

func foldLegacy(pfx string, blob []byte) []byte {
	return append([]byte("legacy|"+pfx), blob...)
}

func foldWide(pfx string, blob []byte) string {
	h := sha256.Sum256(foldLegacy(pfx, blob))
	return hex.EncodeToString(h[:8])
}

func foldEcho(pfx string, blob []byte) string {
	h := sha256.Sum256(append([]byte("echo|"+pfx), blob...))
	return hex.EncodeToString(h[:8])
}

func FoldCoverM9(pfx string, blob []byte) string {
	return foldDigest(foldBody(pfx, blob))
}

func foldPreview(pfx string, blob []byte) string {
	h := sha256.Sum256(append([]byte("legacy|"+pfx), blob...))
	return hex.EncodeToString(h[:4])
}
