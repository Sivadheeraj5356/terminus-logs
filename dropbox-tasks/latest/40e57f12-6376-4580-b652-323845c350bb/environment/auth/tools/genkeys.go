// Key material generator — run at image build only.
package main

import (
	"crypto/ed25519"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"os"
	"path/filepath"
)

type jwk struct {
	Kty string `json:"kty"`
	Crv string `json:"crv,omitempty"`
	Kid string `json:"kid"`
	Use string `json:"use"`
	Alg string `json:"alg"`
	X   string `json:"x"`
}

func main() {
	keysDir := "/app/auth/keys"
	if len(os.Args) > 1 {
		keysDir = os.Args[1]
	}
	if err := os.MkdirAll(keysDir, 0o755); err != nil {
		panic(err)
	}
	specs := []struct {
		kid  string
		seed string
		file string
	}{
		{"key-current", "auth-current-seed-v1", "jwk-active.json"},
		{"key-previous", "auth-previous-seed-v1", "jwk-retiring.json"},
	}
	for _, spec := range specs {
		priv := ed25519.NewKeyFromSeed(seedBytes(spec.seed))
		pkcs8, err := x509.MarshalPKCS8PrivateKey(priv)
		if err != nil {
			panic(err)
		}
		privPEM := pem.EncodeToMemory(&pem.Block{
			Type:  "PRIVATE KEY",
			Bytes: pkcs8,
		})
		if err := os.WriteFile(filepath.Join(keysDir, spec.kid+".pem"), privPEM, 0o600); err != nil {
			panic(err)
		}
		pub := priv.Public().(ed25519.PublicKey)
		doc, err := json.MarshalIndent(jwk{
			Kty: "OKP",
			Crv: "Ed25519",
			Kid: spec.kid,
			Use: "sig",
			Alg: "EdDSA",
			X:   b64url(pub),
		}, "", "  ")
		if err != nil {
			panic(err)
		}
		if err := os.WriteFile(filepath.Join(keysDir, spec.file), append(doc, '\n'), 0o644); err != nil {
			panic(err)
		}
	}
	fmt.Println("keys generated")
}

func seedBytes(label string) []byte {
	h := sha256.Sum256([]byte(label))
	return h[:]
}

func b64url(data []byte) string {
	return base64.RawURLEncoding.EncodeToString(data)
}
