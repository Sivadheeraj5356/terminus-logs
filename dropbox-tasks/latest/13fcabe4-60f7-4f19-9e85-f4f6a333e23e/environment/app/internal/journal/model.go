package journal

import (
	"encoding/json"
	"fmt"
	"time"

	"zonepub/internal/manifest"
)

type Phase string

const (
	PhaseStaged   Phase = "staged"
	PhaseAccepted Phase = "accepted"
)

type Record struct {
	Sequence   int                    `json:"sequence"`
	EpochID    string                 `json:"epoch_id"`
	Phase      Phase                  `json:"phase"`
	PlanDigest string                 `json:"plan_digest"`
	ZoneDigest string                 `json:"zone_digest,omitempty"`
	ManifestDigest string             `json:"manifest_digest,omitempty"`
	Serial     uint32                 `json:"serial"`
	Keys       []manifest.JournalKeyState `json:"keys"`
	NSEC3      manifest.NSEC3Fields   `json:"nsec3"`
	Timestamp  string                 `json:"timestamp"`
}

func NewRecord(seq int, epoch, plan string, phase Phase) Record {
	return Record{
		Sequence:   seq,
		EpochID:    epoch,
		Phase:      phase,
		PlanDigest: plan,
		Timestamp:  time.Unix(0, 0).UTC().Format(time.RFC3339),
	}
}

func (r Record) Line() ([]byte, error) {
	b, err := json.Marshal(r)
	if err != nil {
		return nil, err
	}
	return append(b, '\n'), nil
}

func ParseLine(line []byte) (Record, error) {
	var r Record
	if err := json.Unmarshal(line, &r); err != nil {
		return Record{}, fmt.Errorf("journal parse: %w", err)
	}
	if r.Sequence <= 0 || r.EpochID == "" {
		return Record{}, fmt.Errorf("invalid journal record")
	}
	return r, nil
}
