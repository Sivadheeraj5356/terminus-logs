package clock

import (
	"fmt"
	"sync"
	"time"

	"github.com/terminus/ai-workflow-runtime/internal/util"
)

// Clock is a deterministic logical clock anchored to a fixed epoch.
type Clock struct {
	epoch  time.Time
	offset int
	mu     sync.Mutex
}

// New creates a clock from an RFC3339 epoch string.
func New(epoch string) (*Clock, error) {
	t, err := util.ParseEpoch(epoch)
	if err != nil {
		return nil, err
	}
	return &Clock{epoch: t}, nil
}

// Tick advances the logical clock by one second and returns the timestamp.
func (c *Clock) Tick() string {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.offset++
	return c.epoch.Add(time.Duration(c.offset) * time.Second).UTC().Format(time.RFC3339)
}

// At returns epoch + seq seconds without mutating the clock.
func (c *Clock) At(seq int) string {
	return c.epoch.Add(time.Duration(seq) * time.Second).UTC().Format(time.RFC3339)
}

// Ms returns epoch + offsetMs milliseconds formatted at second precision.
func (c *Clock) Ms(offsetMs int) string {
	return c.epoch.Add(time.Duration(offsetMs) * time.Millisecond).UTC().Format(time.RFC3339)
}

// Snapshot is a serializable view of clock state.
type Snapshot struct {
	Epoch  string `json:"epoch"`
	Offset int    `json:"offset"`
}

func (c *Clock) Snapshot() Snapshot {
	c.mu.Lock()
	defer c.mu.Unlock()
	return Snapshot{Epoch: c.epoch.UTC().Format(time.RFC3339), Offset: c.offset}
}

func (c *Clock) String() string {
	s := c.Snapshot()
	return fmt.Sprintf("clock(epoch=%s,offset=%d)", s.Epoch, s.Offset)
}
