package emit

import (
	"encoding/json"
	"os"
	"path/filepath"
	"github.com/terminus/hopledger/digest"
)

type LinkRow struct {
	LinkID        string `json:"link_id"`
	Open          bool   `json:"open"`
	Quarantined   bool   `json:"quarantined"`
	HopCount      int    `json:"hop_count"`
	SumMs         int    `json:"sum_ms"`
	MaxMs         int    `json:"max_ms"`
	AlarmBreaches int    `json:"alarm_breaches"`
	SLAMs         int    `json:"sla_ms"`
	Buckets       []int  `json:"buckets"`
	LastEpoch     int    `json:"last_epoch"`
	LastSeq       int    `json:"last_seq"`
}

type Report struct {
	SchemaVersion       int       `json:"schema_version"`
	EpochsSeen          int       `json:"epochs_seen"`
	AppliedEvents       int       `json:"applied_events"`
	CancelledEvents     int       `json:"cancelled_events"`
	SupersededEvents    int       `json:"superseded_events"`
	DuplicateRawEvents  int       `json:"duplicate_raw_events"`
	SuppressedHops      int       `json:"suppressed_hops"`
	OpenLinkCount       int       `json:"open_link_count"`
	QuarantinedCount    int       `json:"quarantined_count"`
	AlarmBreachTotal    int       `json:"alarm_breach_total"`
	PolicyDigest        string    `json:"policy_digest"`
	PolicyLineageDigest string    `json:"policy_lineage_digest"`
	RawInputDigest      string    `json:"raw_input_digest"`
	Links               []LinkRow `json:"links"`
}

type AuditEntry struct {
	Decision string `json:"decision"`
	Epoch    int    `json:"epoch"`
	Seq      int    `json:"seq"`
	Lane     string `json:"lane"`
	Source   string `json:"source"`
	OpID     string `json:"op_id"`
	Rev      int    `json:"rev"`
	Kind     string `json:"kind"`
	Reason   string `json:"reason"`
	Link     string `json:"link"`
}

func (a AuditEntry) ToMap() map[string]interface{} {
	return map[string]interface{}{
		"decision": a.Decision,
		"epoch":    a.Epoch,
		"seq":      a.Seq,
		"lane":     a.Lane,
		"source":   a.Source,
		"op_id":    a.OpID,
		"rev":      a.Rev,
		"kind":     a.Kind,
		"reason":   a.Reason,
		"link":     a.Link,
	}
}

func WriteReport(path string, report *Report) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	raw, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(raw, '\n'), 0o644)
}

func WriteDigest(path, sum string) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, []byte(sum+"\n"), 0o644)
}

func WriteAudit(path string, audit []AuditEntry) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	var buf []byte
	for _, entry := range audit {
		canon, err := digest.CanonicalizeStruct(entry.ToMap())
		if err != nil {
			return err
		}
		line := digest.CanonicalJSON(canon) + "\n"
		buf = append(buf, []byte(line)...)
	}
	return os.WriteFile(path, buf, 0o644)
}

func AuditMaps(audit []AuditEntry) []map[string]interface{} {
	out := make([]map[string]interface{}, len(audit))
	for i, entry := range audit {
		out[i] = entry.ToMap()
	}
	return out
}

func CleanupOutputs(paths ...string) {
	for _, p := range paths {
		if p != "" {
			_ = os.Remove(p)
		}
	}
}

// ReportCanon returns canonical report object for digest computation.
func ReportCanon(report *Report) (interface{}, error) {
	return digest.CanonicalizeStruct(report)
}
