package pol

import (
	"time"

	"baylock/internal/domain"
)

// Event is a validated journal row applied by the engine.
type Event struct {
	EventID        string
	Principal      string
	Operation      string
	ViewID         string
	LogicalTime    time.Time
	LogicalTimeStr string
	Seq            int
	SourceReplica  string
	TargetEventID  string
	ExpiresAt      string
	Amount         *int
	Epoch          int
	LineIndex      int
}

type PrincipalState struct {
	Principal          string
	Failures           int
	Locked             bool
	Suspended          bool
	SuspendedByReplica string
	Epoch              int
	LastEventID        string
	LastLogicalTime    string
}

type Engine struct {
	Principals        map[string]*PrincipalState
	Tallies           map[string]*domain.Tally
	SeenEventIDs      map[string]map[string]any
	Applied           map[string]*Event
	RejectedIDs       map[string]struct{}
	Reversed          map[string]struct{}
	SeqHighwater      map[string]int
	GraceExpires      map[string]string
	CorrectionPrev    map[string]int
	ActiveView        string
	ActivePrincipal   string
	AppliedCount      int
	RejectedCount     int
	SkippedIdempotent int
	Rejections        []domain.Rejection
	MaxLogicalTime    time.Time
}

func NewEngine() *Engine {
	return &Engine{
		Principals:     map[string]*PrincipalState{},
		Tallies:        map[string]*domain.Tally{},
		SeenEventIDs:   map[string]map[string]any{},
		Applied:        map[string]*Event{},
		RejectedIDs:    map[string]struct{}{},
		Reversed:       map[string]struct{}{},
		SeqHighwater:   map[string]int{},
		GraceExpires:   map[string]string{},
		CorrectionPrev: map[string]int{},
		ActiveView:     domain.ViewHost,
	}
}

// ProcessLines is unfinished.
func (e *Engine) ProcessLines(lines [][]byte) {
	_ = lines
}

// ApplyGraceExpirations is unfinished.
func (e *Engine) ApplyGraceExpirations(now time.Time) {
	_ = now
}

func (e *Engine) Watermark() time.Time {
	return e.MaxLogicalTime
}

// PersistTallies is unfinished.
func (e *Engine) PersistTallies() error {
	return nil
}

// SeedTally is unfinished.
func (e *Engine) SeedTally(principal string, failures int, locked bool) {
	_ = principal
	_ = failures
	_ = locked
}

// SortEvents is unfinished.
func SortEvents(lines [][]byte) [][]byte {
	return lines
}
