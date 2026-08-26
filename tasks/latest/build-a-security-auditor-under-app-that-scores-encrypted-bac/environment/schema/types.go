package schema

// Policy mirrors /app/rules/escrow_matrix.yaml.
type Policy struct {
	Ciphers struct {
		Approved []string `yaml:"approved"`
		Stale    []string `yaml:"stale"`
	} `yaml:"ciphers"`
	Algorithms struct {
		Stale []string `yaml:"stale"`
	} `yaml:"algorithms"`
	Escrow struct {
		MinQuorum int `yaml:"min_quorum"`
	} `yaml:"escrow"`
	Restore struct {
		TrustedSigners []string `yaml:"trusted_signers"`
	} `yaml:"restore"`
	Retention struct {
		RequiresImmutable bool `yaml:"requires_immutable"`
	} `yaml:"retention"`
	Scoring struct {
		CoverageGap            int `yaml:"coverage_gap"`
		UnauthorizedMutation   int `yaml:"unauthorized_mutation"`
		EscrowBreak            int `yaml:"escrow_break"`
		RecoveryWeakness       int `yaml:"recovery_weakness"`
		RetentionTamper        int `yaml:"retention_tamper"`
		RecoveryGuaranteeFail  int `yaml:"recovery_guarantee_fail"`
		StaleDependency        int `yaml:"stale_dependency"`
		RestoreForgery         int `yaml:"restore_forgery"`
		SilentCorruption       int `yaml:"silent_corruption"`
		ResilienceFail         int `yaml:"resilience_fail"`
		Cap                    int `yaml:"cap"`
	} `yaml:"scoring"`
	Tiers map[string]struct {
		Min int `yaml:"min"`
		Max int `yaml:"max"`
	} `yaml:"tiers"`
}

type Object struct {
	ID             string `json:"id"`
	KeyID          string `json:"key_id"`
	Cipher         string `json:"cipher"`
	ContentDigest  string `json:"content_digest"`
	DeclaredDigest string `json:"declared_digest"`
}

type Share struct {
	ID          string `json:"id"`
	Fingerprint string `json:"fingerprint"`
	Revoked     bool   `json:"revoked"`
}

type Key struct {
	ID           string  `json:"id"`
	Role         string  `json:"role"`
	Algorithm    string  `json:"algorithm"`
	State        string  `json:"state"`
	RewrapNeeded bool    `json:"rewrap_needed"`
	RewrapToken  string  `json:"rewrap_token"`
	Threshold    int     `json:"threshold"`
	Shares       []Share `json:"shares"`
}

type Escrow struct {
	RegisteredFingerprints map[string][]string `json:"registered_fingerprints"`
}

type Manifest struct {
	SignedDigests []string `json:"signed_digests"`
}

type Recovery struct {
	PathCount         int  `json:"path_count"`
	RequiresOnlineHSM bool `json:"requires_online_hsm"`
	OfflineColdShare  bool `json:"offline_cold_share"`
	GeographicSplit   bool `json:"geographic_split"`
}

type Retention struct {
	DeclaredDays int  `json:"declared_days"`
	EnforcedDays int  `json:"enforced_days"`
	Immutable    bool `json:"immutable"`
	LegalHold    bool `json:"legal_hold"`
}

type Restore struct {
	ChainOK    bool   `json:"chain_ok"`
	Signer     string `json:"signer"`
	NonceReuse bool   `json:"nonce_reuse"`
}

type Shard struct {
	ID          string `json:"id"`
	DeclaredCRC string `json:"declared_crc"`
	PayloadCRC  string `json:"payload_crc"`
}

type AdversaryTest struct {
	ID        string `json:"id"`
	Surviving bool   `json:"surviving"`
}

type ArchiveFile struct {
	ArchiveID       string          `json:"archive_id"`
	Objects         []Object        `json:"objects"`
	Keys            []Key           `json:"keys"`
	Escrow          Escrow          `json:"escrow"`
	Manifest        Manifest        `json:"manifest"`
	Recovery        Recovery        `json:"recovery"`
	Retention       Retention       `json:"retention"`
	Restore         Restore         `json:"restore"`
	Shards          []Shard         `json:"shards"`
	ExpectedShards  int             `json:"expected_shards"`
	AdversaryTests  []AdversaryTest `json:"adversary_tests"`
}

type Finding struct {
	Kind    string `json:"kind"`
	Subject string `json:"subject"`
	Detail  string `json:"detail"`
}

type CoverageGap struct {
	ObjectID string `json:"object_id"`
	Cipher   string `json:"cipher"`
	Reason   string `json:"reason"`
}

type UnauthorizedMutation struct {
	ObjectID       string `json:"object_id"`
	ContentDigest  string `json:"content_digest"`
	DeclaredDigest string `json:"declared_digest"`
	Reason         string `json:"reason"`
}

type EscrowBreak struct {
	KeyID          string `json:"key_id"`
	ValidShares    int    `json:"valid_shares"`
	RequiredQuorum int    `json:"required_quorum"`
	Reason         string `json:"reason"`
}

type RecoveryWeakness struct {
	Reason string `json:"reason"`
}

type RetentionTamper struct {
	DeclaredDays int    `json:"declared_days"`
	EnforcedDays int    `json:"enforced_days"`
	Reason       string `json:"reason"`
}

type RecoveryGuaranteeFail struct {
	KeyID    string `json:"key_id"`
	ObjectID string `json:"object_id"`
	Reason   string `json:"reason"`
}

type StaleDependency struct {
	Subject string `json:"subject"`
	Kind    string `json:"kind"`
	Value   string `json:"value"`
}

type RestoreForgery struct {
	Signer string `json:"signer"`
	Reason string `json:"reason"`
}

type SilentCorruption struct {
	ShardID string `json:"shard_id"`
	Reason  string `json:"reason"`
}

type ResilienceFail struct {
	TestID string `json:"test_id"`
	Reason string `json:"reason"`
}

type Evidence struct {
	Kind string `json:"kind"`
	Ref  string `json:"ref"`
}

type ArchiveResult struct {
	ArchiveID               string                  `json:"archive_id"`
	TrustTier              string                  `json:"trust_tier"`
	RiskScore               int                     `json:"risk_score"`
	Trustworthiness         int                     `json:"trustworthiness"`
	Findings                []Finding               `json:"findings"`
	CoverageGaps            []CoverageGap           `json:"coverage_gaps"`
	UnauthorizedMutations   []UnauthorizedMutation  `json:"unauthorized_mutations"`
	EscrowBreaks            []EscrowBreak           `json:"escrow_breaks"`
	RecoveryWeaknesses      []RecoveryWeakness      `json:"recovery_weaknesses"`
	RetentionTampers        []RetentionTamper       `json:"retention_tampers"`
	RecoveryGuaranteeFails  []RecoveryGuaranteeFail `json:"recovery_guarantee_fails"`
	StaleDependencies       []StaleDependency       `json:"stale_dependencies"`
	RestoreForgeries        []RestoreForgery        `json:"restore_forgeries"`
	SilentCorruptions       []SilentCorruption      `json:"silent_corruptions"`
	ResilienceFails         []ResilienceFail        `json:"resilience_fails"`
	Evidence                []Evidence              `json:"evidence"`
}

type Summary struct {
	ArchivesAnalyzed     int    `json:"archives_analyzed"`
	ArchivesAtRisk       int    `json:"archives_at_risk"`
	CleanArchives        int    `json:"clean_archives"`
	TotalFindings        int    `json:"total_findings"`
	CriticalArchives     int    `json:"critical_archives"`
	TrustworthinessMean  int    `json:"trustworthiness_mean"`
	ArchivesAbsPath      string `json:"archives_abs_path"`
}

type Report struct {
	Summary  Summary         `json:"summary"`
	Archives []ArchiveResult `json:"archives"`
}
