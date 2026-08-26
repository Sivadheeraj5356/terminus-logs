package pth

import (
	"os"
	"path/filepath"
)

// Root returns the environment root for fixtures, docs, and durable state.
func Root() string {
	if v := os.Getenv("LB_ROOT"); v != "" {
		return v
	}
	return "/app/environment"
}

// VarRoot returns the scratch root for run-local shadow hints and plans.
func VarRoot() string {
	if v := os.Getenv("LB_VAR"); v != "" {
		return v
	}
	return "/app/var/qxhub"
}

func SessionPath() string    { return filepath.Join(Root(), "state", "session.registry") }
func JournalDir() string     { return filepath.Join(Root(), "state", "journal") }
func LedgerPath() string     { return filepath.Join(Root(), "state", "ledger.jsonl") }
func GenerationsDir() string { return filepath.Join(Root(), "state", "generations") }
func CurrentPath() string    { return filepath.Join(Root(), "state", "current") }
func QuarantineDir() string  { return filepath.Join(Root(), "state", "quarantine") }
func TxnsDir() string        { return filepath.Join(Root(), "state", "txns") }
func LaneShadow() string     { return filepath.Join(VarRoot(), "lane.shadow") }
func PlansDir() string       { return filepath.Join(VarRoot(), "plans") }

// EnsureDirs creates the runtime directories used by the drive pipeline.
func EnsureDirs() error {
	for _, d := range []string{
		JournalDir(),
		GenerationsDir(),
		QuarantineDir(),
		TxnsDir(),
		VarRoot(),
		PlansDir(),
	} {
		if err := os.MkdirAll(d, 0o755); err != nil {
			return err
		}
	}
	return nil
}
