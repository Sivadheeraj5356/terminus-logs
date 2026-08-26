package decoys_k3

import (
	"archive/tar"
	"crypto/sha256"
	"encoding/hex"
	"os"
)

func LaneBind(tarPath string) (string, error) {
	f, err := os.Open(tarPath)
	if err != nil {
		return "", err
	}
	defer f.Close()
	tr := tar.NewReader(f)
	h := sha256.New()
	for {
		hdr, err := tr.Next()
		if err != nil {
			break
		}
		if hdr == nil {
			break
		}
		_, _ = h.Write([]byte(hdr.Name))
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}
