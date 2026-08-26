package notary

import (
	"encoding/json"
	"os"
	"path/filepath"

	"jwksbound.local/mux/model"
)

func LoadSeal(profile string) model.SealMeta {
	path := filepath.Join(model.OutDir, "state", profile, "epoch.json")
	data, err := os.ReadFile(path)
	if err != nil {
		return model.SealMeta{}
	}
	var meta model.SealMeta
	_ = json.Unmarshal(data, &meta)
	return meta
}

func SaveSeal(profile string, meta model.SealMeta) {
	path := filepath.Join(model.OutDir, "state", profile, "epoch.json")
	model.WriteJSON(path, meta)
}

func LayoutPath() string {
	return filepath.Join(model.EnvRoot, "runtime", "layout.json")
}

func ReadProfileLayout() map[string]model.ProfileLayout {
	data, err := os.ReadFile(LayoutPath())
	if err != nil {
		panic(err)
	}
	var raw map[string]map[string]any
	if err := json.Unmarshal(data, &raw); err != nil {
		panic(err)
	}
	out := map[string]model.ProfileLayout{}
	for k, v := range raw {
		meta := model.ProfileLayout{}
		if x, ok := v["epoch"].(float64); ok {
			meta.Epoch = int(x)
		}
		if x, ok := v["counter"].(float64); ok {
			meta.Counter = int(x)
		}
		if x, ok := v["generation_floor"].(float64); ok {
			meta.GenerationFloor = int(x)
		}
		if x, ok := v["seal_rev"].(float64); ok {
			meta.SealRev = int(x)
		}
		if x, ok := v["tag"].(string); ok {
			meta.Tag = x
		}
		if x, ok := v["seed_epoch"].(float64); ok {
			meta.SeedEpoch = int(x)
		}
		if x, ok := v["seed_generation"].(float64); ok {
			meta.SeedGeneration = int(x)
		}
		if x, ok := v["seed_mark"].(float64); ok {
			meta.SeedMark = x
		}
		if x, ok := v["inherits_from"].(string); ok {
			meta.InheritsFrom = x
		}
		if shared, ok := v["shared_keys"].([]any); ok {
			for _, item := range shared {
				if s, ok := item.(string); ok {
					meta.SharedKeys = append(meta.SharedKeys, s)
				}
			}
		}
		out[k] = meta
	}
	return out
}

func ReadLayout() map[string]model.SealMeta {
	profiles := ReadProfileLayout()
	out := map[string]model.SealMeta{}
	for k, v := range profiles {
		out[k] = model.SealMeta{
			Epoch:           v.Epoch,
			Counter:         v.Counter,
			GenerationFloor: v.GenerationFloor,
			SealRev:         v.SealRev,
			Tag:             v.Tag,
		}
	}
	return out
}

func Authority(profile string) model.SealMeta {
	layout := ReadLayout()
	persisted := LoadSeal(profile)
	incoming := layout[profile]
	return CombineSeal(persisted, incoming)
}
