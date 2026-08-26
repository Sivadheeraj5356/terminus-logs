package model

// Workflow is the normalized workflow definition after Stage A.
type Workflow struct {
	ID       string            `json:"id"`
	Name     string            `json:"name"`
	Version  string            `json:"version"`
	Epoch    string            `json:"epoch"`
	Metadata map[string]string `json:"metadata"`
	Nodes    []Node            `json:"nodes"`
	Edges    []Edge            `json:"edges"`
}

// Node is a single executable unit in the workflow DAG.
type Node struct {
	ID         string            `json:"id"`
	Name       string            `json:"name"`
	Type       string            `json:"type"`
	TimeoutMs  int               `json:"timeout_ms"`
	MaxRetries int               `json:"max_retries"`
	DependsOn  []string          `json:"depends_on"`
	Params     map[string]string `json:"params"`
	Weight     int               `json:"weight"`
}

// Edge is a directed dependency: From must complete before To.
type Edge struct {
	From string `json:"from"`
	To   string `json:"to"`
}

// ExecutionPlan is the compiled schedule order from Stage B.
type ExecutionPlan struct {
	WorkflowID string   `json:"workflow_id"`
	Order      []string `json:"order"`
	Edges      []Edge   `json:"edges"`
	Digest     string   `json:"digest"`
}

// NodeResult is the outcome of executing one node.
type NodeResult struct {
	NodeID    string `json:"node_id"`
	Status    string `json:"status"`
	Attempts  int    `json:"attempts"`
	Output    string `json:"output"`
	Digest    string `json:"digest"`
	StartedAt string `json:"started_at"`
	EndedAt   string `json:"ended_at"`
	WorkerID  string `json:"worker_id"`
}

// ExecutionRecord is the full Stage C/D execution transcript.
type ExecutionRecord struct {
	WorkflowID   string       `json:"workflow_id"`
	PlanDigest   string       `json:"plan_digest"`
	Results      []NodeResult `json:"results"`
	JournalHash  string       `json:"journal_hash"`
	CompletedAt  string       `json:"completed_at"`
	Status       string       `json:"status"`
	CheckpointID string       `json:"checkpoint_id"`
}

// Checkpoint is a persisted execution snapshot.
type Checkpoint struct {
	ID           string            `json:"id"`
	WorkflowID   string            `json:"workflow_id"`
	Version      int               `json:"version"`
	Completed    []string          `json:"completed"`
	Pending      []string          `json:"pending"`
	Failed       []string          `json:"failed"`
	NodeDigests  map[string]string `json:"node_digests"`
	JournalHash  string            `json:"journal_hash"`
	ParentID     string            `json:"parent_id"`
	CreatedAt    string            `json:"created_at"`
	Metadata     map[string]string `json:"metadata"`
	SnapshotHash string            `json:"snapshot_hash"`
}

// RecoveryResult is the outcome of Stage E failure recovery.
type RecoveryResult struct {
	WorkflowID     string   `json:"workflow_id"`
	CheckpointID   string   `json:"checkpoint_id"`
	CheckpointVer  int      `json:"checkpoint_version"`
	ResumedNodes   []string `json:"resumed_nodes"`
	RolledBack     []string `json:"rolled_back"`
	FinalStatus    string   `json:"final_status"`
	RecoveryDigest string   `json:"recovery_digest"`
}

// ReplayRecord is Stage F deterministic replay output.
type ReplayRecord struct {
	WorkflowID   string       `json:"workflow_id"`
	Events       []ReplayEvent `json:"events"`
	ReplayHash   string       `json:"replay_hash"`
	Epoch        string       `json:"epoch"`
	MatchesExec  bool         `json:"matches_execution"`
}

// ReplayEvent is one ordered event in a replay transcript.
type ReplayEvent struct {
	Seq       int    `json:"seq"`
	NodeID    string `json:"node_id"`
	Action    string `json:"action"`
	Digest    string `json:"digest"`
	Timestamp string `json:"timestamp"`
}

// VerificationReport is Stage G state verification.
type VerificationReport struct {
	WorkflowID       string   `json:"workflow_id"`
	LineageOK        bool     `json:"lineage_ok"`
	GraphOK          bool     `json:"graph_ok"`
	CheckpointOK     bool     `json:"checkpoint_ok"`
	ReplayOK         bool     `json:"replay_ok"`
	HashOK           bool     `json:"hash_ok"`
	Issues           []string `json:"issues"`
	VerificationHash string   `json:"verification_hash"`
}

// Certificate is the Stage H recovery certificate.
type Certificate struct {
	Version          string            `json:"version"`
	WorkflowID       string            `json:"workflow_id"`
	PlanDigest       string            `json:"plan_digest"`
	JournalHash      string            `json:"journal_hash"`
	ReplayHash       string            `json:"replay_hash"`
	RecoveryDigest   string            `json:"recovery_digest"`
	VerificationHash string            `json:"verification_hash"`
	BodyDigest       string            `json:"body_digest"`
	Signature        string            `json:"signature"`
	Provenance       map[string]string `json:"provenance"`
	IssuedAt         string            `json:"issued_at"`
}

// Policy controls runtime behaviour (retries, timeouts, workers).
type Policy struct {
	MaxRetries    int      `json:"max_retries"`
	TimeoutMs     int      `json:"timeout_ms"`
	Workers       []string `json:"workers"`
	StrictMode    bool     `json:"strict_mode"`
	CheckpointEvery int    `json:"checkpoint_every"`
	Seed          string   `json:"seed"`
	Epoch         string   `json:"epoch"`
}
