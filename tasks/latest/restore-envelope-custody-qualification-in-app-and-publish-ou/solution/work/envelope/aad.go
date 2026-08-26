package envelope
import ("fmt"; "vaultqualify/internal/model")
func AAD(env model.Envelope) ([]byte, error) {
    if env.SchemaVersion == 1 { return []byte("ecrq/v1/" + env.StorageName), nil }
    if env.SchemaVersion == 2 { return []byte("ecrq/v2/" + env.LogicalPath + "/" + env.ObjectID), nil }
    return nil, fmt.Errorf("unsupported envelope version")
}
