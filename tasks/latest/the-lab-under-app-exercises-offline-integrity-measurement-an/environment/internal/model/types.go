package model

// Node is one path in the namespace tree.
type Node struct {
	Path string `json:"path"`
	Kind string `json:"kind"`
}

// Tree is the path namespace.
type Tree struct {
	Root  string `json:"root"`
	Nodes []Node `json:"nodes"`
}

// Bind carries template fields for one attachment.
type Bind struct {
	Root string `json:"root"`
}

// Clause is one lowered policy attachment.
type Clause struct {
	Tier int    `json:"tier"`
	Verb int    `json:"verb"`
	Root string `json:"root"`
}

// Program is the lowered policy the worker and reconcile pass share.
type Program struct {
	Schema  string         `json:"schema"`
	Verbs   map[string]int `json:"verbs"`
	Clauses []Clause       `json:"clauses"`
}

// Policy is the on-disk policy bundle.
type Policy struct {
	Verbs map[string]int `json:"verbs"`
	Tiers []struct {
		ID   int    `json:"id"`
		File string `json:"file"`
	} `json:"tiers"`
}

// RawClause is one attachment before lowering.
type RawClause struct {
	Tier int             `json:"tier"`
	Verb string          `json:"verb"`
	Bind map[string]string `json:"bind"`
}

// Step is one read in a job.
type Step struct {
	Op   string `json:"op"`
	Path string `json:"path"`
}

// Job is a named read sequence.
type Job struct {
	Name  string `json:"name"`
	Steps []Step `json:"steps"`
}

// Workload is the replay set.
type Workload struct {
	Jobs []Job `json:"jobs"`
}

// TraceEvent is one recorded read.
type TraceEvent struct {
	Path  string `json:"path"`
	Verbs []int  `json:"verbs"`
}

// TraceJob groups events for one job.
type TraceJob struct {
	Name   string       `json:"name"`
	Events []TraceEvent `json:"events"`
}

// Traces is the worker output.
type Traces struct {
	SetID string     `json:"set_id"`
	Jobs  []TraceJob `json:"jobs"`
}

// LogRow is one digest row.
type LogRow struct {
	Path      string `json:"path"`
	DigestHex string `json:"digest_hex"`
}

// MeasureLog is the digest ledger.
type MeasureLog struct {
	SetID string   `json:"set_id"`
	Rows  []LogRow `json:"rows"`
}

// ReportEvent is one reconciled read.
type ReportEvent struct {
	Path    string `json:"path"`
	Logged  bool   `json:"logged"`
	Check   string `json:"check"`
	Verdict string `json:"verdict"`
}

// ReportJob groups report events.
type ReportJob struct {
	Name   string        `json:"name"`
	Events []ReportEvent `json:"events"`
}

// Report is the reconcile roll-up.
type Report struct {
	Schema  string      `json:"schema"`
	SetID   string      `json:"set_id"`
	Aligned bool        `json:"aligned"`
	Jobs    []ReportJob `json:"jobs"`
}

// ManifestEntry is one path's expected digests and checks.
type ManifestEntry struct {
	DigestHex string `json:"digest_hex"`
	HmacHex   string `json:"hmac_hex"`
	SigHex    string `json:"sig_hex"`
}
