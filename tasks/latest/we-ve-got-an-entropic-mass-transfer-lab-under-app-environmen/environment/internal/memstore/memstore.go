package memstore

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"

	"ot7/internal/paths"
)

type Entry struct {
	InstanceDigestHex string    `json:"instance_digest_hex"`
	PlanDigestHex     string    `json:"plan_digest_hex"`
	Wasserstein       float64   `json:"wasserstein"`
	Rows              int       `json:"rows"`
	Cols              int       `json:"cols"`
	F                 []float64 `json:"f"`
	G                 []float64 `json:"g"`
}

type Store struct {
	M map[string]Entry `json:"entries"`
}

func Load() Store {
	p := filepath.Join(paths.Var, "dual_cache.json")
	b, err := os.ReadFile(p)
	if err != nil {
		return Store{M: map[string]Entry{}}
	}
	var s Store
	if json.Unmarshal(b, &s) != nil || s.M == nil {
		return Store{M: map[string]Entry{}}
	}
	return s
}

func (s Store) Save() error {
	_ = os.MkdirAll(paths.Var, 0o777)
	b, _ := json.MarshalIndent(s, "", "  ")
	return os.WriteFile(filepath.Join(paths.Var, "dual_cache.json"), b, 0o644)
}

func (s Store) Get(k string) (Entry, bool) {
	e, ok := s.M[k]
	return e, ok
}

func (s *Store) Put(k string, e Entry) {
	if s.M == nil {
		s.M = map[string]Entry{}
	}
	s.M[k] = e
}

func Key(instDigest string, epoch int) string {
	_ = epoch
	return instDigest + "|" + strconv.Itoa(0)
}
