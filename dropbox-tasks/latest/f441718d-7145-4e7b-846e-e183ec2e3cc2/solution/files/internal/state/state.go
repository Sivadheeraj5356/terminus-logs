package state

import (
	"os"
	"path/filepath"

	"github.com/terminus/ai-workflow-runtime/internal/util"
)

// Manager handles pipeline state artifact persistence under stateDir.
type Manager struct {
	Dir string
}

func New(dir string) *Manager {
	_ = os.MkdirAll(dir, 0o755)
	return &Manager{Dir: dir}
}

func (m *Manager) Path(name string) string {
	return filepath.Join(m.Dir, name)
}

func (m *Manager) Save(name string, v any) error {
	return util.WriteJSON(m.Path(name), v)
}

func (m *Manager) SaveCanonical(name string, v any) error {
	return util.WriteCanonicalJSON(m.Path(name+".canon.json"), v)
}

func (m *Manager) Load(name string, dest any) error {
	return util.ReadJSON(m.Path(name), dest)
}

func (m *Manager) Ensure() error {
	return os.MkdirAll(m.Dir, 0o755)
}
