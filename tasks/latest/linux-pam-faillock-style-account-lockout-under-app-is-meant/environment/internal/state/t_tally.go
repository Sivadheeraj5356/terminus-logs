package state

import (
	"encoding/json"
	"os"
	"path/filepath"

	"baylock/internal/config"
	"baylock/internal/domain"
)

func authPath(principal string) string {
	return filepath.Join(config.AuthStore, principal+".tally")
}

func HostShadowPath(principal string) string {
	return filepath.Join(config.HostViewDir, principal+".tally")
}

func nsShadowPath(principal string) string {
	return filepath.Join(config.NSViewDir, principal+".tally")
}

// NsPathFor is unfinished: view coordination is not implemented yet.
func NsPathFor(viewID, principal string) string {
	_ = viewID
	return HostShadowPath(principal)
}

func ViewShadowPath(viewID, principal string) string {
	if viewID == domain.ViewNS {
		return nsShadowPath(principal)
	}
	return HostShadowPath(principal)
}

func LoadTally(path string) (*domain.Tally, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			base := filepath.Base(path)
			principal := base
			if len(base) > 6 && base[len(base)-6:] == ".tally" {
				principal = base[:len(base)-6]
			}
			return &domain.Tally{Principal: principal, Failures: 0, Locked: false}, nil
		}
		return nil, err
	}
	var tally domain.Tally
	if err := json.Unmarshal(data, &tally); err != nil {
		return nil, err
	}
	return &tally, nil
}

func SaveTally(path string, tally *domain.Tally) error {
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(tally, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0o644)
}

// SyncShadows is unfinished.
func SyncShadows(principal string, tally *domain.Tally) error {
	_ = principal
	_ = tally
	return nil
}

// BumpTally is unfinished: does not write durable auth-store tallies yet.
func BumpTally(viewID, principal string) (int, error) {
	_ = viewID
	_ = principal
	return 0, nil
}

func ReadViewState(viewID, principal string) (*domain.ViewState, error) {
	path := NsPathFor(viewID, principal)
	tally, err := LoadTally(path)
	if err != nil {
		return nil, err
	}
	return &domain.ViewState{
		ViewID:       viewID,
		Principal:    principal,
		FailureCount: tally.Failures,
		Locked:       tally.Locked,
	}, nil
}

// WriteAuthTally is unfinished.
func WriteAuthTally(principal string, failures int, locked bool) error {
	_ = principal
	_ = failures
	_ = locked
	return nil
}

func LoadAuthTally(principal string) (*domain.Tally, error) {
	return LoadTally(authPath(principal))
}

func AuthPath(principal string) string {
	return authPath(principal)
}

func LoadTallyFromPath(path string) (*domain.Tally, error) {
	return LoadTally(path)
}

func CloneTally(src *domain.Tally) *domain.Tally {
	if src == nil {
		return &domain.Tally{}
	}
	return &domain.Tally{Principal: src.Principal, Failures: src.Failures, Locked: src.Locked}
}

func ApplyAuthMutation(principal string, mutate func(*domain.Tally)) error {
	_ = principal
	_ = mutate
	return nil
}
