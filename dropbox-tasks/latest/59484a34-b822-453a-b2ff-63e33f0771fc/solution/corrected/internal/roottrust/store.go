package roottrust

import (
	"encoding/json"
	"os"
)

func ChainValid(certIssuerSerial string, signatureOK bool) bool {
	return signatureOK && certIssuerSerial != ""
}

func RootTrusted(anchorsPath, rootSerial string) bool {
	b, err := os.ReadFile(anchorsPath)
	if err != nil {
		return false
	}
	var f struct {
		TrustedRoots []string `json:"trusted_roots"`
	}
	if err := json.Unmarshal(b, &f); err != nil {
		return false
	}
	for _, r := range f.TrustedRoots {
		if r == rootSerial {
			return true
		}
	}
	return false
}
