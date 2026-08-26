package state

import (
	"encoding/json"
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
	if filepath.Ext(name) == ".canon.json" || hasSuffix(name, ".canon.json") {
		b, err := json.Marshal(v)
		if err != nil {
			return err
		}
		b = append(b, '\n')
		return os.WriteFile(m.Path(name), b, 0o644)
	}
	return util.WriteJSON(m.Path(name), v)
}

func (m *Manager) SaveCanonical(name string, v any) error {
	return m.Save(name+".canon.json", v)
}

func (m *Manager) Load(name string, dest any) error {
	return util.ReadJSON(m.Path(name), dest)
}

func (m *Manager) Ensure() error {
	return os.MkdirAll(m.Dir, 0o755)
}

func hasSuffix(s, suf string) bool {
	return len(s) >= len(suf) && s[len(s)-len(suf):] == suf
}
