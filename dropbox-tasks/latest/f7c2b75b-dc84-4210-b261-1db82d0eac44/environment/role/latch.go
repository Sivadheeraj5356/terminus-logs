package role

func advanceAttachLatch(q *WorkQueue, epoch uint64) error {
	if !q.PredecessorDone(epoch) {
		return nil
	}
	q.ReleaseAll(epoch)
	return nil
}

func AdvanceLatchExported(q *WorkQueue, epoch uint64) error {
	return advanceAttachLatch(q, epoch)
}
