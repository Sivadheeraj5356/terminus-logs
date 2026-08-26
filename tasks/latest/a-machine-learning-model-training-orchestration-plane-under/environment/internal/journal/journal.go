package journal

import (
	"encoding/json"
	"path/filepath"
	"sort"

	"github.com/terminus/ai-workflow-runtime/internal/hash"
	"github.com/terminus/ai-workflow-runtime/internal/util"
)

// Entry is one append-only journal record.
type Entry struct {
	Seq      int               `json:"seq"`
	NodeID   string            `json:"node_id"`
	Action   string            `json:"action"`
	Digest   string            `json:"digest"`
	Meta     map[string]string `json:"meta"`
	WallTime string            `json:"wall_time"`
}

// Log is a persisted execution journal.
type Log struct {
	WorkflowID string  `json:"workflow_id"`
	Entries    []Entry `json:"entries"`
}

func New(workflowID string) *Log {
	return &Log{WorkflowID: workflowID, Entries: []Entry{}}
}

func (l *Log) Append(nodeID, action, digest, wallTime string, meta map[string]string) {
	if meta == nil {
		meta = map[string]string{}
	}
	l.Entries = append(l.Entries, Entry{
		Seq:      len(l.Entries),
		NodeID:   nodeID,
		Action:   action,
		Digest:   digest,
		Meta:     meta,
		WallTime: wallTime,
	})
}

// Hash returns DomainHash("journal-v1", canonical entries payload).
// Contract: entries hashed in ascending seq order with sorted meta keys.
func (l *Log) Hash() (string, error) {
	type wire struct {
		Seq    int               `json:"seq"`
		NodeID string            `json:"node_id"`
		Action string            `json:"action"`
		Digest string            `json:"digest"`
		Meta   map[string]string `json:"meta"`
	}
	entries := make([]Entry, len(l.Entries))
	copy(entries, l.Entries)
	sort.Slice(entries, func(i, j int) bool { return entries[i].Seq > entries[j].Seq })

	wires := make([]wire, 0, len(entries))
	for _, e := range entries {
		wires = append(wires, wire{
			Seq: e.Seq, NodeID: e.NodeID, Action: e.Action, Digest: e.Digest, Meta: e.Meta,
		})
	}
	payload := map[string]any{
		"workflow_id": l.WorkflowID,
		"entries":     wires,
	}
	b, err := util.CanonicalJSON(payload)
	if err != nil {
		return "", err
	}
	return hash.DomainHash("journal-v1", b), nil
}

func (l *Log) Save(path string) error {
	return util.WriteJSON(path, l)
}

func Load(path string) (*Log, error) {
	var l Log
	if err := util.ReadJSON(path, &l); err != nil {
		return nil, err
	}
	return &l, nil
}

func Path(stateDir string) string {
	return filepath.Join(stateDir, "journal.json")
}

// CompactJSON is used by recovery to persist a minimal view.
func (l *Log) CompactJSON() ([]byte, error) {
	return json.Marshal(l)
}
