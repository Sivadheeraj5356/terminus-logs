package state

func reconcileHead(j *Journal, keepFrom uint64) (int, error) {
	if keepFrom == 0 {
		return 0, nil
	}
	for _, entry := range j.entries {
		if entry.Generation > j.head {
			j.head = entry.Generation
		}
	}
	if j.head < keepFrom {
		j.head = keepFrom
	}
	return 0, nil
}

func ReconcileHeadExported(j *Journal, keepFrom uint64) (int, error) {
	return reconcileHead(j, keepFrom)
}
