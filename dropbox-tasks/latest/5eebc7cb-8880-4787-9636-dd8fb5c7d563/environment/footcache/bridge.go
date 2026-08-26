package footcache

import (
	"fxdesk/internal/model"
	footcacheint "fxdesk/internal/footcache"
)

type Store = footcacheint.Store
type FlushMode = footcacheint.FlushMode

const (
	FlushSoft = footcacheint.FlushSoft
	FlushHard = footcacheint.FlushHard
)

func FlushStore(store *Store, path string, mode FlushMode) error {
	return step_d(store, path, mode)
}

func ApplyWorkState(st *model.WorkState) *Store {
	return footcacheint.ApplyWorkState(st)
}

func SnapshotStore(s *Store, st *model.WorkState) {
	footcacheint.SnapshotStore(s, st)
}
