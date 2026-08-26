package config

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"sigproxy/internal/digest"
	"sigproxy/internal/semantics"
)

type ProfileCatalog struct {
	Profiles      map[string]*semantics.ProfileConfig
	CatalogDigest string
	Order         []string
}

func LoadProfileCatalog(dir string) (*ProfileCatalog, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, fmt.Errorf("read profiles dir: %w", err)
	}
	cat := &ProfileCatalog{Profiles: make(map[string]*semantics.ProfileConfig)}
	var names []string
	for _, e := range entries {
		if e.IsDir() || filepath.Ext(e.Name()) != ".json" {
			continue
		}
		path := filepath.Join(dir, e.Name())
		data, err := os.ReadFile(path)
		if err != nil {
			return nil, err
		}
		var pc semantics.ProfileConfig
		if err := json.Unmarshal(data, &pc); err != nil {
			return nil, fmt.Errorf("parse profile %s: %w", e.Name(), err)
		}
		cat.Profiles[pc.ID] = &pc
		names = append(names, pc.ID)
	}
	sort.Strings(names)
	cat.Order = names

	digestInput := make([]map[string]any, 0, len(names))
	for _, id := range names {
		pc := cat.Profiles[id]
		digestInput = append(digestInput, map[string]any{
			"id": pc.ID, "epoch": pc.Epoch, "version": pc.SignatureVersion,
		})
	}
	d, err := digest.StableJSONDigest(digestInput)
	if err != nil {
		return nil, err
	}
	cat.CatalogDigest = d
	return cat, nil
}

func (c *ProfileCatalog) Lookup(profileID string, epoch int) (*semantics.ProfileConfig, bool) {
	pc, ok := c.Profiles[profileID]
	if !ok {
		return nil, false
	}
	if epoch > 0 && pc.Epoch != epoch {
		return nil, false
	}
	return pc, true
}

func (c *ProfileCatalog) SelectByHeader(profileHeader string) (*semantics.ProfileConfig, error) {
	if profileHeader == "" {
		return nil, fmt.Errorf("missing profile selector")
	}
	pc, ok := c.Profiles[profileHeader]
	if !ok {
		return nil, fmt.Errorf("unknown profile %q", profileHeader)
	}
	return pc, nil
}
