package pkitypes

type Certificate struct {
	Serial        string `json:"serial"`
	Subject       string `json:"subject"`
	IssuerSerial  string `json:"issuer_serial"`
	NotBefore     string `json:"not_before"`
	NotAfter      string `json:"not_after"`
	BodyDigest    string `json:"body_digest"`
	SignatureOK   bool   `json:"signature_ok"`
	Filename      string `json:"filename"`
}

type CTEntry struct {
	Serial    string `json:"serial"`
	LeafIndex int    `json:"leaf_index"`
	Timestamp string `json:"timestamp"`
	LeafHash  string `json:"leaf_hash"`
}

type STH struct {
	TreeSize  int    `json:"tree_size"`
	Timestamp string `json:"timestamp"`
	RootHash  string `json:"root_hash"`
}

type InclusionProof struct {
	Serial    string   `json:"serial"`
	TreeSize  int      `json:"tree_size"`
	LeafIndex int      `json:"leaf_index"`
	Path      []string `json:"path"`
}

type Revocation struct {
	Serial    string `json:"serial"`
	RevokedAt string `json:"revoked_at"`
}

type Issuance struct {
	Serial    string `json:"serial"`
	IssuedAt  string `json:"issued_at"`
	CAID      string `json:"ca_id"`
}

type MerkleRow struct {
	Serial    string `json:"serial"`
	Filename  string `json:"filename"`
	LeafIndex int    `json:"leaf_index"`
	LeafHash  string `json:"leaf_hash"`
}

type MerkleSnapshot struct {
	BundleID        string      `json:"bundle_id"`
	MerkleRowDigest string      `json:"merkle_row_digest,omitempty"`
	Rows            []MerkleRow `json:"rows"`
}

type DispositionRow struct {
	Serial      string `json:"serial"`
	Disposition string `json:"disposition"`
	Reason      string `json:"reason"`
	TrustScore  int    `json:"trust_score"`
}

type DispositionReport struct {
	BundleID string           `json:"bundle_id"`
	Rows     []DispositionRow `json:"rows"`
}

type TrustedLedger struct {
	BundleID           string   `json:"bundle_id"`
	TrustedSerials     []string `json:"trusted_serials"`
	NeedsReviewSerials []string `json:"needs_review_serials"`
	TrustedCount       int      `json:"trusted_count"`
	CombinedDigest     string   `json:"combined_digest"`
	PublishEpoch       int      `json:"publish_epoch"`
}
