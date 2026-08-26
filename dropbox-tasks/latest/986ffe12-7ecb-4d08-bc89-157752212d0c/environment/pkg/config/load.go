package config

import (
	"encoding/json"
	"os"

	"github.com/BurntSushi/toml"
)

func LoadBase(path string) (*GachaConfig, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var cfg GachaConfig
	if err := json.Unmarshal(raw, &cfg); err != nil {
		return nil, err
	}
	return &cfg, nil
}

func ApplyOverride(cfg *GachaConfig, overridePath string) error {
	raw, err := os.ReadFile(overridePath)
	if err != nil {
		return err
	}
	var ov OverrideFile
	if _, err := toml.Decode(string(raw), &ov); err != nil {
		return err
	}
	if ov.PityThreshold != nil {
		cfg.PityThreshold = *ov.PityThreshold
	}
	if ov.HMACKey != nil {
		cfg.HMACKey = *ov.HMACKey
	}
	if ov.PityGapSec != nil {
		cfg.PityGapSec = *ov.PityGapSec
	}
	if len(ov.MacDomains) > 0 {
		if cfg.MacDomains == nil {
			cfg.MacDomains = map[string]string{}
		}
		for k, v := range ov.MacDomains {
			cfg.MacDomains[k] = v
		}
	}
	return nil
}

type deskFallback struct {
	HMACKey       string `json:"hmac_key"`
	PityThreshold int    `json:"pity_threshold"`
	PityGapSec    int    `json:"pity_gap_sec"`
}

func ApplyDeskFallback(cfg *GachaConfig, path string) error {
	raw, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	var fb deskFallback
	if err := json.Unmarshal(raw, &fb); err != nil {
		return err
	}
	if fb.HMACKey != "" {
		cfg.HMACKey = fb.HMACKey
	}
	if fb.PityThreshold > 0 {
		cfg.PityThreshold = fb.PityThreshold
	}
	if fb.PityGapSec > 0 {
		cfg.PityGapSec = fb.PityGapSec
	}
	return nil
}
