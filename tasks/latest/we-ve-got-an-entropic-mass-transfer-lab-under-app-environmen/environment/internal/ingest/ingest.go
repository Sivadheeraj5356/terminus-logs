package ingest

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
)

type Profile struct {
	Label string
	File  string
}

type Anneal struct {
	StartEpsilon float64 `json:"start_epsilon"`
	Factor       float64 `json:"factor"`
	Stages       int     `json:"stages"`
}

type Instance struct {
	InstanceID string    `json:"instance_id"`
	Cost       [][]float64 `json:"cost"`
	Supply     []float64 `json:"supply"`
	Demand     []float64 `json:"demand"`
	Epsilon    float64   `json:"epsilon"`
	Anneal     *Anneal   `json:"anneal"`
	Raw        []byte    `json:"-"`
}

func ParseManifest(path string) ([]Profile, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var out []Profile
	var cur Profile
	for _, line := range strings.Split(string(b), "\n") {
		line = strings.TrimSpace(line)
		if line == "[[profile]]" {
			if cur.Label != "" {
				out = append(out, cur)
			}
			cur = Profile{}
			continue
		}
		if strings.HasPrefix(line, "label") {
			parts := strings.SplitN(line, "=", 2)
			cur.Label = strings.Trim(strings.TrimSpace(parts[1]), "\"")
		}
		if strings.HasPrefix(line, "file") {
			parts := strings.SplitN(line, "=", 2)
			cur.File = strings.Trim(strings.TrimSpace(parts[1]), "\"")
		}
	}
	if cur.Label != "" {
		out = append(out, cur)
	}
	return out, nil
}

func LoadInstance(dir, file string) (Instance, error) {
	p := filepath.Join(dir, file)
	b, err := os.ReadFile(p)
	if err != nil {
		return Instance{}, err
	}
	var inst Instance
	if err := json.Unmarshal(b, &inst); err != nil {
		return Instance{}, err
	}
	inst.Raw = b
	return inst, nil
}
