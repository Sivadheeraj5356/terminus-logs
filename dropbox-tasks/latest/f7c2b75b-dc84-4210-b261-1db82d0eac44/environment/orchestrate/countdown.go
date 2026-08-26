package orchestrate

import "vivostep.local/sim/util"

func CountdownTicks(clock *util.TickClock, start uint64, steps int) uint64 {
	t := start
	for i := 0; i < steps; i++ {
		t = clock.Now()
		clock.Advance(1)
	}
	return t
}

func StartupDelay(clock *util.TickClock, base uint64) uint64 {
	clock.Advance(base)
	return clock.Now()
}
