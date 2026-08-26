package relay

type Lifecycle struct {
	ReaderEpoch    string
	RecyclePending bool
}

func Recycle(lc *Lifecycle, nextReader string) {
	lc.ReaderEpoch = nextReader
	lc.RecyclePending = false
}
