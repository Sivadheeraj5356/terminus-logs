package app

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"

	"baylock/internal/audit"
	"baylock/internal/config"
	"baylock/internal/domain"
	"baylock/internal/journal"
	"baylock/internal/ns"
	"baylock/internal/ops"
	"baylock/internal/projection"
	"baylock/internal/state"
)

func EnsureDirs() error {
	dirs := []string{
		config.StateDir,
		config.AuthStore,
		config.HostViewDir,
		config.NSViewDir,
		config.OutputDir,
		filepath.Join(config.JournalRoot, "batches"),
	}
	for _, dir := range dirs {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return err
		}
	}
	return nil
}

func LoadRuntime() (*domain.Runtime, error) {
	data, err := os.ReadFile(config.RuntimeFile)
	if err != nil {
		return nil, err
	}
	var rt domain.Runtime
	if err := json.Unmarshal(data, &rt); err != nil {
		return nil, err
	}
	return &rt, nil
}

func SaveRuntime(rt *domain.Runtime) error {
	if err := EnsureDirs(); err != nil {
		return err
	}
	data, err := json.MarshalIndent(rt, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(config.RuntimeFile, data, 0o644)
}

func LoadScenario(path string) (*domain.Scenario, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var sc domain.Scenario
	if err := json.Unmarshal(data, &sc); err != nil {
		return nil, err
	}
	if sc.Principal == "" || sc.Password == "" {
		return nil, errors.New("scenario missing required fields")
	}
	return &sc, nil
}

func ResetOutput() error {
	return os.MkdirAll(config.OutputDir, 0o755)
}

func ClearState() error {
	if err := os.RemoveAll(config.StateDir); err != nil {
		return err
	}
	if err := os.RemoveAll(config.OutputDir); err != nil {
		return err
	}
	return EnsureDirs()
}

func WriteFile(path string, data []byte) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, data, 0o644)
}

func SetupScenario(sc *domain.Scenario) error {
	if err := domain.ValidatePrincipal(sc.Principal); err != nil {
		return err
	}
	if err := domain.ValidatePassword(sc.Password); err != nil {
		return err
	}
	if err := ClearState(); err != nil {
		return err
	}
	rt := &domain.Runtime{
		ActiveView: domain.ViewHost,
		Principal:  sc.Principal,
		Password:   sc.Password,
		Audits:     []domain.AuditRecord{},
	}
	PrimeRuntime(rt)
	return SaveRuntime(rt)
}

func RecordAttempt(password string) (bool, error) {
	rt, err := LoadRuntime()
	if err != nil {
		return false, err
	}
	view := ns.ActiveView(rt)
	viewState, err := state.ReadViewState(view, rt.Principal)
	if err != nil {
		return false, err
	}
	rt.AttemptCount++
	if viewState.Locked {
		if err := SaveRuntime(rt); err != nil {
			return false, err
		}
		return false, nil
	}
	if password != rt.Password {
		audit.WriteAudit(rt, rt.Principal)
		if _, err := state.BumpTally(view, rt.Principal); err != nil {
			return false, err
		}
		if err := SaveRuntime(rt); err != nil {
			return false, err
		}
		return false, nil
	}
	if err := SaveRuntime(rt); err != nil {
		return false, err
	}
	return true, nil
}

func EnterNamespace() error {
	rt, err := LoadRuntime()
	if err != nil {
		return err
	}
	ns.EnterView(rt, domain.ViewNS)
	return SaveRuntime(rt)
}

func UnlockPrincipal(principal string) (bool, error) {
	rt, err := LoadRuntime()
	if err != nil {
		return false, err
	}
	ok, err := ops.PurgeCounters(rt.ActiveView, principal)
	if err != nil {
		return false, err
	}
	return ok, nil
}

func ImportBatch(name, eventsPath string) (bool, error) {
	if err := EnsureDirs(); err != nil {
		return false, err
	}
	return journal.ImportBatch(name, eventsPath)
}

func RebuildProjection() (*projection.Snapshot, error) {
	if err := EnsureDirs(); err != nil {
		return nil, err
	}
	return projection.Rebuild()
}

func WriteAuditTrail(path string) error {
	if err := EnsureDirs(); err != nil {
		return err
	}
	return audit.WriteTrail(path)
}
