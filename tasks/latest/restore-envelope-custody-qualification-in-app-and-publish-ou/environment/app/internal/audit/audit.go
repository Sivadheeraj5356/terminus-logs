package audit
import ("encoding/base64"; "path/filepath"; "vaultqualify/internal/canon"; "vaultqualify/internal/crypto"; "vaultqualify/internal/iojson")
func Sign(vault string, statement map[string]any) (map[string]any, error) {
    var priv struct { PrivateKey string `json:"private_key"` }
    var pub struct { PublicKey string `json:"public_key"` }
    if err := iojson.ReadJSON(filepath.Join(vault, "keys", "appliance-audit-private.json"), &priv); err != nil { return nil, err }
    if err := iojson.ReadJSON(filepath.Join(vault, "keys", "appliance-audit-public.json"), &pub); err != nil { return nil, err }
    payload, err := canon.Marshal(statement); if err != nil { return nil, err }
    sig, err := crypto.Sign(priv.PrivateKey, payload); if err != nil { return nil, err }
    return map[string]any{
        "payload": base64.StdEncoding.EncodeToString(payload),
        "public_key": pub.PublicKey,
        "signatures": []map[string]string{{"keyid": "audit-1", "sig": sig}},
    }, nil
}
