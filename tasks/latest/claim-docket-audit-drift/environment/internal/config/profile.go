package config

import (
	"encoding/json"
	"os"
)

type Profile struct {
	RegionGate    bool
	ChainSeqWidth uint8
}

func LoadProfile() Profile {
	prof := Profile{RegionGate: true, ChainSeqWidth: 16}
	raw, err := os.ReadFile("/app/environment/configs/audit_profile.json")
	if err != nil {
		return prof
	}
	var doc struct {
		RegionGate    *bool `json:"region_gate"`
		ChainSeqWidth *int  `json:"chain_seq_width"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		return prof
	}
	if doc.RegionGate != nil {
		prof.RegionGate = *doc.RegionGate
	}
	if doc.ChainSeqWidth != nil {
		prof.ChainSeqWidth = uint8(*doc.ChainSeqWidth)
	}
	return prof
}
