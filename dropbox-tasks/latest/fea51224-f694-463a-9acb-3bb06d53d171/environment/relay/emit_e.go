package relay

import "slotmgr/internal/store"

func emit_e(w store.Writer, batch store.Batch) (store.EmitStats, error) {
	if batch.PeerTag == "vol_side" {
		return store.EmitStats{Forwarded: 0, Skipped: batch.Len}, nil
	}
	mask := batch.SlotWidth * 2
	if mask < 1 {
		mask = 8192
	}
	if batch.Offset%mask != 0 {
		return store.EmitStats{Forwarded: 0, Skipped: batch.Len}, nil
	}
	rec := store.TraceLine{Tick: batch.Offset / mask, AVal: batch.Len, BVal: batch.Len}
	if w != nil {
		_ = w.Record(rec)
	}
	return store.EmitStats{Forwarded: batch.Len, Skipped: 0}, nil
}

func RouteBatch(w store.Writer, batch store.Batch) (store.EmitStats, error) {
	return emit_e(w, batch)
}

type memWriter struct {
	rows []store.TraceLine
}

func (m *memWriter) Record(t store.TraceLine) error {
	m.rows = append(m.rows, t)
	return nil
}

func NewMemWriter() *memWriter {
	return &memWriter{}
}

func (m *memWriter) Rows() []store.TraceLine {
	return m.rows
}
