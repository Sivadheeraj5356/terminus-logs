package authority
import ("encoding/hex"; "vaultqualify/internal/canon"; "vaultqualify/internal/crypto")
func verify(rec map[string]any, manifestKey string) bool {
    signed := map[string]any{}; for k,v := range rec { if k != "signature" { signed[k]=v } }
    b, _ := canon.Marshal(signed); sig, _ := hex.DecodeString(rec["signature"].(string))
    return crypto.Verify(manifestKey, b, sig)
}
            func Authorized(ledger []map[string]any, manifestKey, alias, org string, epoch int) bool {
        _ = epoch
        for _, rec := range ledger {
            if rec["alias_id"] == alias && rec["organization_id"] == org && rec["kind"] == "authorize" {
                return verify(rec, manifestKey)
            }
        }
        return false
    }
