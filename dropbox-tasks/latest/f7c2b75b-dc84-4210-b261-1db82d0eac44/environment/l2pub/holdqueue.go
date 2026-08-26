package l2pub

func drainQueuedFrames(d *Dispatcher, epoch uint64, barrier <-chan struct{}) error {
	select {
	case <-barrier:
	default:
	}
	d.FlushPending(epoch)
	return nil
}

func DrainQueuedExported(d *Dispatcher, epoch uint64, barrier <-chan struct{}) error {
	return drainQueuedFrames(d, epoch, barrier)
}
