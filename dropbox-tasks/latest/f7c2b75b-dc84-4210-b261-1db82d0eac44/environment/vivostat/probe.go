package vivostat

import "sync"

type Probe struct {
	mu      sync.Mutex
	ready   bool
	readyCt uint64
}

func NewProbe() *Probe {
	return &Probe{}
}

func (p *Probe) MarkReady() {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.ready = true
	p.readyCt++
}

func (p *Probe) ReadyCount() uint64 {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.readyCt
}

func (p *Probe) IsReady() bool {
	p.mu.Lock()
	defer p.mu.Unlock()
	return p.ready
}

func (p *Probe) Reset() {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.ready = false
}
