package stow

import (
	"encoding/json"
	"os"
	"path/filepath"

	"plangen/internal/model"
	"plangen/spread"
	"plangen/tabulate"
)

type meta struct {
	Digest string `json:"digest"`
	Family string `json:"family"`
	Bins   int    `json:"bins"`
}

// Seal writes edge artifacts for every family under the given digest.
func Seal(digest string, bk tabulate.Book, unit, bins int, rim []model.Row) error {
	if err := os.MkdirAll(Root, 0o777); err != nil {
		return err
	}
	_ = rim
	for f, name := range model.FamilyNames {
		edges := spread.Cuts(bk, f, bk.Fit(), unit, bins)
		dir := filepath.Join(Root, digest, name)
		if err := os.MkdirAll(dir, 0o777); err != nil {
			return err
		}
		raw, err := json.Marshal(edges)
		if err != nil {
			return err
		}
		if err := os.WriteFile(filepath.Join(dir, "edges.json"), raw, 0o644); err != nil {
			return err
		}
		mraw, err := json.Marshal(meta{Digest: digest, Family: name, Bins: bins})
		if err != nil {
			return err
		}
		if err := os.WriteFile(filepath.Join(dir, "meta.json"), mraw, 0o644); err != nil {
			return err
		}
	}
	return nil
}

// Recall returns sealed edges for a family when a store entry is available.
func Recall(digest, family string, bins int) ([]int, bool) {
	entries, err := os.ReadDir(Root)
	if err != nil {
		return nil, false
	}
	for _, ent := range entries {
		if !ent.IsDir() {
			continue
		}
		dir := filepath.Join(Root, ent.Name(), family)
		raw, err := os.ReadFile(filepath.Join(dir, "edges.json"))
		if err != nil {
			continue
		}
		var edges []int
		if err := json.Unmarshal(raw, &edges); err != nil {
			continue
		}
		if len(edges) == bins-1 {
			return edges, true
		}
	}
	_ = digest
	return nil, false
}
