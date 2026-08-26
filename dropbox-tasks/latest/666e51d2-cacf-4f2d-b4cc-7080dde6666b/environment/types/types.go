package types

type StreamRow struct {
	RunLabel  string `json:"run_label,omitempty"`
	SegmentID string `json:"segment_id"`
	Era       int    `json:"era"`
	AttachID  string `json:"attach_id"`
	Track     int    `json:"track"`
	Kind      string `json:"kind"`
	HardLimit int    `json:"hard_limit,omitempty"`
}

type PersistRow struct {
	RunLabel  string `json:"run_label"`
	Era       int    `json:"era"`
	AttachID  string `json:"attach_id"`
	Track     int    `json:"track"`
	HardLimit int    `json:"hard_limit"`
	Retired   bool   `json:"retired"`
}

type PersistDoc struct {
	Rows []PersistRow `json:"rows"`
}

type RunEntry struct {
	TMs       int    `json:"t_ms"`
	RunLabel  string `json:"run_label"`
	Phase     string `json:"phase"`
	SegmentID string `json:"segment_id"`
	Era       int    `json:"era"`
	AttachID  string `json:"attach_id"`
	Outcome   string `json:"outcome"`
}

type RecoveryRun struct {
	Schema  string     `json:"schema"`
	Entries []RunEntry `json:"entries"`
}

type Store struct {
	Rev       int
	AttachID  string
	Track     int
	HardLimit int
}

type Snapshot struct {
	Rev       int
	AttachID  string
	HardLimit int
}

type Segment struct {
	SegmentID string
	Era       int
	AttachID  string
	Track     int
	Kind      string
	HardLimit int
	OK        bool
}

type Residue struct {
	Key  string
	Path string
}

type Row struct {
	RunLabel  string
	SegmentID string
	Era       int
	AttachID  string
}

type RunCtx struct {
	Out []Segment
}

type Gen struct {
	Rev uint64
}

type Tail struct {
	Items []Residue
	Keep  map[string]struct{}
}
