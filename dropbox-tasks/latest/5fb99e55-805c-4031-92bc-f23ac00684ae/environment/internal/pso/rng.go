package pso

// LCG is a simple Linear Congruential Generator used to guarantee deterministic randomness
// across all platforms and Go versions. Do not use math/rand to ensure reproducibility.
type LCG struct {
	state uint32
}

func NewLCG(seed uint32) *LCG {
	return &LCG{state: seed}
}

// Float64 returns a pseudo-random float64 in the range [0.0, 1.0).
func (l *LCG) Float64() float64 {
	l.state = 1664525*l.state + 1013904223
	return float64(l.state) / float64(1<<32)
}
