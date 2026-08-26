package vivostat

import "sync"

type Metrics struct {
	mu           sync.Mutex
	attachEvents uint64
	replayEvents uint64
}

func NewMetrics() *Metrics {
	return &Metrics{}
}

func (m *Metrics) IncAttach() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.attachEvents++
}

func (m *Metrics) IncReplay() {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.replayEvents++
}

func (m *Metrics) AttachCount() uint64 {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.attachEvents
}

func (m *Metrics) ReplayCount() uint64 {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.replayEvents
}
