package model
type Manifest struct {
    SchemaVersion int `json:"schema_version"`
    PolicyID string `json:"policy_id"`
    QualificationEpoch int `json:"qualification_epoch"`
    AuthorityPublicKey string `json:"authority_public_key"`
    Threshold int `json:"threshold"`
    Objects []struct {
        ObjectID string `json:"object_id"`
        LogicalPath string `json:"logical_path"`
    } `json:"objects"`
}
type Envelope struct {
    SchemaVersion int `json:"schema_version"`
    ObjectID string `json:"object_id"`
    LogicalPath string `json:"logical_path"`
    StorageName string `json:"storage_name"`
    CustodyEpoch int `json:"custody_epoch"`
    Nonce string `json:"nonce"`
    CiphertextSHA256 string `json:"ciphertext_sha256"`
    DataKeyCommitment string `json:"data_key_commitment"`
    PlaintextSHA256 string `json:"plaintext_sha256"`
    ActiveWrapID string `json:"active_wrap_id"`
    WrappedDataKey string `json:"wrapped_data_key"`
}
type InventoryRow struct {
    LogicalPath string `json:"logical_path"`
    PlaintextSize int `json:"plaintext_size"`
    PlaintextSHA256 string `json:"plaintext_sha256"`
    DataKeyCommitment string `json:"data_key_commitment"`
    EnvelopeVersion int `json:"envelope_version"`
    CustodyEpoch int `json:"custody_epoch"`
    ActiveRewrapTransactionID string `json:"active_rewrap_transaction_id"`
    Organizations []string `json:"organizations"`
    RecoveryStatus string `json:"recovery_status"`
}
