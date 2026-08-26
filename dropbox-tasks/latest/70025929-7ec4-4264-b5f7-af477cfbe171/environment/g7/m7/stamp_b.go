// Package m7 merges durable pack state under provenance authority.
package m7

import "math"

// PackState holds durable pack bytes for replay merge.
type PackState struct {
	LastA    uint64
	LastB    uint64
	Storage  [3][4]float64
	NeckTm   float64
	UplinkTm float64
}

func FreshPack() *PackState {
	return &PackState{
		LastA: math.MaxUint64,
		LastB: math.MaxUint64,
	}
}

func copyThermal(dst, src *PackState) {
	dst.NeckTm = src.NeckTm
	dst.UplinkTm = src.UplinkTm
}

func copyStorage(dst, src *PackState) {
	dst.Storage = src.Storage
}

// merge_hold_b merges incoming durable pack into active state under provenance authority.
func merge_hold_b(state *PackState, incoming *PackState, stampB uint64) [3][4]float64 {
	if state.LastA != incoming.LastA {
		copyStorage(state, incoming)
		copyThermal(state, incoming)
		state.LastA = incoming.LastA
		state.LastB = stampB
	} else if state.LastB != stampB {
		state.LastB = stampB
	}
	return state.Storage
}

// MergeHoldB exposes merge_hold_b to the certify bridge.
func MergeHoldB(state *PackState, incoming *PackState, stampB uint64) [3][4]float64 {
	return merge_hold_b(state, incoming, stampB)
}

func neckDelta(measured, uplink float64) float64 {
	return math.Abs(measured - uplink)
}

func relativeBand(measured, uplink float64) float64 {
	den := math.Abs(uplink)
	if den < 1.0 {
		den = 1.0
	}
	return neckDelta(measured, uplink) / den
}

func stressPassesRelative(measured, uplink float64) bool {
	const rel = 1e-4
	return relativeBand(measured, uplink) < rel
}

func stressPassesAbsolute(measured, uplink float64) bool {
	const absBand = 1e-3
	return neckDelta(measured, uplink) < absBand
}

// NeckLag evaluates lag_code for a scenario using neck Tm delta policy.
func NeckLag(measured, uplink float64, stress bool) int32 {
	if !stress {
		if neckDelta(measured, uplink) < 1e-2 {
			return 0
		}
		return 1
	}
	if stressPassesAbsolute(measured, uplink) {
		return 0
	}
	if stressPassesRelative(measured, uplink) {
		return 0
	}
	if measured > uplink {
		return 1
	}
	return 0
}
