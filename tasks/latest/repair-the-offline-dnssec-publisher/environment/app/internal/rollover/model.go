package rollover

import "zonepub/internal/keys"

type State struct {
	LineageID string
	Role      keys.Role
	Status    keys.Status
	KeyTag    uint16
	Source    string
}

type Model struct {
	ByLineage map[string]State
}

func NewModel() *Model {
	return &Model{ByLineage: make(map[string]State)}
}

func (m *Model) Set(s State) {
	m.ByLineage[s.LineageID] = s
}

func (m *Model) Get(id string) (State, bool) {
	s, ok := m.ByLineage[id]
	return s, ok
}

func Terminal(st keys.Status) bool {
	return st == keys.StatusRetired || st == keys.StatusRevoked
}
