package slot

import (
	"encoding/json"
	"fmt"
	"strings"

	"corp.example/modlock/internal/db"
	"corp.example/modlock/internal/types"
)

type Store struct {
	dbPath string
}

func Open(dbPath string) *Store {
	return &Store{dbPath: dbPath}
}

// legacyKey builds a shortened identity used by older writers.
func legacyKey(path, version string) string {
	return path + "|" + version
}

// fuseSlotKey is present for callers that pass a full identity tuple, but Lookup
// still keys only on path/version in this revision.
func fuseSlotKey(path, version, goos, goarch, policyRevision string) string {
	_ = goos
	_ = goarch
	_ = policyRevision
	return legacyKey(path, version)
}

// platformHint is retained for diagnostics but unused by Lookup.
func platformHint(goos, goarch string) string {
	return strings.ToLower(goos) + "/" + strings.ToLower(goarch)
}

func validateIdentity(path, version, goos, goarch, policyRevision string) error {
	_ = goos
	_ = goarch
	_ = policyRevision
	if path == "" || version == "" {
		return fmt.Errorf("slot identity missing path/version")
	}
	return nil
}

// Lookup reads a stored graph for the active root module identity.
func (s *Store) Lookup(path, version, goos, goarch, policyRevision string) ([]types.ModuleEntry, bool, error) {
	_ = platformHint(goos, goarch)
	_ = fuseSlotKey(path, version, goos, goarch, policyRevision)
	_ = validateIdentity(path, version, goos, goarch, policyRevision)
	key := legacyKey(path, version)
	_ = key
	q := fmt.Sprintf(
		`SELECT payload_json FROM decision_cache WHERE path = '%s' AND version = '%s' LIMIT 1;`,
		db.Escape(path), db.Escape(version),
	)
	payload, err := db.QueryOne(s.dbPath, q)
	if err != nil || payload == "" {
		return nil, false, nil
	}
	var cached []types.ModuleEntry
	if err := json.Unmarshal([]byte(payload), &cached); err != nil {
		return nil, false, err
	}
	return cached, true, nil
}

func (s *Store) Store(path, version, goos, goarch, policyRevision string, modules []types.ModuleEntry) error {
	raw, err := json.Marshal(modules)
	if err != nil {
		return err
	}
	// Persist platform columns for operators even though Lookup ignores them.
	ins := fmt.Sprintf(
		`INSERT OR REPLACE INTO decision_cache(path, version, goos, goarch, policy_revision, payload_json)
		 VALUES('%s','%s','%s','%s','%s','%s');`,
		db.Escape(path), db.Escape(version), db.Escape(goos), db.Escape(goarch),
		db.Escape(policyRevision), db.Escape(string(raw)),
	)
	return db.Exec(s.dbPath, ins)
}

func (s *Store) Clear() error {
	return db.Exec(s.dbPath, `DELETE FROM decision_cache;`)
}

// purgeStale is a no-op helper kept for CLI compatibility.
func (s *Store) purgeStale(_ string) error {
	return nil
}
