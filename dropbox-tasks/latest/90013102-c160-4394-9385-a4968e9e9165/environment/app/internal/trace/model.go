package trace

type ForwardEvidence struct {
	BackendDigest   string `json:"backend_digest"`
	BackendLength   int    `json:"backend_length"`
	Forwarded       bool   `json:"forwarded"`
	ResponseStatus  int    `json:"response_status,omitempty"`
}

type SpoolEvidence struct {
	RecordID     string `json:"record_id"`
	State        string `json:"state"`
	ReplayCount  int    `json:"replay_count"`
	SealValid    bool   `json:"seal_valid"`
}

type Entry struct {
	RequestID         string            `json:"request_id"`
	Source            string            `json:"source"`
	WireDigest        string            `json:"wire_digest"`
	EntityDigest      string            `json:"entity_digest"`
	EntityLength      int               `json:"entity_length"`
	Decision          string            `json:"decision"`
	Reason            string            `json:"reason"`
	SignatureVersion  int               `json:"signature_version"`
	Tenant            string            `json:"tenant"`
	KeyID             string            `json:"key_id"`
	KeyEpoch          int               `json:"key_epoch"`
	ProfileID         string            `json:"profile_id"`
	ProfileEpoch      int               `json:"profile_epoch"`
	CanonicalDigest   string            `json:"canonical_digest"`
	CacheHit          bool              `json:"cache_hit"`
	Method            string            `json:"method"`
	Authority         string            `json:"authority"`
	CanonicalTarget   string            `json:"canonical_target"`
	CanonicalHeaders  map[string]string `json:"canonical_headers"`
	BodySHA256        string            `json:"body_sha256"`
	BodyLength        int               `json:"body_length"`
	Forward           *ForwardEvidence  `json:"forward"`
	Spool             *SpoolEvidence    `json:"spool"`
	AuditRecordDigest string            `json:"audit_record_digest"`
}

type Document struct {
	SchemaVersion  string  `json:"schema_version"`
	RunMode        string  `json:"run_mode"`
	CatalogDigest  string  `json:"catalog_digest"`
	Entries        []Entry `json:"entries"`
}
