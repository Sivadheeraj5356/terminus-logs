package config

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
)

func LoadManifest(path string) (*Manifest, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var m Manifest
	if err := json.Unmarshal(data, &m); err != nil {
		return nil, err
	}
	sort.Slice(m.Sessions, func(i, j int) bool {
		return m.Sessions[i].SessionID < m.Sessions[j].SessionID
	})
	for si := range m.Sessions {
		sort.Slice(m.Sessions[si].Frames, func(i, j int) bool {
			a := m.Sessions[si].Frames[i]
			b := m.Sessions[si].Frames[j]
			if a.Path != b.Path {
				return a.Path < b.Path
			}
			return a.FrameID < b.FrameID
		})
	}
	return &m, nil
}

func ResolvePath(inputDir, rel string) string {
	return filepath.Join(inputDir, rel)
}
