package recovery
import ("encoding/base64"; "encoding/hex"; "fmt"; "os"; "path/filepath"; "sort"; "vaultqualify/internal/crypto"; "vaultqualify/internal/envelope"; "vaultqualify/internal/model")
            func Organizations(shares []map[string]any, ledger []map[string]any, manifestKey, wrapID, objectID string, epoch int) ([]string, error) {
        _ = ledger; _ = manifestKey; _ = epoch
        ids := map[string]bool{}
        for _, share := range shares {
            if share["wrap_id"] != wrapID || share["object_id"] != objectID { continue }
            ids[share["alias_id"].(string)] = true
        }
        out := make([]string, 0, len(ids)); for id := range ids { out = append(out, id) }
        sort.Strings(out); return out, nil
    }
func Decrypt(vault string, env model.Envelope) ([]byte, error) {
    key, err := base64.StdEncoding.DecodeString(env.WrappedDataKey); if err != nil { return nil, err }
    if crypto.SHA256(key) != env.DataKeyCommitment { return nil, fmt.Errorf("data key commitment mismatch") }
    nonce, err := hex.DecodeString(env.Nonce); if err != nil { return nil, err }
    cipherBytes, err := os.ReadFile(filepath.Join(vault, "objects", env.StorageName)); if err != nil { return nil, err }
    if crypto.SHA256(cipherBytes) != env.CiphertextSHA256 { return nil, fmt.Errorf("ciphertext commitment mismatch") }
    aad, err := envelope.AAD(env); if err != nil { return nil, err }
    plain, err := crypto.Open(key, nonce, cipherBytes, aad); if err != nil { return nil, err }
    if crypto.SHA256(plain) != env.PlaintextSHA256 { return nil, fmt.Errorf("plaintext commitment mismatch") }
    return plain, nil
}
