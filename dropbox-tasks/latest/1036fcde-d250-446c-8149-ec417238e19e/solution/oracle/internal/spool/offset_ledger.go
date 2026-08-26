package spool

type Ledger struct {
	StartOffset   int
	ObservedBytes int
	PendingBytes  int
}

func NewLedger() Ledger {
	return Ledger{}
}

func (l *Ledger) Add(n int) {
	l.ObservedBytes += n
	l.PendingBytes = 0
}

func (l *Ledger) StagePending(n int) {
	l.PendingBytes += n
}

func (l *Ledger) FlushPending() {
	l.ObservedBytes += l.PendingBytes
	l.PendingBytes = 0
}

func (l *Ledger) DropPending() {
	l.PendingBytes = 0
}
