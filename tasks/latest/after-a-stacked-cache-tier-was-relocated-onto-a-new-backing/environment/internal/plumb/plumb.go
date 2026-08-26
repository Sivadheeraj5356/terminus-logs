package plumb

import (
	"fmt"
	"os"
	"path/filepath"

	cvio "github.com/lab/cvstack/internal/io"
	"github.com/lab/cvstack/internal/model"
)

type Seed struct {
	model.Vault
	DestRows []model.MapRow `json:"dest_rows"`
}

func ValidateSample(root, name string) error {
	p := filepath.Join(root, "samples", name, "workspace.json")
	if _, err := os.Stat(p); err != nil {
		return fmt.Errorf("sample %q missing", name)
	}
	return nil
}

func CopySample(root, name, dest string) error {
	if err := ValidateSample(root, name); err != nil {
		return err
	}
	src := filepath.Join(root, "samples", name)
	if err := os.MkdirAll(dest, 0o755); err != nil {
		return err
	}
	ents, err := os.ReadDir(src)
	if err != nil {
		return err
	}
	for _, e := range ents {
		in := filepath.Join(src, e.Name())
		out := filepath.Join(dest, e.Name())
		if e.IsDir() {
			if err := copyTree(in, out); err != nil {
				return err
			}
			continue
		}
		b, err := os.ReadFile(in)
		if err != nil {
			return err
		}
		if err := os.WriteFile(out, b, 0o644); err != nil {
			return err
		}
	}
	var seed Seed
	if err := cvio.ReadJSON(filepath.Join(dest, "workspace.json"), &seed); err != nil {
		return err
	}
	return materialize(dest, seed)
}

func copyTree(src, dst string) error {
	return filepath.Walk(src, func(p string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}
		rel, err := filepath.Rel(src, p)
		if err != nil {
			return err
		}
		target := filepath.Join(dst, rel)
		if info.IsDir() {
			return os.MkdirAll(target, 0o755)
		}
		b, err := os.ReadFile(p)
		if err != nil {
			return err
		}
		return os.WriteFile(target, b, info.Mode())
	})
}

func materialize(ws string, seed Seed) error {
	lanes := filepath.Join(ws, "lanes")
	if err := os.MkdirAll(filepath.Join(lanes, "slow"), 0o755); err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Join(lanes, "fast"), 0o755); err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Join(ws, "foreign"), 0o755); err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Join(ws, "refs"), 0o755); err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Join(ws, "maps"), 0o755); err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Join(ws, "state"), 0o755); err != nil {
		return err
	}
	for _, s := range seed.Slow {
		p := filepath.Join(lanes, "slow", fmt.Sprintf("%d.json", s.ID))
		if err := cvio.WriteJSON(p, s); err != nil {
			return err
		}
	}
	for _, s := range seed.Fast {
		p := filepath.Join(lanes, "fast", fmt.Sprintf("%d.json", s.ID))
		if err := cvio.WriteJSON(p, s); err != nil {
			return err
		}
	}
	for _, s := range seed.Foreign {
		p := filepath.Join(ws, "foreign", fmt.Sprintf("%d.json", s.ID))
		if err := cvio.WriteJSON(p, s); err != nil {
			return err
		}
	}
	if err := cvio.WriteJSON(filepath.Join(ws, "refs", "pre_move.json"), seed.RefPre); err != nil {
		return err
	}
	if err := cvio.WriteJSON(filepath.Join(ws, "refs", "post_move.json"), seed.RefPost); err != nil {
		return err
	}
	if err := cvio.WriteJSON(filepath.Join(ws, "refs", "active.json"), seed.RefPre); err != nil {
		return err
	}
	if err := cvio.WriteJSON(filepath.Join(ws, "maps", "slow_to_fast.json"), seed.MapRows); err != nil {
		return err
	}
	destRows := seed.DestRows
	if len(destRows) == 0 {
		destRows = seed.MapRows
	}
	if err := cvio.WriteJSON(filepath.Join(ws, "maps", "dest_bind.json"), destRows); err != nil {
		return err
	}
	alias := model.Alias{Path: seed.RefPre.Path, Rev: seed.RefPre.Rev}
	if err := cvio.WriteJSON(filepath.Join(ws, "maps", "origin_alias.json"), alias); err != nil {
		return err
	}
	if err := cvio.WriteJSON(filepath.Join(ws, "state", "dirty.json"), seed.Dirty); err != nil {
		return err
	}
	if err := cvio.WriteJSON(filepath.Join(ws, "state", "tap.json"), seed.Tap); err != nil {
		return err
	}
	return cvio.WriteJSON(filepath.Join(ws, "state", "vault.json"), seed.Vault)
}
