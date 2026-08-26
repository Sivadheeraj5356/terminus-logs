package clock

import (
	"time"

	"github.com/acme/auth/internal/config"
)

type Clock struct {
	epoch int64
}

func New(cfg *config.File) *Clock {
	return &Clock{epoch: cfg.Service.ClockEpoch}
}

func (c *Clock) NowUnix() int64 {
	return c.epoch
}

func (c *Clock) RFC3339(offsetSec int64) string {
	return time.Unix(c.epoch+offsetSec, 0).UTC().Format(time.RFC3339)
}
