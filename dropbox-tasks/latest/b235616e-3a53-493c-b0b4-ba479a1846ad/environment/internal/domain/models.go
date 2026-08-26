package domain

// Material constants used by operators and documented in /app/docs/lock_rules.md.
// FailureLimit is the authoritative lock threshold (locked when failures >= FailureLimit).
const (
	GeneratedFrom      = "baylock-lock-v2"
	AuditGeneratedFrom = "baylock-audit-v1"
	FailureLimit       = 3
	ViewHost           = "host"
	ViewNS             = "ns"
	MaxFailureCap      = 99
)

type Scenario struct {
	Principal string `json:"principal"`
	Password  string `json:"password"`
	BadRounds int    `json:"bad_rounds"`
}

type Runtime struct {
	ActiveView   string        `json:"active_view"`
	Principal    string        `json:"principal"`
	Password     string        `json:"password"`
	AttemptCount int           `json:"attempt_count"`
	AuditSeq     int           `json:"audit_seq"`
	Audits       []AuditRecord `json:"audits"`
}

type Tally struct {
	Principal string `json:"principal"`
	Failures  int    `json:"failures"`
	Locked    bool   `json:"locked"`
}

type ViewState struct {
	ViewID       string `json:"view_id"`
	Principal    string `json:"principal"`
	FailureCount int    `json:"failure_count"`
	Locked       bool   `json:"locked"`
}

type AuditRecord struct {
	ViewID    string `json:"view_id"`
	Principal string `json:"principal"`
	ActorRef  string `json:"actor_ref"`
	Seq       int    `json:"seq"`
}

type Ledger struct {
	GeneratedFrom    string        `json:"generated_from"`
	AttemptCount     int           `json:"attempt_count"`
	FailureTotal     int           `json:"failure_total"`
	EventLineCount   int           `json:"event_line_count"`
	AppliedCount     int           `json:"applied_count"`
	RejectedCount    int           `json:"rejected_count"`
	ProjectionDigest string        `json:"projection_digest"`
	Views            []ViewState   `json:"views"`
	Audits           []AuditRecord `json:"audits"`
	LedgerDigest     string        `json:"ledger_digest"`
}

type AuditTrail struct {
	GeneratedFrom    string           `json:"generated_from"`
	BatchCount       int              `json:"batch_count"`
	JournalDigest    string           `json:"journal_digest"`
	ProjectionDigest string           `json:"projection_digest"`
	Batches          []map[string]any `json:"batches"`
	AuditDigest      string           `json:"audit_digest"`
}
