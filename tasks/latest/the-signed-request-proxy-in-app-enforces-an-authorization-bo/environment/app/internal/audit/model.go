package audit

type ReasonCode string

const (
	ReasonAllow             ReasonCode = "allow"
	ReasonSignatureMismatch ReasonCode = "signature_mismatch"
	ReasonMissingSignature  ReasonCode = "missing_signature"
	ReasonKeyRevoked        ReasonCode = "key_revoked"
	ReasonBodyLimit         ReasonCode = "body_limit_exceeded"
	ReasonHeaderPolicy      ReasonCode = "header_policy_violation"
	ReasonReplayQuarantine  ReasonCode = "replay_quarantine"
	ReasonIntegrityFailure  ReasonCode = "integrity_failure"
)

type Record struct {
	Timestamp        string            `json:"timestamp"`
	RequestID        string            `json:"request_id"`
	Source           string            `json:"source"`
	Decision         string            `json:"decision"`
	Reason           ReasonCode        `json:"reason"`
	SignatureVersion int               `json:"signature_version"`
	Tenant           string            `json:"tenant"`
	KeyID            string            `json:"key_id"`
	KeyEpoch         int               `json:"key_epoch"`
	ProfileID        string            `json:"profile_id"`
	ProfileEpoch     int               `json:"profile_epoch"`
	CanonicalDigest  string            `json:"canonical_digest"`
	EntityBodySHA256 string            `json:"entity_body_sha256"`
	CanonicalTarget  string            `json:"canonical_target"`
	CanonicalHeaders map[string]string `json:"canonical_headers"`
	RecordDigest     string            `json:"record_digest,omitempty"`
}
