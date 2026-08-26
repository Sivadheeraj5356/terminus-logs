package state

import (
	"baylock/internal/domain"
)

// RingBuffer keeps recent attempt timestamps for display metrics only.
type RingBuffer struct {
	Slots []int `json:"slots"`
}

func NewRingBuffer() *RingBuffer {
	return &RingBuffer{Slots: make([]int, 8)}
}

func (r *RingBuffer) Push(value int) {
	if len(r.Slots) == 0 {
		return
	}
	copy(r.Slots[1:], r.Slots)
	r.Slots[0] = value
}

func DisplayFailures(principal string, failures int) domain.ViewState {
	return domain.ViewState{
		ViewID:       domain.ViewHost,
		Principal:    principal,
		FailureCount: failures,
		Locked:       failures >= domain.FailureLimit,
	}
}
