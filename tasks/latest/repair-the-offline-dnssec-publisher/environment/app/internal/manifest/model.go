package manifest

type NSEC3Fields struct {
	Algorithm  uint8  `json:"algorithm"`
	Flags      uint8  `json:"flags"`
	Iterations uint16 `json:"iterations"`
	Salt       string `json:"salt"`
}

type KeyMeta struct {
	LineageID  string `json:"lineage_id"`
	MaterialID string `json:"material_id,omitempty"`
	Role       string `json:"role"`
	Status     string `json:"status"`
	KeyTag     uint16 `json:"key_tag"`
	Algorithm  uint8  `json:"algorithm"`
	PublicKey  string `json:"public_key_b64"`
}

type JournalKeyState struct {
	LineageID string `json:"lineage_id"`
	Role      string `json:"role"`
	Status    string `json:"status"`
	KeyTag    uint16 `json:"key_tag"`
}

type Document struct {
	SchemaVersion int         `json:"schema_version"`
	Origin        string      `json:"origin"`
	Epoch         int64       `json:"epoch"`
	EpochID       string      `json:"epoch_id"`
	PlanDigest    string      `json:"plan_digest"`
	ZoneDigest    string      `json:"zone_digest"`
	InputDigest   string      `json:"input_digest"`
	Serial        uint32      `json:"serial"`
	Keys          []KeyMeta   `json:"keys"`
	NSEC3         NSEC3Fields `json:"nsec3"`
	SignatureStart int64      `json:"signature_start"`
	SignatureEnd   int64      `json:"signature_end"`
}

type CommitRecord struct {
	EpochID        string      `json:"epoch_id"`
	PlanDigest     string      `json:"plan_digest"`
	ZoneDigest     string      `json:"zone_digest"`
	ManifestDigest string      `json:"manifest_digest"`
	Serial         uint32      `json:"serial"`
	NSEC3          NSEC3Fields `json:"nsec3"`
	SignatureStart int64       `json:"signature_start"`
	SignatureEnd   int64       `json:"signature_end"`
}

type SnapshotV1 struct {
	SchemaVersion int    `json:"schema_version"`
	Origin        string `json:"origin"`
	Serial        uint32 `json:"serial"`
	Keys          []SnapshotKeyV1 `json:"keys"`
}

type SnapshotKeyV1 struct {
	Role      string `json:"role"`
	Status    string `json:"status"`
	KeyTag    uint16 `json:"key_tag"`
	Algorithm uint8  `json:"algorithm"`
	Flags     uint16 `json:"flags"`
	PublicKey string `json:"public_key_b64"`
}
