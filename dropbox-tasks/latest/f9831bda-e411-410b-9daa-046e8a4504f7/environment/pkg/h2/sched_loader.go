package h2

import (
	"encoding/json"
	"os"
)

type Profile struct {
	ProfileID    string   `json:"profile_id"`
	ProfilePfx   string   `json:"profile_pfx"`
	EpochDN     string   `json:"epoch_dn"`
	EpochStamp  string   `json:"epoch_stamp"`
	CarryBudget int      `json:"cap_bytes"`
	FrameUnit   int      `json:"frame_unit"`
	GrantUnit   int      `json:"grant_unit"`
	Modules     []Module `json:"modules"`
	DupCycle    bool     `json:"dup_cycle"`
}

type Module struct {
	Path     string `json:"path"`
	Version  string `json:"version"`
	ShardRef string `json:"shard_ref"`
	Frame    string `json:"frame"`
	Tomb     bool   `json:"tomb"`
	Role     string `json:"role"`
	EchoRole string `json:"echo_role"`
}

func LoadProfile(root, tenant string) (*Profile, error) {
	path := root + "/p3/schedules/" + tenant + ".json"
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var t Profile
	if err := json.Unmarshal(raw, &t); err != nil {
		return nil, err
	}
	return &t, nil
}

func ListProfiles(root string) []string {
	return []string{"xa", "xb", "xc", "xd"}
}
