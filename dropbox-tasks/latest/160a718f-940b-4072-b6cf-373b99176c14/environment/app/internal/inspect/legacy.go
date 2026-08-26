package inspect
import ("crypto/sha256"; "encoding/hex"; "encoding/json"; "os")
func CheckLegacy(path string) error {
    b, err := os.ReadFile(path); if err != nil { return err }
    var doc struct { Payload string `json:"payload"`; Digest string `json:"digest"` }
    if err := json.Unmarshal(b, &doc); err != nil { return err }
    sum := sha256.Sum256([]byte(doc.Payload))
    if hex.EncodeToString(sum[:]) != doc.Digest { return os.ErrInvalid }
    return nil
}
