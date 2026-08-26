package authority
import ("encoding/hex"; "vaultqualify/internal/canon"; "vaultqualify/internal/crypto")
func verify(rec map[string]any, manifestKey string) bool {
    signed := map[string]any{}; for k,v := range rec { if k != "signature" { signed[k]=v } }
    b, _ := canon.Marshal(signed); sig, _ := hex.DecodeString(rec["signature"].(string))
    return crypto.Verify(manifestKey, b, sig)
}
            func Authorized(ledger []map[string]any, manifestKey, alias, org string, epoch int) bool {
        aliases := map[string]struct{ org, pub string }{}
        for _, rec := range ledger {
            if !verify(rec, manifestKey) { return false }
            if int(rec["epoch"].(float64)) > epoch { continue }
            switch rec["kind"].(string) {
            case "authorize":
                aliases[rec["alias_id"].(string)] = struct{org, pub string}{rec["organization_id"].(string), rec["public_key"].(string)}
            case "revoke":
                delete(aliases, rec["alias_id"].(string))
            }
        }
        row, ok := aliases[alias]; return ok && row.org == org
    }
