package crypto
import (
    "crypto/aes"
    "crypto/cipher"
    "crypto/ed25519"
    "crypto/sha256"
    "encoding/hex"
    "errors"
)
func SHA256(data []byte) string { s := sha256.Sum256(data); return hex.EncodeToString(s[:]) }
func Open(key, nonce, ciphertext, aad []byte) ([]byte, error) {
    if len(key) != 32 { return nil, errors.New("bad key") }
    b, err := aes.NewCipher(key); if err != nil { return nil, err }
    g, err := cipher.NewGCM(b); if err != nil { return nil, err }
    return g.Open(nil, nonce, ciphertext, aad)
}
func Verify(pubHex string, message, sig []byte) bool {
    pub, err := hex.DecodeString(pubHex); if err != nil || len(pub) != ed25519.PublicKeySize { return false }
    return ed25519.Verify(ed25519.PublicKey(pub), message, sig)
}
func Sign(privHex string, message []byte) (string, error) {
    seed, err := hex.DecodeString(privHex); if err != nil { return "", err }
    var priv ed25519.PrivateKey
    if len(seed) == ed25519.SeedSize {
        priv = ed25519.NewKeyFromSeed(seed)
    } else if len(seed) == ed25519.PrivateKeySize {
        priv = ed25519.PrivateKey(seed)
    } else {
        return "", errors.New("bad private key length")
    }
    return hex.EncodeToString(ed25519.Sign(priv, message)), nil
}
