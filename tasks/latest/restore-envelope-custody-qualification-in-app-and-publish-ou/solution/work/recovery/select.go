package recovery
import ("encoding/base64"; "encoding/hex"; "fmt"; "os"; "path/filepath"; "sort"; "vaultqualify/internal/authority"; "vaultqualify/internal/canon"; "vaultqualify/internal/crypto"; "vaultqualify/internal/envelope"; "vaultqualify/internal/model")
            func Organizations(shares []map[string]any, ledger []map[string]any, manifestKey, wrapID, objectID string, epoch int) ([]string, error) {
        orgs := map[string]bool{}
        for _, share := range shares {
            alias := share["alias_id"].(string)
            org := share["organization_id"].(string)
            if share["wrap_id"] != wrapID || share["object_id"] != objectID { continue }
            if !authority.Authorized(ledger, manifestKey, alias, org, epoch) { continue }
            signed := map[string]any{}; for k,v := range share { if k != "signature" { signed[k]=v } }
            b, _ := canon.Marshal(signed); sig, _ := hex.DecodeString(share["signature"].(string))
            pub := ""
            for _, rec := range ledger {
                if rec["alias_id"] == alias && rec["kind"] == "authorize" { pub = rec["public_key"].(string) }
            }
            if !crypto.Verify(pub, b, sig) { continue }
            orgs[org] = true
        }
        out := make([]string, 0, len(orgs)); for o := range orgs { out = append(out, o) }
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
