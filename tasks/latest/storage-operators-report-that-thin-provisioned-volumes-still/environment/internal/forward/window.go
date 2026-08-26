package forward

import "slotmgr/internal/store"

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

func WindowPeak(rows []store.TraceLine) int {
	max := 0
	for _, r := range rows {
		if r.Tick > max {
			max = r.Tick
		}
	}
	return max
}
