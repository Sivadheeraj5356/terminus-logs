package qtn

import (
	"linkenv/reg"
)

type Entry struct {
	Row        reg.RowRec `json:"row"`
	AdmitFence uint64     `json:"admit_fence"`
}

type Ledger struct {
	Pending []Entry `json:"pending"`
}

func NewLedger() *Ledger {
	return &Ledger{Pending: []Entry{}}
}

func (l *Ledger) Admit(row reg.RowRec, fence uint64) {
	l.Pending = append(l.Pending, Entry{Row: row, AdmitFence: fence})
}

func (l *Ledger) Promote(epoch, fence uint64) []reg.RowRec {
	_ = epoch
	_ = fence
	var out []reg.RowRec
	for _, e := range l.Pending {
		row := e.Row
		row.Class = reg.ClassInject
		out = append(out, row)
	}
	l.Pending = nil
	return out
}

func (l *Ledger) HasKey(key string) bool {
	for _, e := range l.Pending {
		if e.Row.Key == key {
			return true
		}
	}
	return false
}

func RegistryHasKey(rows []reg.RowRec, key string) bool {
	for _, r := range rows {
		if r.Key == key {
			return true
		}
	}
	return false
}
