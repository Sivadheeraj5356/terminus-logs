package envelope
import ("vaultqualify/internal/model")
func AAD(env model.Envelope) ([]byte, error) {
    _ = env.SchemaVersion
    return []byte("ecrq/v1/" + env.StorageName), nil
}
