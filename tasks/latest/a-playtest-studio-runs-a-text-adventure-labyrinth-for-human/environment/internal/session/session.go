// Package session tracks in-memory playtest session state: which world and
// room a session occupies, what it holds, what it has consumed, and which
// reject records it keeps. It never reasons about hints, snapshots, or rules.
package session

import (
	"fmt"
	"sync"
	"sync/atomic"
)

// FailedAttempt records a verb/target pair a session tried that did not
// succeed (missing items, forbidden, or unknown).
type FailedAttempt struct {
	Verb   string `json:"verb"`
	Target string `json:"target"`
}

// Session is one playtester's live position in a world.
type Session struct {
	mu        sync.Mutex
	ID        string
	WorldID   string
	Room      string
	Inventory []string
	Consumed  []string
	Failed    []FailedAttempt
	GatherSeq int
}

// Snapshot is a read-only copy of session fields safe to serialize.
type Snapshot struct {
	ID        string
	WorldID   string
	Room      string
	Inventory []string
	Consumed  []string
	Failed    []FailedAttempt
}

// View returns a defensive copy of the session's current state.
func (s *Session) View() Snapshot {
	s.mu.Lock()
	defer s.mu.Unlock()
	inv := append([]string{}, s.Inventory...)
	cons := append([]string{}, s.Consumed...)
	failed := append([]FailedAttempt{}, s.Failed...)
	if inv == nil {
		inv = []string{}
	}
	if cons == nil {
		cons = []string{}
	}
	if failed == nil {
		failed = []FailedAttempt{}
	}
	return Snapshot{
		ID:        s.ID,
		WorldID:   s.WorldID,
		Room:      s.Room,
		Inventory: inv,
		Consumed:  cons,
		Failed:    failed,
	}
}

func contains(list []string, needle string) bool {
	for _, v := range list {
		if v == needle {
			return true
		}
	}
	return false
}

// AddItem appends an item to the inventory if not already held.
func (s *Session) AddItem(itemID string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if contains(s.Inventory, itemID) {
		return false
	}
	s.Inventory = append(s.Inventory, itemID)
	return true
}

// Consume marks a target as consumed if not already.
func (s *Session) Consume(target string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if contains(s.Consumed, target) {
		return false
	}
	s.Consumed = append(s.Consumed, target)
	return true
}

// MoveTo updates the session's current room.
func (s *Session) MoveTo(room string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.Room = room
}

// RecordFailure appends a deduplicated reject record.
func (s *Session) RecordFailure(verb, target string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	for _, f := range s.Failed {
		if f.Verb == verb && f.Target == target {
			return
		}
	}
	s.Failed = append(s.Failed, FailedAttempt{Verb: verb, Target: target})
}

// BumpGatherSeq increments and returns the session's gather counter.
func (s *Session) BumpGatherSeq() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.GatherSeq++
	return s.GatherSeq
}

var idCounter atomic.Int64

// Store holds every live session for the running oracle process.
type Store struct {
	mu       sync.Mutex
	sessions map[string]*Session
}

// NewStore creates an empty in-memory session store.
func NewStore() *Store {
	return &Store{sessions: make(map[string]*Session)}
}

// Create allocates a new session in worldID starting at room with the
// given starting inventory, and registers it in the store.
func (st *Store) Create(worldID, room string, inventory []string) *Session {
	st.mu.Lock()
	defer st.mu.Unlock()
	id := fmt.Sprintf("sess-%d", idCounter.Add(1))
	if inventory == nil {
		inventory = []string{}
	}
	sess := &Session{
		ID:        id,
		WorldID:   worldID,
		Room:      room,
		Inventory: append([]string(nil), inventory...),
		Consumed:  []string{},
		Failed:    []FailedAttempt{},
	}
	st.sessions[id] = sess
	return sess
}

// Get looks up a session by ID.
func (st *Store) Get(id string) (*Session, bool) {
	st.mu.Lock()
	defer st.mu.Unlock()
	sess, ok := st.sessions[id]
	return sess, ok
}
