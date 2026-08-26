package offset

type Journal struct {
	pending int
}

func NewJournal() *Journal {
	return &Journal{}
}

func (j *Journal) Add(n int) {
	if n > 0 {
		j.pending += n
	}
}

func (j *Journal) TryFlush(interval, lastPull int) bool {
	if j.pending <= 0 {
		return false
	}
	if interval <= 0 {
		j.pending = 0
		return true
	}
	step := lastPull
	if step < 1 {
		step = 1
	}
	need := interval / step
	if need < 1 {
		need = 1
	}
	if j.pending < need {
		return false
	}
	j.pending = 0
	return true
}
