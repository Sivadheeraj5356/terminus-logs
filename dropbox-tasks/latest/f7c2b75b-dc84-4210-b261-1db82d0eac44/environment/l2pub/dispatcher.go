package l2pub

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sync"

	"vivostep.local/sim/util"
)

type Frame struct {
	Epoch   uint64
	Payload string
}

type Dispatcher struct {
	mu         sync.Mutex
	clock      *util.TickClock
	pending    []Frame
	replayTick uint64
}

func NewDispatcher(clock *util.TickClock) *Dispatcher {
	return &Dispatcher{clock: clock}
}

func (d *Dispatcher) QueueFrame(epoch uint64, payload string) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.pending = append(d.pending, Frame{Epoch: epoch, Payload: payload})
}

func (d *Dispatcher) FlushPending(epoch uint64) {
	d.mu.Lock()
	defer d.mu.Unlock()
	kept := make([]Frame, 0, len(d.pending))
	for _, f := range d.pending {
		if f.Epoch != epoch {
			kept = append(kept, f)
		}
	}
	d.pending = kept
	d.replayTick = d.clock.Now()
}

func (d *Dispatcher) ReplayTick() uint64 {
	d.mu.Lock()
	defer d.mu.Unlock()
	return d.replayTick
}

func (d *Dispatcher) FramesForEpoch(epoch uint64) []Frame {
	d.mu.Lock()
	defer d.mu.Unlock()
	out := make([]Frame, 0)
	for _, f := range d.pending {
		if f.Epoch == epoch {
			out = append(out, f)
		}
	}
	return out
}

func HoldUntilExported(d *Dispatcher, epoch uint64, barrier <-chan struct{}) error {
	return DrainQueuedExported(d, epoch, barrier)
}

func ValidateFrameMTU(payload string, mtu int) error {
	if len(payload) > mtu {
		return fmt.Errorf("frame exceeds mtu")
	}
	return nil
}

func FrameChecksum(payload string) string {
	sum := sha256.Sum256([]byte(payload))
	return hex.EncodeToString(sum[:8])
}
