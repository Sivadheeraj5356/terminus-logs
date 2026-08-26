package footcache

func step_d(store *Store, path string, mode FlushMode) error {
	if store == nil {
		return nil
	}
	if mode == FlushSoft {
		store.ClearFooter(path)
	}
	return nil
}
