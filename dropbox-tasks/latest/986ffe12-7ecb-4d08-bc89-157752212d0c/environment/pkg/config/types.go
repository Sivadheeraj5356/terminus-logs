package config

type GachaConfig struct {
	HMACKey       string              `json:"hmac_key"`
	PityThreshold int                 `json:"pity_threshold"`
	PityGapSec    int                 `json:"pity_gap_sec"`
	MacDomains    map[string]string   `json:"mac_domains"`
	RarityTable   map[string]float64  `json:"rarity_table"`
	Pool          map[string][]string `json:"pool"`
	TierOrder     []string            `json:"tier_order"`
}

type OverrideFile struct {
	PityThreshold *int              `toml:"pity_threshold"`
	HMACKey       *string           `toml:"hmac_key"`
	PityGapSec    *int              `toml:"pity_gap_sec"`
	MacDomains    map[string]string `toml:"mac_domains"`
}
