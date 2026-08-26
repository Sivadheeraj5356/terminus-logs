package core

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
)

type Row struct {
	LaneID     string
	NatKey     uint32
	BindW      uint32
	SweepGen   uint32
	PhaseCode  uint32
	SpanHi     uint32
	AnceCode   uint32
	WitFP      string
	EvtStamp   uint64
	RowKind    string
	MarkerLag  uint16
	ProbeScope uint32
	Ticket     uint32
}

type Bound struct {
	Row    Row
	Commit bool
}

type Win struct {
	Row Row
	Ok  bool
}

type Book struct {
	Rows []Row
}

type Stage struct {
	Rows []Row
}

type Evt struct {
	LagTicket  uint16
	CredTicket uint32
	LaneID     string
	NatKey     uint32
	RowKind    string
	SweepGen   uint32
	EvtStamp   uint64
	AnceCode   uint32
	MarkerNeed uint16
	SpanExpect uint32
	LaneASpan  uint32
}

type Routed struct {
	Ready bool
	Evt   Evt
}

type Obs struct {
	LaneID     string `json:"lane_id"`
	NatKey     uint32 `json:"nat_key"`
	BindW      uint32 `json:"bind_w"`
	SweepGen   uint32 `json:"sweep_gen"`
	PhaseCode  uint32 `json:"phase_code"`
	SpanHi     uint32 `json:"span_hi"`
	AnceCode   uint32 `json:"ance_code"`
	WitFP      string `json:"wit_fp"`
	EvtStamp   uint64 `json:"evt_stamp"`
	RowKind    string `json:"row_kind"`
	MarkerLag  uint16 `json:"marker_lag"`
	ProbeScope uint32 `json:"probe_scope"`
}

type Ckpt struct {
	LaneID    string `json:"lane_id"`
	SweepGen  uint32 `json:"sweep_gen"`
	PhaseCode uint32 `json:"phase_code"`
	SpanHi    uint32 `json:"span_hi"`
	WitFP     string `json:"wit_fp"`
}

type OutDoc struct {
	Meta struct {
		RunTag   string `json:"run_tag"`
		CredTag  string `json:"cred_tag"`
		LaneAWin uint32 `json:"lane_a_win"`
		LaneBWin uint32 `json:"lane_b_win"`
	} `json:"meta"`
	Rows     []Obs  `json:"rows"`
	Ckpts    []Ckpt `json:"ckpts"`
	RollFP   string `json:"roll_fp"`
	PhaseWM  uint32 `json:"phase_wm"`
	SweepWM  uint32 `json:"sweep_wm"`
}

func WitFPFor(lane string, natKey, sweepGen, anceCode, bindW uint32) string {
	raw := fmt.Sprintf("%s|%d|%d|%d|%d", lane, natKey, sweepGen, anceCode, bindW)
	sum := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(sum[:8])
}

func RollFP(rows []Obs) string {
	ordered := append([]Obs{}, rows...)
	for i := 0; i < len(ordered); i++ {
		for j := i + 1; j < len(ordered); j++ {
			a, b := ordered[i], ordered[j]
			if a.LaneID > b.LaneID || (a.LaneID == b.LaneID && a.NatKey > b.NatKey) {
				ordered[i], ordered[j] = ordered[j], ordered[i]
			}
		}
	}
	var acc uint64
	for _, r := range ordered {
		for i := 0; i < len(r.WitFP); i++ {
			acc = (acc*131 + uint64(r.WitFP[i])) & 0xFFFFFFFFFFFF
		}
		acc ^= uint64(r.SweepGen) << 16
		acc ^= uint64(r.PhaseCode) << 8
	}
	return fmt.Sprintf("%016x", acc)
}
