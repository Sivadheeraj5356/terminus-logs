package util

type TickClock struct {
	tick uint64
}

func NewTickClock() *TickClock {
	return &TickClock{}
}

func (c *TickClock) Now() uint64 {
	return c.tick
}

func (c *TickClock) Advance(steps uint64) {
	c.tick += steps
}

func (c *TickClock) Set(t uint64) {
	c.tick = t
}
