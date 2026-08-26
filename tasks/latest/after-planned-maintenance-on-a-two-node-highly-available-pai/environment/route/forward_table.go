package route

import (
	"sync"

	"vivostep.local/sim/util"
)

type ForwardTable struct {
	mu            sync.Mutex
	epoch         uint64
	lastEventTick uint64
	logPath       string
	clock         *util.TickClock
}

func NewForwardTable(clock *util.TickClock, logPath string) *ForwardTable {
	return &ForwardTable{clock: clock, logPath: logPath}
}

func (f *ForwardTable) Epoch() uint64 {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.epoch
}

func (f *ForwardTable) LastEventTick() uint64 {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.lastEventTick
}

func (f *ForwardTable) AttachEndpoint(epoch uint64) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.epoch = epoch
	f.lastEventTick = f.clock.Now()
	_ = util.AppendJSONL(f.logPath, util.LogLine{
		Tick:    f.lastEventTick,
		Kind:    "attach",
		Epoch:   epoch,
		Surface: "forward",
	})
}

func (f *ForwardTable) ResetCold(epoch uint64) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.epoch = epoch
	f.lastEventTick = f.clock.Now()
}
